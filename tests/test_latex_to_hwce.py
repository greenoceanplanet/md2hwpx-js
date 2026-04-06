"""Tests for LaTeX to Hancom equation script converter."""
import pytest
from md2hwpx.latex_to_hwce import LatexToHancomConverter, estimate_equation_size


class TestBasicSymbols:
    def test_greek_lowercase(self):
        assert 'alpha' in LatexToHancomConverter.convert(r'\alpha + \beta')
        assert 'beta' in LatexToHancomConverter.convert(r'\alpha + \beta')

    def test_greek_uppercase(self):
        assert 'Gamma' in LatexToHancomConverter.convert(r'\Gamma')
        assert 'Omega' in LatexToHancomConverter.convert(r'\Omega')

    def test_operators(self):
        assert 'times' in LatexToHancomConverter.convert(r'a \times b')
        assert 'cdot' in LatexToHancomConverter.convert(r'a \cdot b')
        assert '+-' in LatexToHancomConverter.convert(r'a \pm b')

    def test_relations(self):
        assert '!=' in LatexToHancomConverter.convert(r'a \neq b')
        assert 'leq' in LatexToHancomConverter.convert(r'a \leq b')
        assert 'geq' in LatexToHancomConverter.convert(r'a \geq b')
        assert 'approx' in LatexToHancomConverter.convert(r'a \approx b')

    def test_arrows(self):
        assert 'rarrow' in LatexToHancomConverter.convert(r'\rightarrow')
        assert 'rarrow' in LatexToHancomConverter.convert(r'\to')
        assert 'Rarrow' in LatexToHancomConverter.convert(r'\Rightarrow')

    def test_set_logic(self):
        assert 'in' in LatexToHancomConverter.convert(r'x \in A')
        assert 'subset' in LatexToHancomConverter.convert(r'A \subset B')
        assert 'union' in LatexToHancomConverter.convert(r'A \cup B')

    def test_misc_symbols(self):
        assert 'inf' in LatexToHancomConverter.convert(r'\infty')
        assert 'partial' in LatexToHancomConverter.convert(r'\partial')
        assert 'nabla' in LatexToHancomConverter.convert(r'\nabla')


class TestStructuralConversions:
    def test_frac(self):
        result = LatexToHancomConverter.convert(r'\frac{a}{b}')
        assert 'over' in result
        assert '{a}' in result
        assert '{b}' in result

    def test_sqrt(self):
        result = LatexToHancomConverter.convert(r'\sqrt{x}')
        assert result == 'sqrt{x}'

    def test_sqrt_nth(self):
        result = LatexToHancomConverter.convert(r'\sqrt[3]{x}')
        assert '3 sqrt{x}' == result

    def test_superscript(self):
        result = LatexToHancomConverter.convert(r'x^{2}')
        assert 'x^{2}' == result

    def test_subscript(self):
        result = LatexToHancomConverter.convert(r'x_{i}')
        assert 'x_{i}' == result

    def test_sum_with_limits(self):
        result = LatexToHancomConverter.convert(r'\sum_{i=1}^{n}')
        assert 'sum from{i=1} to{n}' == result

    def test_int_with_limits(self):
        result = LatexToHancomConverter.convert(r'\int_{a}^{b}')
        assert 'int from{a} to{b}' == result

    def test_lim(self):
        result = LatexToHancomConverter.convert(r'\lim_{x \to 0}')
        assert 'lim from{x rarrow 0}' == result

    def test_prod(self):
        result = LatexToHancomConverter.convert(r'\prod_{i=1}^{n}')
        assert 'prod from{i=1} to{n}' == result


class TestBrackets:
    def test_left_right_parens(self):
        result = LatexToHancomConverter.convert(r'\left( x \right)')
        assert 'left (' in result
        assert 'right )' in result

    def test_left_right_braces(self):
        result = LatexToHancomConverter.convert(r'\left\{ x \right\}')
        assert 'left lbrace' in result
        assert 'right rbrace' in result

    def test_angle_brackets(self):
        result = LatexToHancomConverter.convert(r'\left\langle x \right\rangle')
        assert 'left langle' in result
        assert 'right rangle' in result


