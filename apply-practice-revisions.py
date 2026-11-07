#!/usr/bin/env python3
"""Validate an exact, checksum-pinned practice delta before changing the local build."""
from pathlib import Path, PurePosixPath
import argparse
import base64
import hashlib
import io
import json
import os
import re
import stat
import sys
import tempfile
import zipfile

SCHEMA = 'aptp-practice-revisions-v1'
BASELINE_COMMIT = 'baa699f831c5252e657ce8993a1c571929deb79c'
BASELINE_DIGEST = '5325a4f3a782ce9b9c1fe5f7c22c046f0a14d1536abbd6c349abccfa5fce8bbe'
BASELINE_MANIFEST_SHA256 = '4962ad10effe498ab25ee5b69c5a949b04a1fa9948629897f83ae49f95b2dd01'
MANIFEST = '_integrated_manifest.sha256'
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
FORBIDDEN = {'__qa', 'previews', '.git', '.github', '__pycache__'}


class GuardError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise GuardError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(files):
    return sha(json.dumps(files, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def manifest_bytes(files):
    return ''.join(value + '  ' + name + '\n' for name, value in sorted(files.items())).encode('utf-8')


def safe_path(name, allow_previews=False):
    require(isinstance(name, str) and bool(name), 'Path must be a nonempty string')
    require('\\' not in name and ':' not in name and not any(ord(c) < 32 or ord(c) == 127 for c in name), 'Unsafe path: ' + repr(name))
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and all(p not in ('', '.', '..') for p in name.split('/')), 'Unsafe path: ' + repr(name))
    forbidden = FORBIDDEN - ({'previews'} if allow_previews and path.parts[0] == 'previews' else set())
    require(not set(path.parts) & forbidden, 'Forbidden package/build path: ' + name)
    require(name != MANIFEST, 'Manifest is generated, never supplied in the delta')
    return path


def scan_tree(root, allow_previews=False, exclude_qa=False):
    """No symlink traversal, hidden build state, special files, or unaccounted app files."""
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'Build root must be a real directory')
    application, previews, ignored = {}, {}, []
    manifest = None

    def walk(directory):
        nonlocal manifest
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            name = child.relative_to(root).as_posix()
            mode = child.lstat().st_mode
            require(not stat.S_ISLNK(mode), 'Symlink rejected: ' + name)
            if exclude_qa and name == '__qa':
                require(stat.S_ISDIR(mode), '__qa exclusion must be a directory')
                ignored.append('__qa/')
                continue
            if name == MANIFEST:
                require(stat.S_ISREG(mode), 'Manifest must be a regular file')
                manifest = child.read_bytes()
                continue
            safe_path(name, allow_previews=allow_previews)
            if stat.S_ISDIR(mode):
                walk(child)
            else:
                require(stat.S_ISREG(mode), 'Special file rejected: ' + name)
                target = previews if name.startswith('previews/') else application
                target[name] = sha(child.read_bytes())
    walk(root)
    return application, previews, manifest, ignored


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_map(value, label):
    require(isinstance(value, dict) and bool(value), label + ' must be a nonempty map')
    for name, value_hash in value.items():
        safe_path(name)
        require(valid_hash(value_hash), 'Invalid hash in ' + label + ': ' + name)


