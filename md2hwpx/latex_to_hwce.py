"""
LaTeX to Hancom Equation Script (HWCE) converter.

Converts LaTeX math expressions to the proprietary script format used by
Hancom Office's equation editor (<hp:equation><hp:script>).

Reference: KS X 6101:2011 (OWPML) equation specification.
"""

import re


class LatexToHancomConverter:
    """Convert LaTeX math to Hancom equation script."""

    # Symbol map: LaTeX command → Hancom keyword
    # Sorted by length (longest first) during replacement to avoid partial matches.
    SYMBOL_MAP = {
        # Greek lowercase
        r'\alpha': 'alpha', r'\beta': 'beta', r'\gamma': 'gamma',
        r'\delta': 'delta', r'\epsilon': 'epsilon', r'\zeta': 'zeta',
        r'\eta': 'eta', r'\theta': 'theta', r'\iota': 'iota',
        r'\kappa': 'kappa', r'\lambda': 'lambda', r'\mu': 'mu',
        r'\nu': 'nu', r'\xi': 'xi', r'\pi': 'pi',
        r'\rho': 'rho', r'\sigma': 'sigma', r'\tau': 'tau',
        r'\upsilon': 'upsilon', r'\phi': 'phi', r'\chi': 'chi',
        r'\psi': 'psi', r'\omega': 'omega',
        # Greek uppercase
        r'\Gamma': 'Gamma', r'\Delta': 'Delta', r'\Theta': 'Theta',
        r'\Lambda': 'Lambda', r'\Xi': 'Xi', r'\Pi': 'Pi',
        r'\Sigma': 'Sigma', r'\Upsilon': 'Upsilon', r'\Phi': 'Phi',
        r'\Psi': 'Psi', r'\Omega': 'Omega',
        # Greek variants
        r'\varepsilon': 'varepsilon', r'\vartheta': 'vartheta',
        r'\varpi': 'varpi', r'\varrho': 'varrho',
        r'\varsigma': 'varsigma', r'\varphi': 'varphi',
        # Operators
        r'\times': 'times', r'\cdot': 'cdot', r'\div': 'div',
        r'\pm': '+-', r'\mp': '-+',
        # Relations
        r'\neq': '!=', r'\leq': 'leq', r'\geq': 'geq',
        r'\approx': 'approx', r'\equiv': 'equiv', r'\sim': 'sim',
        r'\simeq': 'simeq', r'\propto': 'propto',
        r'\ll': 'll', r'\gg': 'gg',
        r'\perp': 'perp', r'\parallel': 'parallel',
        # Set/logic
        r'\in': 'in', r'\notin': 'notin',
        r'\subset': 'subset', r'\supset': 'supset',
        r'\subseteq': 'subseteq', r'\supseteq': 'supseteq',
        r'\cup': 'union', r'\cap': 'inter',
        r'\emptyset': 'emptyset', r'\varnothing': 'emptyset',
        r'\forall': 'forall', r'\exists': 'exists',
        r'\therefore': 'therefore', r'\because': 'because',
        r'\land': 'land', r'\wedge': 'land',
        r'\lor': 'lor', r'\vee': 'lor',
        r'\lnot': 'lnot', r'\neg': 'lnot',
        # Arrows
        r'\rightarrow': 'rarrow', r'\to': 'rarrow',
        r'\leftarrow': 'larrow',
        r'\leftrightarrow': 'lrarrow',
        r'\Rightarrow': 'Rarrow', r'\Leftarrow': 'Larrow',
        r'\Leftrightarrow': 'Lrarrow',
        r'\uparrow': 'uarrow', r'\downarrow': 'darrow',
        # Misc
        r'\infty': 'inf', r'\partial': 'partial',
        r'\nabla': 'nabla', r'\hbar': 'hbar',
        r'\ell': 'ell', r'\aleph': 'aleph',
        r'\wp': 'wp', r'\Re': 'Re', r'\Im': 'Im',
        r'\cdots': 'cdots', r'\ldots': 'ldots',
        r'\vdots': 'vdots', r'\ddots': 'ddots',
        r'\prime': 'prime',
    }

    # Known math functions (backslash removed, rendered in roman)
    _MATH_FUNCTIONS = (
        'sin', 'cos', 'tan', 'csc', 'sec', 'cot',
        'arcsin', 'arccos', 'arctan',
        'sinh', 'cosh', 'tanh',
        'log', 'ln', 'exp', 'det', 'dim', 'gcd',
        'min', 'max', 'mod', 'inf', 'sup', 'ker', 'arg', 'deg', 'hom', 'lim',
    )
    _FUNC_RE = re.compile(
        r'\\(' + '|'.join(_MATH_FUNCTIONS) + r')(?![a-zA-Z])'
    )

    # Environment map: LaTeX env name → Hancom command
    _ENV_MAP = {
        'pmatrix': 'pmatrix',
        'bmatrix': 'bmatrix',
        'vmatrix': 'dmatrix',
        'Vmatrix': 'dmatrix',
        'matrix': 'matrix',
        'cases': 'cases',
    }

    # Structural regex rules: (pattern, replacement)
    # Applied in order. replacement=None means handled separately.
    _STRUCT_RULES = [
        # \frac{a}{b} → {a} over {b}
        (r'\\frac\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
         r'{\1} over {\2}'),
        # \sqrt[n]{x} → n sqrt{x}
        (r'\\sqrt\s*\[([^\]]+)\]\s*\{', r'\1 sqrt{'),
        # \sqrt{x} → sqrt{x}
        (r'\\sqrt\s*\{', 'sqrt{'),
        # \sum with both limits
        (r'\\sum\s*_\s*\{([^}]*)\}\s*\^\s*\{([^}]*)\}', r'sum from{\1} to{\2}'),
        (r'\\sum\s*_\s*\{([^}]*)\}', r'sum from{\1}'),
        (r'\\sum', 'sum'),
        # \prod
        (r'\\prod\s*_\s*\{([^}]*)\}\s*\^\s*\{([^}]*)\}', r'prod from{\1} to{\2}'),
        (r'\\prod\s*_\s*\{([^}]*)\}', r'prod from{\1}'),
        (r'\\prod', 'prod'),
        # \int variants
        (r'\\iiint', 'iiint'),
        (r'\\iint', 'iint'),
        (r'\\oint', 'oint'),
        (r'\\int\s*_\s*\{([^}]*)\}\s*\^\s*\{([^}]*)\}', r'int from{\1} to{\2}'),
        (r'\\int\s*_\s*\{([^}]*)\}', r'int from{\1}'),
        (r'\\int', 'int'),
        # \lim
        (r'\\lim\s*_\s*\{([^}]*)\}', r'lim from{\1}'),
        # \bigcup / \bigcap
        (r'\\bigcup\s*_\s*\{([^}]*)\}\s*\^\s*\{([^}]*)\}', r'bigcup from{\1} to{\2}'),
        (r'\\bigcup\s*_\s*\{([^}]*)\}', r'bigcup from{\1}'),
        (r'\\bigcap\s*_\s*\{([^}]*)\}\s*\^\s*\{([^}]*)\}', r'bigcap from{\1} to{\2}'),
        (r'\\bigcap\s*_\s*\{([^}]*)\}', r'bigcap from{\1}'),
        # Brackets
        (r'\\left\s*\\langle', 'left langle'),
        (r'\\right\s*\\rangle', 'right rangle'),
        (r'\\left\s*\\lfloor', 'left lfloor'),
        (r'\\right\s*\\rfloor', 'right rfloor'),
        (r'\\left\s*\\lceil', 'left lceil'),
        (r'\\right\s*\\rceil', 'right rceil'),
        (r'\\left\s*\\{', 'left lbrace'),
        (r'\\right\s*\\}', 'right rbrace'),
        (r'\\left\s*\\[|]', r'left |'),
        (r'\\right\s*\\[|]', r'right |'),
        (r'\\left(?!arrow|rightarrow)\s*', 'left '),
        (r'\\right(?!arrow)\s*', 'right '),
        # Decorations (single-char argument: \hat{a} → hat a)
        (r'\\hat\s*\{([^}])\}', r'hat \1'),
        (r'\\tilde\s*\{([^}])\}', r'tilde \1'),
        (r'\\bar\s*\{([^}])\}', r'bar \1'),
        (r'\\vec\s*\{([^}])\}', r'vec \1'),
        (r'\\dot\s*\{([^}])\}', r'dot \1'),
        (r'\\ddot\s*\{([^}])\}', r'ddot \1'),
        # Decorations (multi-char: keep braces)
        (r'\\overline\s*\{', 'overline{'),
        (r'\\underline\s*\{', 'underline{'),
        (r'\\widehat\s*\{', 'widehat{'),
        (r'\\widetilde\s*\{', 'widetilde{'),
        (r'\\overbrace\s*\{', 'overbrace{'),
        (r'\\underbrace\s*\{', 'underbrace{'),
        # Font commands
        (r'\\mathrm\s*\{', 'rm{'),
        (r'\\mathit\s*\{', 'it{'),
        (r'\\mathbf\s*\{', 'bf{'),
        (r'\\mathsf\s*\{', 'sf{'),
        (r'\\mathfrak\s*\{', 'frak{'),
        (r'\\mathcal\s*\{', 'cal{'),
        (r'\\mathbb\s*\{', 'Bbb{'),
        (r'\\text\s*\{', 'rm{'),
        (r'\\textrm\s*\{', 'rm{'),
        (r'\\textit\s*\{', 'it{'),
        (r'\\textbf\s*\{', 'bf{'),
    ]

    # Pre-compile structural regexes
    _COMPILED_STRUCT_RULES = [(re.compile(p), r) for p, r in _STRUCT_RULES]

    @classmethod
    def convert(cls, latex: str) -> str:
        """Convert a LaTeX math string to Hancom equation script.

        Args:
            latex: LaTeX math expression (without $ delimiters)

        Returns:
            Hancom equation script string
        """
        s = latex.strip().strip('$')

        # 1. Convert environments (matrix, cases)
        s = cls._convert_environments(s)

        # 2. Structural rules (regex-based)
        for pattern, replacement in cls._COMPILED_STRUCT_RULES:
            s = pattern.sub(replacement, s)

        # 3. Symbol substitution (longest first to avoid partial matches)
        for latex_cmd in sorted(cls.SYMBOL_MAP, key=len, reverse=True):
            s = s.replace(latex_cmd, cls.SYMBOL_MAP[latex_cmd])

        # 4. Math functions: \sin → sin, \cos → cos, etc.
        s = cls._FUNC_RE.sub(r'\1', s)

        # 5. Remaining \command → command (strip backslash)
        s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)

        # 6. LaTeX spacing commands: \, \; \! \> \quad \qquad → space
        s = re.sub(r'\\[,;!>]', ' ', s)
        s = s.replace(r'\quad', ' ')
        s = s.replace(r'\qquad', '  ')

        # 7. Clean up whitespace
        s = re.sub(r'\s+', ' ', s).strip()

        return s

    @classmethod
    def _convert_environments(cls, s: str) -> str:
        """Convert LaTeX environments (matrix, cases) to Hancom commands."""
        for latex_env, hancom_cmd in cls._ENV_MAP.items():
            pattern = re.compile(
                rf'\\begin\{{{latex_env}\}}(.*?)\\end\{{{latex_env}\}}',
                re.DOTALL
            )
            match = pattern.search(s)
            while match:
                body = match.group(1).strip()
                # & → # (column separator), \\ → ## (row separator)
                body = body.replace('&', ' # ')
                body = body.replace('\\\\', ' ## ')
                body = re.sub(r'\s+', ' ', body).strip()
                replacement = f'{hancom_cmd}{{{body}}}'
                s = s[:match.start()] + replacement + s[match.end():]
                match = pattern.search(s)
        return s


def estimate_equation_size(script: str) -> tuple[int, int]:
    """Estimate equation dimensions in HWPUNIT based on script complexity.

    Hancom Office auto-resizes equations when treatAsChar="1", so these
    are initial estimates. The editor will adjust the actual rendering size.
    Reference: equation_sample.hwpx uses w=1775, h=2100 for simple variables.

    Returns (width, height).
    """
    # Base: ~200 HWPUNIT per character width, 2100 default height (matches reference)
    base_w = len(script) * 200
    h = 2100

    if 'over' in script or 'sqrt' in script:
        h = 2800
        base_w = max(base_w, 3000)
    if 'matrix' in script or 'pmatrix' in script or 'bmatrix' in script or 'dmatrix' in script:
        base_w = max(base_w, 8000)
        row_count = script.count('##') + 1
        h = 2100 * row_count
    if 'cases' in script:
        row_count = script.count('##') + 1
        h = 2100 * row_count
        base_w = max(base_w, 6000)
    if 'sum' in script or 'int' in script or 'prod' in script:
        h = max(h, 3200)
    if 'from' in script or 'to' in script:
        h = max(h, 2800)

    width = max(base_w, 1500)
    width = min(width, 42000)  # Cap at ~page width
    return width, h
