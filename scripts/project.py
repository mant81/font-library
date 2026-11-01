"""Select a font workspace while keeping shared tools at the repository root."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

REPO_ROOT=Path(__file__).resolve().parents[1]


def font_root(font_id, repository=REPO_ROOT):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',font_id):
        raise ValueError('font-id must contain lowercase letters, digits and single hyphens')
    library=(repository/'fonts').resolve()
    target=(library/font_id).resolve()
    if not target.is_relative_to(library):
        raise ValueError('Font path must stay inside fonts/')
    config=target/'config/font.json'
    if not config.is_file():
        raise ValueError(f'Unknown font: {font_id} (missing {config})')
    if json.loads(config.read_text(encoding='utf-8')).get('id')!=font_id:
        raise ValueError(f'Font folder/config id mismatch: {font_id}')
    return target


# Consume only our selector; each tool keeps its own remaining arguments.
_selector=argparse.ArgumentParser(add_help=False)
_selector.add_argument('--font',default=os.environ.get('FONT_LIBRARY_FONT','minbo'))
_selection,_rest=_selector.parse_known_args()
try:
    ROOT=font_root(_selection.font)
except ValueError as exc:
    raise SystemExit(str(exc)) from exc
FONT_ID=_selection.font
os.environ['FONT_LIBRARY_FONT']=FONT_ID
sys.argv[1:]=_rest
