> ## 이 포크(greenoceanplanet/md2hwpx)에서 추가된 기능
> 표/그림에 pandoc 스타일 캡션(`: 캡션`, 그림 alt 텍스트)을 넣으면 한/글 네이티브
> 캡션 요소(`<hp:caption>` + `<hp:autoNum>`)로 변환되어, 한/글에서 "표 1", "그림 1"처럼
> **자동 번호가 매겨지고 순서 변경 시 자동 갱신**됩니다. 캡션 문단 스타일은 참조
> 템플릿에서 `표제목`/`그림제목`(있으면 우선) → 범용 `캡션`/`Caption` → Normal
> 순으로 동적으로 찾아 적용합니다.
>
> 변경 사항: [`MarkdownToHwpx.py`](md2hwpx/MarkdownToHwpx.py), [`marko_adapter.py`](md2hwpx/marko_adapter.py)
>
> 이 안내문 아래는 **원본(jundamin/md2hwpx) README 그대로**이며, 이 포크에서 수정하지
> 않았습니다.

---

# md2hwpx

**md2hwpx**는 마크다운(`.md`)을 아래아 한글 HWPX(`.hwpx`)로 변환해주는 파이썬 도구입니다. Pandoc 없이 순수 파이썬으로 동작합니다.

[pypandoc-hwpx 포크](https://github.com/msjang/pypandoc-hwpx)이며, 새로운 기능과 개선을 계속 추가하고 있습니다.

[English README](https://github.com/msjang/md2hwpx/blob/main/README.en.md)

## 주요 기능

- **Pandoc 없이 변환**: Marko 파서 + XML 생성으로 순수 파이썬 변환
- **CLI 및 Python API** 제공
- **YAML 프론트매터** 지원: 문서 `title` 메타데이터 작성
- **템플릿 기반 스타일**: 제목/본문/리스트/표 셀 플레이스홀더로 WYSIWYG 스타일링
- **이미지 prefix 지원**: 플레이스홀더 앞에 이미지를 배치하는 템플릿 스타일 자동 반영
- **헤더 앞 공백/페이지브레이크**: 레벨별 빈줄 수·높이·페이지브레이크 설정
- **설정 파일 지원**: JSON/YAML 설정 파일로 변환 옵션 일괄 관리
- **표 지원**: GFM 표, 정렬 및 컬럼 비율 반영
- **리스트**: 중첩 목록과 시작 번호 지원
- **이미지 임베딩**: 로컬 이미지 삽입, 크기 보정, 경로 검증
- **인용문, 수평선**
- **각주**
- **확장 헤더**: 1–9 레벨
- **디버그 출력**: `.json` AST, `.html` 출력

## 요구 사항

- **Python 3.9+**
- **라이브러리**: marko, python-frontmatter, Pillow

## 설치

### PyPI 설치 (권장)

```bash
pip install md2hwpx
```

### 소스 설치

```bash
git clone https://github.com/jundamin/md2hwpx.git
cd md2hwpx
pip install -e .
```

## 사용 방법

### CLI

```bash
# Markdown -> HWPX
md2hwpx input.md -o output.hwpx

# 참조 템플릿 지정
md2hwpx input.md --reference-doc=custom.hwpx -o output.hwpx

# 디버그: JSON AST 출력
md2hwpx input.md -o debug.json

# 디버그: HTML 출력
md2hwpx input.md -o output.html
```

### CLI 옵션

| 옵션 | 설명 |
|------|------|
| `input_file` | 입력 마크다운 파일 (.md, .markdown) |
| `-o`, `--output` | 출력 파일 (.hwpx, .json, .html) |
| `-r`, `--reference-doc` | 스타일/페이지 설정용 참조 HWPX (기본: 내장 blank.hwpx) |
| `--config FILE` | JSON/YAML 설정 파일 경로 (snake_case 키) |
| `--page-break-before LEVELS` | 지정 레벨 헤더 앞에 페이지브레이크 삽입. 예: `1,2` |
| `--blank-lines-before-header SPEC` | 레벨별 빈줄 수. 예: `2:2,3:1` |
| `--space-before-header SPEC` | 레벨별 정밀 공백 높이(mm). 예: `2:10,3:5` |
| `--blank-line-before-header` | H1–H3 앞에 빈줄 삽입 (레거시, 단순 on/off) |
| `--verbose` | 디버그 로그 출력 |
| `-q`, `--quiet` | 오류 외 출력 억제 |
| `-v`, `--version` | 버전 출력 |

### 프론트매터 (title)

```markdown
---
title: 문서 제목
---

# 제목
```

`title` 값은 HWPX 문서 메타데이터에 기록됩니다.

### Python API

```python
from md2hwpx import convert_string

# 기본 변환
convert_string("# 안녕하세요\n\n내용입니다.", "output.hwpx")

# 커스텀 템플릿
convert_string("# 안녕하세요\n\n내용입니다.", "output.hwpx", reference_doc="template.hwpx")

# ConversionConfig로 세부 설정
from md2hwpx.config import ConversionConfig

config = ConversionConfig()
config.PAGE_BREAK_BEFORE_HEADER_LEVELS = {1: True}
config.BLANK_LINES_BEFORE_HEADER = {2: [2, 5.0], 3: 1}  # H2 앞: 5mm 빈줄 2개, H3 앞: 기본 빈줄 1개

convert_string("# H1\n\n## H2\n\n본문", "output.hwpx", config=config)
```

## 헤더 앞 공백 / 페이지브레이크 설정

헤더(H1–H6) 앞에 빈줄이나 페이지브레이크를 레벨별로 지정할 수 있습니다.

### CLI로 지정

```bash
# H1 앞 페이지브레이크
md2hwpx input.md -o output.hwpx --page-break-before 1

# H2 앞 10mm 공백, H3 앞 5mm 공백
md2hwpx input.md -o output.hwpx --space-before-header 2:10,3:5

# H2 앞 빈줄 2개, H3 앞 빈줄 1개
md2hwpx input.md -o output.hwpx --blank-lines-before-header 2:2,3:1
```

### 설정 파일로 지정 (JSON/YAML)

```yaml
# config.yaml
page_break_before_header_levels:
  1: true
blank_lines_before_header:
  2: [2, 5.0]   # H2 앞: 5mm 높이 빈줄 2개
  3: [1, 3.0]   # H3 앞: 3mm 높이 빈줄 1개
  4: 1          # H4 앞: 기본 높이 빈줄 1개
space_before_header_mm:
  2: 10.0       # H2 앞: 10mm 공백 (blank_lines보다 우선)
```

```bash
md2hwpx input.md -o output.hwpx --config config.yaml
```

JSON 형식도 지원합니다:

```json
{
  "page_break_before_header_levels": {"1": true},
  "blank_lines_before_header": {"2": [2, 5.0], "3": 1}
}
```

### 우선순위

`--page-break-before` > `--space-before-header` > `--blank-lines-before-header` > `--blank-line-before-header` (레거시)

> **참고**: 문서의 첫 번째 블록이 헤더인 경우, 위 설정은 적용되지 않습니다.

## 스타일 커스터마이징 (템플릿)

한컴오피스에서 참조 HWPX 템플릿을 편집하면 출력 스타일을 손쉽게 제어할 수 있습니다.

### 방법 1: 플레이스홀더 방식 (권장)

템플릿에 플레이스홀더 텍스트를 넣고 원하는 서식을 적용합니다.

| 플레이스홀더 | 마크다운 요소 |
|-------------|---------------|
| `{{H1}}` | `# 제목 1` |
| `{{H2}}` | `## 제목 2` |
| `{{H3}}` | `### 제목 3` |
| `{{H4}}`–`{{H9}}` | `####`–`#########` |
| `{{BODY}}` | 본문 |

#### 리스트 플레이스홀더

리스트 레벨(1–7)별 스타일을 정의할 수 있습니다.

- `{{LIST_BULLET_1}}` … `{{LIST_BULLET_7}}`
- `{{LIST_ORDERED_1}}` … `{{LIST_ORDERED_7}}`

플레이스홀더 앞 텍스트는 접두(prefix)로 사용됩니다(예: `1. `, `가. `).
템플릿 단락에 번호 매기기를 지정하면 해당 번호 스타일을 유지합니다.

#### 이미지 prefix 플레이스홀더

플레이스홀더 앞에 이미지(`hp:pic`)를 배치하면 변환 결과에도 해당 이미지가 prefix로 반영됩니다.
예: 체크박스 이미지를 `{{LIST_BULLET_1}}` 앞에 삽입하면, 모든 1레벨 목록 항목 앞에 해당 이미지가 붙습니다.
이미지는 템플릿의 BinData에서 출력 파일로 자동 복사됩니다.

#### 표 셀 플레이스홀더

표 셀 스타일을 세부적으로 지정하려면 아래 12개 플레이스홀더를 사용하세요.

- `{{CELL_HEADER_LEFT}}`, `{{CELL_HEADER_CENTER}}`, `{{CELL_HEADER_RIGHT}}`
- `{{CELL_TOP_LEFT}}`, `{{CELL_TOP_CENTER}}`, `{{CELL_TOP_RIGHT}}`
- `{{CELL_MIDDLE_LEFT}}`, `{{CELL_MIDDLE_CENTER}}`, `{{CELL_MIDDLE_RIGHT}}`
- `{{CELL_BOTTOM_LEFT}}`, `{{CELL_BOTTOM_CENTER}}`, `{{CELL_BOTTOM_RIGHT}}`

사용 예:

```bash
md2hwpx input.md --reference-doc=my_template.hwpx -o output.hwpx
```

### 방법 2: 스타일 직접 편집

1. 기본 템플릿 복사:
   ```bash
   python -c "import md2hwpx; import shutil; shutil.copy(md2hwpx.__path__[0] + '/blank.hwpx', 'my_template.hwpx')"
   ```
2. 한컴오피스에서 **서식 > 스타일(F6)** 메뉴로 편집
3. 참조 템플릿으로 사용

## 지원하는 마크다운 요소

| 요소 | 지원 |
|------|------|
| 제목 (1–9) | 지원 |
| 문단 | 지원 |
| 굵게 / 기울임 / 취소선 | 지원 |
| 링크 | 지원 (HWPX 하이퍼링크) |
| 이미지 | 지원 (임베딩) |
| 표 (GFM) | 지원 (정렬 + 컬럼 비율) |
| 글머리/번호 목록 | 지원 (중첩) |
| 코드 블록 | 지원 |
| 인라인 코드 | 지원 |
| 인용문 | 지원 (중첩) |
| 수평선 | 지원 |
| 각주 | 지원 |
| 위첨자 / 아래첨자 | AST에 있으면 출력 지원 |

## 보안 및 제한 사항

- 입력/템플릿 파일 크기 제한 (기본 50 MB)
- 이미지 개수 제한 (기본 500)
- 이미지 경로 검증(절대 경로/상위 경로 차단)

## 개발

```bash
# 개발 설치
pip install -e .

# 테스트 실행
python -m pytest tests/ -v

# 자세한 로그로 실행
md2hwpx test.md -o output.hwpx --verbose
```

## 포크 이후 변경 사항

원본 포크 이후 주요 변경 사항:

- 헤더/리스트/표 셀 플레이스홀더 기반 스타일
- GFM 표 정렬 및 컬럼 비율 처리
- 프론트매터 메타데이터(title) 반영
- 리스트 시작 번호 및 템플릿 번호 매기기 개선
- 보안 제한(파일 크기, 이미지 개수, 경로 검증)
- 이미지 prefix 플레이스홀더 지원 (체크박스 등 이미지를 헤더/리스트 앞에 자동 반영)
- 헤더 앞 공백/페이지브레이크 레벨별 설정 (`--page-break-before`, `--space-before-header`, `--blank-lines-before-header`)
- 빈줄 높이(mm) 지정 지원 (`blank_lines_before_header: {2: [2, 5.0]}`)
- JSON/YAML 설정 파일 지원 (`--config`), Python API에서도 `ConversionConfig` 직접 전달 가능

## 라이선스

MIT License. 자세한 내용은 `LICENSE`를 참고하세요.
