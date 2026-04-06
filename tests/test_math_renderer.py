"""Tests for math_renderer module."""
import pytest


class TestMathResult:
    def test_math_result_creation(self):
        from md2hwpx.math_renderer import MathResult
        r = MathResult('hwce', script='x^{2}', width=1500, height=1500)
        assert r.kind == 'hwce'
        assert r.data['script'] == 'x^{2}'
        assert r.data['width'] == 1500

    def test_math_result_repr(self):
        from md2hwpx.math_renderer import MathResult
        r = MathResult('text', text='hello')
        assert 'text' in repr(r)


class TestCreateRenderer:
    def test_none_mode_returns_none(self):
        from md2hwpx.math_renderer import create_renderer
        from md2hwpx.config import ConversionConfig
        config = ConversionConfig()
        config.MATH_HANDLING = 'none'
        assert create_renderer(config) is None

    def test_italic_mode_returns_none(self):
        from md2hwpx.math_renderer import create_renderer
        from md2hwpx.config import ConversionConfig
        config = ConversionConfig()
        config.MATH_HANDLING = 'italic'
        assert create_renderer(config) is None

    def test_hwce_mode_returns_renderer(self):
        from md2hwpx.math_renderer import create_renderer, HwceMathRenderer
        from md2hwpx.config import ConversionConfig
        config = ConversionConfig()
        config.MATH_HANDLING = 'hwce'
        renderer = create_renderer(config)
        assert isinstance(renderer, HwceMathRenderer)


class TestHwceMathRenderer:
    def test_render_inline(self):
        from md2hwpx.math_renderer import HwceMathRenderer
        renderer = HwceMathRenderer()
        result = renderer.render_inline(r'E = mc^2')
        assert result.kind == 'hwce'
        assert 'script' in result.data
        assert result.data['width'] > 0
        assert result.data['height'] > 0
        assert result.data['is_block'] is False

    def test_render_block(self):
        from md2hwpx.math_renderer import HwceMathRenderer
        renderer = HwceMathRenderer()
        result = renderer.render_block(r'\frac{a}{b}')
        assert result.kind == 'hwce'
        assert 'over' in result.data['script']
        assert result.data['is_block'] is True

    def test_render_complex_equation(self):
        from md2hwpx.math_renderer import HwceMathRenderer
        renderer = HwceMathRenderer()
        result = renderer.render_inline(r'\sum_{i=1}^{n} x_i')
        assert 'sum' in result.data['script']
        assert 'from' in result.data['script']
        assert 'to' in result.data['script']


class TestMathRendererABC:
    def test_cannot_instantiate_abc(self):
        from md2hwpx.math_renderer import MathRenderer
        with pytest.raises(TypeError):
            MathRenderer()

    def test_subclass_must_implement_methods(self):
        from md2hwpx.math_renderer import MathRenderer

        class BadRenderer(MathRenderer):
            pass

        with pytest.raises(TypeError):
            BadRenderer()
