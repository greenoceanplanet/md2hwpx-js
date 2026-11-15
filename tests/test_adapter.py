"""Tests for MarkoToPandocAdapter."""

import pytest
from md2hwpx.marko_adapter import MarkoToPandocAdapter


class TestAdapterBasicParsing:
    """Test basic parsing and AST structure."""

    def test_empty_document(self, adapter):
        result = adapter.parse("")
        assert result['blocks'] == []
        assert 'meta' in result

    def test_single_paragraph(self, adapter):
        result = adapter.parse("Hello world")
        blocks = result['blocks']
        assert len(blocks) == 1
        assert blocks[0]['t'] == 'Para'

    def test_multiple_paragraphs(self, adapter):
        result = adapter.parse("First paragraph.\n\nSecond paragraph.")
        blocks = result['blocks']
        assert len(blocks) == 2
        assert all(b['t'] == 'Para' for b in blocks)


class TestAdapterHeaders:
    """Test header parsing at all levels."""

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
    def test_standard_headers(self, adapter, level):
        md = "#" * level + " Header Text"
        result = adapter.parse(md)
        blocks = result['blocks']
        assert len(blocks) == 1
        assert blocks[0]['t'] == 'Header'
        assert blocks[0]['c'][0] == level

    @pytest.mark.parametrize("level", [7, 8, 9])
    def test_extended_headers(self, adapter, level):
        md = "#" * level + " Extended Header"
        result = adapter.parse(md)
        blocks = result['blocks']
        assert len(blocks) == 1
        assert blocks[0]['t'] == 'Header'
        assert blocks[0]['c'][0] == level

    def test_header_content_is_inline(self, adapter):
        result = adapter.parse("# Hello **bold** world")
        header = result['blocks'][0]
        inlines = header['c'][2]
        types = [i['t'] for i in inlines]
        assert 'Str' in types
        assert 'Strong' in types


class TestAdapterInlineFormatting:
    """Test inline formatting elements."""

    def test_bold(self, adapter):
        result = adapter.parse("**bold**")
        para = result['blocks'][0]
        inlines = para['c']
        assert any(i.get('t') == 'Strong' for i in inlines)

    def test_italic(self, adapter):
        # Emph mixed with other inline content stays a plain Emph node.
        # (A paragraph that is *only* "*italic*" is the "source-note"
        # convention — see TestSourceNoteParagraph below — and gets
        # unwrapped/tagged instead.)
        result = adapter.parse("plain *italic* text")
        para = result['blocks'][0]
        inlines = para['c']
        assert any(i.get('t') == 'Emph' for i in inlines)

    def test_strikethrough(self, adapter):
        result = adapter.parse("~~deleted~~")
        para = result['blocks'][0]
        inlines = para['c']
        assert any(i.get('t') == 'Strikeout' for i in inlines)

    def test_inline_code(self, adapter):
        result = adapter.parse("`code`")
        para = result['blocks'][0]
        inlines = para['c']
        assert any(i.get('t') == 'Code' for i in inlines)

    def test_link(self, adapter):
        result = adapter.parse("[text](https://example.com)")
        para = result['blocks'][0]
        inlines = para['c']
        link = next(i for i in inlines if i.get('t') == 'Link')
        assert link['c'][2][0] == 'https://example.com'

    def test_image(self, adapter):
        result = adapter.parse("![alt](image.png)")
        para = result['blocks'][0]
        inlines = para['c']
        img = next(i for i in inlines if i.get('t') == 'Image')
        assert img['c'][2][0] == 'image.png'


class TestAdapterLists:
    """Test list parsing."""

    def test_bullet_list(self, adapter):
        md = "- Item 1\n- Item 2\n- Item 3"
        result = adapter.parse(md)
        blocks = result['blocks']
        assert len(blocks) == 1
        assert blocks[0]['t'] == 'BulletList'
        assert len(blocks[0]['c']) == 3

    def test_ordered_list(self, adapter):
        md = "1. First\n2. Second\n3. Third"
        result = adapter.parse(md)
        blocks = result['blocks']
        assert len(blocks) == 1
        assert blocks[0]['t'] == 'OrderedList'
        items = blocks[0]['c'][1]
        assert len(items) == 3

    def test_ordered_list_start_number(self, adapter):
        md = "3. Third\n4. Fourth"
        result = adapter.parse(md)
        block = result['blocks'][0]
        assert block['t'] == 'OrderedList'
        start_num = block['c'][0][0]
        assert start_num == 3

    def test_nested_bullet_list(self, adapter):
        md = "- Item 1\n    - Nested A\n    - Nested B\n- Item 2"
        result = adapter.parse(md)
        block = result['blocks'][0]
        assert block['t'] == 'BulletList'
        # First item should have sub-items
        first_item_blocks = block['c'][0]
        has_nested = any(b['t'] == 'BulletList' for b in first_item_blocks)
        assert has_nested


