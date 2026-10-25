#!/usr/bin/env python3
"""Apply 5A.6A adapter restart-seeking from staged files."""
import argparse,hashlib,json,os,shutil,tempfile
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
def blob(d):return hashlib.sha1(b'blob '+str(len(d)).encode()+b'\0'+d).hexdigest()
def confined(root,name):
 p=PurePosixPath(name)
 if p.is_absolute() or '..' in p.parts or '\\' in name:raise ValueError('Unsafe path: '+name)
 path=root/name;cursor=path
 while cursor!=root:
  if cursor.is_symlink():raise ValueError('Symlink refused: '+name)
  cursor=cursor.parent
 if not path.resolve().is_relative_to(root):raise ValueError('Path escapes root: '+name)
 return path
def transformed(raw,record,name):
 text=raw.decode()
 if blob(raw)==record['before']:
  for old,new in record['edits']:
   if text.count(old)!=1:raise ValueError('Missing unique transform anchor: '+name)
   text=text.replace(old,new,1)
  return text.encode()
 reverse=text
 for old,new in reversed(record['edits']):
  if reverse.count(new)!=1:raise ValueError('Unexpected local version: '+name)
  reverse=reverse.replace(new,old,1)
 if blob(reverse.encode())!=record['before']:raise ValueError('Unexpected local edits: '+name)
 return raw
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--apply',action='store_true');a=ap.parse_args()
 source=Path(__file__).resolve().parents[1];target=a.root.expanduser().resolve()
 if source==target or not target.is_dir():ap.error('Extract separately and specify checkout root')
 name='MANIFEST_5A6A.json';raw=(source/name).read_bytes();manifest=json.loads(raw);errors=[];payload={name:raw}
 for f,expected in manifest['sha256'].items():
  data=confined(source,f).read_bytes()
  if hashlib.sha256(data).hexdigest()!=expected:errors.append('Package checksum mismatch: '+f)
  payload[f]=data;dest=confined(target,f)
  if dest.exists() and (not dest.is_file() or dest.read_bytes()!=data):errors.append('Conflicting existing new file: '+f)
 for f,record in manifest['patches'].items():
  try:payload[f]=transformed(confined(target,f).read_bytes(),record,f)
  except (OSError,ValueError,UnicodeError) as e:errors.append(str(e))
 if errors:raise SystemExit('\n'.join(errors)+'\nNo checkout files changed.')
 changes=[n for n,d in payload.items() if not confined(target,n).exists() or confined(target,n).read_bytes()!=d]
 print(f'Preflight passed: {len(changes)} file(s) to install/update.')
 if not a.apply:print('Check only. Add --apply to write files.');return
 if not changes:print('Already applied; no files changed.');return
 backup=target/'.wapflix-patch-backups'/('5a6a-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));backup.mkdir(parents=True);existed={};written=[]
 for n in changes:
  p=confined(target,n);existed[n]=p.exists()
  if existed[n]:
   saved=backup/n;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,saved)
 (backup/'installed-files.json').write_text(json.dumps({'existed':existed},indent=2)+'\n')
 try:
  for n in changes:
   p=confined(target,n);p.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='.5a6a-',dir=p.parent)
   try:
    with os.fdopen(fd,'wb') as h:h.write(payload[n])
    os.chmod(tmp,0o644);os.replace(tmp,p);written.append(n)
   finally:
    if os.path.exists(tmp):os.unlink(tmp)
 except BaseException:
  for n in reversed(written):
   p=confined(target,n)
   if existed[n]:shutil.copy2(backup/n,p)
   else:p.unlink(missing_ok=True)
  raise
 print('Applied 5A.6A. Backup: '+str(backup));print('No commit, service restart or browser acceptance performed.')
if __name__=='__main__':main()
