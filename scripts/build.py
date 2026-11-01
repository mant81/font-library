"""Reproducible source tracing, Hangul composition and webfont build.

Run from any directory: .venv/Scripts/python scripts/build.py
No OCR, generated reference images or third-party font outlines are used.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import shutil
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools import subset
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

from project import ROOT, REPO_ROOT, FONT_ID
CFG = json.loads((ROOT / 'config/font.json').read_text(encoding='utf-8'))
OVERRIDES = json.loads((ROOT / 'config/overrides.json').read_text(encoding='utf-8'))
L = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
V = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
T = ' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'
PAIRS = dict(zip('ㄲㄸㅃㅆㅉ', ['ㄱㄱ', 'ㄷㄷ', 'ㅂㅂ', 'ㅅㅅ', 'ㅈㅈ']))
PAIRS.update(dict(zip('ㄳㄵㄶㄺㄻㄼㄽㄾㄿㅀㅄ', ['ㄱㅅ','ㄴㅈ','ㄴㅎ','ㄹㄱ','ㄹㅁ','ㄹㅂ','ㄹㅅ','ㄹㅌ','ㄹㅍ','ㄹㅎ','ㅂㅅ'])))
COMPOUND_V = {'ㅐ':('ㅏ','ㅣ'), 'ㅒ':('ㅑ','ㅣ'), 'ㅔ':('ㅓ','ㅣ'), 'ㅖ':('ㅕ','ㅣ'),
              'ㅘ':('ㅗ','ㅏ'), 'ㅙ':('ㅗ','ㅐ'), 'ㅚ':('ㅗ','ㅣ'), 'ㅝ':('ㅜ','ㅓ'),
              'ㅞ':('ㅜ','ㅔ'), 'ㅟ':('ㅜ','ㅣ'), 'ㅢ':('ㅡ','ㅣ')}
HORIZONTAL = set('ㅗㅛㅜㅠㅡ')
MIXED = set('ㅘㅙㅚㅝㅞㅟㅢ')
REQUIRED = set(range(0x20, 0x7f)) | set(range(0x3131, 0x3164)) | set(range(0xac00, 0xd7a4))


def dump(path, value):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def regions():
    """Manually mapped source rows; boundaries are original-image pixels."""
    rows = [
        ('ㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣ', [145,305,456,595,750,946,1135,1295,1445,1635], 40,185),
        ('ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ', [115,235,380,525,655,782,900,1046,1189,1335,1475,1600,1730,1858], 370,575),
        ('ABCDEFGHIJKLMNOP', [78,210,337,475,620,750,880,1037,1188,1340,1485,1623,1755,1907,2050,2250], 695,900),
        ('QRSTUVWXYZ', [62,190,315,455,590,731,865,1017,1167,1325], 980,1170),
        ('abcdefghijklmnop', [60,211,350,520,675,825,961,1100,1222,1350,1445,1570,1715,1865,2027,2135], 1450,1640),
        ('qrstuvwxyz', [87,203,353,510,685,825,960,1105,1240,1370], 1680,1840),
    ]
    for chars, centers, top, bottom in rows:
        edges = [max(0, centers[0]-80)] + [(a+b)//2 for a,b in zip(centers, centers[1:])] + [centers[-1]+85]
        for i, char in enumerate(chars):
            yield char, [edges[i], top, edges[i+1], bottom]


def thin(mask):
    """Zhang-Suen thinning, without optional OpenCV contrib dependency."""
    a = np.pad(mask.astype(np.uint8), 1)
    while True:
        removed = 0
        for step in (0, 1):
            p = [a[:-2,1:-1],a[:-2,2:],a[1:-1,2:],a[2:,2:],a[2:,1:-1],a[2:,:-2],a[1:-1,:-2],a[:-2,:-2]]
            n = sum(p)
            transitions = sum(((p[i] == 0) & (p[(i+1)%8] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                cond = (p[0]*p[2]*p[4] == 0) & (p[2]*p[4]*p[6] == 0)
            else:
                cond = (p[0]*p[2]*p[6] == 0) & (p[0]*p[4]*p[6] == 0)
            delete = (a[1:-1,1:-1] == 1) & (n >= 2) & (n <= 6) & (transitions == 1) & cond
            removed += int(delete.sum())
            a[1:-1,1:-1][delete] = 0
        if not removed:
            return a[1:-1,1:-1]


def skeleton_paths(skel):
    pixels = {(int(x),int(y)) for y,x in np.argwhere(skel)}
    neighbors = {p: sorted((p[0]+dx,p[1]+dy) for dx in (-1,0,1) for dy in (-1,0,1)
                           if (dx or dy) and (p[0]+dx,p[1]+dy) in pixels) for p in pixels}
    visited = set()
    paths = []
    for start in sorted(pixels, key=lambda p: (len(neighbors[p]) == 2, p)):
        for nxt in neighbors[start]:
            edge = tuple(sorted((start,nxt)))
            if edge in visited:
                continue
            path = [start, nxt]
            visited.add(edge)
            prev, current = start, nxt
            while len(neighbors[current]) == 2:
                target = next(p for p in neighbors[current] if p != prev)
                edge = tuple(sorted((current,target)))
                if edge in visited:
                    break
                visited.add(edge)
                path.append(target)
                prev, current = current, target
            points = cv2.approxPolyDP(np.array(path,np.float32).reshape(-1,1,2), .65, False).reshape(-1,2)
            paths.append(points.tolist())
    return paths


def extract():
    source = ROOT / CFG['source']
    gray = np.array(Image.open(source).convert('L'))
    data = {}
    manifest = []
    sheet = Image.new('RGB',(1000,math.ceil(76/8)*145),'#f8f5ef')
    draw = ImageDraw.Draw(sheet)
    for i,(char,bbox) in enumerate(regions()):
        x0,y0,x1,y1 = bbox
        crop = gray[y0:y1,x0:x1]
        mask = (crop < 160).astype(np.uint8)
        count,labels,stats,_ = cv2.connectedComponentsWithStats(mask,8)
        largest = max(stats[1:,cv2.CC_STAT_AREA], default=0)
        mask = np.isin(labels,[j for j in range(1,count) if stats[j,cv2.CC_STAT_AREA] >= max(7,largest*.025)]).astype(np.uint8)
        mask = cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        yy,xx = np.where(mask)
        if len(xx) == 0:
            raise ValueError(f'Empty source region: {char}')
        tight = [int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1]
        m = mask[tight[1]:tight[3],tight[0]:tight[2]]
        paths = skeleton_paths(thin(m))
        if not paths:
            raise ValueError(f'No strokes: {char}')
        key = f'u{ord(char):04X}'
        data[char] = {'paths':paths,'size':[m.shape[1],m.shape[0]]}
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-3 -3 {m.shape[1]+6} {m.shape[0]+6}"><g fill="none" stroke="#222" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        svg += ''.join('<polyline points="'+' '.join(f'{x},{y}' for x,y in p)+'"/>' for p in paths)+'</g></svg>'
        out = ROOT / f'sources/glyphs/{key}.svg'
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(svg,encoding='utf-8')
        manifest.append({'glyph_id':key,'codepoint':ord(char),'character':char,'origin':'traced','source_bbox':bbox,
                         'ink_bbox':[x0+tight[0],y0+tight[1],x0+tight[2],y0+tight[3]],'parent_ids':[],
                         'recipe_id':'trace-v1','vector_path':f'sources/glyphs/{key}.svg','review_status':'pending'})
        thumb = Image.fromarray(crop).convert('RGB')
        thumb.thumbnail((110,105))
        sx,sy = (i%8)*125,(i//8)*145
        sheet.paste(thumb,(sx,sy+20))
        draw.text((sx+6,sy+3),key,fill='#222')
    sheet.save(ROOT/'docs/source-contact-sheet.png')
    dump('sources/manifests/traced.json',manifest)
    dump('sources/manifests/centerlines.json',data)
    dump('assets/source/provenance.json',{'file':CFG['source'],'sha256':sha(source),'dimensions':[gray.shape[1],gray.shape[0]],
          'use':'User supplied handwriting reference. Distribution license not yet specified.'})
    return data


def designed():
    """New matching centerlines; deliberately distinct from traced samples."""
    paths = {
        '0': [[(28,3),(12,10),(5,30),(4,70),(13,94),(30,99),(47,87),(53,57),(49,22),(40,6),(28,3)]],
        '1': [[(10,23),(28,3),(29,98)],[(10,99),(47,99)]],
        '2': [[(6,19),(16,5),(36,3),(51,15),(50,33),(36,54),(5,96),(54,96)]],
        '3': [[(5,9),(24,2),(44,8),(51,23),(42,42),(25,48),(44,53),(54,70),(48,88),(30,99),(9,94),(3,85)]],
        '4': [[(43,99),(43,2),(4,67),(56,67)]],
        '5': [[(51,4),(10,4),(7,47),(27,42),(46,49),(53,67),(48,87),(29,98),(9,93),(3,85)]],
        '6': [[(48,7),(32,3),(15,19),(6,43),(5,75),(15,94),(33,98),(49,88),(53,67),(44,51),(27,47),(8,58)]],
        '7': [[(3,4),(54,4),(30,49),(16,98)]],
        '8': [[(29,47),(10,33),(8,17),(20,3),(38,3),(51,17),(48,33),(29,47),(9,60),(4,78),(14,96),(34,99),(51,86),(52,68),(41,55),(29,47)]],
        '9': [[(47,44),(29,52),(12,45),(5,28),(10,10),(26,2),(44,9),(51,27),(50,57),(40,83),(22,99)]],
        '.': [[(25,94),(26,95)]], ',': [[(27,91),(25,104),(19,114)]],
        ':': [[(26,35),(27,36)],[(26,87),(27,88)]], ';': [[(26,35),(27,36)],[(27,87),(25,102),(18,110)]],
        '!': [[(27,2),(26,70)],[(26,94),(27,95)]],
        '?': [[(6,18),(16,4),(36,3),(50,15),(49,31),(31,49),(26,68)],[(26,94),(27,95)]],
        '-': [[(5,51),(48,49)]], '_': [[(2,103),(57,103)]],
        '+': [[(4,51),(53,50)],[(29,24),(28,78)]], '=': [[(5,38),(52,37)],[(5,64),(52,63)]],
        '/': [[(3,99),(54,2)]], '\\': [[(3,2),(54,99)]], '|': [[(28,0),(28,102)]],
        '(': [[(42,1),(26,19),(18,46),(20,77),(39,101)]], ')': [[(14,1),(30,20),(39,48),(35,78),(16,102)]],
        '[': [[(43,0),(17,1),(18,101),(43,102)]], ']': [[(14,0),(40,1),(39,101),(14,102)]],
        '{': [[(45,0),(29,7),(28,38),(15,50),(28,62),(28,93),(44,103)]],
        '}': [[(13,0),(29,7),(30,38),(43,50),(30,62),(30,93),(14,103)]],
        '<': [[(48,20),(8,51),(49,81)]], '>': [[(8,20),(48,51),(8,81)]],
        "'": [[(27,1),(25,22)]], '"': [[(17,1),(15,23)],[(39,1),(37,23)]], '`': [[(18,0),(31,17)]],
        '~': [[(2,55),(14,45),(28,48),(42,56),(56,45)]], '^': [[(3,34),(28,3),(53,33)]],
        '*': [[(27,13),(28,62)],[(5,24),(50,50)],[(6,49),(49,23)]],
        '#': [[(20,11),(13,91)],[(43,11),(36,91)],[(4,38),(55,36)],[(2,65),(53,63)]],
        '%': [[(5,100),(53,0)],[(13,5),(3,14),(4,30),(15,35),(25,26),(23,10),(13,5)],[(43,65),(33,74),(34,90),(45,96),(55,86),(53,70),(43,65)]],
        '$': [[(50,13),(34,4),(14,10),(7,26),(17,43),(42,55),(51,72),(45,90),(25,97),(7,87)],[(29,-5),(29,106)]],
        '&': [[(51,93),(11,37),(9,18),(20,4),(36,8),(41,22),(29,41),(9,62),(5,79),(16,96),(32,96),(47,79),(54,58)]],
        '@': [[(38,64),(38,32),(27,28),(17,38),(16,58),(25,68),(38,58),(44,68),(54,61),(58,39),(51,14),(33,1),(10,8),(0,30),(0,68),(13,93),(35,101),(55,92)]],
    }
    return {char:{'paths':lines,'size':[60,115]} for char,lines in paths.items()}


class Composer:
    def __init__(self, samples, stroke):
        self.samples = samples
        self.stroke = stroke
        self.glyphs = {}
        self.metrics = {}
        self.cache = {}
        self.recipes = {}

    def part(self,char,w,h):
        key = (char,int(w),int(h))
        if key in self.cache:
            return self.cache[key]
        name = f'part{len(self.cache):04d}'
        self.cache[key] = name
        s = self.samples[char]
        stroke = self.stroke
        if char in '.:,;':
            stroke = max(stroke,140)
        if char == '.':
            stroke = 220
        if char == 'ㅣ' and self.stroke >= 70:
            stroke = 128
        elif self.stroke >= 70 and char in "!'`|":
            stroke = 140
        pad = min(stroke//2+4, (w-2)/2, (h-2)/2)
        mask = np.zeros((int(h)+1,int(w)+1),np.uint8)
        sx,sy = (w-2*pad)/max(1,s['size'][0]-1),(h-2*pad)/max(1,s['size'][1]-1)
        for line in s['paths']:
            points = np.array([(round(pad+x*sx),round(pad+y*sy)) for x,y in line],np.int32)
            cv2.polylines(mask,[points],False,255,stroke,cv2.LINE_8)
            for point in (points[0],points[-1]):
                cv2.circle(mask,tuple(point),stroke//2,255,-1)
        contours,_ = cv2.findContours(mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        pen = TTGlyphPen(None)
        for contour in contours:
            points = cv2.approxPolyDP(contour,1.1,True).reshape(-1,2)
            if len(points)<3:
                continue
            # OpenCV winding becomes TrueType-compatible after y inversion.
            pen.moveTo((int(points[0][0]),int(h-points[0][1])))
            for x,y in points[1:]:
                pen.lineTo((int(x),int(h-y)))
            pen.closePath()
        self.glyphs[name] = pen.glyph()
        self.metrics[name] = (int(w)+20,0)
        return name

    def place(self,char,x,y,w,h):
        if char in PAIRS:
            a,b = PAIRS[char]
            gap = 22
            return self.place(a,x,y,(w-gap)/2,h) + self.place(b,x+(w+gap)/2,y,(w-gap)/2,h)
        if char in COMPOUND_V:
            a,b = COMPOUND_V[char]
            if char in MIXED:
                # L-shaped vowel: horizontal under the initial; vertical to right.
                return self.place(a,x,y,w*.65,h*.27) + self.place(b,x+w*.69,y+h*.02,w*.31,h*.98)
            return self.place(a,x,y,w*.59,h) + self.place(b,x+w*.70,y,w*.30,h)
        if char == 'ㅡ':
            ink_h = min(h, self.stroke+14)
            y += (h-ink_h)/2
            h = ink_h
        elif char == 'ㅣ':
            ink_w = min(w, self.stroke+(80 if self.stroke >= 70 else 14))
            x += (w-ink_w)/2
            w = ink_w
        return [(self.part(char,round(w),round(h)),round(x),round(y))]

    def add(self,name,components,advance=1000,recipe=None):
        pen = TTGlyphPen(self.glyphs)
        for part,x,y in components:
            pen.addComponent(part,(1,0,0,1,x,y))
        self.glyphs[name] = pen.glyph()
        self.metrics[name] = (advance,0)
        cp = int(name[3:],16)
        char = chr(cp)
        if recipe is None:
            recipe = {'origin':'traced' if char.isalpha() else 'designed','characters':[char],
                      'recipe_id':'latin-placement-v1' if char.isalpha() else 'space-v1'}
        def parents(c):
            if c==' ': return []
            if c in PAIRS: return [p for ch in PAIRS[c] for p in parents(ch)]
            if c in COMPOUND_V: return [p for ch in COMPOUND_V[c] for p in parents(ch)]
            return [f'u{ord(c):04X}']
        parent_ids = recipe.get('reference_ids', sorted({p for c in recipe['characters'] for p in parents(c)}))
        self.recipes[name] = dict(recipe,glyph_id=name,codepoint=cp,character=char,source_bbox=None,
                                 parent_ids=parent_ids,vector_path=None,review_status='pending',components=components)

    def syllable(self,l,v,t):
        # Ink inside 70..930 horizontally, 65..850 vertically.
        bottom = 315 if t != ' ' else 65
        upper_h = 850-bottom
        if v in HORIZONTAL:
            parts = self.place(l,170,bottom+upper_h*.40,660,upper_h*.60)
            parts += self.place(v,85,bottom,830,upper_h*.29)
        elif v in MIXED:
            a,b = COMPOUND_V[v]
            parts = self.place(l,85,bottom+upper_h*.34,480,upper_h*.66)
            parts += self.place(a,70,bottom,570,upper_h*.25)
            parts += self.place(b,655,bottom,275,upper_h)
        else:
            parts = self.place(l,75,bottom+upper_h*.05,480,upper_h*.90)
            parts += self.place(v,640,bottom,290,upper_h)
        if t != ' ':
            parts += self.place(t,190,50,620,210)
        return parts

    def build(self,family,path):
        cmap = {}
        for cp in sorted(REQUIRED):
            char = chr(cp)
            name = f'uni{cp:04X}'
            cmap[cp] = name
            if cp == 32:
                self.add(name,[],350)
            elif cp >= 0xac00:
                index = cp-0xac00
                l,v,t = L[index//588],V[(index//28)%21],T[index%28]
                if char in OVERRIDES:
                    override=OVERRIDES[char]
                    if not override.get('reason'):
                        raise ValueError(f'Override requires reason: {char}')
                    components=[]
                    for p in override['parts']:
                        components+=self.place(p['char'],p['x'],p['y'],p['width'],p['height'])
                    self.add(name,components,recipe={'origin':'derived','characters':[p['char'] for p in override['parts']],
                             'recipe_id':'manual-layout-override','reason':override['reason']})
                else:
                    self.add(name,self.syllable(l,v,t),recipe={'origin':'derived','characters':[l,v,t], 'recipe_id':'hangul-v1'})
            elif cp >= 0x3131:
                self.add(name,self.place(char,110,80,780,740),recipe={'origin':'derived','characters':[char],'recipe_id':'jamo-v1'})
            else:
                if char in self.samples and char.isalpha():
                    s = self.samples[char]
                    if char.isupper():
                        height,y = 710,80
                    elif char in 'bdfhklt':
                        height,y = 690,80
                    elif char in 'gjpqy':
                        height,y = 640,-80
                    elif char in 'ij':
                        height,y = 680,80
                    else:
                        height,y = 500,80
                    width = min(830,max(170,round(height*s['size'][0]/s['size'][1])))
                    parts = self.place(char,55,y,width,height)
                    self.add(name,parts,width+110)
                else:
                    width = 530
                    if char in '.:,;!\'`|':
                        width = 230
                    self.add(name,self.place(char,45,-10,width,800),width+90,
                             recipe={'origin':'designed','characters':[char],'reference_ids':['u004F','u006F','u0049'],'recipe_id':'matching-marks-v1'})
        pen = TTGlyphPen(None)
        pen.moveTo((100,50)); pen.lineTo((100,800)); pen.lineTo((700,800)); pen.lineTo((700,50)); pen.closePath()
        pen.moveTo((150,100)); pen.lineTo((650,100)); pen.lineTo((650,750)); pen.lineTo((150,750)); pen.closePath()
        self.glyphs['.notdef'] = pen.glyph(); self.metrics['.notdef'] = (800,0)
        order = ['.notdef'] + [n for n in self.glyphs if n != '.notdef']
        # Match hmtx bearings to actual ink bounds to avoid renderer shifts.
        for name,glyph in self.glyphs.items():
            glyph.recalcBounds(self.glyphs)
            self.metrics[name] = (self.metrics[name][0],getattr(glyph,'xMin',0))
        fb = FontBuilder(1000,isTTF=True)
        fb.setupGlyphOrder(order); fb.setupCharacterMap(cmap); fb.setupGlyf(self.glyphs)
        fb.setupHorizontalMetrics(self.metrics)
        fb.setupHorizontalHeader(ascent=950,descent=-250,lineGap=0)
        fb.setupNameTable({'familyName':family,'styleName':'Regular','uniqueFontIdentifier':f'{family} {CFG["version"]}',
                          'fullName':f'{family} Regular','psName':family.replace(' ','')+'-Regular',
                          'version':f'Version {float(CFG["font_revision"]):.3f}','description':CFG.get('source_statement','Font built from supplied handwriting.')+' Visual style review pending.',
                          'licenseDescription':'Commercial use, modification and redistribution permissions are not yet specified. No third-party font outlines used.'})
        localized=CFG['display_name']+(' Small' if family.endswith(' Small') else '')
        fb.font['name'].setName(localized,1,3,1,0x412)
        fb.font['name'].setName(localized+' Regular',4,3,1,0x412)
        fb.setupOS2(version=4,sTypoAscender=950,sTypoDescender=-250,sTypoLineGap=0,usWinAscent=950,usWinDescent=250,
                    usWeightClass=400,fsType=0,fsSelection=0xC0,sxHeight=500,sCapHeight=710)
        fb.setupPost(); fb.setupMaxp()
        fb.font['head'].created = fb.font['head'].modified = CFG['timestamp']
        fb.font['head'].fontRevision = float(CFG['font_revision'])
        fb.font.recalcTimestamp = False
        gasp = newTable('gasp'); gasp.gaspRange = {65535:15}; fb.font['gasp'] = gasp
        fb.save(path)
        return cmap


def woff(source,target,unicodes=None):
    font = TTFont(source,recalcTimestamp=False)
    if unicodes is not None:
        options = subset.Options(); options.recalc_timestamp = False
        sub = subset.Subsetter(options=options); sub.populate(unicodes=unicodes); sub.subset(font)
    font.flavor='woff2'; font.save(target)


def package(style):
    family = CFG['family'] + (' Small' if style == 'small' else '')
    stem = CFG['file_prefix'] + ('Small' if style == 'small' else '') + '-Regular'
    path = ROOT/f'dist/{stem}.ttf'
    samples = json.loads((ROOT/'sources/manifests/centerlines.json').read_text(encoding='utf-8')) | designed()
    composer = Composer(samples,CFG['small_stroke'] if style == 'small' else CFG['stroke'])
    composer.build(family,path)
    print(f'Built {path.name}: {len(composer.glyphs)} glyphs',flush=True)
    # Auto-hint Latin outlines; Hangul retains the constant-width optical layout.
    from ttfautohint import ttfautohint
    hinted = ttfautohint(in_buffer=path.read_bytes(), hinting_range_min=7, hinting_range_max=48,
                        hinting_limit=48, no_info=True, default_script='latn', fallback_script='none')
    path.write_bytes(hinted)
    font = TTFont(path,recalcTimestamp=False)
    font['head'].created=font['head'].modified=CFG['timestamp']; font.save(path)
    woff(path,ROOT/f'dist/{stem}.woff2')
    face = lambda filename,ur='': f"@font-face{{font-family:'{family}';src:url('./{filename}') format('woff2');font-weight:400;font-style:normal;font-display:swap;{ur}}}\n"
    (ROOT/f'dist/{CFG["id"]}{("-small" if style == "small" else "")}.css').write_text(face(stem+'.woff2'),encoding='utf-8')
    css = []
    ranges = [(0x20,0x7e),(0x3131,0x3163)] + [(start,min(start+511,0xd7a3)) for start in range(0xac00,0xd7a4,512)]
    for i,(start,end) in enumerate(ranges):
        filename = f'{stem}.{i:02}.woff2'
        woff(path,ROOT/f'dist/subsets/{filename}',range(start,end+1))
        css.append(face('subsets/'+filename,f'unicode-range:U+{start:X}-{end:X};'))
    (ROOT/f'dist/{CFG["id"]}{("-small" if style == "small" else "")}-subset.css').write_text(''.join(css),encoding='utf-8')
    if style == 'regular':
        dump('sources/manifests/recipes.json',composer.recipes)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,help='Copy provided original image into project')
    parser.add_argument('--extract-only',action='store_true')
    parser.add_argument('--reextract',action='store_true',help='Regenerate centerlines and SVG diagnostics from the source')
    args=parser.parse_args()
    for d in ['assets/source','dist/subsets','sources/manifests','docs']:
        (ROOT/d).mkdir(parents=True,exist_ok=True)
    if args.source:
        target = ROOT/CFG['source']
        if args.source.resolve()!=target.resolve():
            shutil.copy2(args.source,target)
    if not (ROOT/CFG['source']).exists():
        parser.error('Source missing. Use --source ORIGINAL_IMAGE')
    centerlines=ROOT/'sources/manifests/centerlines.json'
    if args.source or args.reextract or args.extract_only or not centerlines.exists():
        extract()
        print('Traced 76 source characters',flush=True)
    else:
        provenance=json.loads((ROOT/'assets/source/provenance.json').read_text(encoding='utf-8'))
        if provenance['sha256']!=sha(ROOT/CFG['source']):
            parser.error('Source image changed. Use --reextract to regenerate the source mappings.')
        print('Using persisted centerlines; no reviewed source edits overwritten.',flush=True)
    if args.extract_only:
        return
    for style in ['regular','small']:
        package(style)
    dump('dist/characters.json',[f'U+{cp:04X}' for cp in sorted(REQUIRED)])
    dump('dist/build-manifest.json',{
        'version':CFG['version'],'status':CFG['review_status'],'source_sha256':sha(ROOT/CFG['source']),
        'config_sha256':sha(ROOT/'config/font.json'),'script_sha256':sha(__file__),
        'overrides_sha256':sha(ROOT/'config/overrides.json'),'centerlines_sha256':sha(centerlines),
        'python':sys.version.split()[0], 'tools':{m:importlib.metadata.version(m) for m in ['fonttools','pillow','numpy','opencv-python-headless','brotli','ttfautohint-py']},
        'codepoint_count':len(REQUIRED),'outputs':{p.relative_to(ROOT/'dist').as_posix():{'sha256':sha(p),'bytes':p.stat().st_size}
         for p in sorted((ROOT/'dist').rglob('*')) if p.is_file() and p.name!='build-manifest.json'
         and p.relative_to(ROOT/'dist').parts[0]!='android'},
        'validation':'docs/validation.json','minimum_css_px':7,
        'note':'7px rendering requires browser validation. Pixel appearance and character recognition are distinct; no visual approval claimed.'})
    print('Webfont packages complete.',flush=True)


if __name__=='__main__':
    main()
