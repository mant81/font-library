"""Install and exercise the APK in a private, headless Android 36 AVD.

Never targets a physical phone or existing user emulator. All AVD files stay
inside _workspace/ and this script stops only the emulator it created.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from project import ROOT, REPO_ROOT, FONT_ID
CONFIG=json.loads((ROOT/'config/font.json').read_text(encoding='utf-8'))
PACKAGE=ET.parse(ROOT/'examples/android/app/src/main/AndroidManifest.xml').getroot().get('package')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sdk',type=Path,default=Path(os.environ.get('ANDROID_SDK_ROOT',Path(os.environ['LOCALAPPDATA'])/'Android/Sdk')))
    parser.add_argument('--upgrade-from',type=Path,help='Optional previous APK to install before testing the update')
    args=parser.parse_args();sdk=args.sdk.resolve()
    folder=REPO_ROOT/'_workspace/android-emulator';folder.mkdir(parents=True,exist_ok=True)
    evidence=ROOT/'docs/android';evidence.mkdir(parents=True,exist_ok=True)
    avdhome=folder/'avd';avdhome.mkdir(exist_ok=True)
    avd=avdhome/'MinboFontPreview.avd';avd.mkdir(exist_ok=True)
    image=sdk/'system-images/android-36/google_apis/x86_64'
    if not (image/'system.img').exists():parser.error('Installed Android 36 Google APIs x86_64 image required')
    (avdhome/'MinboFontPreview.ini').write_text(f'avd.ini.encoding=UTF-8\npath={avd.as_posix()}\ntarget=android-36\n',encoding='utf-8')
    config={'AvdId':'MinboFontPreview','PlayStore.enabled':'false','abi.type':'x86_64','avd.ini.displayname':'Minbo Font Preview',
            'avd.ini.encoding':'UTF-8','disk.dataPartition.size':'1024M','hw.cpu.arch':'x86_64','hw.cpu.ncore':'2',
            'hw.ramSize':'2048','hw.lcd.width':'720','hw.lcd.height':'1280','hw.lcd.density':'320',
            'hw.gpu.enabled':'yes','hw.gpu.mode':'swiftshader','hw.keyboard':'yes','hw.mainKeys':'no',
            'hw.audioInput':'no','hw.camera.back':'none','hw.camera.front':'none','hw.gps':'no','hw.battery':'yes',
            'hw.device.name':'pixel_2','hw.device.manufacturer':'Google','image.sysdir.1':image.as_posix()+'/',
            'showDeviceFrame':'no','skin.dynamic':'yes','skin.name':'720x1280','tag.id':'google_apis',
            'tag.display':'Google APIs','vm.heapSize':'256','fastboot.forceColdBoot':'yes'}
    (avd/'config.ini').write_text(''.join(f'{k}={v}\n' for k,v in config.items()),encoding='utf-8')
    env=os.environ.copy();env['ANDROID_AVD_HOME']=str(avdhome);env['ANDROID_EMULATOR_HOME']=str(folder/'home')
    env['ANDROID_USER_HOME']=str(folder/'user');env['ANDROID_SDK_ROOT']=str(sdk)
    for p in [folder/'home',folder/'user']:p.mkdir(exist_ok=True)
    adb=sdk/'platform-tools/adb.exe';serial='emulator-5580'
    def command(parts,timeout=60,binary=False,check=True):
        result=subprocess.run([str(adb),'-s',serial,*parts],capture_output=True,
                              text=not binary,encoding=None if binary else 'utf-8',errors=None if binary else 'replace',timeout=timeout)
        if check and result.returncode:raise RuntimeError(str(result.stderr))
        return result.stdout
    existing=subprocess.run([str(adb),'devices'],capture_output=True,text=True).stdout
    if serial in existing:parser.error('Private test port 5580 already in use; refusing to target that device')
    logfile=(folder/'emulator.log').open('wb')
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    process=subprocess.Popen([str(sdk/'emulator/emulator.exe'),'-avd','MinboFontPreview','-port','5580',
        '-no-window','-no-audio','-no-boot-anim','-no-snapshot','-gpu','swiftshader','-feature','-Vulkan'],
        stdout=logfile,stderr=subprocess.STDOUT,env=env,creationflags=flags)
    report={'emulator':'private Android 36 Google APIs x86_64','serial':serial,'status':'running',
            'started':datetime.now(timezone.utc).isoformat(),'physical_device':'not used'}
    apk=ROOT/f'dist/android/{CONFIG["id"]}-font-preview-{CONFIG["android_version_name"]}.apk'
    report['apk_sha256']=hashlib.sha256(apk.read_bytes()).hexdigest()
    def save():
        (evidence/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def ui():
        command(['shell','uiautomator','dump','/sdcard/minbo-ui.xml'])
        return command(['exec-out','cat','/sdcard/minbo-ui.xml'])
    try:
        print('Starting private headless emulator...',flush=True)
        start=time.monotonic();boot=False
        while time.monotonic()-start<240:
            if process.poll() is not None:raise RuntimeError('Emulator exited; see _workspace/android-emulator/emulator.log')
            if command(['shell','getprop','sys.boot_completed'],timeout=10,check=False).strip()=='1':
                boot=True;break
            print(f'Waiting for Android boot ({int(time.monotonic()-start)}s)...',flush=True)
            time.sleep(5)
        if not boot:raise RuntimeError('Emulator boot timeout')
        command(['shell','input','keyevent','82'])
        command(['logcat','-c'])
        if args.upgrade_from:
            # Reset only this app in our private fixture, so repeated upgrade
            # checks do not attempt a downgrade over the last tested version.
            command(['uninstall',PACKAGE],check=False)
            old_install=command(['install','-r','-t',str(args.upgrade_from.resolve())])
            if 'Success' not in old_install:raise RuntimeError('Previous APK install failed: '+old_install)
            report['previous_apk_installed']='pass'
        install=command(['install','-r','-t',str(apk)])
        if 'Success' not in install:raise RuntimeError('Install failed: '+install)
        report['install']='pass'
        if args.upgrade_from:report['upgrade_from_previous_version']='pass'
        launch=command(['shell','am','start','-W','-n',PACKAGE+'/.MainActivity'])
        if 'Status: ok' not in launch:raise RuntimeError('Launch failed: '+launch)
        report['launch']='pass';print('APK installed and Activity launched.',flush=True)
        time.sleep(3)
        xml=ui();(evidence/'ui-initial.xml').write_text(xml,encoding='utf-8')
        if CONFIG['display_name'] not in xml:raise RuntimeError('Expected app title not visible')
        (evidence/'app-initial.png').write_bytes(command(['exec-out','screencap','-p'],binary=True))
        found=None
        for attempt in range(4):
            tree=ET.fromstring(ui())
            found=next((node for node in tree.iter('node') if node.get('text','').casefold()=='7sp 확인' and node.get('clickable')=='true'),None)
            if found is not None:
                coords=list(map(int,re.findall(r'\d+',found.get('bounds',''))))
                if len(coords)==4 and 80 < coords[1] < coords[3] < 1190:break
            found=None
            command(['shell','input','swipe','690','1050','690','450','450']);time.sleep(.7)
        if found is None:raise RuntimeError('7sp button not accessible')
        x0,y0,x1,y1=map(int,re.findall(r'\d+',found.get('bounds')))
        command(['shell','input','tap',str((x0+x1)//2),str((y0+y1)//2)])
        time.sleep(1)
        command(['shell','input','swipe','690','350','690','1150','350']);time.sleep(.7)
        xml=ui();(evidence/'ui-7sp.xml').write_text(xml,encoding='utf-8')
        if '글자 크기 · 7sp' not in xml:raise RuntimeError('7sp control did not update')
        switches=[n for n in ET.fromstring(xml).iter('node') if n.get('class')=='android.widget.Switch']
        if not switches or switches[0].get('checked')!='true':raise RuntimeError('Small optical font not selected')
        report['seven_sp_control']='pass';report['small_font_auto_selection']='pass'
        (evidence/'app-7sp.png').write_bytes(command(['exec-out','screencap','-p'],binary=True))
        edit=next((n for n in ET.fromstring(xml).iter('node') if n.get('class')=='android.widget.EditText'),None)
        if edit is None:raise RuntimeError('Text input not visible')
        x0,y0,x1,y1=map(int,re.findall(r'\d+',edit.get('bounds')))
        command(['shell','input','tap',str((x0+x1)//2),str((y0+y1)//2)])
        command(['shell','input','text','APK_test123'])
        time.sleep(.7)  # Hardware keyboard: BACK would close the Activity when no IME is shown.
        xml=ui();(evidence/'ui-input.xml').write_text(xml,encoding='utf-8')
        if xml.count('APK_test123')<2:raise RuntimeError('Typed text did not update the live preview')
        report['live_text_input']='pass'
        if CONFIG.get('license_file'):
            license_node = None
            for attempt in range(8):
                current=ET.fromstring(ui())
                license_node=next((n for n in current.iter('node') if n.get('text')=='폰트 라이선스' and n.get('clickable')=='true'),None)
                if license_node is not None:
                    bounds=list(map(int,re.findall(r'\d+',license_node.get('bounds',''))))
                    if len(bounds)==4 and 80 < bounds[1] < bounds[3] < 1190:break
                license_node=None
                command(['shell','input','swipe','690','1050','690','350','350']);time.sleep(.6)
            if license_node is None:raise RuntimeError('Font license button not accessible')
            x0,y0,x1,y1=map(int,re.findall(r'\d+',license_node.get('bounds')))
            command(['shell','input','tap',str((x0+x1)//2),str((y0+y1)//2)]);time.sleep(.7)
            license_xml=ui()
            (evidence/'ui-license.xml').write_text(license_xml,encoding='utf-8')
            if '비상업적' not in license_xml or '상업적 이용은 금지' not in license_xml:
                raise RuntimeError('Non-commercial license terms missing from the app dialog')
            (evidence/'app-license.png').write_bytes(command(['exec-out','screencap','-p'],binary=True))
            report['font_license_dialog']='pass'
        crash=command(['logcat','-d','-b','crash'])
        (evidence/'crash-log.txt').write_text(crash,encoding='utf-8')
        if 'FATAL EXCEPTION' in crash:raise RuntimeError('App crash logged')
        pid=command(['shell','pidof',PACKAGE]).strip()
        if not pid:raise RuntimeError('App no longer running')
        report['crash_check']='pass';report['font_loading']='pass (both native Typeface resources loaded without exception)'
        report['status']='pass';report['physical_device_validation']='not run'
        metadata_path=ROOT/'dist/android/apk-manifest.json'
        metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata['sha256']!=report['apk_sha256']:raise RuntimeError('APK changed during validation')
        metadata['device_validation']='Android 36 emulator: install, launch, native fonts, 7sp toggle and live input passed; physical device not run'
        metadata['validation_report']='docs/android/validation.json'
        metadata_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        save();print('Android APK emulator checks PASS.',flush=True)
    except Exception as exc:
        report['status']='fail';report['error']=str(exc);save();raise
    finally:
        if process.poll() is None:
            command(['emu','kill'],timeout=15,check=False)
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:process.terminate()
        logfile.close()


if __name__=='__main__':main()