def validate_package(package):
    """Materialize and validate every archive member in memory, without writing files."""
    required = {'schema', 'baselineCommit', 'before', 'after', 'beforeFilesDigest', 'afterFilesDigest', 'beforeManifestSHA256', 'afterManifestSHA256', 'expectedPreservedPreviews', 'changes', 'archiveBytes', 'archiveSHA256', 'archiveBase64'}
    require(isinstance(package, dict) and set(package) == required, 'Unexpected package schema/fields')
    require(package['schema'] == SCHEMA and package['baselineCommit'] == BASELINE_COMMIT, 'Wrong release baseline')
    before, after = package['before'], package['after']
    validate_map(before, 'before')
    validate_map(after, 'after')
    require(len(before) == 1186 and digest(before) == BASELINE_DIGEST == package['beforeFilesDigest'], 'Pinned whole application baseline mismatch')
    require(sha(manifest_bytes(before)) == BASELINE_MANIFEST_SHA256 == package['beforeManifestSHA256'], 'Pinned baseline manifest mismatch')
    require(digest(after) == package['afterFilesDigest'] and sha(manifest_bytes(after)) == package['afterManifestSHA256'], 'Result tree or manifest digest mismatch')
    require(set(before) <= set(after), 'Deleting application paths is not allowed')
    require(type(package['expectedPreservedPreviews']) is int and package['expectedPreservedPreviews'] == 422, 'Unexpected preserved preview count')
    changes = package['changes']
    require(isinstance(changes, list) and bool(changes), 'Release must contain changes')
    expected_names = sorted(name for name in after if before.get(name) != after[name])
    require(all(isinstance(change, dict) and set(change) == {'path', 'before', 'after', 'bytes'} for change in changes), 'Invalid change record')
    require([change['path'] for change in changes] == expected_names, 'Change list must exactly match the complete before/after delta')
    for change in changes:
        name = change['path']
        safe_path(name)
        require(change['before'] == before.get(name) and change['after'] == after[name], 'Change hash mismatch: ' + name)
        require(type(change['bytes']) is int and 0 <= change['bytes'] <= MAX_EXPANDED_BYTES, 'Invalid file size: ' + name)
    expanded = sum(change['bytes'] for change in changes)
    require(expanded <= MAX_EXPANDED_BYTES, 'Expanded archive exceeds limit')
    require(type(package['archiveBytes']) is int and 0 < package['archiveBytes'] <= MAX_ARCHIVE_BYTES, 'Invalid archive size')
    require(isinstance(package['archiveBase64'], str) and len(package['archiveBase64']) <= 4 * ((MAX_ARCHIVE_BYTES + 2) // 3), 'Invalid archive encoding length')
    try:
        archive = base64.b64decode(package['archiveBase64'], validate=True)
    except (ValueError, TypeError) as error:
        raise GuardError('Invalid base64 archive') from error
    require(len(archive) == package['archiveBytes'] and sha(archive) == package['archiveSHA256'], 'Archive size/checksum mismatch')
    payload = {}
    expected = {change['path']: change for change in changes}
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            entries = zipped.infolist()
            require(len(entries) == len(expected) and sorted(e.filename for e in entries) == expected_names, 'Archive member set mismatch or duplicate path')
            for entry in entries:
                name = entry.filename
                require(entry.orig_filename == name, 'Truncated or NUL-containing archive path')
                safe_path(name)
                require(not entry.is_dir(), 'Archive directories are not permitted')
                require(stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFREG, 'Nonregular or symlink archive member: ' + name)
                require(not entry.flag_bits & 1, 'Encrypted archive member rejected')
                require(entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'Unsupported compression')
                require(entry.file_size == expected[name]['bytes'], 'Archive member size mismatch: ' + name)
                data = zipped.read(entry)
                require(len(data) == expected[name]['bytes'] and sha(data) == expected[name]['after'], 'Archive member checksum mismatch: ' + name)
                payload[name] = data
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as error:
        raise GuardError('Unreadable archive: ' + str(error)) from error
    require(set(payload) == set(expected), 'Incomplete validated archive')
    return before, after, changes, payload


def validate_target(root, before, after, expected_previews):
    current, previews, manifest, ignored = scan_tree(root, allow_previews=True)
    require(not ignored, 'Unexpected excluded files')
    if current == after:
        raise GuardError('Already applied: refusing a repeated application')
    require(current == before, 'Whole application baseline mismatch; no files written')
    require(manifest == manifest_bytes(before), 'Existing integrated manifest mismatch')
    require(len(previews) == expected_previews, 'Preserved preview census mismatch')
    return current, previews, manifest


def apply_package(root, package, validate_only=False, expected_previews=None):
    root = Path(root)
    before, after, changes, payload = validate_package(package)
    if expected_previews is None:
        expected_previews = package['expectedPreservedPreviews']
    require(type(expected_previews) is int and expected_previews >= 0, 'Invalid expected preview count')
    _, previews, old_manifest = validate_target(root, before, after, expected_previews)
    backups, modes = {}, {}
    for change in changes:
        name = change['path']
        target = root / name
        for parent in target.parents:
            if parent == root:
                break
            require(not parent.is_symlink() and (not parent.exists() or parent.is_dir()), 'Invalid target parent: ' + name)
        require(not target.is_symlink(), 'Symlink target: ' + name)
        if change['before'] is None:
            require(not target.exists(), 'New target already exists: ' + name)
            backups[name], modes[name] = None, 0o644
        else:
            require(target.is_file(), 'Existing target missing: ' + name)
            backups[name] = target.read_bytes()
            require(sha(backups[name]) == change['before'], 'Target changed during validation: ' + name)
            modes[name] = stat.S_IMODE(target.stat().st_mode)
    # Every path, archive member, checksum, before hash, and untouched file has
    # now been validated. No application writes happen before this point.
    summary = {'applicationFiles': len(after), 'changedFiles': len(changes), 'addedFiles': len(set(after) - set(before)), 'unchangedFiles': sum(after.get(k) == v for k, v in before.items()), 'preservedPreviewFiles': len(previews), 'archiveSHA256': package['archiveSHA256'], 'resultFilesDigest': digest(after)}
    if validate_only:
        return dict(summary, status='validated-without-writing')
    written, created_dirs = [], []
    with tempfile.TemporaryDirectory(prefix='.practice-revisions-', dir=root.parent) as stage_name:
        stage = Path(stage_name)
        for name, data in payload.items():
            temporary = stage / name
            temporary.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(data)
            temporary.chmod(modes[name])
        staged_manifest = stage / MANIFEST
        staged_manifest.write_bytes(manifest_bytes(after))
        # A change during archive staging must also be rejected before writes.
        _, latest_previews, latest_manifest = validate_target(root, before, after, expected_previews)
        require(latest_previews == previews and latest_manifest == old_manifest, 'Build changed during validation')
        try:
            for name in sorted(payload):
                target = root / name
                missing = []
                parent = target.parent
                while parent != root and not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for directory in reversed(missing):
                    directory.mkdir()
                    created_dirs.append(directory)
                os.replace(stage / name, target)
                written.append(name)
            actual, preserved, current_manifest, _ = scan_tree(root, allow_previews=True)
            require(actual == after, 'Result application census mismatch')
            require(preserved == previews, 'A preserved preview changed')
            require(all(actual[name] == value for name, value in before.items() if name not in payload), 'An untouched application file changed')
            require(current_manifest == old_manifest, 'Manifest changed unexpectedly during application')
            os.replace(staged_manifest, root / MANIFEST)
            require((root / MANIFEST).read_bytes() == manifest_bytes(actual), 'Final integrated manifest mismatch')
        except BaseException:
            # Restore only files owned by this delta if a local I/O/postcheck fails.
            for name in reversed(written):
                target = root / name
                if backups[name] is None:
                    target.unlink(missing_ok=True)
                else:
                    rollback = stage / name
                    rollback.parent.mkdir(parents=True, exist_ok=True)
                    rollback.write_bytes(backups[name])
                    rollback.chmod(modes[name])
                    os.replace(rollback, target)
            (root / MANIFEST).write_bytes(old_manifest)
            for directory in reversed(created_dirs):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            raise
    return dict(summary, status='applied-and-verified', manifestSHA256=sha(manifest_bytes(after)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('_site'))
    parser.add_argument('--package', type=Path, default=Path('practice-revisions.json'))
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--expected-preview-count', type=int, help='Local dry-run override; production defaults to the pinned count of 422')
    args = parser.parse_args()
    try:
        require(args.package.is_file() and not args.package.is_symlink(), 'Package must be a regular file')
        package = json.loads(args.package.read_text(encoding='utf-8'))
        print(json.dumps(apply_package(args.root, package, args.validate_only, args.expected_preview_count), sort_keys=True))
    except (GuardError, OSError, ValueError) as error:
        print('REJECTED: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