class TestAdapterTable:
    """Test table parsing."""

    def test_simple_table(self, adapter):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = adapter.parse(md)
        blocks = result['blocks']
        assert len(blocks) == 1
        assert blocks[0]['t'] == 'Table'

    def test_table_structure(self, adapter):
        md = "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |"
        result = adapter.parse(md)
        table = result['blocks'][0]
        content = table['c']
        specs = content[2]
        assert len(specs) == 3  # 3 columns

        head = content[3]
        head_rows = head[1]
        assert len(head_rows) == 1  # 1 header row

        bodies = content[4]
        assert len(bodies) >= 1
        body_rows = bodies[0][3]
        assert len(body_rows) == 1  # 1 body row

    def test_table_multiple_body_rows(self, adapter):
        md = "| H1 | H2 |\n|---|---|\n| A | B |\n| C | D |\n| E | F |"
        result = adapter.parse(md)
        table = result['blocks'][0]
        bodies = table['c'][4]
        body_rows = bodies[0][3]
        assert len(body_rows) == 3

    def test_table_alignment_specs(self, adapter):
        md = "| Left | Center | Right |\n|:-----|:------:|------:|\n| a | b | c |"
        result = adapter.parse(md)
        table = result['blocks'][0]
        specs = table['c'][2]
        assert specs[0][0] == 'AlignLeft'
        assert specs[1][0] == 'AlignCenter'
        assert specs[2][0] == 'AlignRight'

    def test_table_alignment_cells(self, adapter):
        md = "| Left | Center | Right |\n|:-----|:------:|------:|\n| a | b | c |"
        result = adapter.parse(md)
        table = result['blocks'][0]
        # Check body row cell alignment
        body_rows = table['c'][4][0][3]
        cells = body_rows[0][1]
        assert cells[0][1] == 'AlignLeft'
        assert cells[1][1] == 'AlignCenter'
        assert cells[2][1] == 'AlignRight'

    def test_table_default_alignment(self, adapter):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = adapter.parse(md)
        table = result['blocks'][0]
        specs = table['c'][2]
        assert specs[0][0] == 'AlignDefault'
        assert specs[1][0] == 'AlignDefault'


class TestAdapterCodeBlock:
    """Test code block parsing."""

    def test_fenced_code(self, adapter):
        md = "```python\nprint('hello')\n```"
        result = adapter.parse(md)
        blocks = result['blocks']
        assert len(blocks) == 1
        assert blocks[0]['t'] == 'CodeBlock'

    def test_fenced_code_language(self, adapter):
        md = "```python\ncode\n```"
        result = adapter.parse(md)
        block = result['blocks'][0]
        classes = block['c'][0][1]
        assert 'python' in classes


class TestAdapterFootnotes:
    """Test footnote parsing."""

    def test_footnote_ref(self, adapter):
        md = "Text with footnote[^1].\n\n[^1]: Footnote content here."
        result = adapter.parse(md)
        para = result['blocks'][0]
        inlines = para['c']
        has_note = any(i.get('t') == 'Note' for i in inlines)
        assert has_note

    def test_footnote_content(self, adapter):
        md = "Text[^fn1].\n\n[^fn1]: The footnote body."
        result = adapter.parse(md)
        para = result['blocks'][0]
        note = next(i for i in para['c'] if i.get('t') == 'Note')
        blocks = note['c']
        assert len(blocks) > 0


