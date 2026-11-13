# CLAUDE.md - Project Guide for Claude Code

## Project Overview

**md2hwpx** is a Python tool that converts Markdown documents to Korean Hancom Office HWPX format. It works as both a **CLI tool** and a **Python library**. It uses the Marko library to parse Markdown and generates HWPX output directly (Pandoc-free).

## Quick Commands

```bash
# Install for development
pip install -e .

# CLI usage
md2hwpx <input.md> -o <output.hwpx> [-r <ref.hwpx>]

# Examples
md2hwpx test.md -o output.hwpx
md2hwpx test.md -r custom.hwpx -o output.hwpx
md2hwpx test.md --reference-doc=custom.hwpx -o output.hwpx

# Debug outputs (JSON AST intermediate format)
md2hwpx test.md -o debug.json

# Run tests
pytest tests/ -v
```

### Library API

```python
from md2hwpx import convert_string

# Convert a markdown string to HWPX file
convert_string("# Hello\n\nWorld", "output.hwpx")

# With a custom template
convert_string("# Hello\n\nWorld", "output.hwpx", reference_doc="template.hwpx")
```

## Project Structure

```
md2hwpx/
├── md2hwpx/                   # Main package
│   ├── __init__.py            # Package exports
│   ├── __main__.py            # Module entry point (python -m md2hwpx)
│   ├── cli.py                 # CLI entry point
│   ├── converter_api.py       # Library API (convert_string)
│   ├── insert.py              # Insert mode: md → section of an EXISTING hwpx (insert_markdown)
│   ├── MarkdownToHwpx.py      # Core HWPX conversion engine
│   ├── MarkdownToHtml.py      # HTML conversion (for debugging)
│   ├── marko_adapter.py       # Marko AST to Pandoc-like format adapter
│   ├── math_renderer.py       # Math rendering: MathRenderer ABC + HwceMathRenderer
│   ├── latex_to_hwce.py       # LaTeX → Hancom equation script converter
│   ├── frontmatter_parser.py  # YAML frontmatter parsing
│   ├── quarto_preprocessor.py  # Quarto HTML preprocessing (xrefs, citations, bib, divs)
│   ├── html_table_converter.py # HTML table → HWPX native table converter
│   ├── config.py              # Configuration constants (ConversionConfig)
│   ├── exceptions.py          # Custom exception hierarchy
│   └── blank.hwpx             # Default reference template
├── templates/                 # User-facing template files
│   ├── gov_template.hwpx      # Government document template
│   └── placeholder-template.hwpx  # Template with style placeholders
├── samples/                   # Sample files
├── tests/                     # Automated test suite (pytest)
│   ├── conftest.py            # Shared fixtures
│   ├── test_adapter.py        # Marko adapter tests
│   ├── test_api.py            # Library API tests
│   ├── test_cli.py            # CLI integration tests
│   ├── test_converter.py      # Core converter tests
│   ├── test_latex_to_hwce.py  # LaTeX to Hancom equation converter tests
│   ├── test_math_renderer.py  # Math renderer tests
│   ├── test_preprocessor.py   # Quarto preprocessor, HTML table, RawBlock/RawInline tests
│   └── test_security.py       # Security validation tests
├── CLAUDE.md                  # This file (Claude Code guide)
├── README.md                  # User documentation (Korean)
├── setup.py                   # Package configuration
└── pyproject.toml             # Package metadata
```

## Key Files to Understand

| File | Purpose |
|------|---------|
| `md2hwpx/MarkdownToHwpx.py` | Core HWPX conversion engine |
| `md2hwpx/marko_adapter.py` | Converts Marko AST to Pandoc-like dict format |
| `md2hwpx/math_renderer.py` | Pluggable math rendering (MathRenderer ABC, HwceMathRenderer) |
| `md2hwpx/latex_to_hwce.py` | LaTeX → Hancom equation script converter (70+ symbols, structural rules) |
| `md2hwpx/converter_api.py` | Library API (`convert_string()`) |
| `md2hwpx/config.py` | All configuration constants (`ConversionConfig`) |
| `md2hwpx/exceptions.py` | Custom exception hierarchy |
| `md2hwpx/quarto_preprocessor.py` | Quarto HTML preprocessing (xrefs, citations, bib, div unwrap) |
| `md2hwpx/html_table_converter.py` | HTML `<table>` → HWPX native table converter |
| `md2hwpx/frontmatter_parser.py` | Parses YAML frontmatter metadata |
| `md2hwpx/cli.py` | CLI argument parsing and orchestration |
| `md2hwpx/blank.hwpx` | Default template with styles |

