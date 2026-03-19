"""
AI 마인드맵 생성기
===================
Streamlit + Gemini 2.0 Flash + Mermaid.js

입력 지원: PDF / TXT / 이미지(OCR or Gemini Vision) / 직접 텍스트
출력     : 핵심 요약 + Whimsical 호환 Mermaid 마인드맵
"""

import io
import os
import re

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

# ─── 상수 ──────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"
SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"

# ─── 페이지 설정 ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI 마인드맵 생성기",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 커스텀 CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .main-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.2rem; }
    .sub-desc   { color: #555; margin-bottom: 1rem; }
    .stTabs [data-baseweb="tab"] { font-size: 0.95rem; font-weight: 600; }
    .stButton > button { border-radius: 8px; font-weight: 600; }
    pre { white-space: pre-wrap !important; word-break: break-all !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── 세션 상태 초기화 ────────────────────────────────────────────────────────────
for _key in ("summary", "mermaid_code", "raw_response"):
    if _key not in st.session_state:
        st.session_state[_key] = ""


# ══════════════════════════════════════════════════════════════════════════════
# 1. 텍스트 추출 유틸리티
# ══════════════════════════════════════════════════════════════════════════════

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """PyPDF2로 PDF 전 페이지에서 텍스트를 추출합니다."""
    import PyPDF2

    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[페이지 {i}]\n{text.strip()}")
    return "\n\n".join(pages)


def extract_text_from_txt(file_bytes: bytes) -> str:
    """여러 인코딩을 순서대로 시도하여 TXT 파일을 읽습니다."""
    for enc in ("utf-8", "euc-kr", "cp949", "latin-1"):
        try:
            return file_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return file_bytes.decode("utf-8", errors="replace")


def extract_text_via_ocr(file_bytes: bytes) -> str:
    """pytesseract + Pillow로 이미지에서 텍스트를 추출합니다.
    Tesseract가 설치되지 않았거나 결과가 없으면 빈 문자열을 반환합니다.
    """
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(file_bytes))
        try:
            text = pytesseract.image_to_string(img, lang="kor+eng")
        except pytesseract.TesseractError:
            text = pytesseract.image_to_string(img, lang="eng")
        return text.strip()
    except Exception:
        # pytesseract 미설치 / TesseractNotFoundError 등 모두 무시
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# 2. Gemini API 호출
# ══════════════════════════════════════════════════════════════════════════════

_PROMPT_TEMPLATE = """\
당신은 문서 분석 및 마인드맵 전문가입니다.
아래 내용을 분석하여 **반드시 지정된 형식으로만** 응답하세요.

[분석할 내용]
{content}

---

[응답 형식]

## 핵심 요약
- 요점 1
- 요점 2
- 요점 3
(3~5개 불릿)

## Mermaid 마인드맵
```mindmap
mindmap
  root((핵심 주제))
    대주제1
      소주제1-1
      소주제1-2
    대주제2
      소주제2-1
    대주제3
```

[마인드맵 필수 규칙]
1. 코드 블록은 ```mindmap 으로 시작하고 ``` 으로 끝낼 것
2. 첫 줄은 반드시 "mindmap"
3. 루트 노드는 root((주제)) 형식
4. 들여쓰기는 2칸 스페이스로 계층 표현
5. 최대 3단계 깊이 (root → 대주제 → 소주제)
6. 각 노드 텍스트: 20자 이내, 간결하게
7. 한국어 우선, 코드 블록 외 추가 설명 금지
"""

_IMAGE_PROMPT = """\
이 이미지를 분석하여 반드시 아래 형식으로만 응답하세요.

## 핵심 요약
- 요점 1
- 요점 2
- 요점 3

## Mermaid 마인드맵
```mindmap
mindmap
  root((핵심 주제))
    대주제1
      소주제1-1
    대주제2
    대주제3
```

규칙: mindmap 시작, root((주제)) 형식, 최대 3단계, 노드 20자 이내, 한국어 우선
"""


def _get_client(api_key: str):
    """google-genai 클라이언트를 반환합니다."""
    from google import genai  # google-genai 패키지

    return genai.Client(api_key=api_key)


def call_gemini_text(api_key: str, content: str) -> str:
    """텍스트를 Gemini 2.0 Flash에 전송하고 응답을 반환합니다."""
    client = _get_client(api_key)
    prompt = _PROMPT_TEMPLATE.format(content=content[:10_000])  # 토큰 절약
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text


def call_gemini_vision(api_key: str, image_bytes: bytes) -> str:
    """이미지를 Gemini Vision에 전송하고 응답을 반환합니다."""
    import PIL.Image

    client = _get_client(api_key)
    pil_image = PIL.Image.open(io.BytesIO(image_bytes))
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[_IMAGE_PROMPT, pil_image],
    )
    return response.text


