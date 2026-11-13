# md2hwpx-js

**md2hwpx-js**는 마크다운(`.md`)을 아래아 한글 HWPX(`.hwpx`)로 변환하는 파이썬 도구입니다. Pandoc 없이 순수 파이썬으로 동작합니다.

[jundamin/md2hwpx](https://github.com/jundamin/md2hwpx)의 포크입니다(원본은 [pypandoc-hwpx](https://github.com/msjang/pypandoc-hwpx)의 포크). 원본 개발이 멈춘 뒤 이 저장소에서 따로 고쳐 쓰고 있어, 원본과 구별하려고 저장소 이름을 `md2hwpx-js`로 바꿨습니다. **명령과 파이썬 패키지 이름은 그대로 `md2hwpx`** 입니다. 원본과 달라진 점은 [원본 대비 변경 사항](#원본-대비-변경-사항)에 정리했습니다.

## 주요 기능

- **새 문서 만들기** : md → hwpx. 참조 문서(템플릿)의 스타일과 쪽 설정을 씀
- **기존 문서에 삽입** : md를 이미 있는 hwpx의 특정 절에 그 문서의 양식 그대로 넣음. 다시 돌리면 그 절만 새 내용으로 바뀜
- **스타일을 이름으로 지정** : 참조 문서의 스타일 이름(한/글 F6 목록)으로 제목·본문·글머리표·캡션 서식을 지정
- **한/글 네이티브 캡션** : 표·그림 캡션에 한/글 자동 번호(〈표 1〉, 〈그림 1〉)
- **한국어 보고서 초안 전처리** : 제목 앞 수동 번호 제거, `<표 N> 제목` 줄을 캡션으로, `자료 :` 줄 처리
- 템플릿 플레이스홀더(`{{H1}}`, `{{BODY}}`, `{{LIST_BULLET_1}}`, 표 셀 등)로 서식 지정
- 헤더 앞 공백·페이지브레이크를 수준별로 설정
- JSON/YAML 설정 파일
- GFM 표(정렬, 열 너비 비율), 중첩 목록, 이미지 임베딩, 인용문, 수평선, 각주, 수식(한/글 수식), 1–9 수준 제목
- 디버그 출력 : `.json` AST, `.html`

## 요구 사항

- Python 3.9+
- 라이브러리 : marko, python-frontmatter, Pillow (YAML 설정 파일을 쓰려면 PyYAML)

## 설치

PyPI의 `md2hwpx`는 원본 패키지이므로 이 포크의 기능이 없습니다. GitHub에서 설치합니다.

```bash
# uv (권장) : 전역 명령으로 설치
uv tool install --with pyyaml "git+https://github.com/greenoceanplanet/md2hwpx-js.git"

# 갱신 (uv tool은 설치 시점 커밋에 고정되므로, 저장소가 바뀌면 다시 설치)
uv tool install --reinstall --with pyyaml "git+https://github.com/greenoceanplanet/md2hwpx-js.git"

# pip
pip install "git+https://github.com/greenoceanplanet/md2hwpx-js.git" pyyaml
```

소스에서 개발용으로 설치

```bash
git clone https://github.com/greenoceanplanet/md2hwpx-js.git
cd md2hwpx-js
uv tool install --reinstall --with pyyaml .     # 또는 pip install -e . pyyaml
```

## 사용 방법

### 새 문서 만들기

```bash
md2hwpx input.md -o output.hwpx                         # 내장 blank.hwpx 양식
md2hwpx input.md --reference-doc=custom.hwpx -o output.hwpx
md2hwpx input.md -o output.hwpx --config 설정.yaml
md2hwpx input.md -o debug.json                          # 디버그: AST
md2hwpx input.md -o output.html                         # 디버그: HTML
```

### 기존 문서에 삽입

```bash
md2hwpx 초안.md --insert-into 보고서.hwpx --under-heading "절 제목" \
        --config 삽입설정.yaml -o 결과.hwpx
```

- 글자가 `--under-heading`과 같은 제목 문단을 찾아, 그 **다음부터 같은 수준 이상의 다음 제목 직전까지**를 통째로 바꿉니다. 목차 줄처럼 개요 수준이 없는 같은 글자 문단보다 개요 제목을 우선합니다.
- 다시 돌리면 이전 삽입분이 새 내용으로 바뀝니다. `-o`를 대상 파일과 같게 주면 제자리에서 갱신합니다.
- 대상 문서의 header.xml(스타일 정의)은 기존 정의를 그대로 두고, 변환 중 새로 생긴 정의만 끝에 덧붙입니다. 기존 정의와 똑같은 것은 덧붙이지 않고 재사용하므로, 여러 번 돌려도 정의가 쌓이지 않습니다.
- 그림 파일은 BinData에 넣고, 이전 삽입에서 넣었다가 더는 쓰지 않는 그림은 지웁니다. 표·그림 자동번호 값도 문서 순서대로 다시 매깁니다.
- 대상 문서의 스타일을 쓰려면 보통 `style_map`과 `table_style_from_document`를 함께 설정합니다(아래 설정 파일 참고).

### CLI 옵션

| 옵션 | 설명 |
|------|------|
| `input_file` | 입력 마크다운 파일 (.md, .markdown) |
| `-o`, `--output` | 출력 파일 (.hwpx, .json, .html) |
| `-r`, `--reference-doc` | 스타일·쪽 설정용 참조 HWPX (기본: 내장 blank.hwpx) |
| `--insert-into HWPX` | 새 문서 대신 이 기존 HWPX에 삽입 |
| `--under-heading TEXT` | `--insert-into`와 함께 : 이 제목 아래 절을 교체 |
| `--config FILE` | JSON/YAML 설정 파일 |
| `--page-break-before LEVELS` | 지정 수준 제목 앞에 쪽 나눔. 예: `1,2` |
| `--blank-lines-before-header SPEC` | 수준별 빈 줄 수. 예: `2:2,3:1` |
| `--space-before-header SPEC` | 수준별 정밀 공백(mm). 예: `2:10,3:5` |
| `--blank-line-before-header` | H1–H3 앞 빈 줄 (단순 on/off) |
| `--strip-quarto` 등 | Quarto/Pandoc 전처리 (`--help` 참고) |
| `--math {none,italic,hwce}` | LaTeX 수식 처리 |
| `--verbose` / `-q` / `-v` | 디버그 로그 / 오류만 출력 / 버전 |

### 프론트매터 (title)

```markdown
---
title: 문서 제목
---
```

`title` 값은 HWPX 문서 메타데이터에 기록됩니다.

### Python API

```python
from md2hwpx import convert_string, insert_markdown
from md2hwpx.config import ConversionConfig

# 새 문서
convert_string("# 안녕하세요\n\n내용입니다.", "output.hwpx", reference_doc="template.hwpx")

# 기존 문서에 삽입 (여러 절을 한 번에)
config = ConversionConfig.from_file("삽입설정.yaml")
insert_markdown("보고서.hwpx", "결과.hwpx",
                [("2절.md", "시뮬레이션 결과"), ("3절.md", "재원 조달")], config=config)
```

## 설정 파일 (YAML)

`--config 파일.yaml`로 넘깁니다(`.json`도 가능).

### 작성 요령

- 한 줄에 `키: 값`. 키는 아래 표의 이름(소문자·밑줄), 값 뒤 `#`부터는 주석
- 참/거짓은 `true` / `false`, 없음은 `null`, 목록은 `["자료", "주"]`
- 글자 값은 큰따옴표로 감싸는 편이 안전함. 특히 `1)` `(1)` `-` `□`처럼 기호가 든 스타일 이름
- `style_map`처럼 묶음인 값은 다음 줄부터 **공백 2칸** 들여 써서 `키: 값`을 나열(탭 금지)
- 정규식(`caption_line_regex`)은 작은따옴표로 감쌈(역슬래시를 그대로 쓰기 위해)
- 적지 않은 키는 기본값을 씀. CLI 옵션이 설정 파일보다 우선

예시 : [`templates/insert-config.example.yaml`](templates/insert-config.example.yaml)

```yaml
style_map:
  H1: null            # null이면 해당 수준 제목을 버림 (대상 문서에 이미 있는 절 제목 등)
  H2: "1)"
  H3: "(1)"
  BODY: "□"
  LIST_BULLET_1: "□"
  LIST_BULLET_2: "○"
  SOURCE: "표,그림 주,자료"
table_style_from_document: true
table_auto_width: true
strip_heading_numbers: true
korean_caption_lines: true
source_note_prefixes: ["자료", "주", "출처"]
```

### 스타일 지정 (`style_map`)

키는 마크다운 요소, 값은 참조(삽입 대상) 문서의 스타일 이름입니다. 문서마다 다른 스타일 번호를 몰라도 됩니다.

| 키 | 마크다운 요소 |
|---|---|
| `H1` … `H9` | `#` … `#########` 제목 (`null`이면 버림) |
| `BODY` | 일반 문단 |
| `LIST_BULLET_1` … `LIST_BULLET_7` | 글머리 목록 수준별 |
| `LIST_ORDERED_1` … `LIST_ORDERED_7` | 번호 목록 수준별 |
| `CAPTION`, `CAPTION_TABLE`, `CAPTION_FIGURE` | 캡션 (표·그림 공통 / 표 / 그림) |
| `SOURCE` | 자료 줄 (`source_note_prefixes` 또는 `*자료: ...*` 단독 문단) |
| `TABLE` | 표를 담는 문단 |
| `FIGURE` | 그림만 있는 문단 |

- 글머리 스타일의 문단모양에 글머리표(□ ○ 등)가 들어 있으면 글자 접두어를 따로 붙이지 않습니다.
- `style_map`은 템플릿 플레이스홀더보다 우선합니다. `style_map`을 쓰면 개요 수준이 중간에 빠진 문서도 오류 없이 처리합니다.

### 전체 키

| 키 | 값 | 기본값 | 뜻 |
|---|---|---|---|
| `style_map` | 묶음 | 없음 | 위 표 참고 |
| `table_style_from_document` | true/false | false | 참조 문서의 기존 표(캡션 있는 표 우선)에서 셀 테두리·배경, 셀 글자·문단 모양, 캡션 모양, 표 너비·바깥 여백을 본뜸 |
| `table_auto_width` | true/false | false | md 구분줄에 열 비율이 없을 때 열 너비를 글자 수에 비례 |
| `strip_heading_numbers` | true/false | false | 제목 앞 수동 번호(`가.` `1.` `1)` `(1)` `Ⅲ.` `①`) 제거. 한/글 개요 번호와 중복 방지 |
| `korean_caption_lines` | true/false | false | 표 위 `<표 N> 제목`, 그림 아래 `<그림 N> 제목` 줄을 자동번호 캡션으로 |
| `caption_line_regex` | 정규식 | `<표 N>`·`〈표 N〉` 형식 | 캡션 줄 형식. 괄호 묶음 2개(종류 낱말, 제목) |
| `caption_table_word` / `caption_figure_word` | 글자 | `표` / `그림` | 캡션 줄의 종류 낱말 |
| `table_caption_line_position` | above/below | above | 표 캡션 줄이 표의 위/아래 |
| `figure_caption_line_position` | above/below | below | 그림 캡션 줄이 그림의 위/아래 |
| `source_note_prefixes` | 목록 | 없음 | 이 낱말 + `:`로 시작하는 문단을 자료 줄로 |
| `single_tilde_strikethrough` | true/false | false | 물결표 하나(`60~80%`)를 취소선으로 볼지. `~~x~~`는 항상 취소선 |
| `page_break_before_header_levels` | 묶음 | 없음 | 예 `{1: true}` : H1 앞 쪽 나눔 |
| `blank_lines_before_header` | 묶음 | 없음 | 예 `{2: [2, 5.0], 3: 1}` : H2 앞 5mm 빈 줄 2개, H3 앞 기본 빈 줄 1개 |
| `space_before_header_mm` | 묶음 | 없음 | 예 `{2: 10.0}` : H2 앞 10mm (빈 줄 설정보다 우선) |
| `table_repeat_header` | true/false | true | 쪽이 넘어갈 때 표 머리행 반복 |
| `math_handling` | none/italic/hwce | hwce | LaTeX 수식 처리 |

헤더 앞 공백 우선순위 : `--page-break-before` > `--space-before-header` > `--blank-lines-before-header` > `--blank-line-before-header`. 문서의 첫 블록이 제목이면 이 설정은 적용되지 않습니다.

## 템플릿으로 서식 지정 (새 문서 만들기)

### 방법 1 : 플레이스홀더

참조 템플릿에 플레이스홀더 글자를 넣고 원하는 서식을 적용합니다. 예시 : [`templates/placeholder-template.hwpx`](templates/placeholder-template.hwpx)

| 플레이스홀더 | 마크다운 요소 |
|---|---|
| `{{H1}}` … `{{H9}}` | 제목 |
| `{{BODY}}` | 본문 |
| `{{LIST_BULLET_1}}` … `{{LIST_BULLET_7}}`, `{{LIST_ORDERED_1}}` … `{{LIST_ORDERED_7}}` | 목록 수준별 |
| `{{CELL_HEADER_LEFT/CENTER/RIGHT}}`, `{{CELL_TOP_*}}`, `{{CELL_MIDDLE_*}}`, `{{CELL_BOTTOM_*}}` | 표 셀(12종) |

- 플레이스홀더 앞 글자는 접두어로 쓰입니다(예 : `1. `, `가. `). 템플릿 문단에 번호 매기기가 있으면 그 번호를 유지합니다.
- 플레이스홀더 앞에 그림(`hp:pic`)을 두면 변환 결과에도 그 그림이 접두어로 붙습니다(예 : 체크박스).
- 표 셀 플레이스홀더는 테두리·배경, 셀 안 글자·문단 모양, 세로 정렬, 여백을 모두 가져옵니다.

### 방법 2 : 스타일 직접 편집

1. 기본 템플릿 복사 : `python -c "import md2hwpx, shutil; shutil.copy(md2hwpx.__path__[0] + '/blank.hwpx', 'my_template.hwpx')"`
2. 한컴오피스 **서식 > 스타일(F6)** 에서 편집
3. `--reference-doc`으로 지정. 또는 플레이스홀더 없이 `style_map`으로 스타일 이름을 지정

참조 템플릿의 제목 스타일에 개요 수준이 없으면(`style_map` 없이 쓸 때) `Requested Header Level N not found` 오류가 납니다. 스타일(F6) → 해당 제목 스타일 → 문단 모양에서 개요 수준을 지정하거나 `style_map`을 쓰세요.

## 지원하는 마크다운 요소

| 요소 | 지원 |
|------|------|
| 제목 (1–9) | 지원 |
| 문단 | 지원 |
| 굵게 / 기울임 / 취소선(`~~x~~`) | 지원 |
| 링크 | 지원 (HWPX 하이퍼링크) |
| 이미지 | 지원 (임베딩, 크기 자동 보정) |
| 표 (GFM) | 지원 (정렬, 열 비율, 캡션) |
| 글머리/번호 목록 | 지원 (중첩) |
| 코드 블록 / 인라인 코드 | 지원 |
| 인용문 | 지원 (중첩) |
| 수평선 | 지원 |
| 각주 | 지원 |
| 수식 (LaTeX) | 지원 (한/글 수식 개체) |

## 보안 및 제한 사항

- 입력·템플릿 파일 크기 제한 (기본 50 MB)
- 이미지 개수 제한 (기본 500)
- 이미지 경로 검증 : 절대 경로와 상위 폴더(`..`) 경로는 막음. 그림은 md 파일 기준 하위 경로에 둘 것

## 개발

```bash
uv run --with pytest --with marko --with python-frontmatter --with pillow --with pyyaml python -m pytest -q
md2hwpx test.md -o output.hwpx --verbose
```

코드 구조는 [`CLAUDE.md`](CLAUDE.md) 참고. 엔진을 고친 뒤에는 커밋·push 후 전역 설치를 갱신해야 반영됩니다.

## 원본 대비 변경 사항

원본 [jundamin/md2hwpx](https://github.com/jundamin/md2hwpx) 0.1.5 이후 이 포크에서 바꾼 것

- **기존 문서 삽입** : `--insert-into`, `--under-heading`, `insert_markdown()` ([`insert.py`](md2hwpx/insert.py))
- **스타일 이름 지정** : `style_map`
- **기존 표 양식 본뜨기** : `table_style_from_document`, 글자 수 기반 열 너비 `table_auto_width`
- **한/글 네이티브 캡션** : 표·그림 캡션을 `<hp:caption>` + `<hp:autoNum>`으로. 캡션 글자 모양도 캡션 스타일을 따름
- **한국어 보고서 초안 전처리** : `strip_heading_numbers`, `korean_caption_lines`(형식·위치 설정 가능), `source_note_prefixes`
- **자료 줄** : `*자료: ...*` 단독 문단을 본문과 다른 서식으로
- **버그 수정**
  - 물결표 하나(`60~80%`)가 취소선으로 해석되어 글자가 사라지던 문제
  - 글머리표·본문 문단에 플레이스홀더의 스타일 번호가 빠지던 문제
  - 표 셀 플레이스홀더의 글자·문단 모양과 세로 정렬이 무시되던 문제(머리행은 템플릿 정렬 유지, 본문 셀은 md 열 정렬을 셀 문단모양 위에 적용)
  - 단어마다 쪼개지던 글자 묶음(run)을 같은 글자모양끼리 합침

원본 README는 [jundamin/md2hwpx](https://github.com/jundamin/md2hwpx)에서 볼 수 있습니다. [`README.en.md`](README.en.md)는 원본의 영문 README이며 이 포크의 기능은 반영되어 있지 않습니다.

## 라이선스

MIT License. 원본 저작권 표시는 [`LICENSE`](LICENSE), [`NOTICE`](NOTICE)를 참고하세요.
