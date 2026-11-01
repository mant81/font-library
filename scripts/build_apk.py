"""Build a signed offline Android preview APK with installed SDK/JDK tools.

No Gradle download or global Android configuration changes. The test signing
key is persisted under .local/ and is not a release/store signing credential.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

from project import ROOT, REPO_ROOT, FONT_ID
APP=ROOT/'examples/android/app/src/main'
BUILD=ROOT/'examples/android/build'
CONFIG=json.loads((ROOT/'config/font.json').read_text(encoding='utf-8'))
PACKAGE=ET.parse(APP/'AndroidManifest.xml').getroot().get('package')


def run(args, **kwargs):
    result=subprocess.run([str(a) for a in args],cwd=ROOT,check=True,**kwargs)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sdk',type=Path,default=Path(os.environ.get('ANDROID_SDK_ROOT',Path(os.environ['LOCALAPPDATA'])/'Android/Sdk')))
    parser.add_argument('--java-home',type=Path,default=Path(shutil.which('java') or 'java').resolve().parent.parent)
    args=parser.parse_args()
    sdk=args.sdk.resolve(); java=args.java_home.resolve()
    tools=sdk/'build-tools/36.0.0'; platform=sdk/'platforms/android-35/android.jar'
    required=[java/'bin/java.exe',java/'bin/javac.exe',java/'bin/keytool.exe',tools/'aapt2.exe',tools/'zipalign.exe',
              tools/'lib/d8.jar',tools/'lib/apksigner.jar',platform]
    for file in required:
        if not file.is_file():parser.error(f'Required build tool missing: {file}')
    for folder in ['generated','classes','dex']:(BUILD/folder).mkdir(parents=True,exist_ok=True)
    # javac's Windows ZIP provider can fail resolving a sandbox-external JAR
    # during close. Compile against a read-only source copy inside the build.
    local_platform=BUILD/'android-35.jar'
    shutil.copyfile(platform,local_platform)
    platform=local_platform
    # Always package the verified TTF masters rather than stale resource copies.
    run([sys.executable,REPO_ROOT/'scripts/package_android.py'])
    run([tools/'aapt2.exe','compile','--dir',APP/'res','-o',BUILD/'resources.zip'])
    run([tools/'aapt2.exe','link','-o',BUILD/'resources.apk','-I',platform,'--manifest',APP/'AndroidManifest.xml',
         '--java',BUILD/'generated','--min-sdk-version','26','--target-sdk-version','35',BUILD/'resources.zip'])
    sources=sorted((APP/'java').rglob('*.java'))+sorted((BUILD/'generated').rglob('*.java'))
    run([java/'bin/javac.exe','--release','8','-encoding','UTF-8','-classpath',platform,'-d',BUILD/'classes',*sources])
    classes=sorted((BUILD/'classes').rglob('*.class'))
    run([java/'bin/java.exe','-cp',tools/'lib/d8.jar','com.android.tools.r8.D8','--release','--min-api','26',
         '--lib',platform,'--output',BUILD/'dex',*classes])
    unsigned=BUILD/'unsigned.apk'
    shutil.copyfile(BUILD/'resources.apk',unsigned)
    with zipfile.ZipFile(unsigned,'a') as apk:
        for dex in sorted((BUILD/'dex').glob('*.dex')):
            info=zipfile.ZipInfo(dex.name,date_time=(2026,11,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            apk.writestr(info,dex.read_bytes())
    aligned=BUILD/'aligned.apk'
    run([tools/'zipalign.exe','-f','-p','4',unsigned,aligned])
    key=REPO_ROOT/'.local/android-debug.keystore';key.parent.mkdir(parents=True,exist_ok=True)
    if not key.exists():
        run([java/'bin/keytool.exe','-genkeypair','-keystore',key,'-storepass','android','-keypass','android',
             '-alias','androiddebugkey','-keyalg','RSA','-keysize','2048','-validity','10000',
             '-dname','CN=Minbo Font Preview Debug,O=Local Development,C=KR'])
    output=ROOT/f'dist/android/{CONFIG["id"]}-font-preview-{CONFIG["android_version_name"]}.apk';output.parent.mkdir(parents=True,exist_ok=True)
    signer=[java/'bin/java.exe','-jar',tools/'lib/apksigner.jar']
    run([*signer,'sign','--ks',key,'--ks-key-alias','androiddebugkey','--ks-pass','pass:android',
         '--key-pass','pass:android','--out',output,aligned])
    verification=run([*signer,'verify','--verbose','--print-certs',output],capture_output=True,text=True)
    print(verification.stdout)
    alignment=run([tools/'zipalign.exe','-c','4',output],capture_output=True,text=True)
    badging=run([tools/'aapt2.exe','dump','badging',output],capture_output=True,text=True,encoding='utf-8')
    print(badging.stdout)
    sha=hashlib.sha256(output.read_bytes()).hexdigest()
    manifest={'package':PACKAGE,'display_name':CONFIG['display_name'],
              'version':CONFIG['android_version_name'],'version_code':CONFIG['android_version_code'],'min_sdk':26,'target_sdk':35,
              'file':output.relative_to(ROOT).as_posix(),'bytes':output.stat().st_size,'sha256':sha,
              'signing':'local debug/test certificate; not a store release','signature_verified':True,'zipalign_verified':True,
              'permissions':[],'font_sources':json.loads((ROOT/'examples/android/font-manifest.json').read_text(encoding='utf-8')),
              'build_tools':'36.0.0','device_validation':'not yet run'}
    (output.parent/'apk-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (BUILD/'signature-verification.txt').write_text(verification.stdout,encoding='utf-8')
    (BUILD/'badging.txt').write_text(badging.stdout,encoding='utf-8')
    output.with_suffix('.apk.sha256').write_text(sha+'  '+output.name+'\n',encoding='utf-8')
    print(f'APK ready: {output} ({output.stat().st_size:,} bytes)')


if __name__=='__main__':main()