# ══════════════════════════════════════════════════════════════════════════════
# 3. 응답 파싱
# ══════════════════════════════════════════════════════════════════════════════

def parse_gemini_response(text: str) -> tuple[str, str]:
    """Gemini 응답에서 (요약, Mermaid 코드) 를 분리합니다."""

    # ── 요약 추출 ──────────────────────────────────────────────────────────────
    summary = ""
    m = re.search(r"## 핵심 요약\s*(.*?)(?=## Mermaid|\Z)", text, re.DOTALL)
    if m:
        summary = m.group(1).strip()

    # ── Mermaid 코드 추출 ──────────────────────────────────────────────────────
    mermaid_code = ""

    # 방법 1: ```mindmap ... ``` 블록
    m = re.search(r"```mindmap\s*(.*?)```", text, re.DOTALL)
    if m:
        mermaid_code = m.group(1).strip()
        if not mermaid_code.startswith("mindmap"):
            mermaid_code = "mindmap\n" + mermaid_code

    # 방법 2 (폴백): mindmap 키워드부터 들여쓰기 블록
    if not mermaid_code:
        m = re.search(r"(mindmap\s*\n(?:[ \t]+.+\n?)+)", text)
        if m:
            mermaid_code = m.group(1).strip()

    return summary, mermaid_code


# ══════════════════════════════════════════════════════════════════════════════
# 4. Mermaid HTML 렌더러
# ══════════════════════════════════════════════════════════════════════════════

def build_mermaid_html(mermaid_code: str, height: int = 560) -> str:
    """mermaid.js CDN을 이용해 마인드맵을 렌더링하는 HTML을 반환합니다."""

    # JS 템플릿 리터럴 안에서 안전하게 사용하기 위한 이스케이프
    safe = (
        mermaid_code
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("$", "\\$")
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #ffffff; }}
    #wrap {{
      width: 100%;
      min-height: {height - 40}px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    #mm {{ width: 100%; text-align: center; }}
    #mm svg {{ max-width: 100% !important; height: auto !important; }}
    #loading {{ color: #666; font: 14px/1.5 sans-serif; }}
    #err {{
      display: none;
      color: #c0392b;
      background: #fdecea;
      border: 1px solid #e74c3c;
      border-radius: 6px;
      padding: 12px 16px;
      font: 13px/1.6 monospace;
      margin: 10px;
      white-space: pre-wrap;
      word-break: break-all;
    }}
  </style>
</head>
<body>
  <div id="wrap">
    <span id="loading">🔄 마인드맵 렌더링 중…</span>
    <div id="mm" style="display:none"></div>
  </div>
  <div id="err"></div>

  <script type="module">
    import mermaid from '{MERMAID_CDN}';

    mermaid.initialize({{
      startOnLoad: false,
      theme: 'default',
      mindmap: {{ useMaxWidth: true, padding: 20 }},
      securityLevel: 'loose',
      fontFamily: '"Noto Sans KR", "Malgun Gothic", sans-serif',
    }});

    const code = `{safe}`;
    const loading = document.getElementById('loading');
    const mm      = document.getElementById('mm');
    const errBox  = document.getElementById('err');

    try {{
      const {{ svg }} = await mermaid.render('mindmap-svg', code);
      mm.innerHTML = svg;
      mm.style.display = 'block';
      loading.style.display = 'none';
    }} catch (e) {{
      loading.style.display = 'none';
      errBox.style.display  = 'block';
      errBox.textContent =
        '⚠ 렌더링 오류: ' + e.message +
        '\\n\\n[원본 코드]\\n' + code;
    }}
  </script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# 5. 사이드바
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("⚙️ 설정")

    _env_key = os.getenv("GEMINI_API_KEY", "")
    api_key: str = st.text_input(
        "🔑 Gemini API Key",
        value=_env_key,
        type="password",
        placeholder="AIzaSy…",
        help="Google AI Studio(aistudio.google.com)에서 무료로 발급받을 수 있습니다.",
    )

    if api_key:
        st.success("API 키 설정 완료 ✔")
    else:
        st.warning("API 키를 입력해 주세요.")

    st.divider()

    with st.expander("📖 사용 방법", expanded=True):
        st.markdown(
            """
1. **API Key** 입력
2. **입력 방식** 선택
3. 파일 업로드 또는 텍스트 입력
4. **마인드맵 생성** 버튼 클릭
5. 탭에서 결과 확인 및 다운로드
            """
        )

    with st.expander("📋 지원 형식"):
        st.markdown(
            """
| 유형 | 확장자 |
|------|--------|
| 문서 | `.pdf`, `.txt` |
| 이미지 | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif` |
| 직접 입력 | 모든 텍스트 |
            """
        )

    st.divider()
    st.caption("Gemini 2.0 Flash · Mermaid v11 · Streamlit")


