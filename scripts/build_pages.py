"""Build a curated multi-font GitHub Pages artifact using the standard library."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import urllib.parse

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'_site'
REPOSITORY='mant81/font-library'


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('href','src') and value:self.links.append(value)


def build():
    if OUT.resolve()!=ROOT.resolve()/'_site':raise ValueError('Unexpected output location')
    if OUT.exists():
        if not (OUT/'.font-library-generated').is_file():raise ValueError('Refusing to replace unrecognized _site directory')
        shutil.rmtree(OUT)
    OUT.mkdir();(OUT/'.font-library-generated').write_text('generated\n')
    for name in ['index.html','style.css','app.js','favicon.svg','copyright.html','license.html']:shutil.copy2(ROOT/'site'/name,OUT/name)
    (OUT/'.nojekyll').write_text('')
    catalog=[]
    for config in sorted((ROOT/'fonts').glob('*/config/font.json')):
        font=config.parent.parent;cfg=json.loads(config.read_text(encoding='utf-8'));font_id=cfg['id']
        if font_id!=font.name or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',font_id):raise ValueError(font_id)
        dist=font/'dist';target=OUT/'fonts'/font_id/'dist';target.mkdir(parents=True)
        # Publish only webfont assets and usage material; private workspaces,
        # raw handwriting, keys, machine-local reports and SDK build caches stay out.
        for file in dist.rglob('*'):
            if file.is_file() and file.suffix in ('.woff2','.ttf','.css'):
                destination=target/file.relative_to(dist);destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(file,destination)
        for name in ['USAGE.md','review.html','LICENSE.txt']:
            if (dist/name).exists():shutil.copy2(dist/name,target/name)
        shutil.copytree(font/'examples/web',OUT/'fonts'/font_id/'examples/web')
        prefix=cfg['file_prefix'];base=f'fonts/{font_id}/dist'
        paths={'woff':f'{base}/{prefix}-Regular.woff2','small_woff':f'{base}/{prefix}Small-Regular.woff2',
               'ttf':f'{base}/{prefix}-Regular.ttf','specimen':f'fonts/{font_id}/examples/web/'}
        if any(not (OUT/path).exists() for path in paths.values()):raise ValueError(f'Missing public assets for {font_id}')
        for key in ['woff','small_woff','ttf']:
            paths[key]+='?v='+urllib.parse.quote(cfg['version'])
        version=cfg['android_version_name'];apk_name=f'{font_id}-font-preview-{version}.apk'
        meta=json.loads((dist/'android/apk-manifest.json').read_text(encoding='utf-8'))
        apk=dist/'android'/apk_name
        if hashlib.sha256(apk.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('APK digest mismatch')
        tag=f'{font_id}-v{version}'
        catalog.append(dict(id=font_id,name=cfg['display_name'],english_name=cfg.get('english_name',cfg['family']),family=cfg['family'],version=cfg['version'],
             apk=f'https://github.com/{REPOSITORY}/releases/download/{tag}/{apk_name}',
             release=f'https://github.com/{REPOSITORY}/releases/tag/{tag}',apk_sha256=meta['sha256'],**paths))
    if not catalog:raise ValueError('No fonts available')
    (OUT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for html in OUT.rglob('*.html'):
        parser=Links();parser.feed(html.read_text(encoding='utf-8'))
        for url in parser.links:
            parsed=urllib.parse.urlparse(url)
            if parsed.scheme or parsed.netloc or not parsed.path:continue
            path=(html.parent/urllib.parse.unquote(parsed.path)).resolve()
            if not path.is_relative_to(OUT.resolve()) or not path.exists():raise ValueError(f'Broken public link: {html.name}: {url}')
    print(f'Pages ready: {len(catalog)} font(s), {len(list(OUT.rglob("*")))} public paths → {OUT}')


if __name__=='__main__':build()
