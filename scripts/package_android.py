"""Copy the same verified TTF masters into Android resource directories."""
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build import ROOT,CFG,sha,dump


def main():
    validation=json.loads((ROOT/'docs/validation.json').read_text(encoding='utf-8'))
    assert validation['status']=='automated-structure-pass'
    target=ROOT/'examples/android/app/src/main/res/font';target.mkdir(parents=True,exist_ok=True)
    files={}
    resource=CFG['id'].replace('-','_')
    for stem,name in [(CFG['file_prefix'],resource+'_regular.ttf'),(CFG['file_prefix']+'Small',resource+'_small.ttf')]:
        source=ROOT/f'dist/{stem}-Regular.ttf';dest=target/name
        shutil.copyfile(source,dest)
        assert sha(source)==sha(dest)
        files[name]={'source':source.relative_to(ROOT).as_posix(),'sha256':sha(dest)}
    if CFG.get('license_file'):
        raw=target.parent/'raw';raw.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/CFG['license_file'],raw/'font_license.txt')
    dump('examples/android/font-manifest.json',{'files':files,'device_validation':'not run','sample':'Java Activity; import into an Android app with minSdk 26 or newer'})
    print('Android TTF resources packaged; device test not run.')


if __name__=='__main__':main()