# ══════════════════════════════════════════════════════════════════════════════
# 6. 메인 UI
# ══════════════════════════════════════════════════════════════════════════════

st.markdown('<p class="main-title">🧠 AI 마인드맵 생성기</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-desc">PDF · 이미지 · 텍스트를 입력하면 '
    "<b>Gemini 2.0 Flash</b>가 분석하고 "
    "<b>Mermaid 마인드맵</b>을 자동 생성합니다.</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── 입력 방식 선택 ──────────────────────────────────────────────────────────────
input_mode: str = st.radio(
    "입력 방식",
    options=["📁 파일 업로드", "✏️ 텍스트 직접 입력"],
    horizontal=True,
    label_visibility="collapsed",
)

# 처리할 데이터를 담을 변수
raw_text: str = ""
vision_bytes: bytes | None = None  # Vision API에 넘길 이미지 바이트
use_vision: bool = False

st.markdown("")

# ══════════════════════════════════════════════════════════════════════════════
# 6-A. 파일 업로드 경로
# ══════════════════════════════════════════════════════════════════════════════
if input_mode == "📁 파일 업로드":

    uploaded = st.file_uploader(
        "파일을 선택하세요",
        type=["pdf", "txt", "png", "jpg", "jpeg", "webp", "bmp", "gif"],
        help="PDF·TXT·이미지(PNG/JPG/WEBP/BMP/GIF) 파일을 지원합니다.",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        file_bytes = uploaded.read()
        ext = os.path.splitext(uploaded.name)[1].lower()
        size_kb = len(file_bytes) / 1024

        st.caption(f"📂 `{uploaded.name}` — {size_kb:.1f} KB")

        # ── PDF ──────────────────────────────────────────────────────────────
        if ext == ".pdf":
            with st.spinner("PDF에서 텍스트 추출 중…"):
                raw_text = extract_text_from_pdf(file_bytes)

            if raw_text.strip():
                st.success(f"텍스트 추출 완료 ({len(raw_text):,}자)")
                with st.expander("📄 추출 텍스트 미리보기"):
                    st.text_area(
                        "내용",
                        value=raw_text[:3_000] + ("…" if len(raw_text) > 3_000 else ""),
                        height=180,
                        disabled=True,
                        label_visibility="collapsed",
                    )
            else:
                st.error(
                    "PDF에서 텍스트를 추출하지 못했습니다. "
                    "스캔 이미지 PDF의 경우 이미지 파일로 변환 후 업로드해 주세요."
                )

        # ── TXT ──────────────────────────────────────────────────────────────
        elif ext == ".txt":
            raw_text = extract_text_from_txt(file_bytes)
            st.success(f"파일 로드 완료 ({len(raw_text):,}자)")
            with st.expander("📝 파일 내용 미리보기"):
                st.text_area(
                    "내용",
                    value=raw_text[:3_000] + ("…" if len(raw_text) > 3_000 else ""),
                    height=180,
                    disabled=True,
                    label_visibility="collapsed",
                )

        # ── 이미지 ────────────────────────────────────────────────────────────
        elif ext in SUPPORTED_IMAGE_EXT:
            st.image(file_bytes, caption=uploaded.name, width=420)

            # OCR 시도
            with st.spinner("OCR로 텍스트 추출 중…"):
                ocr_text = extract_text_via_ocr(file_bytes)

            if ocr_text and len(ocr_text) > 30:
                raw_text = ocr_text
                st.success(f"OCR 완료 ({len(raw_text):,}자)")
                with st.expander("🔍 OCR 결과 미리보기"):
                    st.text_area(
                        "OCR",
                        value=ocr_text[:2_000],
                        height=150,
                        disabled=True,
                        label_visibility="collapsed",
                    )
            else:
                st.info(
                    "OCR 결과가 없거나 부족합니다. "
                    "Gemini Vision API로 이미지를 직접 분석합니다."
                )
                vision_bytes = file_bytes
                use_vision = True

# ══════════════════════════════════════════════════════════════════════════════
# 6-B. 텍스트 직접 입력 경로
# ══════════════════════════════════════════════════════════════════════════════
else:
    raw_text = st.text_area(
        "분석할 텍스트를 입력하세요",
        height=240,
        placeholder=(
            "논문 초록, 회의록, 강의 노트, 책 내용 등 어떤 텍스트든 입력하세요…\n\n"
            "예시:\n"
            "인공지능(AI)은 기계가 인간의 지능을 모방하도록 하는 기술입니다. "
            "머신러닝, 딥러닝, 자연어 처리 등의 분야로 나뉘며, "
            "현재 의료·금융·교육 등 다양한 분야에서 활용되고 있습니다."
        ),
        label_visibility="collapsed",
    )
    if raw_text:
        st.caption(f"입력 글자 수: {len(raw_text):,}자")

# ══════════════════════════════════════════════════════════════════════════════
# 7. 생성 버튼
# ══════════════════════════════════════════════════════════════════════════════
st.divider()

has_input = bool(raw_text and raw_text.strip()) or use_vision

btn_col, hint_col = st.columns([2, 5])
with btn_col:
    generate_clicked = st.button(
        "🚀 마인드맵 생성",
        type="primary",
        disabled=not has_input,
        use_container_width=True,
    )
with hint_col:
    if not api_key:
        st.warning("⚠️ 사이드바에서 Gemini API 키를 먼저 입력하세요.")
    elif not has_input:
        st.info("💡 파일을 업로드하거나 텍스트를 입력하세요.")
    else:
        st.success("✅ 준비 완료! 버튼을 클릭하세요.")

# ══════════════════════════════════════════════════════════════════════════════
# 8. 생성 실행
# ══════════════════════════════════════════════════════════════════════════════
if generate_clicked:
    if not api_key:
        st.error("Gemini API 키를 사이드바에 입력해 주세요.")
        st.stop()

    bar = st.progress(0, text="Gemini AI에 요청 준비 중…")

    try:
        bar.progress(15, text="Gemini AI에 요청 중…")

        if use_vision:
            response_text = call_gemini_vision(api_key, vision_bytes)
        else:
            response_text = call_gemini_text(api_key, raw_text)

        bar.progress(70, text="응답 파싱 중…")
        summary, mermaid_code = parse_gemini_response(response_text)

        bar.progress(90, text="마인드맵 준비 중…")

        if not mermaid_code:
            bar.empty()
            st.error("마인드맵 코드를 파싱하지 못했습니다. 다시 시도해 주세요.")
            with st.expander("🔍 원본 Gemini 응답 확인"):
                st.text(response_text)
            st.stop()

        # 세션 상태에 저장
        st.session_state["summary"] = summary
        st.session_state["mermaid_code"] = mermaid_code
        st.session_state["raw_response"] = response_text

        bar.progress(100, text="완료!")

    except Exception as exc:
        bar.empty()
        st.error(f"오류가 발생했습니다: {exc}")
        st.info("API 키를 확인하거나 잠시 후 다시 시도해 주세요.")
        st.stop()

    bar.empty()
    st.success("🎉 마인드맵이 생성되었습니다!")


# ══════════════════════════════════════════════════════════════════════════════
# 9. 결과 표시
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.get("mermaid_code"):
    st.divider()
    st.subheader("📊 분석 결과")

    tab_map, tab_summary, tab_code = st.tabs(
        ["🗺️ 마인드맵", "📝 핵심 요약", "💻 Mermaid 코드"]
    )

    # ── 탭 1: 마인드맵 렌더링 ─────────────────────────────────────────────────
    with tab_map:
        html_content = build_mermaid_html(st.session_state["mermaid_code"], height=580)
        components.html(html_content, height=600, scrolling=False)

        st.markdown("")
        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "⬇️ .mmd 파일로 저장",
                data=st.session_state["mermaid_code"],
                file_name="mindmap.mmd",
                mime="text/plain",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                "⬇️ Markdown (.md) 저장",
                data=(
                    "```mermaid\n"
                    + st.session_state["mermaid_code"]
                    + "\n```"
                ),
                file_name="mindmap.md",
                mime="text/markdown",
                use_container_width=True,
            )

    # ── 탭 2: 핵심 요약 ──────────────────────────────────────────────────────
    with tab_summary:
        if st.session_state.get("summary"):
            st.markdown(st.session_state["summary"])
        else:
            st.info("요약 내용을 찾지 못했습니다.")

    # ── 탭 3: Mermaid 코드 ───────────────────────────────────────────────────
    with tab_code:
        st.code(st.session_state["mermaid_code"], language="")

        st.markdown(
            """
**활용 방법**
- 코드를 복사 → [Mermaid Live Editor](https://mermaid.live/edit) 에 붙여넣기
- Whimsical 편집기의 **Import** 기능 사용
- Notion · Obsidian 등 Mermaid 지원 도구에서 직접 사용
            """
        )

        with st.expander("🔍 원본 Gemini 응답 전체 보기"):
            st.text(st.session_state.get("raw_response", ""))