## Dependencies

- **Python**: 3.6+
- **marko**: Markdown parser
- **python-frontmatter**: YAML frontmatter parsing
- **Pillow**: Image processing

## Architecture Summary

```
                    CLI                          Library API
                     │                               │
          md2hwpx input.md -o out.hwpx    convert_string(md, "out.hwpx")
                     │                               │
                     └───────────┬───────────────────┘
                                 ▼
                    Marko Parser → Marko AST
                                 ▼
                    MarkoToPandocAdapter → Pandoc-like AST
                                 ▼
                    MarkdownToHwpx Converter ← Reference HWPX (styles, page setup)
                                 ▼                    ← ConversionConfig (defaults)
                           HWPX ZIP output
```

### Conversion Pipeline

1. `marko` parses Markdown into an AST
2. `marko_adapter.py` converts Marko AST to Pandoc-like dict format (with preprocessing for extended headers, table dash counts, Quarto cleanup, and math extraction)
3. Reference HWPX (ZIP) provides styles from `header.xml` and page setup from `section0.xml`
4. Template placeholders (e.g., `{{H1}}`, `{{BODY}}`) are extracted for style mapping
5. AST blocks (paragraphs, headers, tables, lists) mapped to HWPX XML
6. Math expressions rendered via `HwceMathRenderer` → native `<hp:equation>` elements
7. Images extracted and embedded into HWPX `BinData/` directory
8. Output ZIP created with all components

## HWPX Format Basics

HWPX is a ZIP archive containing:
- `Contents/header.xml` - Style definitions
- `Contents/section0.xml` - Document body
- `Contents/content.hpf` - Package manifest
- `BinData/` - Embedded images
- `META-INF/` - Package metadata

### Key XML Namespaces

| Prefix | Purpose | URI |
|--------|---------|-----|
| `hh` | Head (styles) | `http://www.hancom.co.kr/hwpml/2011/head` |
| `hp` | Paragraph (body) | `http://www.hancom.co.kr/hwpml/2011/paragraph` |
| `hc` | Core (common) | `http://www.hancom.co.kr/hwpml/2011/core` |
| `hs` | Section | `http://www.hancom.co.kr/hwpml/2011/section` |

## Code Patterns

### Adding New Block Handler

In `MarkdownToHwpx.py`, handlers follow this pattern:
```python
def _handle_blocktype(self, content):
    # 1. Create paragraph start
    xml = self._create_para_start(style_id=..., para_pr_id=...)

    # 2. Process inline content
    xml += self._process_inlines(content, base_char_pr_id=...)

    # 3. Close paragraph
    xml += '</hp:p>'
    return xml
```

### Style System

- Styles from reference HWPX are parsed into `self.dynamic_style_map` dict
- Character properties cached with `_get_char_pr_id()`
- Placeholder-based styling supported (e.g., `{{H1}}`, `{{BODY}}` in template)
- Users can customize styles by editing the template HWPX in Hancom Office (WYSIWYG)

### Template Placeholders

Templates can contain placeholder text to define styles for output elements. The converter extracts style IDs (`paraPrIDRef`, `charPrIDRef`, `styleIDRef`) from paragraphs containing these placeholders:

| Placeholder | Purpose |
|-------------|---------|
| `{{H1}}`–`{{H9}}` | Header levels 1–9 |
| `{{BODY}}` | Body paragraph style |
| `{{CELL_HEADER}}` | Table header cell style |
| `{{CELL_BODY}}` | Table body cell style |
| `{{LIST_BULLET_1}}`–`{{LIST_BULLET_7}}` | Bullet list levels |
| `{{LIST_ORDERED_1}}`–`{{LIST_ORDERED_7}}` | Ordered list levels |

Placeholders can appear in plain paragraphs, inside table cells, or as prefix text in table rows. Headers support three rendering modes: `table` (header in a table row), `prefix` (text prefix before header), and `plain` (standalone paragraph).

### Extended Header Levels (7-9)

Standard Markdown only supports header levels 1-6. md2hwpx extends this to support levels 7-9:
- `marko_adapter.py` preprocesses `#######`, `########`, `#########` lines
- Converts them to placeholders before Marko parsing
- Restores them as Header blocks with levels 7, 8, 9 after parsing

### Proportional Table Column Widths

Table column widths are derived from the dash counts in the markdown separator line:

