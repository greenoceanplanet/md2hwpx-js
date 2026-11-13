"""Tests for insert mode, STYLE_MAP, and Korean report-draft preprocessing."""

import os
import re
import zipfile

import pytest

from md2hwpx.config import ConversionConfig
from md2hwpx.marko_adapter import MarkoToPandocAdapter
from md2hwpx.MarkdownToHwpx import MarkdownToHwpx
from md2hwpx.insert import insert_markdown, InsertError


def _texts(ast_blocks):
    out = []
    for b in ast_blocks:
        if b.get('t') in ('Para', 'Plain', 'Header'):
            inl = b['c'][2] if b['t'] == 'Header' else b['c']
            out.append(''.join(i.get('c', '') if i.get('t') == 'Str' else ' ' for i in inl if i.get('t') in ('Str', 'Space')))
    return out


# --- preprocessing -------------------------------------------------------------

def test_single_tilde_is_literal_by_default():
    ast = MarkoToPandocAdapter().parse('범위는 60~80%이고 2.8~6.3조임\n')
    assert _texts(ast['blocks']) == ['범위는 60~80%이고 2.8~6.3조임']


def test_double_tilde_still_strikes():
    ast = MarkoToPandocAdapter().parse('~~삭제~~ 유지\n')
    kinds = [i['t'] for i in ast['blocks'][0]['c']]
    assert 'Strikeout' in kinds


def test_strip_heading_numbers():
    cfg = ConversionConfig()
    cfg.STRIP_HEADING_NUMBERS = True
    ast = MarkoToPandocAdapter(config=cfg).parse('## 가. 조건\n\n### (1) 수지\n\n## 2026년 계획\n')
    assert _texts(ast['blocks']) == ['조건', '수지', '2026년 계획']


def test_korean_caption_lines():
    cfg = ConversionConfig()
    cfg.KOREAN_CAPTION_LINES = True
    md = ('<표 1> 주요 가정\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n'
          '![](x.png)\n\n<그림 1> 누적수지\n')
    ast = MarkoToPandocAdapter(config=cfg).parse(md)
    tbl = [b for b in ast['blocks'] if b['t'] == 'Table'][0]
    cap = tbl['c'][1][1][0]['c']
    assert ''.join(i.get('c', ' ') for i in cap) == '주요 가정'
    img = [i for b in ast['blocks'] if b['t'] == 'Para' for i in b['c'] if i['t'] == 'Image'][0]
    assert ''.join(i.get('c', ' ') for i in img['c'][1]) == '누적수지'
    assert not any('<그림' in t or '<표' in t for t in _texts(ast['blocks']))


def test_source_note_prefixes():
    cfg = ConversionConfig()
    cfg.SOURCE_NOTE_PREFIXES = ('자료',)
    ast = MarkoToPandocAdapter(config=cfg).parse('자료 : 국토부\n\n자료가 많음\n')
    assert ast['blocks'][0].get('sourceNote') is True
    assert not ast['blocks'][1].get('sourceNote')


# --- STYLE_MAP / run merge ----------------------------------------------------------

def _convert(md, cfg, ref):
    with zipfile.ZipFile(ref) as z:
        header = z.read('Contents/header.xml').decode('utf-8')
        section = z.read('Contents/section0.xml').decode('utf-8')
    ast = MarkoToPandocAdapter(config=cfg).parse(md)
    conv = MarkdownToHwpx(ast, header, section, None, config=cfg)
    body, _ = conv.convert()
    return body


def test_style_map_by_name_and_list_style_id(blank_hwpx_path):
    cfg = ConversionConfig()
    cfg.STYLE_MAP = {'H1': None, 'H2': '제목 3', 'BODY': '제목 5', 'LIST_BULLET_1': '제목 6'}
    body = _convert('# 버림\n\n## 소제목\n\n본문 한 줄\n\n- 항목\n', cfg, blank_hwpx_path)
    assert '버림' not in body
    paras = re.findall(r'<hp:p [^>]*styleIDRef="(\d+)"[^>]*>.*?<hp:t>([^<]*)</hp:t>', body)
    styles = {t: s for s, t in paras}
    assert styles['소제목'] == '3'
    assert styles['본문 한 줄'] == '5'
    assert styles['항목'] == '6'


def test_runs_are_merged(blank_hwpx_path):
    body = _convert('하나 둘 셋 넷\n', ConversionConfig(), blank_hwpx_path)
    assert '<hp:t>하나 둘 셋 넷</hp:t>' in body


# --- insert mode -------------------------------------------------------------------------

@pytest.fixture
def target_hwpx(tmp_path, blank_hwpx_path):
    md = tmp_path / 'base.md'
    md.write_text('# 첫째 절\n\n옛 내용\n\n## 하위\n\n옛 하위 내용\n\n# 둘째 절\n\n남길 내용\n', encoding='utf-8')
    ast = MarkoToPandocAdapter().parse(md.read_text(encoding='utf-8'))
    out = tmp_path / 'target.hwpx'
    MarkdownToHwpx.convert_to_hwpx(str(md), str(out), blank_hwpx_path, json_ast=ast)
    return out


def _section(path):
    with zipfile.ZipFile(path) as z:
        return z.read('Contents/section0.xml').decode('utf-8')


def test_insert_replaces_section_and_is_repeatable(tmp_path, target_hwpx):
    draft = tmp_path / 'draft.md'
    draft.write_text('새 문단 60~80%\n\n- 항목 하나\n', encoding='utf-8')
    out = tmp_path / 'out.hwpx'
    insert_markdown(str(target_hwpx), str(out), [(str(draft), '첫째 절')])
    sec = _section(out)
    assert '새 문단 60~80%' in sec and '항목 하나' in sec
    assert '옛 내용' not in sec and '옛 하위 내용' not in sec   # whole section replaced
    assert '둘째 절' in sec and '남길 내용' in sec           # next section kept
    assert '첫째 절' in sec

    with zipfile.ZipFile(out) as z:
        header_1 = z.read('Contents/header.xml')
    insert_markdown(str(out), str(out), [(str(draft), '첫째 절')])
    sec2 = _section(out)
    assert sec2.count('새 문단 60~80%') == 1
    with zipfile.ZipFile(out) as z:
        assert z.read('Contents/header.xml') == header_1     # no duplicate defs piled up


def test_insert_keeps_original_header_untouched(tmp_path, target_hwpx):
    draft = tmp_path / 'draft.md'
    draft.write_text('| a | b |\n|---|--:|\n| 1 | 2 |\n', encoding='utf-8')
    out = tmp_path / 'out.hwpx'
    insert_markdown(str(target_hwpx), str(out), [(str(draft), '둘째 절')])
    with zipfile.ZipFile(target_hwpx) as z:
        orig = z.read('Contents/header.xml').decode('utf-8')
    with zipfile.ZipFile(out) as z:
        new = z.read('Contents/header.xml').decode('utf-8')
    # every original definition is still there, byte for byte
    for m in re.finditer(r'<hh:(charPr|paraPr|borderFill) id="\d+".*?</hh:\1>', orig, re.S):
        assert m.group(0) in new


def test_insert_missing_heading(tmp_path, target_hwpx):
    draft = tmp_path / 'draft.md'
    draft.write_text('x\n', encoding='utf-8')
    with pytest.raises(InsertError):
        insert_markdown(str(target_hwpx), str(tmp_path / 'o.hwpx'), [(str(draft), '없는 제목')])
