"""
Insert converted Markdown into an EXISTING HWPX document.

The target document is used as the style reference (header.xml) and the
converted paragraphs replace one section of its body: everything after a
heading paragraph (matched by its text) up to the next heading of the same
or higher outline level. Running it again replaces the previous insertion,
so a draft can be edited in Markdown and re-inserted any number of times.

Only new style definitions created during conversion are appended to the
target's header.xml; existing definitions are left byte-for-byte untouched.
"""

import copy
import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET

from .config import ConversionConfig
from .exceptions import HwpxError
from .frontmatter_parser import parse_markdown_with_frontmatter
from .marko_adapter import MarkoToPandocAdapter
from .MarkdownToHwpx import MarkdownToHwpx, NS_HEAD, NS_PARA

logger = logging.getLogger('md2hwpx')

_HH = f'{{{NS_HEAD}}}'
_HP = f'{{{NS_PARA}}}'

# Containers in header.xml whose children carry an "id" and an itemCnt
_HEADER_LISTS = ['charProperties', 'paraProperties', 'borderFills', 'numberings',
                 'bullets', 'tabProperties', 'styles']


class InsertError(HwpxError):
    pass


# --- section helpers ---------------------------------------------------------

def _top_level_paragraphs(sec_xml):
    """Yield (start, end) offsets of top-level <hp:p> elements of hs:sec."""
    pos = sec_xml.find('>', sec_xml.find('<hs:sec')) + 1
    tag_re = re.compile(r'<(/?)hp:p(?=[\s>/])[^>]*?(/?)>')
    depth = 0
    start = None
    for m in tag_re.finditer(sec_xml, pos):
        closing, selfclose = m.group(1), m.group(2)
        if not closing and not selfclose:
            if depth == 0:
                start = m.start()
            depth += 1
        elif closing:
            depth -= 1
            if depth == 0 and start is not None:
                yield start, m.end()
                start = None


def _para_text(p_xml):
    """Text of a paragraph, excluding text nested in tables/captions/notes."""
    try:
        el = ET.fromstring(_wrap(p_xml))[0]
    except ET.ParseError:
        return ''
    parts = []
    for run in el.findall(f'{_HP}run'):
        for t in run.findall(f'{_HP}t'):
            parts.append(''.join(t.itertext()))
    return ''.join(parts)


def _wrap(xml):
    return (f'<r xmlns:hp="{NS_PARA}" xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
            f'xmlns:hh="{NS_HEAD}">{xml}</r>')


def _outline_levels(header_xml):
    """paraPr id -> outline level (only OUTLINE headings)."""
    levels = {}
    root = ET.fromstring(header_xml.encode('utf-8'))
    for pp in root.iter(f'{_HH}paraPr'):
        for h in pp.iter(f'{_HH}heading'):
            if h.get('type') == 'OUTLINE':
                levels[pp.get('id')] = int(h.get('level', '0'))
            break
    return levels


def _find_section(sec_xml, header_xml, heading):
    """Return (insert_start, insert_end) offsets of the body region under
    the heading paragraph whose text equals `heading`."""
    levels = _outline_levels(header_xml)
    paras = list(_top_level_paragraphs(sec_xml))
    want = re.sub(r'\s+', '', heading)
    matches = []
    for idx, (s, e) in enumerate(paras):
        if re.sub(r'\s+', '', _para_text(sec_xml[s:e])) == want:
            m = re.match(r'<hp:p [^>]*paraPrIDRef="(\d+)"', sec_xml[s:e])
            lvl = levels.get(m.group(1)) if m else None
            matches.append((idx, lvl))
    if not matches:
        raise InsertError(f'Heading not found in target document: {heading!r}')
    # Prefer an outline heading over e.g. a table-of-contents line
    outline = [x for x in matches if x[1] is not None]
    if len(outline) > 1:
        logger.warning('Heading %r appears %d times; using the first outline heading', heading, len(outline))
    idx, lvl = (outline or matches)[0]
    start = paras[idx][1]
    end = None
    for s, e in paras[idx + 1:]:
        m = re.match(r'<hp:p [^>]*paraPrIDRef="(\d+)"', sec_xml[s:e])
        nl = levels.get(m.group(1)) if m else None
        if nl is not None and (lvl is None or nl <= lvl):
            end = s
            break
    if end is None:
        end = sec_xml.rfind('</hs:sec>')
    return start, end


# --- header merge ------------------------------------------------------------

_REF_ATTR = {'charProperties': 'charPrIDRef', 'paraProperties': 'paraPrIDRef',
             'borderFills': 'borderFillIDRef'}


