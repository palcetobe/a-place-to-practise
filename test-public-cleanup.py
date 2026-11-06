"""Check the cleanup against the exact assembled application before publishing."""
from pathlib import Path
import hashlib
from html.parser import HTMLParser
import importlib.util
import re
import subprocess

spec = importlib.util.spec_from_file_location('cleanup', 'clean-public-site.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)
root = Path('_site')
library = root / 'practice-library/skills-library/index.html'
before = library.read_text(encoding='utf-8')


class Census(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.cards = []
        self.links = []
        self.controls = []
        self.scripts = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'article':
            self.cards.append((a.get('id'), a.get('data-id'), a.get('data-group')))
        if tag == 'a' and 'href' in a:
            self.links.append(a['href'])
        if tag in ('input', 'select', 'button'):
            self.controls.append((tag, a.get('id'), a.get('type')))
        if tag == 'script':
            self.scripts.append(a.get('src', '').split('?')[0])


def hashes():
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def safety(text):
    return re.findall(r'<h3>(?:Safety and scope|Therapist support and fit)</h3>.*?(?=<h3>|<p><a|</div>)', text, re.S)


old_hashes = hashes()
old = Census(before)
old_safety = safety(before)
html_before = {p: p.read_text(encoding='utf-8') for p in (root / 'practice-library').rglob('*.html')}
js_before = {p: p.read_text(encoding='utf-8') for p in (root / 'practice-library/assets').glob('*practice.js')}
cleanup.apply(root)
after = library.read_text(encoding='utf-8')
new = Census(after)
assert old.cards == new.cards and len(new.cards) == 83
assert old.controls == new.controls, 'Search/filter controls changed'
assert old.scripts == new.scripts
assert old_safety == safety(after), 'Therapist-fit or safety guidance changed'
launches = [u for u in old.links if 'skills-map' not in u]
assert set(launches) <= set(new.links), 'A skill/support URL was removed'
for p, text in html_before.items():
    if 'skills-map' not in str(p):
        assert Census(text).scripts == Census(p.read_text(encoding='utf-8')).scripts, p
new_hashes = hashes()
for p, text in js_before.items():
    assert cleanup.clean_practice_js(text) == p.read_text(encoding='utf-8'), 'Only display edits allowed in practice controllers'
    if text != p.read_text(encoding='utf-8'):
        subprocess.run(['node', '--check', str(p)], check=True, capture_output=True)
for name in ('pilot.js', 'review-hub.js', 'practice-library/skills-library/library.js', 'practice-library/assets/shared-support-chrome.js'):
    subprocess.run(['node', '--check', str(root / name)], check=True, capture_output=True)
assert old_hashes.keys() == new_hashes.keys()
protected = [k for k in old_hashes if k.endswith(('.json', '.mp3', '.wav', '.mp4', '.pdf', '.svg')) or k.startswith('previews/')]
assert all(old_hashes[k] == new_hashes[k] for k in protected), 'Underlying data or assets changed'
for internal in ['Catalogue evidence', 'Overnight review', 'Catalogue source snapshot', 'Current written REVIEW implementation', 'NOT_IMPLEMENTED_AS_COMPLETE_METHOD', 'written implementation registry', 'canonical count']:
    assert internal not in after, internal
practice = (root / 'practice-library/cope-ahead/index.html').read_text(encoding='utf-8')
assert 'clears when you leave or reload' in practice
assert 'Files you choose to download remain on your device' in practice
assert 'Use with therapist guidance' in practice
assert 'acceptance remain open' not in practice
assert 'library.js?v=public-cleanup-1' in after
assert 'abc-component-practice.js?v=public-cleanup-1' in practice
thought = (root / 'practice-library/retained-classics/thought-record/native.html').read_text(encoding='utf-8')
assert 'Your writing stays in this open page.' in thought and 'Leaving clears unsaved writing.' in thought
assert 'href="readable-handout.html"' in thought
print(f'PASS: 83 card identities, {len(launches)} skill/support links, {len(old_safety)} safety/fit sections, all controls/scripts, {len(protected)} data/assets/previews preserved')