class TestAdapterSpecialChars:
    """Test special character handling."""

    def test_unicode_text(self, adapter):
        result = adapter.parse("한글 테스트입니다.")
        para = result['blocks'][0]
        assert para['t'] == 'Para'

    def test_ampersand_in_text(self, adapter):
        result = adapter.parse("A & B")
        para = result['blocks'][0]
        inlines = para['c']
        text_parts = [i['c'] for i in inlines if i.get('t') == 'Str']
        assert any('&' in t for t in text_parts)

    def test_angle_brackets(self, adapter):
        result = adapter.parse("a < b > c")
        para = result['blocks'][0]
        inlines = para['c']
        text_parts = [i['c'] for i in inlines if i.get('t') == 'Str']
        full_text = ' '.join(text_parts)
        assert '<' in full_text or '&lt;' in full_text


class TestAdapterBlockQuote:
    """Test block quote parsing."""

    def test_blockquote(self, adapter):
        result = adapter.parse("> This is a quote.")
        blocks = result['blocks']
        assert len(blocks) == 1
        assert blocks[0]['t'] == 'BlockQuote'

    def test_blockquote_content(self, adapter):
        result = adapter.parse("> Quoted text here.")
        bq = result['blocks'][0]
        inner_blocks = bq['c']
        assert len(inner_blocks) > 0
        assert inner_blocks[0]['t'] == 'Para'


class TestAdapterHorizontalRule:
    """Test horizontal rule parsing."""

    def test_horizontal_rule(self, adapter):
        result = adapter.parse("---")
        blocks = result['blocks']
        assert len(blocks) == 1
        assert blocks[0]['t'] == 'HorizontalRule'


class TestAdapterFallbackEmphasis:
    """Test fallback emphasis parsing for CommonMark edge cases.

    When bold/italic text ends with punctuation (e.g., ')') and is
    immediately followed by a word character (e.g., Korean '를'),
    Marko's CommonMark parser fails to recognize the closing delimiter.
    The fallback parser in _convert_raw_text() handles these cases.
    """

    def test_bold_before_korean_with_paren(self, adapter):
        """Bold ending with ')' followed by Korean character."""
        result = adapter.parse("**맞춤형 보고서(Tailored Report)**를")
        inlines = result['blocks'][0]['c']
        assert any(i.get('t') == 'Strong' for i in inlines)
        # Verify the trailing text is separate
        str_tokens = [i for i in inlines if i.get('t') == 'Str']
        assert any(i['c'] == '를' for i in str_tokens)

    def test_bold_paren_followed_by_word(self, adapter):
        """Bold ending with ')' followed by ASCII word character."""
        result = adapter.parse("**hello(world)**text")
        inlines = result['blocks'][0]['c']
        assert any(i.get('t') == 'Strong' for i in inlines)

    def test_bold_bracket_followed_by_word(self, adapter):
        """Bold ending with ']' followed by word character."""
        result = adapter.parse("**item[1]**값")
        inlines = result['blocks'][0]['c']
        assert any(i.get('t') == 'Strong' for i in inlines)

    def test_bold_period_followed_by_word(self, adapter):
        """Bold ending with '.' followed by word character."""
        result = adapter.parse("**v1.0**release")
        inlines = result['blocks'][0]['c']
        assert any(i.get('t') == 'Strong' for i in inlines)

    def test_multiple_bold_in_sentence(self, adapter):
        """Multiple bold sections, one requiring fallback."""
        result = adapter.parse(
            "갖춘 **보고서(Report)**를 생성 **슬라이드** 제작"
        )
        inlines = result['blocks'][0]['c']
        strong_tokens = [i for i in inlines if i.get('t') == 'Strong']
        assert len(strong_tokens) == 2

    def test_normal_bold_unaffected(self, adapter):
        """Normal bold (space after closing **) still works."""
        result = adapter.parse("**bold** text")
        inlines = result['blocks'][0]['c']
        assert any(i.get('t') == 'Strong' for i in inlines)
        strong = next(i for i in inlines if i.get('t') == 'Strong')
        str_in_strong = [s for s in strong['c'] if s.get('t') == 'Str']
        assert any(s['c'] == 'bold' for s in str_in_strong)

    def test_no_false_positive_on_plain_text(self, adapter):
        """Plain text without emphasis markers is unaffected."""
        result = adapter.parse("plain text without bold")
        inlines = result['blocks'][0]['c']
        assert not any(i.get('t') == 'Strong' for i in inlines)

    def test_bold_content_preserved(self, adapter):
        """Verify the content inside fallback bold is correct."""
        result = adapter.parse("**Report)**를")
        inlines = result['blocks'][0]['c']
        strong = next(i for i in inlines if i.get('t') == 'Strong')
        inner_strs = [s['c'] for s in strong['c'] if s.get('t') == 'Str']
        assert 'Report)' in inner_strs