```markdown
| Narrow | Wide Column         | Narrow |
|--------|---------------------|--------|
| a      | b                   | c      |
```

Dashes: 8 : 21 : 8 → proportional widths: 22% : 57% : 22% of total table width.

- `marko_adapter.py` preprocesses dash counts in `_preprocess_table_dashes()` before Marko parsing
- Stored as `ColWidth` (proportional) in colspecs; equal-dash tables use `ColWidthDefault`
- Total table width is extracted from the template's `hp:sz width` attribute when available, falling back to `config.TABLE_WIDTH`

### Configuration System

`config.py` provides `ConversionConfig` with all default values:
- Table layout (width, margins, borders)
- List indentation and bullet characters
- Image size limits
- Block quote indentation
- Link styling
- Math handling (`MATH_HANDLING`: `'hwce'` default, `'italic'`, or `'none'`)
- Quarto/Pandoc preprocessing toggles
- Security limits (file size, nesting depth, image count)

Override via `DEFAULT_CONFIG` or pass a custom `ConversionConfig` instance.

### Exception Hierarchy

```
HwpxError (base)
├── TemplateError      # Reference template issues
├── ImageError         # Image processing failures
├── StyleError         # Style parsing issues
├── ConversionError    # General conversion failures
└── SecurityError      # Path traversal, size limits, etc.
```

### Security

- Input file size validation (`MAX_INPUT_FILE_SIZE`)
- Template file size validation (`MAX_TEMPLATE_FILE_SIZE`)
- Image path traversal prevention (rejects absolute paths and `..`)
- Nesting depth limits for lists and block quotes (`MAX_NESTING_DEPTH`)
- Image count limits (`MAX_IMAGE_COUNT`)

### Marko Adapter

The adapter (`marko_adapter.py`) converts Marko AST to Pandoc-like dict format:

| Marko Element | Pandoc Type |
|---------------|-------------|
| `Heading` | `Header` |
| `Paragraph` | `Para` |
| `List(ordered=False)` | `BulletList` |
| `List(ordered=True)` | `OrderedList` |
| `FencedCode` | `CodeBlock` |
| `Table` (GFM) | `Table` |
| `RawText` | `Str` + `Space` |
| `StrongEmphasis` | `Strong` |
| `Emphasis` | `Emph` |
| `Link` | `Link` |
| `Image` | `Image` |
| `CodeSpan` | `Code` |

Preprocessing steps (run before Marko parsing):
1. `_preprocess_extended_headers()` — converts `#######`–`#########` to placeholders
2. `_preprocess_table_dashes()` — extracts dash counts for proportional column widths
3. `_preprocess_math()` — extracts `$...$` and `$$...$$` into placeholders, later restored as Image AST nodes with `__math_inline:`/`__math_block:` targets
4. Quarto/Pandoc preprocessing — strips fenced divs, pandoc attributes, style blocks, cell-code blocks (when enabled)

## Testing

Automated test suite with **299 tests** using pytest:

```bash
# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/test_converter.py -v
pytest tests/test_api.py -v
```

### Test Modules

| Module | Coverage |
|--------|----------|
| `test_adapter.py` | Marko adapter: AST conversion, extended headers, table dashes, Quarto preprocessing, math placeholders |
| `test_api.py` | Library API: `convert_string()`, frontmatter, templates |
| `test_cli.py` | CLI: argument parsing, file validation, output formats, math flags |
| `test_converter.py` | Core converter: all block types, styles, tables, lists, images |
| `test_latex_to_hwce.py` | LaTeX→Hancom converter: symbols, structures, environments, decorations, fonts, complex expressions, size estimation |
| `test_math_renderer.py` | Math renderer: HWCE renderer, factory, ABC contract |
| `test_preprocessor.py` | Quarto preprocessor, HTML table converter, RawBlock/RawInline handling, marker rendering |
| `test_security.py` | Security: path traversal, size limits, nesting depth, image count |

## Common Tasks

### Add support for new Marko block type

1. Add conversion logic in `marko_adapter.py` to convert Marko element to Pandoc-like format
2. If needed, add handler method `_handle_<blocktype>()` in `MarkdownToHwpx.py`
3. Register in `_process_blocks()` method's block processing loop

### Modify style handling

1. Study `_parse_styles_and_init_xml()` method in `MarkdownToHwpx.py`
2. Reference `header.xml` from `blank.hwpx` for style structure
3. Update style mapping in relevant handler

### Customize template styles (for users)

