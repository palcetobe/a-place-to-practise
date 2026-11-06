"""Remove development presentation from the verified public build, retaining practice data."""
from pathlib import Path
import hashlib
import json
import re


def clean_library(s):
    s = re.sub(r'<nav aria-label="Review navigation">.*?</nav>', '', s, flags=re.S)
    s = re.sub(r'<p class="public-review-notice">.*?</p>',
               '<p class="public-review-notice">Use these practices with therapist guidance. They are not a complete treatment programme or a substitute for urgent support.</p>', s, flags=re.S)
    s = re.sub(r'<p>Existing full practices, 77 downloadable guides.*?</p>', '', s)
    s = re.sub(r'<p class="preview-note">.*?</p>', '', s)
    s = s.replace('Skills library · public REVIEW', 'Skills library')
    s = re.sub(r'<div class="card-detail">.*?(?=<h3>What it involves</h3>)', '<div class="card-detail">', s, flags=re.S)
    s = re.sub(r'<h3>Catalogue source snapshot.*?(?=<h3>)', '', s, flags=re.S)
    s = re.sub(r'<p><a href="../skills-map/[^>]*>.*?</a></p>', '', s)
    s = re.sub(r'<p class="(?:set-label|rights-hold-note)">.*?</p>', '', s)
    s = re.sub(r'<p class="guidance-label">Planned clinician-supported conversation / follow-through family — not built</p>', '', s)
    s = s.replace('Planned guided reflection adaptation in MBT-I context', 'Guided reflection in MBT-I context')
    s = re.sub(r'<span class="status [^"]*">.*?</span>',
               lambda m: '<span class="status">Not available here</span>' if 'Planned placeholder' in m[0] else '', s)
    s = re.sub(r'<p class="current-implementation"><span>.*?</span></p>', '', s)
    s = re.sub(r'<p class="component-note">.*?</p>', lambda m: clean_note(m[0]), s)
    s = s.replace('These help you find this entry; they are not extra cards or extra tools.', 'Related exercise names.')
    s = re.sub(r'About this (?:component and remaining set|component and catalogue entry|restoration and catalogue entry|placeholder)', 'About this skill', s)
    s = re.sub(r'<section id="library-notes" class="library-notes">.*?<details class="reference"',
               '<section id="library-notes" class="library-notes"><h2>About this library</h2><p>Choose practices with your therapist. Topic and approach filters help you browse; they do not assess suitability. Some entries are information only and have no practice to open here.</p><details class="reference"', s, flags=re.S)
    s = s.replace('These eight retained protocol references are not eight more skill cards. Additional approach and dyadic references remain in the full catalogue.', 'These treatments require an appropriate clinician and are not standalone exercises in this library.')
    s = re.sub(r'<a href="../skills-map/.*?</a>', '', s)
    s = re.sub(r'<p>\s*</p>', '', s)
    s = re.sub(r'<footer>.*?</footer>', '', s, flags=re.S)
    s = s.replace('Show only entries with a written practice you can open. These are review drafts, not clinically approved tools or complete treatment programmes.', 'Show only entries with a written practice you can open.')
    s = s.replace('Hide placeholders</label>', 'Show available practices only</label>')
    s = s.replace('Safety-planning placeholder', 'About safety planning')
    s = s.replace('Catalogue entries and current public REVIEW drafts', 'Skills and practices')
    s = s.replace('Find and browse catalogue entries', 'Find and browse skills')
    s = s.replace('Existing full Tool Library', 'Full Tool Library').replace('Original goals and pathways', 'Goals and pathways')
    s = re.sub(r'(?:Open|Review) ([^<]*?)(?: written restoration| guided component draft| component draft| written draft| draft)( →)?(?=</a>)', r'Open \1 →', s)
    s = s.replace('Scope placeholder - not a standalone tool', 'Clinician-led treatment — not a standalone exercise').replace('Protocol reference - not a standalone built tool', 'Clinician-led treatment — not a standalone exercise')
    return s


def clean_note(s):
    # These are release/counting sentences, not clinical instructions. Keep all other scope guidance.
    s = re.sub(r'(?:Existing canonical|Existing classic/|Existing canonical entry|Existing classic|No new canonical|No new count|No added canonical|No invented component|Retained native resources keep their identities|Clinical suitability, source rights|This review draft does not establish|Clinical acceptance is not asserted|Clinical and browser acceptance|Written candidate withheld|This update does not release)[^.]*\.', '', s)
    s = re.sub(r'Clinical acceptance is not asserted; narration is pending\.', '', s)
    s = re.sub(r'Source/clinical fidelity acceptance remains pending\.', '', s)
    s = s.replace('Existing original public resources remain separate and unchanged. Method-specific guidance and safeguards remain applicable.', '')
    if 'This update does not release' in s or not re.sub('<[^>]+>', '', s).strip():
        return ''
    return s


