"""Font structure, subset coverage, source provenance and render sheets."""
import json
import math
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen

sys.path.insert(0,str(Path(__file__).resolve().parent))
from build import ROOT, REQUIRED, L, V, T, CFG, sha, dump
from project import REPO_ROOT


def validate():
    results = []
    original_hash = json.loads((ROOT/'assets/source/provenance.json').read_text(encoding='utf-8'))['sha256']
    assert sha(ROOT/'assets/source/minbo-handwriting.jpg') == original_hash
    manifest=json.loads((ROOT/'dist/build-manifest.json').read_text(encoding='utf-8'))
    assert manifest['source_sha256']==original_hash
    assert manifest['config_sha256']==sha(ROOT/'config/font.json')
    assert manifest['script_sha256']==sha(REPO_ROOT/'scripts/build.py')
    assert manifest['overrides_sha256']==sha(ROOT/'config/overrides.json')
    assert manifest['centerlines_sha256']==sha(ROOT/'sources/manifests/centerlines.json')
    traced=json.loads((ROOT/'sources/manifests/traced.json').read_text(encoding='utf-8'))
    recipes=json.loads((ROOT/'sources/manifests/recipes.json').read_text(encoding='utf-8'))
    traced_ids={entry['glyph_id'] for entry in traced}
    assert len(traced_ids)==76
    assert {entry['codepoint'] for entry in recipes.values()}==REQUIRED
    for entry in recipes.values():
        assert all(parent in traced_ids for parent in entry['parent_ids']),entry['glyph_id']
    for filename,info in manifest['outputs'].items():
        assert sha(ROOT/'dist'/filename)==info['sha256'],filename
    for prefix in [CFG['file_prefix'],CFG['file_prefix']+'Small']:
        stem=prefix+'-Regular'
        font=TTFont(ROOT/f'dist/{stem}.ttf')
        master=font.getBestCmap()
        assert set(master)==REQUIRED, 'Master coverage'
        web=TTFont(ROOT/f'dist/{stem}.woff2')
        assert web.getBestCmap()==master,'WOFF2 cmap mismatch'
        # Compare decomposed outlines after conversion, not merely cmap names.
        a,b=font.getGlyphSet(),web.getGlyphSet()
        empty=[]; out_of_bounds=[]; max_points=0
        for cp,name in master.items():
            pa,pb=DecomposingRecordingPen(a),DecomposingRecordingPen(b)
            a[name].draw(pa); b[name].draw(pb)
            assert pa.value==pb.value, f'Outline mismatch U+{cp:04X}'
            if not pa.value and cp!=32:
                empty.append(cp)
            glyph=font['glyf'][name]
            if getattr(glyph,'yMax',0)>950 or getattr(glyph,'yMin',0)<-250:
                out_of_bounds.append(cp)
            max_points=max(max_points,len(pa.value))
        assert not empty,empty
        assert not out_of_bounds,out_of_bounds
        coverage=set(); duplicates=set()
        files=sorted((ROOT/'dist/subsets').glob(stem+'.*.woff2'))
        assert len(files)==24,len(files)
        for file in files:
            sub=TTFont(file)
            chars=set(sub.getBestCmap())
            duplicates |= coverage & chars
            coverage |= chars
        assert coverage==REQUIRED and not duplicates,'Subset coverage'
        css=(ROOT/f'dist/{CFG["id"]}{("-small" if "Small" in prefix else "")}-subset.css').read_text(encoding='utf-8')
        family=CFG['family']+(' Small' if 'Small' in prefix else '')
        names=[n.toUnicode() for n in font['name'].names]
        assert family in names,'Font name mismatch'
        assert font['name'].getName(1,3,1,0x412).toUnicode().startswith(CFG['display_name'])
        import re
        declarations=re.findall(r"url\('\./([^']+)'\).*?unicode-range:U\+([0-9A-F]+)-([0-9A-F]+)",css)
        assert len(declarations)==24
        for filename,start,end in declarations:
            actual=set(TTFont(ROOT/'dist'/filename).getBestCmap())
            assert actual==set(range(int(start,16),int(end,16)+1)),'CSS unicode-range mismatch'
        results.append({'font':stem,'codepoints':len(master),'empty_nonspace':len(empty),
                        'vertical_overflow':len(out_of_bounds),'subset_count':len(files),
                        'woff2_outline_match':True,'subset_union_match':True,'css_ranges_match':True,
                        'ttf_bytes':(ROOT/f'dist/{stem}.ttf').stat().st_size,
                        'woff2_bytes':(ROOT/f'dist/{stem}.woff2').stat().st_size,
                        'subset_total_bytes':sum(f.stat().st_size for f in files)})
    review=ROOT/'docs/review'
    review.mkdir(parents=True,exist_ok=True)
    # Every syllable gets a numbered, printable contact sheet; status remains pending.
    ttf=ROOT/f'dist/{CFG["file_prefix"]}-Regular.ttf'
    face=ImageFont.truetype(str(ttf),30)
    review_entries=[]
    for start in range(0xac00,0xd7a4,400):
        chars=list(range(start,min(start+400,0xd7a4)))
        sheet=Image.new('RGB',(1100,90+math.ceil(len(chars)/20)*57),'white')
        d=ImageDraw.Draw(sheet)
        d.text((20,15),f'{CFG["family"]} {CFG["version"]} | U+{start:04X} - U+{chars[-1]:04X} | REVIEW PENDING',fill='#283c31')
        for i,cp in enumerate(chars):
            x,y=20+(i%20)*54,65+(i//20)*57
            d.text((x,y),chr(cp),font=face,fill='#20251f',anchor='lt')
            d.text((x,y+34),f'{cp:04X}',fill='#777777')
        name=f'{start:04X}-{chars[-1]:04X}.png'
        sheet.save(review/name)
        review_entries.append({'start':start,'end':chars[-1],'sheet':f'docs/review/{name}','status':'pending'})
    dump('docs/review-status.json',review_entries)
    # PIL/FreeType overview supplements actual browser checks; never label it browser evidence.
    sheet=Image.new('RGB',(1300,700),'white'); d=ImageDraw.Draw(sheet)
    y=20
    sample='안녕하세요 minbo체 한글과 영문 꽃 빛 삶 꿈 읽다 괜찮아 | Hello Minbo! 0123456789'
    for size in [7,9,12,16,24,40]:
        d.text((20,y),f'{size}px',fill='#586c5e'); y+=25
        font=ImageFont.truetype(str(ROOT/f'dist/{CFG["file_prefix"]}Small-Regular.ttf' if size<=15 else ttf),size)
        d.text((20,y),sample,font=font,fill='black'); y+=max(45,size*2)
    sheet.save(ROOT/'docs/render-freetype.png')
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>minbo체 전체 검토</title>
<link rel="stylesheet" href="minbo.css"><link rel="stylesheet" href="minbo-small.css">
<style>body{margin:30px;background:#faf8f1;color:#20251f;font:14px system-ui}nav{position:sticky;top:0;background:#faf8f1;padding:15px;border-bottom:1px solid #ccc}.glyphs{font:30px/1.8 'Minbo';display:grid;grid-template-columns:repeat(auto-fill,52px)}.glyphs span{padding:3px}.glyphs small{display:block;font:9px system-ui;color:#777}h2{font:16px system-ui}</style>
<nav><a href="../examples/web/">← 미리보기</a> · 전체 11,172자 · 검토 대기 <label> 크기 <select id="size"><option>30</option><option>7</option><option>12</option><option>48</option></select>px</label></nav><p>자동 생성 검토표입니다. 생성은 시각 검토 통과를 의미하지 않습니다.</p>'''
    for entry in review_entries:
        html+=f'<h2>U+{entry["start"]:04X}–U+{entry["end"]:04X}</h2><div class="glyphs">'
        html+=''.join(f'<span title="U+{cp:04X}">{chr(cp)}<small>{cp:04X}</small></span>' for cp in range(entry['start'],entry['end']+1))+'</div>'
    html+='''<script>document.querySelector('#size').onchange=e=>document.querySelectorAll('.glyphs').forEach(el=>{el.style.fontSize=e.target.value+'px';el.style.fontFamily=+e.target.value<=15?'Minbo Small':'Minbo'})</script></html>'''
    # The generated review belongs to the selected font, just like its CSS.
    html=html.replace('Minbo Small','__FONT_SMALL__').replace('Minbo','__FONT_FAMILY__')
    html=html.replace('__FONT_SMALL__',CFG['family']+' Small').replace('__FONT_FAMILY__',CFG['family'])
    html=html.replace('minbo-small.css',CFG['id']+'-small.css').replace('minbo.css',CFG['id']+'.css')
    (ROOT/'dist/review.html').write_text(html,encoding='utf-8')
    report={'status':'automated-structure-pass','fonts':results,'source_hash_match':True,'provenance_parent_links_valid':True,
            'manual_review':'pending','browser_validation':'see browser-validation.json',
            'seven_px_legibility':'pending visual review; nonempty pixel checks do not prove readability',
            'android_device_validation':'not run','safari_firefox':'not run'}
    dump('docs/validation.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    validate()
