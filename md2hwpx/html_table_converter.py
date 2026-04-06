"""
HTML table to HWPX table converter.

Converts HTML <table> elements (from RawBlock) into HWPX native <hp:tbl> XML,
reusing the existing table generation infrastructure in MarkdownToHwpx.

This module parses HTML tables into an intermediate structure compatible with
the Pandoc-like AST format, then delegates to the converter's existing
_handle_table_elem() method.
"""

import re
import logging
from html.parser import HTMLParser

logger = logging.getLogger('md2hwpx')


class _HTMLTableParser(HTMLParser):
    """Parse an HTML table into a structured representation.

    Produces:
        {
            'headers': [['cell1', 'cell2', ...], ...],  # rows from <thead>
            'rows': [['cell1', 'cell2', ...], ...],     # rows from <tbody>
            'aligns': ['left', 'center', 'right', None, ...],  # per-column alignment
            'col_count': int,
        }
    """

    def __init__(self):
        super().__init__()
        self.headers = []   # list of header rows, each is list of cell texts
        self.rows = []      # list of body rows
        self.aligns = []    # per-column alignment from first header/row

        self._in_thead = False
        self._in_tbody = False
        self._in_tr = False
        self._in_cell = False
        self._is_header_cell = False
        self._current_row = []
        self._current_cell_parts = []
        self._current_cell_align = None
        self._cell_aligns_row = []
        self._row_has_th = False  # track if any cell in current row is <th>
        self._skip_depth = 0
        self._skip_tags = {'style', 'script'}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag in self._skip_tags:
            self._skip_depth += 1
            return

        if tag == 'thead':
            self._in_thead = True
        elif tag == 'tbody':
            self._in_tbody = True
        elif tag == 'tr':
            self._in_tr = True
            self._current_row = []
            self._cell_aligns_row = []
            self._row_has_th = False
        elif tag in ('th', 'td'):
            self._in_cell = True
            self._is_header_cell = (tag == 'th')
            if tag == 'th':
                self._row_has_th = True
            self._current_cell_parts = []
            # Extract alignment from style attribute
            style = attrs_dict.get('style', '')
            align = attrs_dict.get('align', '')
            self._current_cell_align = self._parse_alignment(style, align)
        elif tag == 'br' and self._in_cell:
            self._current_cell_parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._skip_depth > 0:
            self._skip_depth -= 1
            return

        if tag == 'thead':
            self._in_thead = False
        elif tag == 'tbody':
            self._in_tbody = False
        elif tag == 'tr':
            self._in_tr = False
            if self._in_thead or (not self._in_tbody and self._row_has_th):
                self.headers.append(self._current_row)
            else:
                self.rows.append(self._current_row)
            # Capture column alignments from first row
            if not self.aligns and self._cell_aligns_row:
                self.aligns = self._cell_aligns_row
            self._current_row = []
        elif tag in ('th', 'td'):
            cell_text = ''.join(self._current_cell_parts).strip()
            self._current_row.append(cell_text)
            self._cell_aligns_row.append(self._current_cell_align)
            self._in_cell = False
            self._is_header_cell = False

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        if self._in_cell:
            self._current_cell_parts.append(data)

    @staticmethod
    def _parse_alignment(style, align_attr):
        """Extract text alignment from CSS style or align attribute."""
        # Check style attribute: text-align: left/center/right
        if style:
            m = re.search(r'text-align\s*:\s*(left|center|right)', style, re.IGNORECASE)
            if m:
                return m.group(1).lower()
        # Check align attribute
        if align_attr:
            a = align_attr.lower()
            if a in ('left', 'center', 'right'):
                return a
        return None


def _parse_html_table(html_text):
    """Parse HTML table string into structured data."""
    parser = _HTMLTableParser()
    try:
        parser.feed(html_text)
    except Exception as e:
        logger.warning("Failed to parse HTML table: %s", e)
        return None

    col_count = 0
    if parser.headers:
        col_count = max(len(row) for row in parser.headers)
    if parser.rows:
        col_count = max(col_count, max(len(row) for row in parser.rows))

    if col_count == 0:
        return None

    return {
        'headers': parser.headers,
        'rows': parser.rows,
        'aligns': parser.aligns,
        'col_count': col_count,
    }


def _to_pandoc_table_ast(table_data):
    """Convert parsed HTML table data to Pandoc-like Table AST.

    The AST format expected by _handle_table is:
    [caption, [alignment...], [colwidth...], [header_cells...], [[row_cells...]...]]

    Where each cell is a list of blocks:
    [{"t": "Plain", "c": [{"t": "Str", "c": "text"}]}]
    """
    col_count = table_data['col_count']

    # Caption (empty)
    caption = [[], []]

    # Alignments
    align_map = {
        'left': 'AlignLeft',
        'center': 'AlignCenter',
        'right': 'AlignRight',
    }
    aligns = []
    for i in range(col_count):
        if i < len(table_data['aligns']) and table_data['aligns'][i]:
            aligns.append(align_map.get(table_data['aligns'][i], 'AlignDefault'))
        else:
            aligns.append('AlignDefault')

    # Column widths (equal distribution)
    colwidths = [['ColWidthDefault', 0]] * col_count

    # Convert cell text to AST inline nodes
    def _cell_to_ast(text):
        """Convert cell text to a list of blocks with inline content."""
        if not text:
            return [{'t': 'Plain', 'c': [{'t': 'Str', 'c': ''}]}]

        # Simple text splitting into Str + Space
        inlines = []
        words = text.split(' ')
        for j, word in enumerate(words):
            if word:
                inlines.append({'t': 'Str', 'c': word})
            if j < len(words) - 1:
                inlines.append({'t': 'Space'})
        if not inlines:
            inlines = [{'t': 'Str', 'c': ''}]
        return [{'t': 'Plain', 'c': inlines}]

    # Header row(s) - combine all header rows, use first if multiple
    header_cells = []
    if table_data['headers']:
        first_header = table_data['headers'][0]
        for i in range(col_count):
            cell_text = first_header[i] if i < len(first_header) else ''
            header_cells.append(_cell_to_ast(cell_text))
    else:
        # No header: empty cells
        for i in range(col_count):
            header_cells.append(_cell_to_ast(''))

    # Body rows
    body_rows = []
    # If there are multiple header rows, treat extras as body rows
    for header_row in table_data['headers'][1:]:
        row_cells = []
        for i in range(col_count):
            cell_text = header_row[i] if i < len(header_row) else ''
            row_cells.append(_cell_to_ast(cell_text))
        body_rows.append(row_cells)

    for data_row in table_data['rows']:
        row_cells = []
        for i in range(col_count):
            cell_text = data_row[i] if i < len(data_row) else ''
            row_cells.append(_cell_to_ast(cell_text))
        body_rows.append(row_cells)

    return [caption, aligns, colwidths, header_cells, body_rows]


def convert_html_table(html_text, converter):
    """Convert HTML table to HWPX table XML.

    Args:
        html_text: HTML string containing a <table> element
        converter: MarkdownToHwpx instance (for access to table generation methods)

    Returns:
        XML string for the HWPX table, or empty string on failure
    """
    table_data = _parse_html_table(html_text)
    if not table_data:
        logger.warning("Could not parse HTML table")
        return ''

    # Convert to Pandoc-like AST and use existing table handler
    table_ast = _to_pandoc_table_ast(table_data)

    try:
        return converter._handle_table(table_ast)
    except Exception as e:
        logger.warning("HTML table conversion failed: %s", e)
        return ''
