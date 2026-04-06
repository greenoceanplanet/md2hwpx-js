"""
Pluggable math rendering for md2hwpx.

Provides an abstract MathRenderer base class and concrete implementation:
- HwceMathRenderer: LaTeX → native Hancom equation script
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger('md2hwpx')


class MathResult:
    """Result of math rendering — abstracts away different formats.

    Attributes:
        kind: Result type ('hwce', 'text')
        data: Dict of type-specific data:
            - kind='hwce':  {'script': str, 'width': int, 'height': int, 'is_block': bool}
            - kind='text':  {'text': str}
    """

    def __init__(self, kind, **kwargs):
        self.kind = kind
        self.data = kwargs

    def __repr__(self):
        return f"MathResult(kind={self.kind!r}, data={self.data!r})"


class MathRenderer(ABC):
    """Abstract base for math renderers.

    The converter calls render_inline() / render_block() and uses
    the returned MathResult to embed content into HWPX.
    """

    @abstractmethod
    def render_inline(self, latex: str) -> MathResult:
        """Render inline math ($...$). Returns MathResult."""
        ...

    @abstractmethod
    def render_block(self, latex: str) -> MathResult:
        """Render display/block math ($$...$$). Returns MathResult."""
        ...

    def cleanup(self):
        """Called after conversion completes. Override to clean temp files."""
        pass


class HwceMathRenderer(MathRenderer):
    """Converts LaTeX to native Hancom equation script (HWCE).

    Returns MathResult with kind='hwce' containing the script string
    and estimated dimensions. No external dependencies required.
    """

    def _render(self, latex: str, is_block: bool) -> MathResult:
        from .latex_to_hwce import LatexToHancomConverter, estimate_equation_size
        script = LatexToHancomConverter.convert(latex)
        width, height = estimate_equation_size(script)
        logger.debug("HWCE script: %s (est. %dx%d)", script, width, height)
        return MathResult('hwce', script=script, width=width, height=height,
                          is_block=is_block)

    def render_inline(self, latex: str) -> MathResult:
        return self._render(latex, is_block=False)

    def render_block(self, latex: str) -> MathResult:
        return self._render(latex, is_block=True)


def create_renderer(config) -> MathRenderer | None:
    """Factory: create renderer based on config.MATH_HANDLING.

    Returns None for 'none' and 'italic' modes (no renderer needed).
    """
    if config.MATH_HANDLING == 'hwce':
        return HwceMathRenderer()
    return None