class TestQuartoPreprocessing:
    """Test Quarto/Pandoc preprocessing features."""

    def _make_adapter(self, **kwargs):
        from md2hwpx.config import ConversionConfig
        config = ConversionConfig()
        for k, v in kwargs.items():
            setattr(config, k.upper(), v)
        return MarkoToPandocAdapter(config=config)

    def test_strip_fenced_divs_basic(self):
        adapter = self._make_adapter(strip_fenced_divs=True)
        md = "::: {.cell}\nHello world\n:::"
        result = adapter.parse(md)
        assert len(result['blocks']) == 1
        assert result['blocks'][0]['t'] == 'Para'

    def test_strip_fenced_divs_nested(self):
        adapter = self._make_adapter(strip_fenced_divs=True)
        md = "::::: {.cell execution_count=\"2\"}\n:::: {.cell-output}\n::: {}\nContent here\n:::\n::::\n:::::"
        result = adapter.parse(md)
        assert len(result['blocks']) == 1
        assert result['blocks'][0]['t'] == 'Para'

    def test_strip_fenced_divs_preserves_content(self):
        adapter = self._make_adapter(strip_fenced_divs=True)
        md = "::: {.cell}\n\n# Header\n\nParagraph text\n\n:::"
        result = adapter.parse(md)
        types = [b['t'] for b in result['blocks']]
        assert 'Header' in types
        assert 'Para' in types

    def test_strip_pandoc_attributes(self):
        adapter = self._make_adapter(strip_pandoc_attributes=True)
        md = "[표 1](#tbl-litreview){.quarto-xref}"
        result = adapter.parse(md)
        blocks = result['blocks']
        assert len(blocks) == 1
        inlines = blocks[0]['c']
        link = [i for i in inlines if i.get('t') == 'Link']
        assert len(link) == 1

    def test_strip_pandoc_attributes_preserves_math(self):
        """Pandoc attribute removal must not touch {} inside $...$."""
        adapter = self._make_adapter(strip_pandoc_attributes=True, math_handling='italic')
        md = "The value $x_{i}$ is important{.note}"
        result = adapter.parse(md)
        inlines = result['blocks'][0]['c']
        # Should have Emph for math (containing x_{i})
        emph_items = [i for i in inlines if i.get('t') == 'Emph']
        assert len(emph_items) >= 1
        # {.note} should be stripped (not appear as text)
        all_text = ''
        for i in inlines:
            if i.get('t') == 'Str':
                all_text += i['c']
        assert '{.note}' not in all_text

    def test_strip_html_style(self):
        adapter = self._make_adapter(strip_html_style_blocks=True)
        md = "<style scoped>\n.dataframe { color: red; }\n</style>\n\nHello"
        result = adapter.parse(md)
        # Only the paragraph should remain
        para_blocks = [b for b in result['blocks'] if b['t'] == 'Para']
        assert len(para_blocks) == 1

    def test_strip_cell_code(self):
        adapter = self._make_adapter(strip_cell_code_blocks=True)
        md = "``` {.python .cell-code}\nimport os\nprint('hello')\n```\n\nOutput text"
        result = adapter.parse(md)
        # Code block should be gone, only paragraph remains
        types = [b['t'] for b in result['blocks']]
        assert 'CodeBlock' not in types
        assert 'Para' in types

    def test_strip_cell_code_preserves_normal_code(self):
        adapter = self._make_adapter(strip_cell_code_blocks=True)
        md = "```python\nprint('hello')\n```\n\nText"
        result = adapter.parse(md)
        types = [b['t'] for b in result['blocks']]
        assert 'CodeBlock' in types

    def test_inline_math_becomes_italic(self):
        adapter = self._make_adapter(math_handling='italic')
        md = "The formula $E = mc^2$ is famous."
        result = adapter.parse(md)
        inlines = result['blocks'][0]['c']
        emph_items = [i for i in inlines if i.get('t') == 'Emph']
        assert len(emph_items) >= 1

    def test_block_math_becomes_paragraph(self):
        adapter = self._make_adapter(math_handling='italic')
        md = "Text before\n\n$$\nE = mc^2\n$$\n\nText after"
        result = adapter.parse(md)
        assert len(result['blocks']) == 3
        # Middle block should be a Para with Emph content
        mid = result['blocks'][1]
        assert mid['t'] == 'Para'
        assert any(i.get('t') == 'Emph' for i in mid['c'])

    def test_backward_compat_default_config(self):
        """Default config (all off) should not alter behavior."""
        adapter = MarkoToPandocAdapter()
        md = "::: {.cell}\n[text](url){.class}\n:::\n\n<style>.x{}</style>"
        result = adapter.parse(md)
        # Fenced divs become paragraphs with ::: text or are parsed by Marko
        # The key point: no error and blocks are produced
        assert len(result['blocks']) >= 1

    def test_combined_quarto_preprocessing(self):
        """Test all preprocessing features together on realistic Quarto output."""
        from md2hwpx.config import ConversionConfig
        config = ConversionConfig()
        config.enable_quarto_defaults()
        adapter = MarkoToPandocAdapter(config=config)

        md = """\
::: {.cell execution_count="1"}
``` {.python .cell-code}
import pandas as pd
df = pd.read_csv("data.csv")
```
:::

The result is $x_i = 2$.

::: {.cell-output-display}

| A | B |
|---|---|
| 1 | 2 |

:::

See [Section 1](#sec-intro){.quarto-xref} for details.

<style scoped>
.dataframe { color: red; }
</style>

$$
Y = \\beta_0 + \\beta_1 X
$$
"""
        result = adapter.parse(md)
        types = [b['t'] for b in result['blocks']]

        # Code block should be stripped
        assert 'CodeBlock' not in types
        # Table should survive
        assert 'Table' in types
        # Should have paragraphs (including math blocks)
        assert 'Para' in types


