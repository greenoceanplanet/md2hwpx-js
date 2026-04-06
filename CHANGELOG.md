# Changelog

All notable changes to md2hwpx will be documented in this file.

Forked from pypandoc-hwpx: https://github.com/msjang/pypandoc-hwpx

## [Unreleased]

### Added
- **Native LaTeX math support (HWCE)**: `$...$` inline and `$$...$$` block math converted to native Hancom equation objects (`<hp:equation>`)
- LaTeX → Hancom equation script converter (`latex_to_hwce.py`): 70+ symbol mappings, 40+ structural rules, matrix/cases environments, font commands
- Pluggable `MathRenderer` architecture with `HwceMathRenderer` implementation
- `--math` CLI flag with modes: `hwce` (default), `italic`, `none`
- **Quarto/Pandoc GFM preprocessing pipeline**: `--strip-quarto` enables all preprocessing
- Individual preprocessing flags: `--strip-fenced-divs`, `--strip-pandoc-attributes`, `--strip-html-style`, `--strip-cell-code`
- **Full Quarto HTML preprocessor** (`quarto_preprocessor.py`): cross-reference markers, citation markers, CSL bibliography extraction, div unwrapping, scoped style removal
- **RawBlock handler**: HTML blocks now parsed — `<style>`/`<script>` skipped, `<table>` converted to native HWPX tables, other HTML text-extracted as paragraphs
- **Improved RawInline handler**: `<sub>`→subscript, `<sup>`→superscript, `<a href>`→hyperlinks, Quarto marker rendering, fallback text extraction
- **HTML table converter** (`html_table_converter.py`): parses HTML `<table>` elements from RawBlock into native HWPX tables with alignment support
- Support for single-line block math (`$$...$$` on one line)
- 46 tests for LaTeX→Hancom converter, 10 tests for math renderer
- 42 tests for Quarto preprocessor, HTML table converter, RawBlock/RawInline handling

### Changed
- Default `MATH_HANDLING` set to `'hwce'` — math equations are converted by default
- `enable_quarto_defaults()` now sets `MATH_HANDLING = 'hwce'`
- RawBlock blocks no longer silently dropped — content is preserved as text or native elements

## [0.1.4] - 2026-03-25

### Added
- CLI support for loading JSON or YAML config files with `--config`
- Per-header-level spacing controls via `--page-break-before`, `--blank-lines-before-header`, and `--space-before-header`
- Config fields for per-level header page breaks and spacing
- Preservation of image-based prefix runs for placeholders and list bullets

### Changed
- Header pre-spacing now resolves through a single helper so page breaks, blank lines, and fixed-height spacers follow consistent precedence

## [0.2.0] - 2026-01-29

### Added
- **Placeholder-based style system**: Use `{{H1}}`, `{{BODY}}`, `{{CELL_HEADER_LEFT}}`, `{{LIST_BULLET_1}}` etc. in templates for WYSIWYG style control
- **Table cell placeholders**: 12 cell position types (header/top/middle/bottom x left/center/right) for fine-grained table styling
- **Table column alignment**: GFM alignment syntax (`:--`, `:--:`, `--:`) now applies to HWPX output
- **Block quote support**: Rendered with increased left margin, supports nesting
- **Horizontal rule support**: Rendered as paragraph with bottom border
- **Configuration system**: `ConversionConfig` class centralizes all magic numbers and defaults
- **Custom exceptions**: `HwpxError`, `TemplateError`, `ImageError`, `StyleError`, `ConversionError`
- **Input validation**: File existence, ZIP validity, required files check for templates
- **Logging**: Replaced all print statements with Python `logging` module
- **CLI flags**: `--verbose` for debug output, `-q`/`--quiet` for silent mode
- **`__main__.py`**: Support for `python -m md2hwpx` invocation
- **Test suite**: 109 tests covering adapter, converter, CLI, and end-to-end scenarios
- **English README** with full documentation

### Changed
- Refactored list handlers to use ElementTree API (`_handle_bullet_list_elem`, `_handle_ordered_list_elem`)
- Table handler uses ElementTree API (`_handle_table_elem`)
- Marko adapter now extracts column alignment from GFM table cells

### Fixed
- Table parsing with Marko GFM extension (TableRow handling)
- Footnote parsing (extension loading, attribute names)

## [0.1.0] - Initial Release

### Added
- Markdown to HWPX conversion (Pandoc-free)
- Support for headers, paragraphs, bold/italic/strikethrough, links, images, tables, lists, code blocks, footnotes
- Reference template system for style customization
- Marko-based markdown parser with GFM and footnote extensions
- Extended header levels (7-9)
- YAML frontmatter support
- CLI tool with `--reference-doc` option