def _merge_header(orig_xml, new_xml, body):
    """Append to `orig_xml` every id-bearing definition present in `new_xml`
    but missing in `orig_xml` (fonts per language included).

    A new charPr/paraPr/borderFill identical to an existing one (apart from
    its id) is not added; `body` references are pointed at the existing id
    instead, so repeated insertions don't pile up duplicate definitions.

    Returns (merged_header_xml, body).
    """
    for p, u in (('hh', NS_HEAD), ('hc', 'http://www.hancom.co.kr/hwpml/2011/core'),
                 ('hp', NS_PARA)):
        ET.register_namespace(p, u)
    new_root = ET.fromstring(new_xml.encode('utf-8'))

    def serialize(el):
        s = ET.tostring(el, encoding='unicode')
        return re.sub(r'\s+xmlns:\w+="[^"]+"', '', s)

    def signature(el):
        c = copy.deepcopy(el)
        c.attrib.pop('id', None)
        return ET.canonicalize(ET.tostring(c, encoding='unicode'), strip_text=True)

    def remap_header_refs(lst, old, new):
        """Point references inside new_root from definition `old` to `new`."""
        for el in new_root.iter():
            tag = el.tag.split('}')[-1]
            if lst == 'borderFills' and el.get('borderFillIDRef') == old:
                el.set('borderFillIDRef', new)
            elif lst == 'charProperties' and el.get('charPrIDRef') == old and tag in ('style', 'paraHead'):
                el.set('charPrIDRef', new)
            elif lst == 'tabProperties' and el.get('tabPrIDRef') == old:
                el.set('tabPrIDRef', new)
            elif lst == 'paraProperties' and el.get('paraPrIDRef') == old and tag == 'style':
                el.set('paraPrIDRef', new)
            elif tag == 'heading' and el.get('idRef') == old and (
                    (lst == 'numberings' and el.get('type') == 'NUMBER') or
                    (lst == 'bullets' and el.get('type') == 'BULLET')):
                el.set('idRef', new)

    # Referenced kinds first, so dependants compare equal after remapping
    order = ['borderFills', 'charProperties', 'tabProperties', 'numberings', 'bullets',
             'paraProperties', 'styles']
    for lst in order:
        container = new_root.find(f'.//{_HH}{lst}')
        if container is None:
            continue
        m = re.search(r'<hh:%s\b[^>]*>(.*?)</hh:%s>' % (lst, lst), orig_xml, re.S)
        if not m:
            continue
        existing = set(re.findall(r'<hh:\w+ id="(\d+)"', m.group(1)))
        added = [c for c in container if c.get('id') is not None and c.get('id') not in existing]
        if added and lst != 'styles':
            known = {}
            for c in container:
                if c.get('id') in existing:
                    known.setdefault(signature(c), c.get('id'))
            keep = []
            for c in added:
                dup = known.get(signature(c))
                if dup is not None:
                    remap_header_refs(lst, c.get('id'), dup)
                    ref_attr = _REF_ATTR.get(lst)
                    if ref_attr:
                        body = re.sub(r'(\b%s=")%s"' % (ref_attr, re.escape(c.get('id'))),
                                      r'\g<1>%s"' % dup, body)
                else:
                    keep.append(c)
            added = keep
        if not added:
            continue
        insert_at = m.end(1)
        orig_xml = orig_xml[:insert_at] + ''.join(serialize(c) for c in added) + orig_xml[insert_at:]
        orig_xml = re.sub(r'(<hh:%s\b[^>]*itemCnt=")(\d+)' % lst,
                          lambda mm: mm.group(1) + str(int(mm.group(2)) + len(added)), orig_xml, count=1)

    for ff in new_root.iter(f'{_HH}fontface'):
        lang = ff.get('lang')
        m = re.search(r'<hh:fontface lang="%s"[^>]*>(.*?)</hh:fontface>' % re.escape(lang), orig_xml, re.S)
        if not m:
            continue
        existing = set(re.findall(r'<hh:font id="(\d+)"', m.group(1)))
        added = [f for f in ff.findall(f'{_HH}font') if f.get('id') not in existing]
        if not added:
            continue
        insert_at = m.end(1)
        orig_xml = orig_xml[:insert_at] + ''.join(serialize(f) for f in added) + orig_xml[insert_at:]
        orig_xml = re.sub(r'(<hh:fontface lang="%s"[^>]*fontCnt=")(\d+)' % re.escape(lang),
                          lambda mm: mm.group(1) + str(int(mm.group(2)) + len(added)), orig_xml, count=1)
    return orig_xml, body


