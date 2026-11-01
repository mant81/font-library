"""Rebuild unchanged persisted inputs and compare every packaged output."""
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build import ROOT,dump
from project import REPO_ROOT


def main():
    manifest=ROOT/'dist/build-manifest.json'
    before=json.loads(manifest.read_text(encoding='utf-8'))
    subprocess.run([sys.executable,str(REPO_ROOT/'scripts/build.py')],cwd=REPO_ROOT,check=True)
    after=json.loads(manifest.read_text(encoding='utf-8'))
    keys=['version','source_sha256','config_sha256','script_sha256','overrides_sha256','centerlines_sha256','python','tools']
    same_inputs=all(before[k]==after[k] for k in keys)
    changed=sorted(k for k in before['outputs'].keys()|after['outputs'].keys()
                   if before['outputs'].get(k)!=after['outputs'].get(k))
    passed=same_inputs and not changed
    dump('docs/reproducibility.json',{'status':'pass' if passed else 'fail','same_inputs':same_inputs,
         'inputs':{k:after[k] for k in keys},'output_count':len(after['outputs']),
         'font_file_count':sum(p.endswith(('.ttf','.woff2')) for p in after['outputs']),
         'changed_outputs':changed,'checks':'Two consecutive builds; all packaged output sizes and SHA-256 digests compared.'})
    print(f'Reproducibility: {"PASS" if passed else "FAIL"}, {len(after["outputs"])} outputs, changed={len(changed)}')
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
