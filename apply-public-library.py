from pathlib import Path, PurePosixPath
import hashlib, json, base64, zipfile, io
root=Path('_site');sha=lambda b:hashlib.sha256(b).hexdigest()
raw=Path('public-library-release.json').read_bytes()
assert sha(raw)=='2f3fdf0543807c0b30d69e19f6cfb11a8fc2cf9afee4fd50df978c7f67edc81f', 'Current review manifest hash mismatch'
m=json.loads(raw);assert m['schema']=='aptp-additive-public-library-v1'
assert m['routes']==68 and m['narrationIncluded'] is False
before=m['before'];delta=m['files'];assert len(before)==744
assert set(before)&set(delta)=={'index.html'}
assert all(k=='index.html' or k=='public-library-home.js' or k.startswith('practice-library/') for k in delta)
def census():
 result={}
 for f in root.rglob('*'):
  assert not f.is_symlink()
  if f.is_file():result[f.relative_to(root).as_posix()]=sha(f.read_bytes())
 return result
all_before=census();previews={k:v for k,v in all_before.items() if k.startswith('previews/')}
assert len(previews)==m['expectedPreservedPreviews']==422
assert {k:v for k,v in all_before.items() if not k.startswith('previews/') and k!='_integrated_manifest.sha256'}==before, 'Public application baseline changed'
parts=[]
for i,p in enumerate(m['parts'],1):
 assert p['path']==f'public-library.part{i:02d}.b64'
 b=Path(p['path']).read_bytes();assert len(b)==p['bytes'] and sha(b)==p['sha256']
 assert b.endswith(b'\n') and b'\n' not in b[:-1] and b'\r' not in b
 parts.append(b[:-1])
blob=base64.b64decode(b''.join(parts),validate=True)
assert len(blob)==m['archiveBytes'] and sha(blob)==m['archiveSHA256']
with zipfile.ZipFile(io.BytesIO(blob)) as z:
 assert z.testzip() is None and len(z.infolist())==len(delta) and set(z.namelist())==set(delta)
 for e in z.infolist():
  p=PurePosixPath(e.filename)
  assert not p.is_absolute() and '..' not in p.parts and '\\' not in e.filename
  assert (e.external_attr>>16)&0o170000!=0o120000
  assert sha(z.read(e))==delta[e.filename]
 for e in z.infolist():
  target=root/e.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(e))
after=dict(before);after.update(delta);actual=census()
assert {k:v for k,v in actual.items() if k.startswith('previews/')}==previews
assert {k:v for k,v in actual.items() if not k.startswith('previews/') and k!='_integrated_manifest.sha256'}==after
assert all(after[k]==v for k,v in before.items() if k!='index.html')
(root/'_integrated_manifest.sha256').write_text(''.join(v+'  '+k+'\n' for k,v in sorted(after.items())),encoding='utf-8',newline='\n')
print(json.dumps({'currentExerciseRoutes':68,'newFiles':len(delta)-1,'unchangedOldApplicationFiles':743,'preservedPreviews':len(previews),'applicationFiles':len(after),'archiveSHA256':m['archiveSHA256'],'narrationIncluded':False}))