def _renumber(sec_xml):
    """Store sequential autoNum values for tables/figures (Hangul recomputes
    them on open; this keeps the saved values consistent too)."""
    for kind in ('TABLE', 'PICTURE'):
        counter = [0]

        def rep(m):
            counter[0] += 1
            return f'<hp:autoNum num="{counter[0]}" numType="{kind}"'
        sec_xml = re.sub(r'<hp:autoNum num="\d+" numType="%s"' % kind, rep, sec_xml)
    return sec_xml


_MIME = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif',
         'bmp': 'image/bmp'}


# --- public API ------------------------------------------------------------

def insert_markdown(target_path, output_path, sections, config=None):
    """Insert one or more Markdown files into sections of an existing HWPX.

    Args:
        target_path: existing HWPX (style source and destination body)
        output_path: where to write the result (may equal target_path)
        sections: list of (markdown_path, heading_text)
        config: ConversionConfig (STYLE_MAP etc.)

    Returns:
        list of dicts with per-section stats
    """
    config = config or ConversionConfig()
    for p, u in (('hp', NS_PARA), ('hh', NS_HEAD), ('hc', 'http://www.hancom.co.kr/hwpml/2011/core'),
                 ('hs', 'http://www.hancom.co.kr/hwpml/2011/section'),
                 ('hp10', 'http://www.hancom.co.kr/hwpml/2016/paragraph')):
        ET.register_namespace(p, u)   # so converted XML uses the hp:/hc: prefixes
    with zipfile.ZipFile(target_path) as z:
        entries = [(i, z.read(i.filename)) for i in z.infolist()]
    files = {i.filename: data for i, data in entries}
    header = files['Contents/header.xml'].decode('utf-8')
    sec = files['Contents/section0.xml'].decode('utf-8')
    hpf = files['Contents/content.hpf'].decode('utf-8')

    new_bins = {}
    stats = []
    for md_path, heading in sections:
        metadata, md_text = parse_markdown_with_frontmatter(md_path)
        ast = MarkoToPandocAdapter(config=config).parse(md_text)
        conv = MarkdownToHwpx(ast, header, sec, md_path, config=config)
        try:
            body, new_header = conv.convert(page_setup_xml=None)
            images = list(conv.images)
        finally:
            conv._cleanup()

        start, end = _find_section(sec, header, heading)
        body = re.sub(r'\s+xmlns:(hp|hc)="[^"]+"', '', body).strip()
        header, body = _merge_header(header, new_header, body)
        sec = sec[:start] + body + sec[end:]

        md_dir = os.path.dirname(os.path.abspath(md_path))
        for img in images:
            src = img['path'] if os.path.isabs(img['path']) else os.path.join(md_dir, img['path'])
            if not os.path.exists(src):
                logger.warning('Image not found: %s', src)
                continue
            with open(src, 'rb') as f:
                new_bins[img['id']] = (f"BinData/{img['id']}.{img['ext']}", f.read(), img['ext'])
        stats.append({'markdown': md_path, 'heading': heading,
                      'tables': body.count('<hp:tbl '), 'images': len(images)})

    sec = _renumber(sec)

    # Manifest: add new images, drop converter-made images nothing references
    referenced = set(re.findall(r'binaryItemIDRef="([^"]+)"', sec))
    for iid, (href, _, ext) in new_bins.items():
        if iid in referenced and f'id="{iid}"' not in hpf:
            item = f'<opf:item id="{iid}" href="{href}" media-type="{_MIME.get(ext.lower(), "image/" + ext)}" isEmbeded="1"/>'
            hpf = hpf.replace('</opf:manifest>', item + '</opf:manifest>')
    dropped = set()
    for m in list(re.finditer(r'<opf:item id="(img_[^"]+)" href="([^"]+)"[^>]*/>', hpf)):
        if m.group(1) not in referenced:
            dropped.add(m.group(2))
            hpf = hpf.replace(m.group(0), '')

    tmp = output_path + '.tmp'
    with zipfile.ZipFile(tmp, 'w') as zo:
        for info, data in entries:
            name = info.filename
            if name in dropped:
                continue
            if name == 'Contents/section0.xml':
                data = sec.encode('utf-8')
            elif name == 'Contents/header.xml':
                data = header.encode('utf-8')
            elif name == 'Contents/content.hpf':
                data = hpf.encode('utf-8')
            zo.writestr(info, data, compress_type=zipfile.ZIP_STORED if name == 'mimetype' else zipfile.ZIP_DEFLATED)
        existing = {i.filename for i, _ in entries}
        for iid, (href, data, _) in new_bins.items():
            if iid in referenced and href not in existing:
                zo.writestr(href, data, compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tmp, output_path)
    return stats