def clean_html(s, name):
    if name == 'practice-library/skills-library/index.html':
        s = clean_library(s)
    if name.startswith('practice-library/'):
        s = s.replace('<span>Current exercise review</span>', '')
        s = s.replace('Written practice draft. Use with therapist guidance; clinical, device and source-rights acceptance remain open. No additional recordings are included. Existing public recordings remain in the original library.', 'Use with therapist guidance. This practice is not a complete treatment programme or a validated digital treatment.')
        s = s.replace('For therapist-supported review, not a complete treatment programme or validated digital treatment. Optional writing', 'Optional writing')
        s = re.sub(r'<span class="(?:draft-tag|edition)">.*?</span>', '', s, flags=re.S)
        s = re.sub(r'<span class="withheld-reference">.*?</span>', '', s, flags=re.S)
        s = re.sub(r'<details class="design-explanation">.*?</details>', '', s, flags=re.S)
        s = s.replace('Design navigation', 'Practice navigation').replace('Back to review home', 'Back to skills library').replace('Public review home', 'Skills library')
        s = s.replace('This written review draft includes the Urge Surfing practice, safety choices and optional timer. Clinical and accessibility review remain open.', 'Practise Urge Surfing with safety choices and an optional timer.')
        s = s.replace('Four review tools now use the selected Guided focus layout. Their content is not yet accepted for public client release. Each preserves its own practice needs, with self-contained prompts and a source-informed explanation under Learn more. Nothing requires writing or feeling different.', 'Choose a practice with your therapist. Each has prompts and an explanation under Learn more. Writing and feeling different are not required.')
        s = s.replace('Guided focus is the selected design standard; these are still content review drafts. Toolbox shortcuts last in this page only; selected downloads and clipboard copies have their own lifetimes.', 'Toolbox shortcuts last in this page only; selected downloads and clipboard copies have their own lifetimes.')
        s = s.replace('Written practice is available. No additional recordings are included in this update. Existing public recordings remain in the original Tool Library.', 'Written practice is available. Audio is unavailable here.')
        s = re.sub(r'<details><summary>Restoration status and source limits</summary>.*?(<p>Writing stays.*?)</details>', r'\1', s, flags=re.S)
        s = re.sub(r'<p>Public REVIEW written restoration.*?</p>', '<p>Therapist-supported written practice. Audio and film are unavailable here.</p>', s)
        s = re.sub(r'<p class="status">Practice Room · Draft.*?</p>', '', s)
        s = re.sub(r'<aside class="v8b-review-note".*?</aside>', '', s, flags=re.S)
        s = re.sub(r'<aside class="native-review".*?</aside>', lambda m: '<aside class="practice-information">' + re.search(r'<nav.*?</nav>', m[0], re.S)[0].replace('Review context', 'Library navigation') + '<p>For therapist-supported practice. Film and recordings are unavailable here.</p>' + re.search(r'<p>Your writing.*?</p>', m[0], re.S)[0].replace('This review does not save', 'This practice does not save') + re.search(r'<a href="readable-handout.html".*?</a>', m[0], re.S)[0].replace('Read preserved V8B written teaching', 'Read the written teaching') + '</aside>', s, flags=re.S)
        s = re.sub(r'(?i)(?:isolated )?written review candidate', 'written practice', s)
        s = re.sub(r'(?i)(?:public review draft|public REVIEW library|public written review draft)', 'A Place to Practise', s)
        s = re.sub(r'(?i) · public review(?: draft)?', '', s)
    return s


DISPLAY_REPLACEMENTS = {
    'This review only: this shortcut lasts in this open session.': 'This shortcut lasts in this open session.',
    ' Recordings are privately archived, not connected to this practice, and awaiting listening review.': '',
    ' Scripts are prepared; recordings and listening review are still needed.': '',
    'Written practice draft. Use with therapist guidance; clinical, device and source-rights acceptance remain open. No additional recordings are included. Existing public recordings remain in the original library.': 'Use with therapist guidance. This practice is not a complete treatment programme or a validated digital treatment.',
}