class TestEnvironments:
    def test_pmatrix(self):
        result = LatexToHancomConverter.convert(
            r'\begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix}')
        assert 'pmatrix{' in result
        assert '#' in result
        assert '##' in result

    def test_bmatrix(self):
        result = LatexToHancomConverter.convert(
            r'\begin{bmatrix} a & b \\ c & d \end{bmatrix}')
        assert 'bmatrix{' in result

    def test_vmatrix(self):
        result = LatexToHancomConverter.convert(
            r'\begin{vmatrix} a & b \\ c & d \end{vmatrix}')
        assert 'dmatrix{' in result

    def test_cases(self):
        result = LatexToHancomConverter.convert(
            r'\begin{cases} x & x \geq 0 \\ -x & x < 0 \end{cases}')
        assert 'cases{' in result


class TestDecorations:
    def test_hat(self):
        assert 'hat' in LatexToHancomConverter.convert(r'\hat{a}')

    def test_bar(self):
        assert 'bar' in LatexToHancomConverter.convert(r'\bar{x}')

    def test_vec(self):
        assert 'vec' in LatexToHancomConverter.convert(r'\vec{v}')

    def test_overline(self):
        result = LatexToHancomConverter.convert(r'\overline{AB}')
        assert 'overline{AB}' == result

    def test_dot(self):
        assert 'dot' in LatexToHancomConverter.convert(r'\dot{x}')


class TestFontCommands:
    def test_mathrm(self):
        result = LatexToHancomConverter.convert(r'\mathrm{kg}')
        assert 'rm{kg}' == result

    def test_mathbf(self):
        result = LatexToHancomConverter.convert(r'\mathbf{A}')
        assert 'bf{A}' == result

    def test_mathbb(self):
        result = LatexToHancomConverter.convert(r'\mathbb{R}')
        assert 'Bbb{R}' == result

    def test_text(self):
        result = LatexToHancomConverter.convert(r'\text{hello}')
        assert 'rm{hello}' == result

    def test_mathcal(self):
        result = LatexToHancomConverter.convert(r'\mathcal{L}')
        assert 'cal{L}' == result


class TestMathFunctions:
    def test_sin(self):
        result = LatexToHancomConverter.convert(r'\sin x')
        assert result == 'sin x'

    def test_log(self):
        result = LatexToHancomConverter.convert(r'\log x')
        assert result == 'log x'

    def test_multiple_functions(self):
        result = LatexToHancomConverter.convert(r'\sin^{2} x + \cos^{2} x = 1')
        assert 'sin' in result
        assert 'cos' in result


class TestComplexExpressions:
    def test_quadratic_formula(self):
        result = LatexToHancomConverter.convert(
            r'\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}')
        assert 'over' in result
        assert 'sqrt' in result
        assert '+-' in result

    def test_euler_formula(self):
        result = LatexToHancomConverter.convert(r'e^{i \pi} + 1 = 0')
        assert 'pi' in result

    def test_linear_regression(self):
        result = LatexToHancomConverter.convert(
            r'Y_i = \beta_0 + \beta_1 X_i + \varepsilon_i')
        assert 'beta' in result
        assert 'varepsilon' in result

    def test_covariance(self):
        result = LatexToHancomConverter.convert(r'\text{Cov}(Z, X) \neq 0')
        assert 'rm{Cov}' in result
        assert '!=' in result

    def test_dollar_signs_stripped(self):
        result = LatexToHancomConverter.convert('$x^2$')
        assert result == 'x^{2}' or result == 'x^2'

    def test_spacing_commands_cleaned(self):
        result = LatexToHancomConverter.convert(r'a \, b \; c')
        assert '\\,' not in result
        assert '\\;' not in result


class TestEstimateSize:
    def test_simple_expression(self):
        w, h = estimate_equation_size('x^{2}')
        assert w >= 1500
        assert h >= 1000

    def test_fraction_taller(self):
        _, h_simple = estimate_equation_size('x')
        _, h_frac = estimate_equation_size('{a} over {b}')
        assert h_frac > h_simple

    def test_matrix_large(self):
        w, h = estimate_equation_size('pmatrix{1 # 0 ## 0 # 1}')
        assert w >= 8000
        assert h >= 2500

    def test_sum_tall(self):
        _, h = estimate_equation_size('sum from{i=1} to{n}')
        assert h >= 2500
