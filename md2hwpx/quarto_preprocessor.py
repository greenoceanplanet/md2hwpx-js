"""
Quarto HTML preprocessing for md2hwpx.

Converts Quarto-specific HTML elements (cross-references, citations,
bibliography, figure wrappers, scoped styles) into markers or clean
Markdown before Marko parsing.

Markers produced:
- {{xref:target-id:display text}}  — cross-references
- {{cite:cite-key:display text}}   — inline citations
- {{bib-start}} / {{bib:ref-id:text}} / {{bib-end}} — bibliography
"""

import re
import logging
from html.parser import HTMLParser

logger = logging.getLogger('md2hwpx')


def strip_scoped_styles(text: str) -> str:
    """Remove all <style ...>...</style> blocks (scoped, typed, plain)."""
    return re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)


def convert_quarto_xrefs(text: str) -> str:
    """Convert Quarto cross-reference links to markers.

    <a href="#tbl-X" class="quarto-xref">표 N</a>
    → {{xref:tbl-X:표 N}}
    """
    pattern = r'<a[^>]*href="#([^"]*)"[^>]*class="[^"]*quarto-xref[^"]*"[^>]*>(.*?)</a>'
    return re.sub(pattern, r'{{xref:\1:\2}}', text, flags=re.DOTALL)


def convert_quarto_citations(text: str) -> str:
    """Convert Quarto citation spans to markers.

    <span class="citation" data-cites="key">(<a ...>Author, Year</a>)</span>
    → {{cite:key:Author, Year}}

    Also handles cases without parentheses.
    """
    # Full pattern: <span class="citation" data-cites="key">(<a...>text</a>)</span>
    pattern = (
        r'<span[^>]*class="[^"]*citation[^"]*"[^>]*data-cites="([^"]*)"[^>]*>'
        r'\s*\(?'                        # optional opening paren
        r'<a[^>]*>(.*?)</a>'             # link text
        r'\)?\s*'                        # optional closing paren
        r'</span>'
    )

    def _replace_citation(m):
        key = m.group(1)
        display = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        return '{{cite:' + key + ':' + display + '}}'

    text = re.sub(pattern, _replace_citation, text, flags=re.DOTALL)

    # Fallback: simpler citation spans (multiple <a> tags inside)
    pattern2 = (
        r'<span[^>]*class="[^"]*citation[^"]*"[^>]*data-cites="([^"]*)"[^>]*>'
        r'(.*?)</span>'
    )

    def _replace_citation_fallback(m):
        key = m.group(1)
        inner = m.group(2)
        # Strip all HTML tags, keep text
        display = re.sub(r'<[^>]+>', '', inner).strip()
        # Remove surrounding parens if present
        display = display.strip('()')
        return '{{cite:' + key + ':' + display + '}}'

    text = re.sub(pattern2, _replace_citation_fallback, text, flags=re.DOTALL)

    return text


class _TextExtractor(HTMLParser):
    """Simple HTML parser that extracts text content only."""

    def __init__(self):
        super().__init__()
        self.texts = []
        self._skip_tags = {'style', 'script'}
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            self.texts.append(data)

    def get_text(self) -> str:
        return ' '.join(self.texts).strip()


def _extract_text_from_html(html: str) -> str:
    """Extract plain text from HTML, ignoring tags."""
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        # Fallback: regex strip
        return re.sub(r'<[^>]+>', '', html).strip()
    return extractor.get_text()


def convert_csl_bibliography(text: str) -> str:
    """Convert CSL bibliography block to markers.

    <div id="refs" ...>
      <div id="ref-key" class="csl-entry">Author. (Year). Title...</div>
      ...
    </div>

    → {{bib-start}}
    {{bib:ref-key:Author. (Year). Title...}}
    {{bib-end}}
    """
    # Find the refs block — it may be followed by </div> on next line
    refs_pattern = re.compile(
        r'<div[^>]*id="refs"[^>]*>(.*?)</div>\s*(?=\n\n|\n[^<]|\Z)',
        re.DOTALL
    )
    match = refs_pattern.search(text)
    if not match:
        return text

    refs_block = match.group(1)

    # Extract individual entries
    entry_pattern = re.compile(
        r'<div[^>]*id="([^"]*)"[^>]*class="[^"]*csl-entry[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL
    )
    entries = entry_pattern.findall(refs_block)

    if not entries:
        return text

    replacement = '\n\n{{bib-start}}\n\n'
    for ref_id, html_text in entries:
        clean_text = _extract_text_from_html(html_text)
        if clean_text:
            replacement += '{{bib:' + ref_id + ':' + clean_text + '}}\n\n'
    replacement += '{{bib-end}}\n\n'

    return text[:match.start()] + replacement + text[match.end():]


