"""Project harness: sequential stages, fail-fast gates, persistent evidence.

The my_harness factory is a design reference; no fake native-agent install
or independent AI review is claimed. This runner executes real local tools.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone

from project import ROOT, REPO_ROOT, FONT_ID


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-browser',action='store_true',help='Explicitly mark browser check NOT RUN')
    args=parser.parse_args()
    spec=json.loads((REPO_ROOT/'harness/pipeline.json').read_text(encoding='utf-8'))
    report={'started':datetime.now(timezone.utc).isoformat(),'mode':spec['mode'],
            'external_review':spec['external_review'],'steps':[],'status':'running'}
    path=ROOT/'docs/last-run.json'
    def save():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for step in spec['steps']:
        if args.skip_browser and step['id']=='browser-7px':
            report['steps'].append({'id':step['id'],'status':'not-run'})
            save();continue
        print(f'\n[{step["id"]}]',flush=True)
        result=subprocess.run([sys.executable,*step['args']],cwd=REPO_ROOT)
        item={'id':step['id'],'exit_code':result.returncode,'status':'pass' if result.returncode==0 else 'fail'}
        if 'evidence' in step:
            item['evidence']=step['evidence']
            if result.returncode==0 and not (ROOT/step['evidence']).is_file():
                item['status']='fail';item['reason']='Missing evidence'
        report['steps'].append(item)
        if item['status']=='fail':
            report['status']='failed';save();raise SystemExit(1)
        save()
    report['status']='automated-checks-pass' if not args.skip_browser else 'partial-browser-not-run'
    report['manual_review']='pending; automated success does not approve optical quality or 7px legibility'
    report['completed']=datetime.now(timezone.utc).isoformat()
    save()
    print(f'\n{report["status"]}: {path}',flush=True)


if __name__=='__main__':main()
