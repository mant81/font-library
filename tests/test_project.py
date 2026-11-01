import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from project import font_root


class FontWorkspaceTests(unittest.TestCase):
    def test_two_fonts_resolve_to_separate_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Path(directory)
            for name in ['first','second-font']:
                config=repo/'fonts'/name/'config/font.json'
                config.parent.mkdir(parents=True)
                config.write_text(json.dumps({'id':name}),encoding='utf-8')
            first=font_root('first',repo)
            second=font_root('second-font',repo)
            (first/'marker.txt').write_text('first',encoding='utf-8')
            self.assertNotEqual(first,second)
            self.assertFalse((second/'marker.txt').exists())

    def test_invalid_unknown_or_mismatched_font_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Path(directory)
            for bad in ['../minbo','MINBO','x/y','x--y','missing']:
                with self.assertRaises(ValueError):font_root(bad,repo)
            config=repo/'fonts/one/config/font.json'
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({'id':'two'}),encoding='utf-8')
            with self.assertRaises(ValueError):font_root('one',repo)


if __name__=='__main__':unittest.main()
