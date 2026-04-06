"""
Marko AST to Pandoc-like dict adapter.

Converts Marko's object-based AST to the dict format expected by MarkdownToHwpx handlers.
"""

import re
from marko import Markdown
from marko.ext.gfm import GFM


class MarkoToPandocAdapter:
    """Converts Marko AST to Pandoc-like dict format."""

    # Regex to match extended headers (7-9 levels)
    # Standard Markdown only supports 1-6, but HWPX supports up to 9
    EXTENDED_HEADER_RE = re.compile(r'^(#{7,9})\s+(.+)$')

    # Regex to match table separator lines (e.g., |---|-----------|---|)
    TABLE_SEPARATOR_RE = re.compile(r'^\|[\s:]*-')

    # Regex patterns for Quarto/Pandoc preprocessing
    FENCED_DIV_OPEN_RE = re.compile(r'^:{3,}\s*\{[^}]*\}\s*$')
    FENCED_DIV_CLOSE_RE = re.compile(r'^:{3,}\s*$')
    STYLE_BLOCK_RE = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE)
    PANDOC_ATTR_RE = re.compile(r'\{[#.][^}]*\}')
    BLOCK_MATH_RE = re.compile(r'\$\$[^$]+\$\$', re.DOTALL)
    INLINE_MATH_RE = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')
    # Match both multi-line $$\n...\n$$ and single-line $$...$$ block math
    BLOCK_MATH_DELIM_RE = re.compile(
        r'^\$\$\s*\n(.*?)\n\s*\$\$\s*$'   # multi-line: $$\n content \n$$
        r'|'
        r'^\$\$(.+?)\$\$\s*$',             # single-line: $$content$$
        re.MULTILINE | re.DOTALL
    )

    def __init__(self, config=None):
        from .config import DEFAULT_CONFIG
        self.config = config if config is not None else DEFAULT_CONFIG
        # Initialize Marko with GFM (tables, strikethrough, etc.) and Footnote support
        # Extensions are loaded by name string
        self.md = Markdown(extensions=['gfm', 'footnote'])
        self.footnotes = {}  # Store footnote definitions from document
        self.extended_headers = {}  # Store extended header placeholders
        self.table_dash_counts = {}  # Store dash counts per table separator
        self.table_counter = 0  # Track table index during conversion
        self._math_blocks = {}  # Store block math placeholders
        self._math_inlines = {}  # Store inline math placeholders (image mode)

    def _preprocess_extended_headers(self, markdown_text: str) -> str:
        """
        Preprocess markdown to handle header levels 7-9.

        Standard Markdown only supports levels 1-6.
        We convert ####### lines to unique placeholders, then restore
        them as Header blocks after Marko parsing.

        Each placeholder is wrapped with blank lines to ensure it becomes
        its own paragraph block (not merged with adjacent text).
        """
        lines = markdown_text.split('\n')
        processed_lines = []
        placeholder_counter = 0

        for line in lines:
            match = self.EXTENDED_HEADER_RE.match(line)
            if match:
                hashes = match.group(1)
                content = match.group(2)
                level = len(hashes)

                # Use a placeholder that won't trigger markdown formatting
                # (no __, *, or other special chars)
                placeholder = f"EXTHEADER{placeholder_counter}MARKER"
                self.extended_headers[placeholder] = {
                    'level': level,
                    'content': content
                }
                # Add blank lines around placeholder to ensure it's a separate paragraph
                processed_lines.append('')
                processed_lines.append(placeholder)
                processed_lines.append('')
                placeholder_counter += 1
            else:
                processed_lines.append(line)

        return '\n'.join(processed_lines)

    def _create_extended_header_block(self, level: int, content: str) -> dict:
        """Create a Header block for extended levels (7-9)."""
        # Parse the content as inline markdown
        inlines = self._convert_raw_text(content)
        return {
            "t": "Header",
            "c": [level, ["", [], []], inlines]
        }

    def _preprocess_table_dashes(self, markdown_text):
        """Extract dash counts from table separator rows before Marko parsing.

        Scans the raw markdown for table separator lines and records
        the number of dashes in each column. This is used later to
        calculate proportional column widths.

        Args:
            markdown_text: Raw markdown string
        """
        self.table_dash_counts = {}
        table_index = 0
        for line in markdown_text.split('\n'):
            stripped = line.strip()
            if not self.TABLE_SEPARATOR_RE.match(stripped):
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if cells and all(re.match(r'^:?-+:?$', c) for c in cells if c):
                dash_counts = {}
                for col_idx, cell in enumerate(cells):
                    if cell:
                        dash_counts[col_idx] = cell.count('-')
                self.table_dash_counts[table_index] = dash_counts
                table_index += 1

    def _preprocess_strip_cell_code(self, text: str) -> str:
        """Remove fenced code blocks with .cell-code class (Quarto source output)."""
        lines = text.split('\n')
        result = []
        in_cell_code = False
        fence_re = re.compile(r'^`{3,}')

        for line in lines:
            if not in_cell_code:
                if fence_re.match(line) and '.cell-code' in line:
                    in_cell_code = True
                    continue
                result.append(line)
            else:
                if fence_re.match(line.strip()):
                    in_cell_code = False
                    continue
                # Skip content inside cell-code block
        return '\n'.join(result)

    def _preprocess_strip_fenced_divs(self, text: str) -> str:
        """Remove Pandoc fenced div markers, keeping inner content."""
        lines = text.split('\n')
        result = []
        for line in lines:
            stripped = line.strip()
            if self.FENCED_DIV_OPEN_RE.match(stripped):
                continue
            if self.FENCED_DIV_CLOSE_RE.match(stripped):
                continue
            result.append(line)
        return '\n'.join(result)

    def _preprocess_strip_html_style(self, text: str) -> str:
        """Remove <style>...</style> blocks."""
        return self.STYLE_BLOCK_RE.sub('', text)

    def _preprocess_math(self, text: str) -> str:
        """Convert LaTeX math to internal representations.

        Modes (config.MATH_HANDLING):
          - 'italic': Block → placeholder → italic Para. Inline → *emphasis*.
          - 'image':  Block → placeholder → Image node. Inline → placeholder → Image node.
        """
        self._math_blocks = {}
        self._math_inlines = {}
        block_counter = [0]
        inline_counter = [0]

        def replace_block_math(match):
            # group(1) = multi-line match, group(2) = single-line match
            content = (match.group(1) or match.group(2)).strip()
            key = f"MATHBLOCK{block_counter[0]}MARKER"
            self._math_blocks[key] = content
            block_counter[0] += 1
            return f"\n\n{key}\n\n"

        if self.config.MATH_HANDLING == 'italic':
            result = self.BLOCK_MATH_DELIM_RE.sub(replace_block_math, text)
            result = self.INLINE_MATH_RE.sub(r'*\1*', result)
            return result

        elif self.config.MATH_HANDLING == 'hwce':
            result = self.BLOCK_MATH_DELIM_RE.sub(replace_block_math, text)

            def replace_inline_math(match):
                content = match.group(1)
                key = f"MATHINLINE{inline_counter[0]}MARKER"
                self._math_inlines[key] = content
                inline_counter[0] += 1
                return key

            result = self.INLINE_MATH_RE.sub(replace_inline_math, result)
            return result

        return text

    def _preprocess_strip_pandoc_attributes(self, text: str) -> str:
        """Remove Pandoc inline attributes ({.class #id}) while protecting math regions."""
        # Protect math regions with placeholders
        math_placeholders = {}
        counter = [0]

        def protect_math(match):
            key = f"__MATH_PROTECT_{counter[0]}__"
            math_placeholders[key] = match.group(0)
            counter[0] += 1
            return key

        protected = self.BLOCK_MATH_RE.sub(protect_math, text)
        protected = self.INLINE_MATH_RE.sub(protect_math, protected)

        # Strip Pandoc attributes
        protected = self.PANDOC_ATTR_RE.sub('', protected)

        # Restore math
        for key, value in math_placeholders.items():
            protected = protected.replace(key, value)

        return protected

    def _get_col_width_info(self, table_index, col_idx):
        """Get width info dict for a column from stored dash counts.

        Args:
            table_index: Index of the table (order of appearance)
            col_idx: Column index within the table

        Returns:
            Pandoc-compatible width dict:
            - {"t": "ColWidth", "c": proportion} if dash count available
            - {"t": "ColWidthDefault"} otherwise
        """
        if table_index not in self.table_dash_counts:
            return {"t": "ColWidthDefault"}
        col_dashes = self.table_dash_counts[table_index]
        total_dashes = sum(col_dashes.values())
        if total_dashes == 0 or col_idx not in col_dashes:
            return {"t": "ColWidthDefault"}
        return {"t": "ColWidth", "c": col_dashes[col_idx] / total_dashes}

    def parse(self, markdown_text: str) -> dict:
        """
        Parse markdown and return Pandoc-like AST dict.

        Returns:
            {"pandoc-api-version": [...], "meta": {...}, "blocks": [...]}
        """
        # Reset state for each parse
        self.extended_headers = {}
        self.footnotes = {}
        self.table_dash_counts = {}
        self.table_counter = 0
        self._math_blocks = {}
        self._math_inlines = {}

        processed_text = markdown_text

        # Quarto/Pandoc preprocessing (before Marko parsing)
        if self.config.STRIP_CELL_CODE_BLOCKS:
            processed_text = self._preprocess_strip_cell_code(processed_text)
        if self.config.STRIP_FENCED_DIVS:
            processed_text = self._preprocess_strip_fenced_divs(processed_text)
        if self.config.STRIP_HTML_STYLE_BLOCKS:
            processed_text = self._preprocess_strip_html_style(processed_text)
        if getattr(self.config, 'QUARTO_FULL_PREPROCESS', False):
            from .quarto_preprocessor import preprocess_quarto_full
            processed_text = preprocess_quarto_full(processed_text)
        if self.config.MATH_HANDLING != 'none':
            processed_text = self._preprocess_math(processed_text)
        if self.config.STRIP_PANDOC_ATTRIBUTES:
            processed_text = self._preprocess_strip_pandoc_attributes(processed_text)

        # Preprocess to handle extended headers (7-9)
        processed_text = self._preprocess_extended_headers(processed_text)

        # Extract table dash counts for proportional column widths
        self._preprocess_table_dashes(processed_text)

        doc = self.md.parse(processed_text)

        # Store footnotes from document (if footnote extension is active)
        if hasattr(doc, 'footnotes'):
            self.footnotes = doc.footnotes

        blocks = []
        for child in doc.children:
            block = self._convert_block(child)
            if block:
                # Check if this is an extended header or math placeholder
                block = self._restore_extended_header(block)
                block = self._restore_math_block(block)
                if self._math_inlines:
                    block = self._restore_math_inlines(block)
                blocks.append(block)

        return {
            "pandoc-api-version": [1, 23, 1],  # Compatibility marker
            "meta": {},  # Metadata handled separately by python-frontmatter
            "blocks": blocks
        }

    def _restore_extended_header(self, block: dict) -> dict:
        """
        Check if a block is an extended header placeholder and restore it.

        Extended header placeholders become paragraphs with text like
        "__EXTENDED_HEADER_0__", which we convert back to Header blocks.
        """
        if block.get('t') != 'Para':
            return block

        inlines = block.get('c', [])
        if len(inlines) != 1:
            return block

        first = inlines[0]
        if first.get('t') != 'Str':
            return block

        text = first.get('c', '')
        if text in self.extended_headers:
            info = self.extended_headers[text]
            return self._create_extended_header_block(info['level'], info['content'])

        return block

    def _restore_math_block(self, block: dict) -> dict:
        """Check if a block is a math placeholder and restore."""
        if block.get('t') != 'Para':
            return block
        inlines = block.get('c', [])
        if len(inlines) != 1:
            return block
        first = inlines[0]
        if first.get('t') != 'Str':
            return block
        text = first.get('c', '')
        if text in self._math_blocks:
            content = self._math_blocks[text]
            if self.config.MATH_HANDLING == 'hwce':
                return {
                    "t": "Para",
                    "c": [{"t": "Math", "c": ["DisplayMath", content]}]
                }
            else:
                return {
                    "t": "Para",
                    "c": [{"t": "Emph", "c": self._convert_raw_text(content)}]
                }
        return block

    def _restore_math_inlines(self, block: dict) -> dict:
        """Walk a block's inlines and replace math placeholders with Math nodes."""
        if block.get('t') in ('Para', 'Plain'):
            block['c'] = self._replace_math_in_inlines(block['c'])
        elif block.get('t') == 'Header':
            # Header c = [level, attr, inlines]
            content = block.get('c', [])
            if len(content) >= 3 and isinstance(content[2], list):
                content[2] = self._replace_math_in_inlines(content[2])
        elif block.get('t') in ('BulletList', 'OrderedList'):
            items = block.get('c', [])
            if block['t'] == 'OrderedList':
                items = items[1] if len(items) > 1 else []
            for item in items:
                for sub_block in item:
                    self._restore_math_inlines(sub_block)
        elif block.get('t') == 'BlockQuote':
            for sub_block in block.get('c', []):
                self._restore_math_inlines(sub_block)
        elif block.get('t') == 'Table':
            # Walk table cells
            content = block.get('c', [])
            if len(content) >= 5:
                # head rows
                head = content[3]
                if len(head) >= 2:
                    for row in head[1]:
                        for cell in row[1]:
                            for cell_block in cell[4]:
                                self._restore_math_inlines(cell_block)
                # body rows
                for body in content[4]:
                    if len(body) >= 4:
                        for row in body[3]:
                            for cell in row[1]:
                                for cell_block in cell[4]:
                                    self._restore_math_inlines(cell_block)
        return block

    def _replace_math_in_inlines(self, inlines: list) -> list:
        """Replace MATHINLINE placeholders in an inline list with Math nodes."""
        if not inlines:
            return inlines
        result = []
        for item in inlines:
            i_type = item.get('t')
            if i_type == 'Str':
                text = item.get('c', '')
                # Check if the whole Str is a placeholder
                if text in self._math_inlines:
                    latex = self._math_inlines[text]
                    result.append({"t": "Math", "c": ["InlineMath", latex]})
                elif any(k in text for k in self._math_inlines):
                    # Placeholder embedded in larger text — split
                    remaining = text
                    for key, latex in self._math_inlines.items():
                        if key in remaining:
                            parts = remaining.split(key, 1)
                            if parts[0]:
                                result.extend(self._convert_raw_text_simple(parts[0]))
                            result.append({"t": "Math", "c": ["InlineMath", latex]})
                            remaining = parts[1]
                    if remaining:
                        result.extend(self._convert_raw_text_simple(remaining))
                else:
                    result.append(item)
            elif i_type in ('Strong', 'Emph', 'Underline', 'Strikeout'):
                item['c'] = self._replace_math_in_inlines(item.get('c', []))
                result.append(item)
            elif i_type == 'Link':
                item['c'][1] = self._replace_math_in_inlines(item['c'][1])
                result.append(item)
            else:
                result.append(item)
        return result

    def _convert_block(self, element) -> dict | None:
        """Convert a Marko block element to Pandoc dict format."""
        elem_type = type(element).__name__

        if elem_type == 'Heading':
            return self._convert_heading(element)
        elif elem_type == 'Paragraph':
            return self._convert_paragraph(element)
        elif elem_type == 'List':
            return self._convert_list(element)
        elif elem_type == 'FencedCode':
            return self._convert_fenced_code(element)
        elif elem_type == 'CodeBlock':
            return self._convert_code_block(element)
        elif elem_type == 'Table':
            return self._convert_table(element)
        elif elem_type == 'Quote':
            return self._convert_blockquote(element)
        elif elem_type == 'ThematicBreak':
            return {"t": "HorizontalRule"}
        elif elem_type == 'BlankLine':
            return None  # Skip blank lines
        elif elem_type == 'HTMLBlock':
            return self._convert_raw_block(element)
        elif elem_type == 'LinkRefDef':
            return None  # Skip link reference definitions (handled during parsing)
        elif elem_type == 'SetextHeading':
            return self._convert_heading(element)
        elif elem_type == 'FootnoteDef':
            return None  # Skip - footnote content is handled via FootnoteRef

        # Unknown block type - skip with warning
        # print(f"[Warn] Unknown block type: {elem_type}")
        return None

    def _convert_heading(self, elem) -> dict:
        """Heading -> {"t": "Header", "c": [level, [id, [], []], inlines]}"""
        inlines = self._convert_children_to_inlines(elem.children)
        level = getattr(elem, 'level', 1)
        return {
            "t": "Header",
            "c": [level, ["", [], []], inlines]
        }

    def _convert_paragraph(self, elem) -> dict:
        """Paragraph -> {"t": "Para", "c": [inlines]}"""
        inlines = self._convert_children_to_inlines(elem.children)
        return {"t": "Para", "c": inlines}

    def _convert_list(self, elem) -> dict:
        """List -> BulletList or OrderedList"""
        items = []
        for item in elem.children:
            item_blocks = []
            for child in item.children:
                block = self._convert_block(child)
                if block:
                    item_blocks.append(block)
            items.append(item_blocks)

        ordered = getattr(elem, 'ordered', False)
        if ordered:
            # OrderedList: [[start, style, delim], items]
            start = getattr(elem, 'start', 1) or 1
            return {
                "t": "OrderedList",
                "c": [[start, {"t": "Decimal"}, {"t": "Period"}], items]
            }
        else:
            return {"t": "BulletList", "c": items}

    def _convert_fenced_code(self, elem) -> dict:
        """FencedCode -> {"t": "CodeBlock", "c": [[id, classes, attrs], code]}"""
        lang = getattr(elem, 'lang', '') or ''
        code = ''
        for child in elem.children:
            if hasattr(child, 'children'):
                code += child.children
            else:
                code += str(child)
        return {
            "t": "CodeBlock",
            "c": [["", [lang] if lang else [], []], code]
        }

    def _convert_code_block(self, elem) -> dict:
        """CodeBlock (indented) -> {"t": "CodeBlock", "c": [[id, [], []], code]}"""
        code = ''
        for child in elem.children:
            if hasattr(child, 'children'):
                code += child.children
            else:
                code += str(child)
        return {
            "t": "CodeBlock",
            "c": [["", [], []], code]
        }

    _ALIGN_MAP = {
        'left': 'AlignLeft',
        'center': 'AlignCenter',
        'right': 'AlignRight',
    }

    def _convert_table(self, elem) -> dict:
        """Convert Marko GFM Table to Pandoc Table format."""
        # Pandoc Table: [attr, caption, specs, head, bodies, foot]

        children = list(elem.children)
        if not children:
            return None

        # Marko GFM tables can have children as:
        # 1. TableHead + TableBody (older/some versions)
        # 2. Direct TableRow elements (current GFM extension)
        head_rows = []
        body_rows = []

        for child in children:
            child_type = type(child).__name__
            if child_type == 'TableHead':
                # Wrapped in TableHead
                for row in child.children:
                    head_rows.append(row)
            elif child_type == 'TableBody':
                # Wrapped in TableBody
                for row in child.children:
                    body_rows.append(row)
            elif child_type == 'TableRow':
                # Direct TableRow - first row is header, rest are body
                if not head_rows:
                    head_rows.append(child)
                else:
                    body_rows.append(child)

        # Determine column count from header or first body row
        col_count = 0
        first_row = head_rows[0] if head_rows else (body_rows[0] if body_rows else None)
        if first_row and first_row.children:
            col_count = len(first_row.children)

        # Column specs (alignment + proportional width from dash counts)
        table_idx = self.table_counter
        self.table_counter += 1

        specs = []
        if first_row and first_row.children:
            for col_idx, cell in enumerate(first_row.children):
                cell_align = getattr(cell, 'align', None)
                align_str = self._ALIGN_MAP.get(cell_align, 'AlignDefault')
                width_info = self._get_col_width_info(table_idx, col_idx)
                specs.append([align_str, width_info])
        else:
            specs = [["AlignDefault", self._get_col_width_info(table_idx, i)]
                     for i in range(col_count)]

        # Convert header
        head_converted = [self._convert_table_row(row) for row in head_rows]
        head = [["", [], []], head_converted]

        # Convert body
        body_converted = [self._convert_table_row(r) for r in body_rows]
        bodies = [[["", [], []], 0, [], body_converted]] if body_converted else []

        # Foot (GFM doesn't have)
        foot = [["", [], []], []]

        return {
            "t": "Table",
            "c": [
                ["", [], []],           # attr
                [None, []],             # caption
                specs,                  # colspecs
                head,                   # thead
                bodies,                 # tbody
                foot                    # tfoot
            ]
        }

    def _convert_table_row(self, row) -> list:
        """Convert TableRow to Pandoc row format."""
        # Pandoc row: [attr, [cells]]
        cells = []
        for cell in row.children:
            # Pandoc cell: [attr, align, rowspan, colspan, [blocks]]
            content = self._convert_children_to_inlines(cell.children)
            para = {"t": "Plain", "c": content}
            cell_align = getattr(cell, 'align', None)
            align_str = self._ALIGN_MAP.get(cell_align, 'AlignDefault')
            cells.append([
                ["", [], []],   # attr
                align_str,      # align
                1,              # rowspan (GFM doesn't support)
                1,              # colspan (GFM doesn't support)
                [para]          # blocks
            ])
        return [["", [], []], cells]

    def _convert_blockquote(self, elem) -> dict:
        """Quote -> {"t": "BlockQuote", "c": [blocks]}"""
        blocks = []
        for child in elem.children:
            block = self._convert_block(child)
            if block:
                blocks.append(block)
        return {"t": "BlockQuote", "c": blocks}

    def _convert_raw_block(self, elem) -> dict:
        """HTMLBlock -> {"t": "RawBlock", "c": ["html", content]}"""
        content = getattr(elem, 'children', '')
        return {"t": "RawBlock", "c": ["html", content]}

    def _convert_children_to_inlines(self, children) -> list:
        """Convert Marko inline children to Pandoc inline list."""
        if children is None:
            return []

        result = []
        for child in children:
            inlines = self._convert_inline(child)
            if isinstance(inlines, list):
                result.extend(inlines)
            elif inlines:
                result.append(inlines)
        return result

    def _convert_inline(self, elem):
        """Convert a Marko inline element to Pandoc inline dict."""
        elem_type = type(elem).__name__

        if elem_type == 'RawText':
            return self._convert_raw_text(elem.children)
        elif elem_type == 'Emphasis':
            inlines = self._convert_children_to_inlines(elem.children)
            return {"t": "Emph", "c": inlines}
        elif elem_type == 'StrongEmphasis':
            inlines = self._convert_children_to_inlines(elem.children)
            return {"t": "Strong", "c": inlines}
        elif elem_type == 'Link':
            inlines = self._convert_children_to_inlines(elem.children)
            dest = getattr(elem, 'dest', '')
            title = getattr(elem, 'title', '') or ''
            return {"t": "Link", "c": [["", [], []], inlines, [dest, title]]}
        elif elem_type == 'Image':
            inlines = self._convert_children_to_inlines(elem.children)
            dest = getattr(elem, 'dest', '')
            title = getattr(elem, 'title', '') or ''
            return {"t": "Image", "c": [["", [], []], inlines, [dest, title]]}
        elif elem_type == 'CodeSpan':
            code = getattr(elem, 'children', '')
            return {"t": "Code", "c": [["", [], []], code]}
        elif elem_type == 'LineBreak':
            return {"t": "LineBreak"}
        elif elem_type == 'SoftBreak':
            return {"t": "SoftBreak"}
        elif elem_type == 'Strikethrough':
            inlines = self._convert_children_to_inlines(elem.children)
            return {"t": "Strikeout", "c": inlines}
        elif elem_type == 'InlineHTML':
            content = getattr(elem, 'children', '')
            return {"t": "RawInline", "c": ["html", content]}
        elif elem_type == 'AutoLink':
            dest = getattr(elem, 'dest', '')
            return {"t": "Link", "c": [["", [], []], [{"t": "Str", "c": dest}], [dest, ""]]}
        elif elem_type == 'Literal':
            text = getattr(elem, 'children', '')
            return self._convert_raw_text(text)
        elif elem_type == 'FootnoteRef':
            # Convert footnote reference to Pandoc Note
            return self._convert_footnote_ref(elem)

        # Handle string children (e.g., from RawText)
        if isinstance(elem, str):
            return self._convert_raw_text(elem)

        # Unknown inline type - try to get text content
        if hasattr(elem, 'children'):
            if isinstance(elem.children, str):
                return self._convert_raw_text(elem.children)
            elif isinstance(elem.children, list):
                return self._convert_children_to_inlines(elem.children)

        return None

    # Regex for fallback emphasis parsing: detect literal **...** or *...*
    # that Marko failed to parse due to CommonMark delimiter rules
    # (e.g., punctuation before closing ** followed by a word character)
    _FALLBACK_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
    _FALLBACK_ITALIC_RE = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')

    def _convert_raw_text(self, text: str) -> list:
        """Convert raw text to Str and Space tokens, with fallback emphasis parsing.

        Handles CommonMark edge cases where Marko leaves literal **...** or *...*
        in RawText nodes (e.g., punctuation before closing ** followed by a
        non-punctuation character like Korean syllables).
        """
        if not text:
            return []

        # Fallback: detect literal **...** that Marko failed to parse
        if self._FALLBACK_BOLD_RE.search(text):
            return self._parse_fallback_emphasis(text, self._FALLBACK_BOLD_RE, 'Strong')

        # Fallback: detect literal *...* that Marko failed to parse
        if self._FALLBACK_ITALIC_RE.search(text):
            return self._parse_fallback_emphasis(text, self._FALLBACK_ITALIC_RE, 'Emph')

        # Standard logic: split by spaces into Str and Space tokens
        return self._convert_raw_text_simple(text)

    def _parse_fallback_emphasis(self, text: str, pattern, emph_type: str) -> list:
        """Parse text with fallback emphasis detection for patterns Marko missed.

        Splits text around emphasis matches, converting matched regions to
        Strong or Emph tokens and processing surrounding text normally.
        """
        result = []
        last_end = 0

        for match in pattern.finditer(text):
            # Add text before the match
            before = text[last_end:match.start()]
            if before:
                result.extend(self._convert_raw_text(before))

            # Add the emphasis content
            inner_text = match.group(1)
            inner_inlines = self._convert_raw_text(inner_text)
            result.append({"t": emph_type, "c": inner_inlines})

            last_end = match.end()

        # Add remaining text after last match (use simple to avoid infinite recursion)
        after = text[last_end:]
        if after:
            result.extend(self._convert_raw_text_simple(after))

        return result

    def _convert_raw_text_simple(self, text: str) -> list:
        """Convert raw text to Str and Space tokens (no emphasis fallback).

        This is the original text splitting logic, used to avoid infinite
        recursion when processing trailing text after a fallback emphasis match.
        """
        if not text:
            return []

        result = []
        parts = text.split(' ')

        for i, part in enumerate(parts):
            if part:
                result.append({"t": "Str", "c": part})
            if i < len(parts) - 1:
                result.append({"t": "Space"})

        return result

    def _convert_footnote_ref(self, elem) -> dict:
        """Convert FootnoteRef to Pandoc Note format."""
        # Get footnote label from the element (stored as 'label' attribute)
        label = getattr(elem, 'label', None)
        if not label:
            return None

        # Look up the footnote definition (keys are lowercase)
        footnote_def = self.footnotes.get(label.lower())
        if not footnote_def:
            # Footnote not found - return the reference as plain text
            return {"t": "Str", "c": f"[^{label}]"}

        # Convert footnote content to blocks
        blocks = []
        for child in footnote_def.children:
            block = self._convert_block(child)
            if block:
                blocks.append(block)

        # Pandoc Note format: {"t": "Note", "c": [blocks]}
        return {"t": "Note", "c": blocks}
