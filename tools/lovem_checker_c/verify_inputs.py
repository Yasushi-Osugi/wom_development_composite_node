"""Verify input ZIP manifests and fixed source revision; never changes inputs."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
from rules import dump

def main(repo,inputs,out):
 repo=Path(repo);inputs=Path(inputs);results=[]
 for mode in ('legacy','identity'):
  zpath=repo/'handoff/lovem_stageC'/f'handoff_ev-thailand-2026_C_{mode}.zip'
  root=inputs/mode/f'handoff_ev-thailand-2026_C_{mode}'
  checked=[]
  for line in (root/'SHA256SUMS.txt').read_text().splitlines():
   if not line.strip():continue
   want,name=line.split(maxsplit=1);name=name.lstrip('*');p=root/name
   assert p.resolve().is_relative_to(root.resolve())
   got=hashlib.sha256(p.read_bytes()).hexdigest();assert got==want,name;checked.append({'file':name,'sha256':got})
  with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
  m=json.loads((root/'run/manifest.json').read_text());assert m['lot_flow_mode']==mode and m['dirty'] is False and m['code_sha']=='3481fc5b30ba88f8bb445d1ced888212b3221591'
  results.append(dict(mode=mode,zip_sha256=hashlib.sha256(zpath.read_bytes()).hexdigest(),code_sha=m['code_sha'],dirty=m['dirty'],dirty_scope=m['dirty_scope'],checked=checked))
 diff=subprocess.check_output(['git','-C',str(repo),'diff','--name-only','a43163f','3481fc5'],text=True).splitlines()
 assert diff==['requests/RequestLetter_LOVEM_StageC_to_Astra.md'],diff
 dump(out,{'input_checks':results,'baseline_to_run_commit_changed_files':diff,'source_worktree_status':subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True)})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--inputs',required=True);p.add_argument('--out',required=True);a=p.parse_args();main(a.repo,a.inputs,a.out)
