#!/usr/bin/env python3
"""Apply WAPFLIX screen/control consistency v7. Run from repository root."""
from pathlib import Path
import argparse, shutil, sys

FILES=['streaming.js','theme.js']
REPLACEMENTS={
'streaming.js':[
("const short=e=>e.episode_title||e.title;",
 """const short=e=>e.episode_title||e.title;
const handsetId=()=>window.wapflixHandset?.id||'';
const singleNavi=()=>['3210','3310'].includes(handsetId());
const baseFooter=footer;
footer=function(left,right){
  if(singleNavi()){left='SELECT';right='BACK';}
  baseFooter(left,right);
};"""),
("rows.slice(start,start+capacity).forEach((r,n)=>drawLine(r.label,y+n*20,start+n===page.selected,r.suffix||''));",
 "rows.slice(start,start+capacity).forEach((r,n)=>drawLine(r.label,y+n*18,start+n===page.selected,r.suffix||''));"),
("text((page.selected+1)+'/'+rows.length,4,193);",
 """const filled=Math.max(1,Math.round((page.selected+1)/rows.length*8));
  text('#'.repeat(filled)+'-'.repeat(8-filled),4,193);"""),
],
'theme.js':[
("window.wapflixHandset = { cycle, set, current: () => THEMES[index][1] };",
 "window.wapflixHandset = { cycle, set, current: () => THEMES[index][1], id: () => THEMES[index][0], singleNavi: () => ['3210','3310'].includes(THEMES[index][0]) };"),
("  b.onclick = () => run(action); return b;",
 """  b.onclick = () => {
    if(['handset-up','handset-down','roller-up','roller-down'].includes(className)&&typeof view!=='undefined'&&view==='player'){run(className.endsWith('-up')?'4':'6');return;}
    run(action);
  };
  return b;"""),
]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--restore',action='store_true')
    args=ap.parse_args()
    root=Path.cwd()
    if args.restore:
        for name in FILES:
            backup=root/(name+'.v7.bak')
            target=root/name
            if backup.exists():
                shutil.copyfile(backup,target); print('restored',name)
            else: print('no backup for',name)
        return
    for name,changes in REPLACEMENTS.items():
        path=root/name
        if not path.exists(): sys.exit('missing '+name)
        original=path.read_text()
        if (root/(name+'.v7.bak')).exists():
            original=(root/(name+'.v7.bak')).read_text()
        modified=original
        for old,new in changes:
            if old not in modified: sys.exit(f'anchor not found in {name}: {old[:60]}...')
            if modified.count(old)!=1: sys.exit(f'ambiguous anchor in {name}: {old[:60]}...')
            modified=modified.replace(old,new,1)
        shutil.copyfile(path,root/(name+'.v7.bak'))
        path.write_text(modified)
        print('patched',name)
    print('v7 applied. Backups: streaming.js.v7.bak, theme.js.v7.bak')

if __name__=='__main__': main()
