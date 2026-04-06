"""Tests for Quarto preprocessor and RawBlock/RawInline handling."""

import pytest
from md2hwpx.quarto_preprocessor import (
    strip_scoped_styles,
    convert_quarto_xrefs,
    convert_quarto_citations,
    convert_csl_bibliography,
    unwrap_quarto_divs,
    strip_remaining_html_inline,
    preprocess_quarto_full,
)


class TestStripScopedStyles:
    def test_removes_style_block(self):
        text = '<style scoped>.cls{color:red}</style>\nHello'
        assert strip_scoped_styles(text) == '\nHello'

    def test_removes_typed_style(self):
        text = '<style type="text/css">\n.x { font: bold }\n</style>rest'
        assert strip_scoped_styles(text) == 'rest'

    def test_removes_plain_style(self):
        text = 'before<style>.a{}</style>after'
        assert strip_scoped_styles(text) == 'beforeafter'

    def test_no_style_unchanged(self):
        text = 'No style here'
        assert strip_scoped_styles(text) == text


class TestConvertQuartoXrefs:
    def test_basic_xref(self):
        text = '<a href="#tbl-1" class="quarto-xref">표 1</a>'
        assert convert_quarto_xrefs(text) == '{{xref:tbl-1:표 1}}'

    def test_xref_with_extra_classes(self):
        text = '<a href="#fig-2" class="quarto-xref foo">Figure 2</a>'
        assert convert_quarto_xrefs(text) == '{{xref:fig-2:Figure 2}}'

    def test_no_xref_unchanged(self):
        text = '<a href="http://example.com">link</a>'
        assert convert_quarto_xrefs(text) == text


class TestConvertQuartoCitations:
    def test_basic_citation(self):
        text = '<span class="citation" data-cites="smith2020"><a href="#ref-smith2020">Smith, 2020</a></span>'
        result = convert_quarto_citations(text)
        assert '{{cite:smith2020:Smith, 2020}}' == result

    def test_citation_with_parens(self):
        text = '<span class="citation" data-cites="jones">(<a href="#ref-jones">Jones 2021</a>)</span>'
        result = convert_quarto_citations(text)
        assert '{{cite:jones:Jones 2021}}' == result

    def test_no_citation_unchanged(self):
        text = '<span class="other">text</span>'
        assert convert_quarto_citations(text) == text


class TestConvertCslBibliography:
    def test_basic_bibliography(self):
        text = '''Some text

<div id="refs" class="references">
<div id="ref-smith" class="csl-entry">Smith, J. (2020). Title. Journal.</div>
<div id="ref-jones" class="csl-entry">Jones, A. (2021). Another. Press.</div>
</div>

End'''
        result = convert_csl_bibliography(text)
        assert '{{bib-start}}' in result
        assert '{{bib:ref-smith:' in result
        assert '{{bib:ref-jones:' in result
        assert '{{bib-end}}' in result
        assert 'Smith, J. (2020)' in result

    def test_no_bibliography_unchanged(self):
        text = 'No bibliography here'
        assert convert_csl_bibliography(text) == text


class TestUnwrapQuartoDivs:
    def test_removes_figure_tags(self):
        text = '<figure class="quarto-figure">content</figure>'
        result = unwrap_quarto_divs(text)
        assert '<figure' not in result
        assert 'content' in result

    def test_figcaption_to_bold(self):
        text = '<figcaption>Caption text</figcaption>'
        result = unwrap_quarto_divs(text)
        assert '**Caption text**' in result

    def test_removes_tbl_div(self):
        text = '<div id="tbl-data" class="something">inner</div>'
        result = unwrap_quarto_divs(text)
        assert '<div' not in result
        assert 'inner' in result