def unwrap_quarto_divs(text: str) -> str:
    """Remove Quarto div wrappers so inner Markdown can be parsed normally.

    - <figure ...> → removed
    - <figcaption ...>text</figcaption> → **text** (bold paragraph)
    - <div id="tbl-X" ...> or <div id="fig-X" ...> → removed
    - <div class="cell-output ..."> → removed
    - </div>, </figure> → removed
    """
    replacements = [
        # figcaption → bold paragraph (preserve caption text)
        (re.compile(r'<figcaption[^>]*>(.*?)</figcaption>', re.DOTALL),
         lambda m: '\n\n**' + _extract_text_from_html(m.group(1)).strip() + '**\n\n'),
        # figure opening tags
        (re.compile(r'<figure[^>]*>'), ''),
        # div wrappers with tbl-/fig- IDs
        (re.compile(r'<div[^>]*id="(?:tbl|fig)-[^"]*"[^>]*>'), ''),
        # Quarto cell-output divs
        (re.compile(r'<div[^>]*class="[^"]*cell-output[^"]*"[^>]*>'), ''),
        # Generic Quarto layout divs
        (re.compile(r'<div[^>]*class="[^"]*quarto-[^"]*"[^>]*>'), ''),
        # Closing tags
        (re.compile(r'</(?:figure|div)>'), ''),
    ]

    for pattern, repl in replacements:
        text = pattern.sub(repl, text)

    return text


def strip_remaining_html_inline(text: str) -> str:
    """Convert remaining inline HTML elements that Marko won't parse.

    - <a href="url">text</a> (non-xref, non-citation) → text only
    - <span ...>text</span> → text only
    - <i ...>text</i> → *text* (italic)
    - <b ...>text</b> → **text** (bold)
    - <em>text</em> → *text*
    - <strong>text</strong> → **text**
    """
    # Keep functional markers ({{xref:...}}, {{cite:...}}) untouched
    # Only strip truly remaining HTML

    # <em>, <i> → italic
    text = re.sub(r'<(?:em|i)(?:\s[^>]*)?>(.*?)</(?:em|i)>', r'*\1*', text, flags=re.DOTALL)
    # <strong>, <b> → bold
    text = re.sub(r'<(?:strong|b)(?:\s[^>]*)?>(.*?)</(?:strong|b)>', r'**\1**', text, flags=re.DOTALL)
    # <a href>text</a> → just text (links without xref class)
    text = re.sub(r'<a[^>]*>(.*?)</a>', r'\1', text, flags=re.DOTALL)
    # <span ...>text</span> → just text
    text = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', text, flags=re.DOTALL)
    # <code>text</code> → `text`
    text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)

    return text


def preprocess_quarto_full(text: str) -> str:
    """Full Quarto preprocessing pipeline.

    Order matters:
    1. Scoped styles first (they can confuse later parsing)
    2. Cross-references → markers (before div unwrapping removes context)
    3. Citations → markers
    4. Bibliography → markers
    5. Div unwrapping (exposes inner Markdown)
    6. Remaining inline HTML cleanup
    """
    text = strip_scoped_styles(text)
    text = convert_quarto_xrefs(text)
    text = convert_quarto_citations(text)
    text = convert_csl_bibliography(text)
    text = unwrap_quarto_divs(text)
    text = strip_remaining_html_inline(text)

    # Clean up excessive blank lines
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    logger.debug("Quarto preprocessing complete")
    return text
