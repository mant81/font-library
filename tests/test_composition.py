import unittest
import sys
import unicodedata
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build import L,V,T,REQUIRED,PAIRS,COMPOUND_V,regions


class CompositionTests(unittest.TestCase):
    def test_unicode_roundtrip_all_modern_hangul(self):
        points=[]
        for li,l in enumerate(L):
            for vi,v in enumerate(V):
                for ti,t in enumerate(T):
                    cp=0xac00+(li*21+vi)*28+ti
                    canonical=chr(0x1100+li)+chr(0x1161+vi)+(chr(0x11a7+ti) if ti else '')
                    self.assertEqual(chr(cp),unicodedata.normalize('NFC',canonical))
                    n=cp-0xac00
                    self.assertEqual((l,v,t),(L[n//588],V[n//28%21],T[n%28]))
                    points.append(cp)
        self.assertEqual(points,list(range(0xac00,0xd7a4)))
        self.assertEqual('힣',chr(points[-1]))

    def test_source_map_and_derived_parts_are_complete(self):
        direct={c for c,_ in regions()}
        self.assertEqual(len(direct),76)
        def resolve(c):
            if c==' ': return
            if c in direct: return
            if c in PAIRS:
                for p in PAIRS[c]: resolve(p)
            elif c in COMPOUND_V:
                for p in COMPOUND_V[c]: resolve(p)
            else: self.fail(f'Missing component {c}')
        for c in L+V+T: resolve(c)

    def test_boundary_syllables_and_complex_finals(self):
        for c,expected in {'가':('ㄱ','ㅏ',' '),'각':('ㄱ','ㅏ','ㄱ'),'값':('ㄱ','ㅏ','ㅄ'),
                           '읽':('ㅇ','ㅣ','ㄺ'),'꿰':('ㄲ','ㅞ',' '),'힣':('ㅎ','ㅣ','ㅎ')}.items():
            n=ord(c)-0xac00
            self.assertEqual((L[n//588],V[n//28%21],T[n%28]),expected)
        self.assertEqual(len(REQUIRED),11318)


if __name__=='__main__': unittest.main()