class TestMathHwceMode:
    """Test math='hwce' mode produces Math AST nodes."""

    def _make_adapter(self, **kwargs):
        from md2hwpx.config import ConversionConfig
        config = ConversionConfig()
        for k, v in kwargs.items():
            setattr(config, k.upper(), v)
        return MarkoToPandocAdapter(config=config)

    def test_inline_math_becomes_math_node(self):
        adapter = self._make_adapter(math_handling='hwce')
        md = "The formula $E = mc^2$ is famous."
        result = adapter.parse(md)
        inlines = result['blocks'][0]['c']
        maths = [i for i in inlines if i.get('t') == 'Math']
        assert len(maths) == 1
        assert maths[0]['c'][0] == 'InlineMath'
        assert maths[0]['c'][1] == 'E = mc^2'

    def test_block_math_becomes_display_math_node(self):
        adapter = self._make_adapter(math_handling='hwce')
        md = "Text before\n\n$$\nE = mc^2\n$$\n\nText after"
        result = adapter.parse(md)
        mid = result['blocks'][1]
        assert mid['t'] == 'Para'
        maths = [i for i in mid['c'] if i.get('t') == 'Math']
        assert len(maths) == 1
        assert maths[0]['c'][0] == 'DisplayMath'
        assert maths[0]['c'][1] == 'E = mc^2'

    def test_inline_math_preserves_latex(self):
        adapter = self._make_adapter(math_handling='hwce')
        md = "Value $\\beta_1$ here."
        result = adapter.parse(md)
        inlines = result['blocks'][0]['c']
        maths = [i for i in inlines if i.get('t') == 'Math']
        assert len(maths) == 1
        assert '\\beta_1' in maths[0]['c'][1]

    def test_multiple_inline_math(self):
        adapter = self._make_adapter(math_handling='hwce')
        md = "Both $x$ and $y$ are variables."
        result = adapter.parse(md)
        inlines = result['blocks'][0]['c']
        maths = [i for i in inlines if i.get('t') == 'Math']
        assert len(maths) == 2

    def test_hwce_mode_does_not_affect_normal_images(self):
        adapter = self._make_adapter(math_handling='hwce')
        md = "![alt](image.png)\n\nValue $x$ here."
        result = adapter.parse(md)
        blocks = result['blocks']
        first_images = [i for i in blocks[0]['c'] if i.get('t') == 'Image']
        assert first_images[0]['c'][2][0] == 'image.png'
        second_maths = [i for i in blocks[1]['c'] if i.get('t') == 'Math']
        assert len(second_maths) == 1
        assert second_maths[0]['c'][0] == 'InlineMath'

    def test_math_in_header(self):
        adapter = self._make_adapter(math_handling='hwce')
        md = "### 종속변수 ($Y$)"
        result = adapter.parse(md)
        header = result['blocks'][0]
        assert header['t'] == 'Header'
        inlines = header['c'][2]
        maths = [i for i in inlines if i.get('t') == 'Math']
        assert len(maths) == 1


