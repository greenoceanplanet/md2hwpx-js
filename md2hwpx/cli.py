"""
md2hwpx - Markdown to HWPX Converter

A Pandoc-free tool to convert Markdown files to Korean Hancom Office HWPX format.
"""

import argparse
import sys
import json
import os
import logging

from .frontmatter_parser import parse_markdown_with_frontmatter, convert_metadata_to_pandoc_meta
from .marko_adapter import MarkoToPandocAdapter
from .MarkdownToHtml import MarkdownToHtml
from .MarkdownToHwpx import MarkdownToHwpx
from .exceptions import HwpxError, SecurityError
from .config import DEFAULT_CONFIG, ConversionConfig
from . import __version__

logger = logging.getLogger('md2hwpx')


def setup_logging(verbose=False, quiet=False):
    """Configure logging based on CLI flags.

    Args:
        verbose: If True, show DEBUG level messages
        quiet: If True, suppress all non-error output
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    root_logger = logging.getLogger('md2hwpx')
    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def main():
    parser = argparse.ArgumentParser(
        prog="md2hwpx",
        description="Convert Markdown to HWPX format (Pandoc-free).",
        epilog="Examples:\n"
               "  md2hwpx input.md -o output.hwpx\n"
               "  md2hwpx input.md --reference-doc=custom.hwpx -o output.hwpx\n"
               "  md2hwpx input.md -o debug.json\n"
               "  md2hwpx input.md -o output.hwpx --verbose",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("input_file", help="Input Markdown file (.md, .markdown)")
    parser.add_argument("-o", "--output", required=True,
                        help="Output file (.hwpx, .json for debug)")
    parser.add_argument("-r", "--reference-doc", required=False, default=None,
                        help="Reference HWPX for styles and page setup (default: built-in blank.hwpx)")
    parser.add_argument("--insert-into", default=None, metavar="HWPX",
                        help="Insert into this EXISTING HWPX instead of creating a new document "
                             "(its styles are used; see --under-heading). -o may equal this file.")
    parser.add_argument("--under-heading", default=None, metavar="TEXT",
                        help="With --insert-into: replace the body under the heading with this text "
                             "(up to the next heading of the same or higher level).")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Show detailed debug output")
    parser.add_argument("-q", "--quiet", action="store_true", default=False,
                        help="Suppress all non-error output")
    parser.add_argument("--blank-line-before-header", action="store_true", default=False,
                        help="Insert a blank line before headers (H1-H3) in the middle of the document")
    parser.add_argument("--config", default=None, metavar="FILE",
                        help="Path to JSON or YAML config file (snake_case keys). CLI args override file settings.")
    parser.add_argument("--page-break-before", default=None, metavar="LEVELS",
                        help="Insert page break before specified header levels. "
                             "Comma-separated, e.g. --page-break-before 1,2")
    parser.add_argument("--blank-lines-before-header", default=None, metavar="SPEC",
                        help="Blank line count before headers per level. "
                             "Format: LEVEL:COUNT, e.g. --blank-lines-before-header 2:2,3:1")
    parser.add_argument("--space-before-header", default=None, metavar="SPEC",
                        help="Precise space (mm) before headers per level. "
                             "Format: LEVEL:MM, e.g. --space-before-header 2:10,3:5. "
                             "Overrides --blank-lines-before-header for the same level.")

    # Quarto/Pandoc preprocessing
    quarto_group = parser.add_argument_group('Quarto/Pandoc preprocessing')
    quarto_group.add_argument("--strip-quarto", action="store_true", default=False,
                              help="Enable all Quarto GFM preprocessing (fenced divs, attributes, "
                                   "style blocks, cell-code blocks, math as native equation)")
    quarto_group.add_argument("--strip-fenced-divs", action="store_true", default=False,
                              help="Remove Pandoc fenced div markers (::: lines)")
    quarto_group.add_argument("--strip-pandoc-attributes", action="store_true", default=False,
                              help="Remove Pandoc inline attributes ({.class #id})")
    quarto_group.add_argument("--strip-html-style", action="store_true", default=False,
                              help="Remove <style>...</style> blocks")
    quarto_group.add_argument("--strip-cell-code", action="store_true", default=False,
                              help="Remove code blocks with .cell-code class")
    quarto_group.add_argument("--math", choices=['none', 'italic', 'hwce'], default=None,
                              help="LaTeX math handling: 'none' (skip), 'italic' (render as italic text), "
                                   "'hwce' (native Hancom equation object)")

    args = parser.parse_args()

    # Set up logging
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    input_file = args.input_file

    # Validate input is Markdown
    input_ext = os.path.splitext(input_file)[1].lower()
    if input_ext not in ['.md', '.markdown']:
        logger.error("Only Markdown files are supported. Got: %s", input_ext)
        sys.exit(1)

    if not os.path.exists(input_file):
        logger.error("Input file not found: %s", input_file)
        sys.exit(1)

    # Validate input file size
    input_size = os.path.getsize(input_file)
    if input_size > DEFAULT_CONFIG.MAX_INPUT_FILE_SIZE:
        logger.error(
            "Input file too large: %d bytes (max %d bytes)",
            input_size, DEFAULT_CONFIG.MAX_INPUT_FILE_SIZE
        )
        sys.exit(1)

    output_ext = os.path.splitext(args.output)[1].lower()

    # Determine Reference Doc
    ref_doc = args.reference_doc
    if not ref_doc and output_ext == ".hwpx":
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        default_ref = os.path.join(pkg_dir, "blank.hwpx")
        if os.path.exists(default_ref):
            ref_doc = default_ref
        else:
            logger.error("--reference-doc is required and no default 'blank.hwpx' found in package.")
            sys.exit(1)

    # Build config: load file first, then apply individual CLI flags (which override file)
    if args.config:
        try:
            config = ConversionConfig.from_file(args.config)
        except (OSError, ValueError, ImportError) as e:
            logger.error("Failed to load config file %s: %s", args.config, e)
            sys.exit(1)
    else:
        config = ConversionConfig()

    if args.blank_line_before_header:
        config.BLANK_LINE_BEFORE_HEADER = True

    if args.page_break_before:
        levels = {}
        for x in args.page_break_before.split(','):
            x = x.strip()
            if x.isdigit() and 1 <= int(x) <= 6:
                levels[int(x)] = True
            else:
                logger.warning("--page-break-before: invalid level %r (must be 1-6), skipped", x)
        if levels:
            config.PAGE_BREAK_BEFORE_HEADER_LEVELS = levels

    if args.blank_lines_before_header:
        pairs = {}
        for part in args.blank_lines_before_header.split(','):
            if ':' in part:
                lvl_s, cnt_s = part.strip().split(':', 1)
                if lvl_s.isdigit() and cnt_s.isdigit():
                    lvl, cnt = int(lvl_s), int(cnt_s)
                    if 1 <= lvl <= 6 and 0 <= cnt <= 2:
                        pairs[lvl] = cnt
                    else:
                        logger.warning("--blank-lines-before-header: out-of-range %r, skipped", part)
        if pairs:
            config.BLANK_LINES_BEFORE_HEADER = pairs

    if args.space_before_header:
        pairs = {}
        for part in args.space_before_header.split(','):
            if ':' in part:
                lvl_s, mm_s = part.strip().split(':', 1)
                if lvl_s.isdigit():
                    try:
                        lvl, mm = int(lvl_s), float(mm_s)
                        if 1 <= lvl <= 6 and mm >= 0:
                            pairs[lvl] = mm
                        else:
                            logger.warning("--space-before-header: out-of-range %r, skipped", part)
                    except ValueError:
                        logger.warning("--space-before-header: invalid value %r, skipped", part)
        if pairs:
            config.SPACE_BEFORE_HEADER_MM = pairs

    # Quarto/Pandoc preprocessing flags
    if args.strip_quarto:
        config.enable_quarto_defaults()
    if args.strip_fenced_divs:
        config.STRIP_FENCED_DIVS = True
    if args.strip_pandoc_attributes:
        config.STRIP_PANDOC_ATTRIBUTES = True
    if args.strip_html_style:
        config.STRIP_HTML_STYLE_BLOCKS = True
    if args.strip_cell_code:
        config.STRIP_CELL_CODE_BLOCKS = True
    if args.math is not None:
        config.MATH_HANDLING = args.math

    if args.insert_into:
        if not args.under_heading:
            logger.error("--insert-into requires --under-heading")
            sys.exit(1)
        from .insert import insert_markdown
        try:
            stats = insert_markdown(args.insert_into, args.output,
                                    [(input_file, args.under_heading)], config=config)
        except HwpxError as e:
            logger.error("%s", e)
            sys.exit(1)
        for s in stats:
            logger.info("Inserted %s under %r (tables %d, images %d) -> %s",
                        s['markdown'], s['heading'], s['tables'], s['images'], args.output)
        return

    # Parse Markdown with front matter
    metadata, md_content = parse_markdown_with_frontmatter(input_file)

    # Convert to Pandoc-like AST using Marko adapter
    adapter = MarkoToPandocAdapter(config=config)
    ast = adapter.parse(md_content)

    # Inject metadata into AST
    ast['meta'] = convert_metadata_to_pandoc_meta(metadata)

    try:
        if output_ext == ".hwpx":
            MarkdownToHwpx.convert_to_hwpx(input_file, args.output, ref_doc, json_ast=ast, config=config)
            logger.info("Successfully converted to %s", args.output)

        elif output_ext == ".json":
            # Debug: output the converted AST
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(ast, f, indent=2, ensure_ascii=False)
            logger.info("Successfully wrote AST to %s", args.output)

        elif output_ext in [".htm", ".html"]:
            # Hidden feature: HTML output for debugging
            MarkdownToHtml.convert_to_html(input_file, args.output, json_ast=ast)
            logger.info("Successfully converted to %s", args.output)

        else:
            logger.error("Unsupported output format: %s", output_ext)
            logger.error("Supported formats: .hwpx, .json")
            sys.exit(1)

    except HwpxError as e:
        logger.error("%s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