class TestStripRemainingHtmlInline:
    def test_em_to_italic(self):
        assert '*text*' == strip_remaining_html_inline('<em>text</em>')

    def test_strong_to_bold(self):
        assert '**text**' == strip_remaining_html_inline('<strong>text</strong>')

    def test_link_to_text(self):
        result = strip_remaining_html_inline('<a href="url">link text</a>')
        assert 'link text' in result

    def test_span_to_text(self):
        result = strip_remaining_html_inline('<span class="x">inner</span>')
        assert 'inner' in result

    def test_code_to_backtick(self):
        result = strip_remaining_html_inline('<code>x = 1</code>')
        assert '`x = 1`' in result


class TestPreprocessQuartoFull:
    def test_full_pipeline(self):
        text = '''<style>.x{}</style>

<a href="#tbl-1" class="quarto-xref">Table 1</a>

<span class="citation" data-cites="key">(<a href="#ref-key">Author 2020</a>)</span>

<div id="refs">
<div id="ref-key" class="csl-entry">Author. (2020). Title.</div>
</div>

<figure class="quarto-figure">
<figcaption>My Caption</figcaption>
</figure>'''

        result = preprocess_quarto_full(text)
        # Style removed
        assert '<style' not in result
        # Xref converted
        assert '{{xref:tbl-1:Table 1}}' in result
        # Citation converted
        assert '{{cite:key:Author 2020}}' in result
        # Bibliography converted
        assert '{{bib-start}}' in result
        assert '{{bib:ref-key:' in result
        # Figure unwrapped
        assert '<figure' not in result
        assert '**My Caption**' in result


class TestHTMLTableConverter:
    """Tests for html_table_converter module."""

    def test_parse_simple_table(self):
        from md2hwpx.html_table_converter import _parse_html_table
        html = '''<table>
        <thead><tr><th>A</th><th>B</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>2</td></tr>
        <tr><td>3</td><td>4</td></tr>
        </tbody></table>'''
        result = _parse_html_table(html)
        assert result is not None
        assert result['col_count'] == 2
        assert len(result['headers']) == 1
        assert result['headers'][0] == ['A', 'B']
        assert len(result['rows']) == 2
        assert result['rows'][0] == ['1', '2']

    def test_parse_table_with_alignment(self):
        from md2hwpx.html_table_converter import _parse_html_table
        html = '''<table>
        <tr><th style="text-align: left">Left</th><th style="text-align: center">Center</th></tr>
        <tr><td>a</td><td>b</td></tr>
        </table>'''
        result = _parse_html_table(html)
        assert result is not None
        assert result['aligns'][0] == 'left'
        assert result['aligns'][1] == 'center'

    def test_parse_empty_table_returns_none(self):
        from md2hwpx.html_table_converter import _parse_html_table
        html = '<table></table>'
        result = _parse_html_table(html)
        assert result is None

    def test_to_pandoc_ast(self):
        from md2hwpx.html_table_converter import _parse_html_table, _to_pandoc_table_ast
        html = '''<table>
        <thead><tr><th>Name</th><th>Value</th></tr></thead>
        <tbody><tr><td>foo</td><td>bar</td></tr></tbody>
        </table>'''
        table_data = _parse_html_table(html)
        ast = _to_pandoc_table_ast(table_data)
        # ast = [caption, aligns, colwidths, header_cells, body_rows]
        assert len(ast) == 5
        assert len(ast[1]) == 2  # 2 alignment entries
        assert len(ast[3]) == 2  # 2 header cells
        assert len(ast[4]) == 1  # 1 body row

    def test_parse_table_no_thead(self):
        from md2hwpx.html_table_converter import _parse_html_table
        html = '''<table>
        <tr><th>H1</th><th>H2</th></tr>
        <tr><td>a</td><td>b</td></tr>
        </table>'''
        result = _parse_html_table(html)
        assert result is not None
        # th cells without thead should be treated as headers
        assert len(result['headers']) == 1
        assert result['headers'][0] == ['H1', 'H2']


