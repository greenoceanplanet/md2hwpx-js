# md2hwpx

**md2hwpx** is a Python tool that converts Markdown (`.md`) files to Korean Hancom Office HWPX format (`.hwpx`). It works entirely in pure Python without requiring Pandoc.

[Fork of pypandoc-hwpx](https://github.com/msjang/pypandoc-hwpx). This project continues development with new features and improvements.

[한국어 README](https://github.com/msjang/md2hwpx/blob/main/README.md)

## Features

- **Pandoc-free conversion**: Pure Python pipeline using Marko + XML generation
- **CLI and Python API**: Use `md2hwpx` or import the converter classes
- **YAML front matter**: Supports metadata; document `title` is written into HWPX
- **Template-driven styling**: WYSIWYG placeholders for headings, body text, lists, and table cells
- **Image prefix support**: Images placed before placeholders (e.g., checkboxes) are preserved in output
- **Per-level header spacing**: Configure blank lines (with custom height) and page breaks per header level
- **Config file support**: JSON/YAML config files for batch-setting conversion options
- **Tables**: GFM tables with alignment and proportional column widths
- **Lists**: Nested bullet/ordered lists, custom start numbers
- **Images**: Local image embedding, size normalization, and safe path validation
- **Block quotes & horizontal rules**
- **Footnotes**
- **Extended headers**: Levels 1–9
- **Debug outputs**: `.json` AST and `.html` outputs

## Requirements

- **Python 3.9+**
- **Libraries**: marko, python-frontmatter, Pillow

## Installation

### From PyPI (recommended)

```bash
pip install md2hwpx
```

### From source

```bash
git clone https://github.com/jundamin/md2hwpx.git
cd md2hwpx
pip install -e .
```

## Usage

### CLI

```bash
# Markdown to HWPX
md2hwpx input.md -o output.hwpx

# With custom reference template
md2hwpx input.md --reference-doc=custom.hwpx -o output.hwpx

# Debug: output intermediate JSON AST
md2hwpx input.md -o debug.json

# Debug: output HTML (for inspection)
md2hwpx input.md -o output.html
```

### CLI options

| Option | Description |
|--------|-------------|
| `input_file` | Input Markdown file (.md, .markdown) |
| `-o`, `--output` | Output file (.hwpx, .json, .html) |
| `-r`, `--reference-doc` | Reference HWPX for styles and page setup (default: built-in blank.hwpx) |
| `--config FILE` | Path to JSON or YAML config file (snake_case keys) |
| `--page-break-before LEVELS` | Insert page break before the specified header levels, e.g. `1,2` |
| `--blank-lines-before-header SPEC` | Blank lines before headers per level, e.g. `2:2,3:1` |
| `--space-before-header SPEC` | Precise spacing (mm) before headers per level, e.g. `2:10,3:5` |
| `--blank-line-before-header` | Insert a blank line before H1–H3 (legacy on/off toggle) |
| `--verbose` | Show detailed debug output |
| `-q`, `--quiet` | Suppress all non-error output |
| `-v`, `--version` | Show version number |

### Front matter (title)

```markdown
---
title: My Document Title
---

# Heading
```

The `title` is written into the HWPX document metadata.

### Python API

```python
from md2hwpx import convert_string

# Basic conversion
convert_string("# Hello World\n\nThis is a paragraph.", "output.hwpx")

# With a custom template
convert_string("# Hello\n\nWorld", "output.hwpx", reference_doc="template.hwpx")

# With ConversionConfig for fine-grained control
from md2hwpx.config import ConversionConfig

config = ConversionConfig()
config.PAGE_BREAK_BEFORE_HEADER_LEVELS = {1: True}
config.BLANK_LINES_BEFORE_HEADER = {2: [2, 5.0], 3: 1}  # H2: 2 blank lines at 5mm; H3: 1 default-height line

convert_string("# H1\n\n## H2\n\nBody text", "output.hwpx", config=config)
```

## Header Spacing & Page Breaks

You can configure blank lines or page breaks before any header level (H1–H6).

### Via CLI

```bash
# Page break before H1
md2hwpx input.md -o output.hwpx --page-break-before 1

# 10mm space before H2, 5mm before H3
md2hwpx input.md -o output.hwpx --space-before-header 2:10,3:5

# 2 blank lines before H2, 1 before H3
md2hwpx input.md -o output.hwpx --blank-lines-before-header 2:2,3:1
```

### Via config file (JSON/YAML)

```yaml
# config.yaml
page_break_before_header_levels:
  1: true
blank_lines_before_header:
  2: [2, 5.0]   # H2: 2 blank lines, each 5mm tall
  3: [1, 3.0]   # H3: 1 blank line, 3mm tall
  4: 1          # H4: 1 blank line, default height
space_before_header_mm:
  2: 10.0       # H2: 10mm space (takes priority over blank_lines)
```

```bash
md2hwpx input.md -o output.hwpx --config config.yaml
```

JSON format is also supported. Dictionary keys can be integers or digit strings (`"2"` is treated as `2`).

### Priority order

`--page-break-before` > `--space-before-header` > `--blank-lines-before-header` > `--blank-line-before-header` (legacy)

> **Note**: Spacing is never inserted before the very first block in the document.

## Style Customization (Template)

You can customize output styles by editing a reference HWPX template in Hancom Office.

### Method 1: Placeholder-based (recommended)

Create a template with placeholder text and apply your desired formatting:

| Placeholder | Markdown Element |
|-------------|------------------|
| `{{H1}}` | `# Heading 1` |
| `{{H2}}` | `## Heading 2` |
| `{{H3}}` | `### Heading 3` |
| `{{H4}}`–`{{H9}}` | `####`–`#########` |
| `{{BODY}}` | Body text |

#### List placeholders

Use placeholders for list styling (levels 1–7):

- `{{LIST_BULLET_1}}` … `{{LIST_BULLET_7}}`
- `{{LIST_ORDERED_1}}` … `{{LIST_ORDERED_7}}`

Text before the placeholder can be used as a prefix (e.g., `1. `, `가. `).
If your template paragraph uses numbering, md2hwpx preserves that numbering.

#### Image prefix placeholders

You can place an image (`hp:pic`) directly before a placeholder text in the template. md2hwpx will detect the image and reproduce it as a prefix in all matching output elements.

For example: placing a checkbox image before `{{LIST_BULLET_1}}` will prepend that image to every level-1 list item in the output. Images are automatically copied from the template's BinData to the output file.

#### Table cell placeholders

Use these 12 placeholders inside a template table to control cell styles:

- `{{CELL_HEADER_LEFT}}`, `{{CELL_HEADER_CENTER}}`, `{{CELL_HEADER_RIGHT}}`
- `{{CELL_TOP_LEFT}}`, `{{CELL_TOP_CENTER}}`, `{{CELL_TOP_RIGHT}}`
- `{{CELL_MIDDLE_LEFT}}`, `{{CELL_MIDDLE_CENTER}}`, `{{CELL_MIDDLE_RIGHT}}`
- `{{CELL_BOTTOM_LEFT}}`, `{{CELL_BOTTOM_CENTER}}`, `{{CELL_BOTTOM_RIGHT}}`

Then convert with:

```bash
md2hwpx input.md --reference-doc=my_template.hwpx -o output.hwpx
```

### Method 2: Style editing

1. Copy the built-in template:
   ```bash
   python -c "import md2hwpx; import shutil; shutil.copy(md2hwpx.__path__[0] + '/blank.hwpx', 'my_template.hwpx')"
   ```
2. Open in Hancom Office and edit styles via **Format > Styles** (F6)
3. Use as reference template

## Supported Markdown Elements

| Element | Support |
|---------|---------|
| Headings (1–9) | Full |
| Paragraphs | Full |
| Bold / italic / strikethrough | Full |
| Links | Full (HWPX hyperlinks) |
| Images | Full (embedded) |
| Tables (GFM) | Full (alignment + proportional widths) |
| Bullet lists | Full (nested) |
| Ordered lists | Full (nested, custom start) |
| Code blocks | Full |
| Inline code | Full |
| Block quotes | Full (nested) |
| Horizontal rules | Full |
| Footnotes | Full |
| Superscript / subscript | Supported in output if present in AST |

## Security & Limits

- Input and template size limits (default: 50 MB each)
- Image count limit (default: 500)
- Image path validation blocks absolute paths and directory traversal

## Development

```bash
# Install for development
pip install -e .

# Run tests
python -m pytest tests/ -v

# Run with verbose output
md2hwpx test.md -o output.hwpx --verbose
```

## Changelog Since Fork

Highlights since the original fork:

- Placeholder-based styles for headers, lists, and table cells
- GFM tables with alignment and proportional column widths
- Front matter metadata injection (title)
- Enhanced list handling with custom starts and template numbering
- Security limits (file size, image count, path validation)
- Image prefix placeholder support (e.g., checkbox images before header/list placeholders)
- Per-level header spacing: page breaks, blank line count, and precise mm height (`--page-break-before`, `--space-before-header`, `--blank-lines-before-header`)
- `[count, height_mm]` format for `blank_lines_before_header` to control both count and height of blank lines
- JSON/YAML config file support (`--config`); `ConversionConfig` can be passed directly in Python API

## License

MIT License. See `LICENSE` for details.
