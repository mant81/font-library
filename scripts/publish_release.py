"""Publish a verified, already signed APK. Credentials never leave memory.

Uses GITHUB_TOKEN in Actions; locally, uses the configured Git credential helper.
Creates a draft, uploads the exact APK/checksum, then publishes the prerelease.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def git(*args):
    result=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','-C',str(ROOT),*args],
                          capture_output=True,text=True,check=True)
    return result.stdout.strip()


class GitHubError(RuntimeError):
    def __init__(self,status,message):self.status=status;super().__init__(f'GitHub HTTP {status}: {message}')


class GitHub:
    def __init__(self):
        self.repo=os.environ.get('GITHUB_REPOSITORY')
        if not self.repo:
            remote=git('remote','get-url','origin').removesuffix('.git')
            if remote.startswith('https://github.com/'):self.repo=remote.removeprefix('https://github.com/')
            elif remote.startswith('git@github.com:'):self.repo=remote.removeprefix('git@github.com:')
        if not self.repo or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',self.repo):
            raise ValueError('Expected a GitHub origin repository')
        self.token=os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
        if not self.token:
            env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
            result=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','-C',str(ROOT),'credential','fill'],
                input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,env=env,timeout=30)
            fields=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
            self.token=fields.get('password')
        if not self.token:raise RuntimeError('No non-interactive GitHub credential available')

    def request(self,method,path,data=None,raw=None,content_type=None):
        url=path if path.startswith('https://') else 'https://api.github.com'+path
        parsed=urllib.parse.urlparse(url)
        if parsed.hostname not in ('api.github.com','uploads.github.com'):raise ValueError('Unexpected API host')
        headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2026-03-10','User-Agent':'font-library-publisher'}
        if data is not None:raw=json.dumps(data).encode();content_type='application/json'
        if content_type:headers['Content-Type']=content_type
        try:
            with urllib.request.urlopen(urllib.request.Request(url,data=raw,headers=headers,method=method),timeout=90) as response:
                body=response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            try:message=json.loads(exc.read()).get('message','Request failed')
            except Exception:message='Request failed'
            raise GitHubError(exc.code,message) from None


def publish(font_id):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',font_id):raise ValueError('Invalid font ID')
    font=ROOT/'fonts'/font_id;cfg=json.loads((font/'config/font.json').read_text(encoding='utf-8'))
    if cfg['id']!=font_id:raise ValueError('Font ID mismatch')
    version=cfg['android_version_name'];tag=f'{font_id}-v{version}'
    meta=json.loads((font/'dist/android/apk-manifest.json').read_text(encoding='utf-8'))
    apk=font/meta['file'];checksum=apk.with_suffix('.apk.sha256')
    validation=json.loads((font/'docs/android/validation.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256(apk.read_bytes()).hexdigest()
    if digest!=meta['sha256'] or digest!=validation['apk_sha256'] or validation['status']!='pass':raise ValueError('APK verification evidence does not match')
    if not meta['signature_verified'] or not meta['zipalign_verified']:raise ValueError('Unsigned or unaligned APK')
    if not checksum.read_text(encoding='utf-8').startswith(digest):raise ValueError('Checksum file mismatch')
    api=GitHub();base=f'/repos/{api.repo}'
    commit=os.environ.get('GITHUB_SHA') or git('rev-parse','HEAD')
    body=f'''## {cfg['display_name']} / {cfg.get('english_name',cfg['family'])} {version} · 시험판

한글·영문·숫자·문장부호를 직접 입력해 확인하는 Android 서체 미리보기 앱입니다.

- Android 8.0(API 26) 이상
- 글자 크기 7–72sp 조절, 작은 글자용 보정본 자동/수동 선택
- 인터넷·저장소 등 추가 앱 권한 없음
- APK 서명·정렬 검사 및 Android 36 에뮬레이터 설치·실행·입력 검증 통과
- 휴대폰 전체의 시스템 기본 글꼴을 바꾸는 패키지는 아닙니다.

APK를 휴대폰에 내려받아 열고 설치하세요. 로컬 시험용 인증서로 서명했으며 실제 휴대폰 검증과 전수 가독성 검토는 남아 있습니다. 직접 쓴 손글씨를 바탕으로 독자 제작했습니다. 개인·기업·관공서의 비상업적 사용은 무료이며, 상업적 이용은 금지합니다. 전체 이용 조건은 첨부한 LICENSE.txt와 [라이선스 안내](https://mant81.github.io/font-library/license.html)를 확인하세요. 실제 문장 표본 검토에서 자모 간격·받침 형태·마침표 크기의 보정 필요성을 확인했으며, 이 버전은 필체 재현 완료판이 아닌 자모 조합 시험판입니다.

SHA-256: `{digest}`

[폰트 라이브러리](https://{api.repo.split('/')[0]}.github.io/{api.repo.split('/')[1]}/)
'''
    try:release=api.request('GET',base+'/releases/tags/'+urllib.parse.quote(tag))
    except GitHubError as exc:
        if exc.status!=404:raise
        release=api.request('POST',base+'/releases',{'tag_name':tag,'target_commitish':commit,
            'name':f"{cfg['display_name']} / {cfg.get('english_name',cfg['family'])} {version} · 시험판",'body':body,'draft':True,'prerelease':True,'make_latest':'false'})
    existing={a['name']:a for a in release.get('assets',[])}
    uploaded=[]
    files=[apk,checksum]
    if cfg.get('license_file'):files.append(font/cfg['license_file'])
    for file in files:
        content=file.read_bytes();sha=hashlib.sha256(content).hexdigest()
        if file.name in existing:
            asset=existing[file.name]
            if asset.get('size')!=len(content) or asset.get('digest')!='sha256:'+sha:
                raise ValueError('Existing release asset differs; refusing to replace '+file.name)
        else:
            upload=release['upload_url'].split('{')[0]+'?'+urllib.parse.urlencode({'name':file.name})
            mime='application/vnd.android.package-archive' if file.suffix=='.apk' else 'text/plain'
            asset=api.request('POST',upload,raw=content,content_type=mime)
        if asset['state']!='uploaded' or asset['size']!=len(content):raise ValueError('Incomplete asset upload')
        if asset.get('digest') and asset['digest']!='sha256:'+sha:raise ValueError('Server asset checksum mismatch')
        uploaded.append({'name':file.name,'bytes':asset['size'],'sha256':sha,'url':asset['browser_download_url']})
    release=api.request('PATCH',base+f'/releases/{release["id"]}',{'draft':False,'prerelease':True,'body':body,'make_latest':'false'})
    # Draft asset URLs use an untagged placeholder. Refresh canonical URLs
    # after publication instead of returning those temporary upload-time links.
    published_assets={asset['name']:asset for asset in release.get('assets',[])}
    for item in uploaded:
        if item['name'] in published_assets:
            item['url']=published_assets[item['name']]['browser_download_url']
    result={'repository':api.repo,'tag':tag,'url':release['html_url'],'commit':commit,'assets':uploaded,'prerelease':True}
    folder=ROOT/'_workspace/publication';folder.mkdir(parents=True,exist_ok=True)
    (folder/'release.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--font',required=True)
    publish(parser.parse_args().font)