class TestRawBlockHandler:
    """Tests for RawBlock handling in MarkdownToHwpx converter."""

    @pytest.fixture
    def converter(self):
        from md2hwpx.MarkdownToHwpx import MarkdownToHwpx
        return MarkdownToHwpx(json_ast={'blocks': [], 'meta': {}})

    def test_raw_block_style_skipped(self, converter):
        content = ['html', '<style>.cls { color: red; }</style>']
        result = converter._handle_raw_block(content)
        assert result == ''

    def test_raw_block_script_skipped(self, converter):
        content = ['html', '<script>alert("x")</script>']
        result = converter._handle_raw_block(content)
        assert result == ''

    def test_raw_block_comment_skipped(self, converter):
        content = ['html', '<!-- comment -->']
        result = converter._handle_raw_block(content)
        assert result == ''

    def test_raw_block_text_extracted(self, converter):
        content = ['html', '<div><p>Hello World</p></div>']
        result = converter._handle_raw_block(content)
        assert 'Hello' in result
        assert 'World' in result

    def test_raw_block_empty_html(self, converter):
        content = ['html', '<div></div>']
        result = converter._handle_raw_block(content)
        assert result == ''

    def test_raw_block_none_content(self, converter):
        result = converter._handle_raw_block(['html', ''])
        assert result == ''


class TestRawInlineHandler:
    """Tests for improved RawInline handling."""

    @pytest.fixture
    def converter(self):
        from md2hwpx.MarkdownToHwpx import MarkdownToHwpx
        return MarkdownToHwpx(json_ast={'blocks': [], 'meta': {}})

    def _process_raw_inline(self, converter, html_content):
        """Helper to process a single RawInline through the converter."""
        import xml.etree.ElementTree as ET
        parent = ET.Element('temp')
        inlines = [{'t': 'RawInline', 'c': ['html', html_content]}]
        converter._process_inlines_to_elems(inlines, parent)
        return ET.tostring(parent, encoding='unicode')

    def test_br_tag(self, converter):
        result = self._process_raw_inline(converter, '<br>')
        assert 'lineBreak' in result

    def test_sub_tag(self, converter):
        result = self._process_raw_inline(converter, '<sub>2</sub>')
        assert '2' in result

    def test_sup_tag(self, converter):
        result = self._process_raw_inline(converter, '<sup>n</sup>')
        assert 'n' in result

    def test_a_tag_hyperlink(self, converter):
        result = self._process_raw_inline(converter, '<a href="http://example.com">Example</a>')
        assert 'Example' in result
        assert 'HYPERLINK' in result

    def test_fallback_text_extraction(self, converter):
        result = self._process_raw_inline(converter, '<span class="x">some text</span>')
        assert 'some' in result
        assert 'text' in result

    def test_quarto_marker(self, converter):
        result = self._process_raw_inline(converter, '{{xref:tbl-1:Table 1}}')
        assert 'Table' in result
        assert '1' in result


class TestTextToInlines:
    """Tests for _text_to_inlines helper."""

    @pytest.fixture
    def converter(self):
        from md2hwpx.MarkdownToHwpx import MarkdownToHwpx
        return MarkdownToHwpx(json_ast={'blocks': [], 'meta': {}})

    def test_plain_text(self, converter):
        inlines = converter._text_to_inlines('Hello World')
        types = [i['t'] for i in inlines]
        assert 'Str' in types
        assert 'Space' in types

    def test_xref_marker(self, converter):
        inlines = converter._text_to_inlines('See {{xref:tbl-1:Table 1}} above')
        texts = [i['c'] for i in inlines if i['t'] == 'Str']
        assert 'Table 1' in texts
        assert 'See' in texts

    def test_cite_marker(self, converter):
        inlines = converter._text_to_inlines('{{cite:smith:Smith 2020}}')
        texts = [i['c'] for i in inlines if i['t'] == 'Str']
        assert '(Smith 2020)' in texts

    def test_bib_marker(self, converter):
        inlines = converter._text_to_inlines('{{bib:ref-smith:Smith, J. (2020). Title.}}')
        texts = [i['c'] for i in inlines if i['t'] == 'Str']
        assert any('Smith' in t for t in texts)