class TestSourceNoteParagraph:
    """A Para whose ENTIRE content is a single Emph (e.g. a standalone
    "*자료: ...*" caption line right after a chart image or table) is the
    "source-note" convention shared with the web (`p.source-note`) and PDF
    (`source-note()` Typst function) builds. It must come out unwrapped
    (no nested Emph, so MarkdownToHwpx.py doesn't double-apply italic) and
    tagged with `sourceNote: True` so the renderer can style it distinctly.
    """

    def test_standalone_emphasis_paragraph_is_tagged(self, adapter):
        result = adapter.parse("*자료: 국토교통부 토지소유현황.*")
        blocks = result['blocks']
        assert len(blocks) == 1
        para = blocks[0]
        assert para['t'] == 'Para'
        assert para.get('sourceNote') is True
        # Emph should be unwrapped, not left nested inside 'c'
        assert not any(i.get('t') == 'Emph' for i in para['c'])
        assert any(i.get('t') == 'Str' for i in para['c'])

    def test_mixed_emphasis_paragraph_is_not_tagged(self, adapter):
        # Emph alongside other inline content mid-sentence must NOT be
        # treated as a source-note.
        result = adapter.parse("설명 *강조* 계속.")
        para = result['blocks'][0]
        assert para['t'] == 'Para'
        assert 'sourceNote' not in para
        assert any(i.get('t') == 'Emph' for i in para['c'])

    def test_bold_only_paragraph_is_not_tagged(self, adapter):
        # Only a *whole-paragraph Emph* qualifies — Strong (bold) is a
        # different convention and must be left alone.
        result = adapter.parse("**bold only**")
        para = result['blocks'][0]
        assert para['t'] == 'Para'
        assert 'sourceNote' not in para
        assert any(i.get('t') == 'Strong' for i in para['c'])

    def test_extended_header_placeholder_not_affected(self, adapter):
        # Order-of-operations regression guard: extended header (7-9)
        # restoration keys off a single-Str Para, which is unrelated to
        # the single-Emph source-note check and must still work.
        result = adapter.parse("####### Extended Header")
        blocks = result['blocks']
        assert any(b['t'] == 'Header' and b['c'][0] == 7 for b in blocks)


class TestAdapterHtmlScriptTags:
    """<sup>/<sub> inline HTML is split into separate tokens by Marko; adapter pairs them."""

    def _para(self, adapter, md):
        return adapter.parse(md)['blocks'][0]['c']

    def test_sup_in_paragraph(self, adapter):
        inl = self._para(adapter, "자금<sup>1)</sup> 끝")
        sup = [x for x in inl if x['t'] == 'Superscript']
        assert len(sup) == 1
        assert sup[0]['c'] == [{"t": "Str", "c": "1)"}]
        assert not any(x['t'] == 'RawInline' for x in inl)

    def test_sub_in_paragraph(self, adapter):
        inl = self._para(adapter, "H<sub>2</sub>O")
        assert any(x['t'] == 'Subscript' for x in inl)

    def test_sup_in_table_cell(self, adapter):
        md = "| a | b |\n|---|---|\n| 초기 자금<sup>1)</sup> | 4 |\n"
        import json
        s = json.dumps(adapter.parse(md), ensure_ascii=False)
        assert '"Superscript"' in s
        assert '<sup>' not in s

    def test_unmatched_tag_kept(self, adapter):
        inl = self._para(adapter, "a<sup>b")
        assert not any(x['t'] == 'Superscript' for x in inl)