1. Copy `blank.hwpx` from the package
2. Open in Hancom Office and edit styles via Format > Styles (F6)
3. Save and use with `-r custom.hwpx` or `--reference-doc=custom.hwpx`
4. Or use placeholder method: add `{{H1}}`, `{{BODY}}` text with desired formatting

### Debug conversion issues

1. Generate intermediate JSON: `md2hwpx input.md -o debug.json`
2. Inspect AST structure for problematic content
3. Run with `--verbose` flag for debug logging
4. Add logging in specific handler methods

### Math/Equation Support

LaTeX math expressions are converted to native Hancom equation objects (`<hp:equation>`):

- **Inline math**: `$E = mc^2$` → inline equation in text flow
- **Block math**: `$$\frac{a}{b}$$` → standalone equation paragraph
- Both single-line (`$$...$$`) and multi-line (`$$\n...\n$$`) block math supported
- `--math` flag controls mode: `hwce` (default), `italic`, or `none`
- `--strip-quarto` enables Quarto GFM preprocessing + HWCE math

#### LaTeX → Hancom Script Conversion

`latex_to_hwce.py` converts LaTeX to Hancom's proprietary equation script:
- 70+ symbol mappings (Greek letters, operators, relations, arrows, etc.)
- 40+ structural transformation rules (fractions, roots, limits, integrals)
- Environment support (pmatrix, bmatrix, vmatrix, cases)
- Font commands (\mathrm, \mathbf, \mathbb, \mathcal, \text)

Example conversions:
| LaTeX | Hancom Script |
|-------|---------------|
| `\frac{a}{b}` | `{a} over {b}` |
| `\sqrt{x}` | `sqrt{x}` |
| `\sum_{i=1}^{n}` | `sum from{i=1} to{n}` |
| `\alpha + \beta` | `alpha + beta` |

#### HWPX Equation XML Structure

Equations are embedded as `<hp:equation>` elements with required attributes:
- `version="Equation Version 60"`, `font="HancomEQN"`, `lineMode="CHAR"`
- `baseLine` set to ~71% of height for proper text alignment
- `treatAsChar="1"` for inline rendering
- `<hp:script>` contains the Hancom equation script

### Quarto/Pandoc Preprocessing

For Quarto `.qmd` → GFM → HWPX pipelines, enable with `--strip-quarto` or individual flags:
- `--strip-fenced-divs` — remove `:::` fenced div markers
- `--strip-pandoc-attributes` — remove `{.class #id}` attributes
- `--strip-html-style` — remove `<style>...</style>` blocks
- `--strip-cell-code` — remove `.cell-code` code blocks

When `--strip-quarto` is used, the full preprocessing pipeline (`quarto_preprocessor.py`) runs:
1. Scoped `<style>` blocks removed
2. Quarto cross-references → `{{xref:id:text}}` markers
3. Quarto citations → `{{cite:key:text}}` markers
4. CSL bibliography → `{{bib-start}}`/`{{bib:id:text}}`/`{{bib-end}}` markers
5. Quarto div wrappers (`<figure>`, `<div id="tbl-X">`) unwrapped
6. Remaining inline HTML (`<em>`, `<strong>`, `<a>`, `<span>`, `<code>`) → Markdown equivalents

### RawBlock/RawInline Handling

HTML blocks that Marko can't parse as Markdown become `RawBlock` nodes:
- `<style>`, `<script>`, HTML comments → silently skipped
- `<table>` → routed to `html_table_converter.py` for native HWPX table conversion
- Other HTML → text extracted and rendered as paragraphs

HTML inline elements become `RawInline` nodes:
- `<br>` → line break
- `<sub>text</sub>` → subscript character formatting
- `<sup>text</sup>` → superscript character formatting
- `<a href="url">text</a>` → HWPX HYPERLINK field
- `{{xref:...}}`, `{{cite:...}}`, `{{bib:...}}` markers → text output
- Other HTML → text extracted as fallback

### HTML Table Converter

`html_table_converter.py` converts HTML `<table>` elements into Pandoc-like AST format,
then delegates to the existing `_handle_table()` method:
- Parses `<thead>`/`<tbody>`, `<th>`/`<td>` cells
- Extracts text-align from `style` attribute or `align` attribute
- Supports tables with or without explicit `<thead>` (detects `<th>` cells)

## Known Limitations

- Only Markdown input is supported (no DOCX, HTML, or JSON AST input)
- Complex formatting (letter-spacing, precise styles) not supported
- No colspan/rowspan in HTML tables (basic cell support only)
- Tool focuses on content preservation over exact formatting
