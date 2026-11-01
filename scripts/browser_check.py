"""Actual Edge loading and 7 CSS px raster checks, at DPR 1 and 2."""
import base64
import functools
import http.server
import json
from pathlib import Path
import threading
import sys
from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0,str(Path(__file__).resolve().parent))
from build import ROOT,REQUIRED,CFG,dump
from project import REPO_ROOT, FONT_ID


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass


RASTER = r'''async ({cps, family, dpr, offset}) => {
  await document.fonts.load(`7px '${family}'`,String.fromCodePoint(...cps));
  const tile=18*dpr, columns=48, rows=Math.ceil(cps.length/columns);
  const atlas=document.createElement('canvas');atlas.width=columns*tile;atlas.height=rows*tile;
  const out=atlas.getContext('2d');
  const canvas=document.createElement('canvas');canvas.width=tile;canvas.height=tile;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  ctx.font=`${7*dpr}px '${family}'`;ctx.fillStyle='#000';ctx.textBaseline='alphabetic';
  let blank=[],lowContrast=[],clipped=[],minPeak=255,inkPixels=0;
  const shapes=new Map(),exact=new Map();
  for(let i=0;i<cps.length;i++){
    const cp=cps[i];ctx.clearRect(0,0,tile,tile);
    ctx.fillText(String.fromCodePoint(cp),(3+offset)*dpr,12*dpr);
    const data=ctx.getImageData(0,0,tile,tile).data;
    let count=0,peak=0,edge=false,key='',rgba='';
    for(let p=0;p<tile*tile;p++){
      const alpha=data[p*4+3];peak=Math.max(peak,alpha);rgba+=String.fromCharCode(alpha);
      if(alpha>=96)key+=p+',';
      if(alpha>16){count++;const x=p%tile,y=Math.floor(p/tile);if(x===0||y===0||x===tile-1||y===tile-1)edge=true;}
    }
    if(!count)blank.push(cp);if(peak<96)lowContrast.push(cp);if(edge)clipped.push(cp);
    minPeak=Math.min(minPeak,peak);inkPixels+=count;
    for(const [map,k] of [[shapes,key],[exact,rgba]]){if(!map.has(k))map.set(k,[]);map.get(k).push(cp);}
    out.drawImage(canvas,(i%columns)*tile,Math.floor(i/columns)*tile);
  }
  const groups=[...shapes.values()].filter(a=>a.length>1);
  const exactGroups=[...exact.values()].filter(a=>a.length>1);
  return {family,dpr,offset_css_px:offset,css_px:7,glyphs:cps.length,blank,low_contrast:lowContrast,clipped,min_peak_alpha:minPeak,
    threshold_ambiguity_groups:groups.length,threshold_ambiguity_examples:groups.slice(0,12),
    exact_duplicate_groups:exactGroups.length,exact_duplicate_examples:exactGroups.slice(0,12),
    atlas:atlas.toDataURL('image/png')};
}'''


def check():
    handler=functools.partial(QuietHandler,directory=str(REPO_ROOT))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    folder=ROOT/'docs/browser';folder.mkdir(parents=True,exist_ok=True)
    results=[];errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
            version=browser.version
            for dpr in [1,2]:
                context=browser.new_context(viewport={'width':1440,'height':1080},device_scale_factor=dpr)
                page=context.new_page()
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('response',lambda r:errors.append(f'HTTP {r.status} {r.url}') if r.status>=400 else None)
                page.goto(f'http://127.0.0.1:{server.server_port}/{ROOT.relative_to(REPO_ROOT).as_posix()}/examples/web/',wait_until='networkidle')
                page.wait_for_function("document.querySelector('#font-state').textContent.includes('로딩 완료')")
                page.screenshot(path=str(folder/f'demo-dpr{dpr}.png'),full_page=True)
                page.click('[data-size="7"]')
                assert page.locator('#editor').evaluate('(el)=>getComputedStyle(el).fontSize')=='7px'
                assert 'Small' in page.locator('#editor').evaluate('(el)=>getComputedStyle(el).fontFamily')
                page.screenshot(path=str(folder/f'demo-7px-dpr{dpr}.png'),full_page=True)
                for family,stem,offset in [(CFG['family'],'regular',0),(CFG['family']+' Small','small',0),(CFG['family']+' Small','small',.5)]:
                    suffix='-half' if offset else ''
                    report=page.evaluate(RASTER,{'cps':sorted(REQUIRED-{32}),'family':family,'dpr':dpr,'offset':offset})
                    data=report.pop('atlas').split(',',1)[1]
                    atlas_path=folder/f'all-7px-{stem}-dpr{dpr}{suffix}.png'
                    atlas_path.write_bytes(base64.b64decode(data))
                    atlas=Image.open(atlas_path).convert('RGBA')
                    white=Image.new('RGBA',atlas.size,'white');white.alpha_composite(atlas)
                    white.convert('RGB').save(atlas_path)
                    crop=white.crop((0,0,min(864*dpr,white.width),min(180*dpr,white.height)))
                    crop.resize((crop.width*5,crop.height*5),Image.Resampling.NEAREST).convert('RGB').save(folder/f'7px-{stem}-dpr{dpr}{suffix}-enlarged.png')
                    report['atlas']=atlas_path.relative_to(ROOT).as_posix()
                    results.append(report)
                    print(f'{stem} DPR {dpr} offset {offset}: blank={len(report["blank"])} clipped={len(report["clipped"])} low-contrast={len(report["low_contrast"])} exact duplicate groups={report["exact_duplicate_groups"]}',flush=True)
                context.close()
            mobile=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
            page=mobile.new_page()
            page.goto(f'http://127.0.0.1:{server.server_port}/{ROOT.relative_to(REPO_ROOT).as_posix()}/examples/web/',wait_until='networkidle')
            page.wait_for_function("document.querySelector('#font-state').textContent.includes('로딩 완료')")
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile horizontal overflow'
            page.screenshot(path=str(folder/'demo-mobile.png'),full_page=True)
            mobile.close()
            browser.close()
    finally:
        server.shutdown()
    # The Small optical variant is the supported face at 7px. Regular is a control.
    supported=[r for r in results if r['family']==CFG['family']+' Small']
    passed=not errors and len(supported)==4 and all(not r['blank'] and not r['clipped'] and not r['low_contrast'] for r in supported)
    report={'browser':'Microsoft Edge','version':version,'os':'Windows','status':'raster-check-pass' if passed else 'raster-check-fail',
            'checks':'Small face: all required nonspace glyphs at 7 CSS px, DPR 1 and 2, integer and half-pixel positions; no blank, clipped or low-contrast glyphs. Regular results are comparison controls.',
            'results':results,'errors':errors,'legibility_review':'pending; raster presence alone does not establish distinguishable or readable characters',
            'safari_firefox':'not run'}
    dump('docs/browser-validation.json',report)
    if not passed:
        raise SystemExit('Browser raster checks failed; see browser-validation.json')


if __name__=='__main__':check()