def clean_practice_js(s):
    for old, new in DISPLAY_REPLACEMENTS.items():
        s = s.replace(old, new)
    # Remove only the disclosure built expressly for reviewers. Method scope and sources remain.
    s = re.sub(r"const scope=E\('details','reviewer-scope'\);scope\.append\(.*?target\.append\(scope\);", '', s)
    return s


def apply(root):
    before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob('*') if p.is_file()}
    changed = []
    for p in (root / 'practice-library').rglob('*.html'):
        name = p.relative_to(root).as_posix()
        original = p.read_text(encoding='utf-8')
        # Catalogue evidence is an internal reference surface; preserve its data assets and old anchors.
        if name in ('practice-library/skills-map/index.html', 'practice-library/skills-map/overview.html'):
            cleaned = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Skills library · A Place to Practise</title><meta name="viewport" content="width=device-width,initial-scale=1"><a href="../skills-library/">Open the skills library</a><script>location.replace('../skills-library/'+location.hash);</script></html>'''
        else:
            cleaned = clean_html(original, name)
        if cleaned != original:
            p.write_text(cleaned, encoding='utf-8', newline='\n')
            changed.append(name)
    for p in (root / 'practice-library/assets').glob('*practice.js'):
        original = p.read_text(encoding='utf-8')
        cleaned = clean_practice_js(original)
        if cleaned != original:
            p.write_text(cleaned, encoding='utf-8', newline='\n')
            changed.append(p.relative_to(root).as_posix())
    # Original public library keeps its existing controllers and Toolbox navigation.
    for name in ('index.html', 'pilot.js', 'review-hub.js'):
        p = root / name
        s = p.read_text(encoding='utf-8')
        s = s.replace('A Place to Practise - Review pilot', 'A Place to Practise')
        s = s.replace('A Place to Practise — Review pilot', 'A Place to Practise')
        s = re.sub(r"const note=document.createElement\('div'\);note.className='pp-review-note';note.textContent='[^']*';header.before\(note\);", '', s)
        s = s.replace('Consolidated review navigation', 'Practice navigation')
        s = s.replace("const checklist=el('a','Working draft checklist');checklist.href=new URL('review.html',base).href;nav.append(checklist);", '')
        s = s.replace('Provisional Kokoro af_heart audition. Not yet approved for release. This player reads fixed teaching.', 'This player reads fixed teaching with a synthetic voice.')
        s = s.replace(' See pilot evidence for provenance.', '')
        p.write_text(s, encoding='utf-8', newline='\n')
        changed.append(name)
    for name in ('review.html', 'review-audio.html'):
        p = root / name
        p.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>A Place to Practise</title><meta http-equiv="refresh" content="0; url=practice-library/skills-library/"><a href="practice-library/skills-library/">Open the skills library</a></html>', encoding='utf-8', newline='\n')
        changed.append(name)
    # Status badge is generated by this shared support header, rather than static HTML.
    p = root / 'practice-library/assets/shared-support-chrome.js'
    s = p.read_text(encoding='utf-8')
    s = s.replace("status.textContent='PUBLIC REVIEW DRAFT'", "status.textContent=''")
    p.write_text(s, encoding='utf-8', newline='\n')
    changed.append(p.relative_to(root).as_posix())
    # The existing availability filter remains functional; use audience-facing wording.
    p = root / 'practice-library/skills-library/library.js'
    s = p.read_text(encoding='utf-8').replace(' · placeholders hidden', ' · available practices')
    p.write_text(s, encoding='utf-8', newline='\n')
    changed.append(p.relative_to(root).as_posix())
    after = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in root.rglob('*') if p.is_file()}
    assert before.keys() == after.keys(), 'Cleanup must not remove routes or underlying files'
    assert all(before[k] == v for k, v in after.items() if k not in changed)
    assert all(before[k] == v for k, v in after.items() if k.endswith(('.json', '.mp3', '.wav', '.pdf', '.mp4')))
    app = {k: v for k, v in after.items() if not k.startswith('previews/') and k != '_integrated_manifest.sha256'}
    (root / '_integrated_manifest.sha256').write_text(''.join(v+'  '+k+'\n' for k,v in sorted(app.items())), encoding='utf-8', newline='\n')
    print(json.dumps({'cleanedPresentationFiles': len(changed), 'preservedFilePaths': len(after), 'changed': changed}))


if __name__ == '__main__':
    apply(Path('_site'))
