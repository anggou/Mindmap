"""
AI Mindmap Generator · AI 마인드맵 생성기
==========================================
Streamlit + Gemini 2.5 Flash / GPT-4o / Claude Sonnet + Mermaid.js
언어 선택: 한국어 / English
"""

import base64
import io
import os
import re

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

# ─── 상수 ──────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
GPT_MODEL    = "gpt-4o"
CLAUDE_MODEL = "claude-sonnet-4-6"

SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"

PROVIDER_OPTIONS = ["🔷 Gemini (Google)", "🟢 GPT (OpenAI)", "🟠 Claude (Anthropic)"]
PROVIDER_KEYS    = {
    "🔷 Gemini (Google)":    "gemini",
    "🟢 GPT (OpenAI)":       "gpt",
    "🟠 Claude (Anthropic)": "claude",
}
MODEL_LABEL = {
    "gemini": "🔷 Gemini 2.5 Flash",
    "gpt":    "🟢 GPT-4o",
    "claude": "🟠 Claude Sonnet 4.6",
}


# ══════════════════════════════════════════════════════════════════════════════
# 다국어 번역 테이블
# ══════════════════════════════════════════════════════════════════════════════

TRANSLATIONS: dict[str, dict] = {
    "한국어": {
        # ── 페이지 ──────────────────────────────────────────────────────────
        "main_title":        "🧠 AI 마인드맵 생성기",
        "sub_desc":          "PDF · 이미지 · 텍스트를 입력하면 <b>{model}</b>가 분석하고 <b>Mermaid 마인드맵</b>을 자동 생성합니다.",
        # ── 사이드바 ─────────────────────────────────────────────────────────
        "lang_label":        "🌐 언어 / Language",
        "settings":          "⚙️ 설정",
        "step1":             "**1단계: AI 모델 선택**",
        "step2":             "**2단계: API 키 입력**",
        "api_key_ok":        "API 키 설정 완료 ✔",
        "api_key_missing":   "API 키를 입력해 주세요.\n\n{hint}",
        # ── API 키 입력 ───────────────────────────────────────────────────────
        "gemini_key_label":  "🔑 Gemini API Key",
        "gemini_key_ph":     "AIzaSy…",
        "gemini_key_help":   "Google AI Studio에서 무료로 발급받을 수 있습니다.",
        "gemini_key_hint":   "💡 aistudio.google.com → Get API key",
        "gpt_key_label":     "🔑 OpenAI API Key",
        "gpt_key_ph":        "sk-…",
        "gpt_key_help":      "platform.openai.com에서 발급받을 수 있습니다.",
        "gpt_key_hint":      "💡 platform.openai.com → API keys → Create",
        "claude_key_label":  "🔑 Anthropic API Key",
        "claude_key_ph":     "sk-ant-…",
        "claude_key_help":   "console.anthropic.com에서 발급받을 수 있습니다.",
        "claude_key_hint":   "💡 console.anthropic.com → API keys → Create key",
        # ── 사이드바 익스팬더 ─────────────────────────────────────────────────
        "how_to_use":        "📖 사용 방법",
        "how_to_use_body":   """\
1. **AI 모델** 선택 (Gemini / GPT / Claude)
2. 선택한 모델의 **API Key** 입력
3. **입력 방식** 선택 (파일 업로드 또는 텍스트)
4. 파일 업로드 또는 텍스트 입력
5. **마인드맵 생성** 버튼 클릭
6. 탭에서 결과 확인 및 다운로드
""",
        "key_guide":         "🔑 API 키 발급 방법",
        "key_guide_body":    """\
**Gemini** (무료 티어 있음)
- [aistudio.google.com](https://aistudio.google.com/app/apikey) → Get API key

**GPT (OpenAI)**
- [platform.openai.com](https://platform.openai.com/api-keys) → API keys → Create

**Claude (Anthropic)**
- [console.anthropic.com](https://console.anthropic.com/settings/keys) → API keys → Create key
""",
        "formats":           "📋 지원 형식",
        "formats_body":      """\
| 유형 | 확장자 |
|------|--------|
| 문서 | `.pdf`, `.txt` |
| 이미지 | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif` |
| 직접 입력 | 모든 텍스트 |
""",
        "sidebar_caption":   "현재 모델: {model} · Mermaid v11 · Streamlit",
        # ── 입력 UI ───────────────────────────────────────────────────────────
        "mode_file":         "📁 파일 업로드",
        "mode_text":         "✏️ 텍스트 직접 입력",
        "uploader_help":     "PDF·TXT·이미지(PNG/JPG/WEBP/BMP/GIF) 파일을 지원합니다.",
        "file_caption":      "📂 `{name}` — {size:.1f} KB",
        "pdf_spinner":       "PDF에서 텍스트 추출 중…",
        "pdf_ok":            "텍스트 추출 완료 ({n:,}자)",
        "pdf_preview":       "📄 추출 텍스트 미리보기",
        "pdf_error":         "PDF에서 텍스트를 추출하지 못했습니다. 스캔 이미지 PDF는 이미지 파일로 변환 후 업로드해 주세요.",
        "txt_ok":            "파일 로드 완료 ({n:,}자)",
        "txt_preview":       "📝 파일 내용 미리보기",
        "ocr_spinner":       "OCR로 텍스트 추출 중…",
        "ocr_ok":            "OCR 완료 ({n:,}자)",
        "ocr_preview":       "🔍 OCR 결과 미리보기",
        "ocr_fallback":      "OCR 결과가 없거나 부족합니다. {model} Vision으로 이미지를 직접 분석합니다.",
        "text_label":        "분석할 텍스트를 입력하세요",
        "text_ph":           "논문 초록, 회의록, 강의 노트, 책 내용 등 어떤 텍스트든 입력하세요…\n\n예시:\n인공지능(AI)은 기계가 인간의 지능을 모방하도록 하는 기술입니다. 머신러닝, 딥러닝, 자연어 처리 등의 분야로 나뉘며, 현재 의료·금융·교육 등 다양한 분야에서 활용되고 있습니다.",
        "char_count":        "입력 글자 수: {n:,}자",
        # ── 버튼 & 힌트 ───────────────────────────────────────────────────────
        "gen_btn":           "🚀 마인드맵 생성",
        "hint_no_key":       "⚠️ 사이드바에서 {model} API 키를 먼저 입력하세요.",
        "hint_no_input":     "💡 파일을 업로드하거나 텍스트를 입력하세요.",
        "hint_ready":        "✅ 준비 완료! ({model}) 버튼을 클릭하세요.",
        # ── 진행 & 오류 ───────────────────────────────────────────────────────
        "prog_prepare":      "{model}에 요청 준비 중…",
        "prog_request":      "{model}에 요청 중…",
        "prog_parse":        "응답 파싱 중…",
        "prog_render":       "마인드맵 준비 중…",
        "prog_done":         "완료!",
        "err_no_key":        "{model} API 키를 사이드바에 입력해 주세요.",
        "err_parse":         "마인드맵 코드를 파싱하지 못했습니다. 다시 시도해 주세요.",
        "err_raw":           "🔍 원본 {model} 응답 확인",
        "err_general":       "오류가 발생했습니다: {err}",
        "err_retry":         "API 키를 확인하거나 잠시 후 다시 시도해 주세요.",
        "success":           "🎉 마인드맵이 생성되었습니다!",
        # ── 결과 탭 ───────────────────────────────────────────────────────────
        "results":           "📊 분석 결과",
        "tab_map":           "🗺️ 마인드맵",
        "tab_summary":       "📝 핵심 요약",
        "tab_code":          "💻 Mermaid 코드",
        "dl_mmd":            "⬇️ .mmd 파일로 저장",
        "dl_md":             "⬇️ Markdown (.md) 저장",
        "summary_empty":     "요약 내용을 찾지 못했습니다.",
        "code_usage":        """\
**활용 방법**
- 코드를 복사 → [Mermaid Live Editor](https://mermaid.live/edit) 에 붙여넣기
- Whimsical 편집기의 **Import** 기능 사용
- Notion · Obsidian 등 Mermaid 지원 도구에서 직접 사용
""",
        "raw_response":      "🔍 원본 AI 응답 전체 보기",
    },

    "English": {
        # ── Page ────────────────────────────────────────────────────────────
        "main_title":        "🧠 AI Mindmap Generator",
        "sub_desc":          "Upload PDF · images · text and <b>{model}</b> will analyze and auto-generate a <b>Mermaid mindmap</b>.",
        # ── Sidebar ──────────────────────────────────────────────────────────
        "lang_label":        "🌐 Language / 언어",
        "settings":          "⚙️ Settings",
        "step1":             "**Step 1: Select AI Model**",
        "step2":             "**Step 2: Enter API Key**",
        "api_key_ok":        "API key configured ✔",
        "api_key_missing":   "Please enter your API key.\n\n{hint}",
        # ── API Key inputs ───────────────────────────────────────────────────
        "gemini_key_label":  "🔑 Gemini API Key",
        "gemini_key_ph":     "AIzaSy…",
        "gemini_key_help":   "Get a free key at Google AI Studio (aistudio.google.com).",
        "gemini_key_hint":   "💡 aistudio.google.com → Get API key",
        "gpt_key_label":     "🔑 OpenAI API Key",
        "gpt_key_ph":        "sk-…",
        "gpt_key_help":      "Get your key at platform.openai.com.",
        "gpt_key_hint":      "💡 platform.openai.com → API keys → Create",
        "claude_key_label":  "🔑 Anthropic API Key",
        "claude_key_ph":     "sk-ant-…",
        "claude_key_help":   "Get your key at console.anthropic.com.",
        "claude_key_hint":   "💡 console.anthropic.com → API keys → Create key",
        # ── Sidebar expanders ────────────────────────────────────────────────
        "how_to_use":        "📖 How to Use",
        "how_to_use_body":   """\
1. **Select AI Model** (Gemini / GPT / Claude)
2. Enter the **API Key** for the selected model
3. **Choose input method** (file upload or text)
4. Upload a file or type/paste text
5. Click **Generate Mindmap**
6. View results and download from the tabs
""",
        "key_guide":         "🔑 How to Get API Keys",
        "key_guide_body":    """\
**Gemini** (free tier available)
- [aistudio.google.com](https://aistudio.google.com/app/apikey) → Get API key

**GPT (OpenAI)**
- [platform.openai.com](https://platform.openai.com/api-keys) → API keys → Create

**Claude (Anthropic)**
- [console.anthropic.com](https://console.anthropic.com/settings/keys) → API keys → Create key
""",
        "formats":           "📋 Supported Formats",
        "formats_body":      """\
| Type | Extension |
|------|-----------|
| Document | `.pdf`, `.txt` |
| Image | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif` |
| Direct input | Any text |
""",
        "sidebar_caption":   "Model: {model} · Mermaid v11 · Streamlit",
        # ── Input UI ─────────────────────────────────────────────────────────
        "mode_file":         "📁 File Upload",
        "mode_text":         "✏️ Direct Text Input",
        "uploader_help":     "Supports PDF · TXT · images (PNG/JPG/WEBP/BMP/GIF).",
        "file_caption":      "📂 `{name}` — {size:.1f} KB",
        "pdf_spinner":       "Extracting text from PDF…",
        "pdf_ok":            "Text extracted ({n:,} chars)",
        "pdf_preview":       "📄 Extracted Text Preview",
        "pdf_error":         "Could not extract text from the PDF. For scanned PDFs, please convert to an image file first.",
        "txt_ok":            "File loaded ({n:,} chars)",
        "txt_preview":       "📝 File Content Preview",
        "ocr_spinner":       "Extracting text via OCR…",
        "ocr_ok":            "OCR complete ({n:,} chars)",
        "ocr_preview":       "🔍 OCR Result Preview",
        "ocr_fallback":      "OCR found little or no text. Analyzing image directly with {model} Vision.",
        "text_label":        "Enter text to analyze",
        "text_ph":           "Paste any text — paper abstract, meeting notes, lecture notes, book content…\n\nExample:\nArtificial Intelligence (AI) is technology that enables machines to mimic human intelligence. It spans fields like machine learning, deep learning, and natural language processing, and is used in healthcare, finance, education, and more.",
        "char_count":        "Character count: {n:,}",
        # ── Button & hints ───────────────────────────────────────────────────
        "gen_btn":           "🚀 Generate Mindmap",
        "hint_no_key":       "⚠️ Please enter your {model} API key in the sidebar.",
        "hint_no_input":     "💡 Please upload a file or enter some text.",
        "hint_ready":        "✅ Ready! ({model}) Click the button.",
        # ── Progress & errors ────────────────────────────────────────────────
        "prog_prepare":      "Preparing request to {model}…",
        "prog_request":      "Sending request to {model}…",
        "prog_parse":        "Parsing response…",
        "prog_render":       "Preparing mindmap…",
        "prog_done":         "Done!",
        "err_no_key":        "Please enter your {model} API key in the sidebar.",
        "err_parse":         "Could not parse the mindmap code. Please try again.",
        "err_raw":           "🔍 View raw {model} response",
        "err_general":       "An error occurred: {err}",
        "err_retry":         "Please check your API key or try again later.",
        "success":           "🎉 Mindmap generated successfully!",
        # ── Result tabs ──────────────────────────────────────────────────────
        "results":           "📊 Analysis Results",
        "tab_map":           "🗺️ Mindmap",
        "tab_summary":       "📝 Key Summary",
        "tab_code":          "💻 Mermaid Code",
        "dl_mmd":            "⬇️ Save as .mmd",
        "dl_md":             "⬇️ Save as Markdown (.md)",
        "summary_empty":     "No summary content found.",
        "code_usage":        """\
**How to use this code**
- Copy → paste into [Mermaid Live Editor](https://mermaid.live/edit)
- Use the **Import** feature in Whimsical
- Use directly in Notion, Obsidian, or any Mermaid-compatible tool
""",
        "raw_response":      "🔍 View full AI response",
    },
}

LANG_OPTIONS = list(TRANSLATIONS.keys())   # ["한국어", "English"]


# ══════════════════════════════════════════════════════════════════════════════
# AI 프롬프트 템플릿 (언어별)
# ══════════════════════════════════════════════════════════════════════════════

_TEXT_PROMPTS: dict[str, str] = {
    "한국어": """\
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
7. 반드시 한국어로 응답, 코드 블록 외 추가 설명 금지
""",
    "English": """\
You are an expert in document analysis and mindmap creation.
Analyze the content below and **respond strictly in the specified format only**.

[Content to Analyze]
{content}

---

[Response Format]

## Key Summary
- Key point 1
- Key point 2
- Key point 3
(3–5 bullet points)

## Mermaid Mindmap
```mindmap
mindmap
  root((Main Topic))
    Topic1
      Subtopic1-1
      Subtopic1-2
    Topic2
      Subtopic2-1
    Topic3
```

[Mindmap Rules]
1. Code block must start with ```mindmap and end with ```
2. First line must be "mindmap"
3. Root node must use the format root((Topic))
4. Use 2-space indentation for hierarchy
5. Maximum 3 levels deep (root → main topic → subtopic)
6. Each node text: concise, under 20 characters
7. Respond entirely in English. No extra explanation outside code blocks.
""",
}

_IMAGE_PROMPTS: dict[str, str] = {
    "한국어": """\
이 이미지를 분석하여 반드시 아래 형식으로만 한국어로 응답하세요.

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

규칙: mindmap 시작, root((주제)) 형식, 최대 3단계, 노드 20자 이내, 한국어 응답
""",
    "English": """\
Analyze this image and respond strictly in the format below. Use English only.

## Key Summary
- Key point 1
- Key point 2
- Key point 3

## Mermaid Mindmap
```mindmap
mindmap
  root((Main Topic))
    Topic1
      Subtopic1-1
    Topic2
    Topic3
```

Rules: start with mindmap, use root((Topic)) format, max 3 levels, node text under 20 chars, English only
""",
}


# ─── 페이지 설정 ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Mindmap Generator · 마인드맵 생성기",
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
for _k in ("summary", "mermaid_code", "raw_response"):
    if _k not in st.session_state:
        st.session_state[_k] = ""


# ══════════════════════════════════════════════════════════════════════════════
# 1. 텍스트 추출 유틸리티
# ══════════════════════════════════════════════════════════════════════════════

def extract_text_from_pdf(file_bytes: bytes) -> str:
    import PyPDF2
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[Page {i}]\n{text.strip()}")
    return "\n\n".join(pages)


def extract_text_from_txt(file_bytes: bytes) -> str:
    for enc in ("utf-8", "euc-kr", "cp949", "latin-1"):
        try:
            return file_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return file_bytes.decode("utf-8", errors="replace")


def extract_text_via_ocr(file_bytes: bytes) -> str:
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
        return ""


def _to_png_bytes(image_bytes: bytes) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# 2. Gemini API
# ══════════════════════════════════════════════════════════════════════════════

def call_gemini_text(api_key: str, content: str, lang: str) -> str:
    from google import genai
    client = genai.Client(api_key=api_key)
    prompt = _TEXT_PROMPTS[lang].format(content=content[:10_000])
    return client.models.generate_content(model=GEMINI_MODEL, contents=prompt).text


def call_gemini_vision(api_key: str, image_bytes: bytes, lang: str) -> str:
    import PIL.Image
    from google import genai
    client = genai.Client(api_key=api_key)
    pil_image = PIL.Image.open(io.BytesIO(image_bytes))
    return client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[_IMAGE_PROMPTS[lang], pil_image],
    ).text


# ══════════════════════════════════════════════════════════════════════════════
# 3. GPT (OpenAI) API
# ══════════════════════════════════════════════════════════════════════════════

def call_gpt_text(api_key: str, content: str, lang: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    prompt = _TEXT_PROMPTS[lang].format(content=content[:10_000])
    resp = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return resp.choices[0].message.content


def call_gpt_vision(api_key: str, image_bytes: bytes, lang: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    b64 = base64.standard_b64encode(_to_png_bytes(image_bytes)).decode()
    resp = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": _IMAGE_PROMPTS[lang]},
            ],
        }],
        max_tokens=2048,
    )
    return resp.choices[0].message.content


# ══════════════════════════════════════════════════════════════════════════════
# 4. Claude (Anthropic) API
# ══════════════════════════════════════════════════════════════════════════════

def call_claude_text(api_key: str, content: str, lang: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _TEXT_PROMPTS[lang].format(content=content[:10_000])
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def call_claude_vision(api_key: str, image_bytes: bytes, lang: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    b64 = base64.standard_b64encode(_to_png_bytes(image_bytes)).decode()
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": _IMAGE_PROMPTS[lang]},
            ],
        }],
    )
    return msg.content[0].text


# ══════════════════════════════════════════════════════════════════════════════
# 5. AI 디스패처
# ══════════════════════════════════════════════════════════════════════════════

def call_ai_text(provider: str, api_key: str, content: str, lang: str) -> str:
    if provider == "gemini":
        return call_gemini_text(api_key, content, lang)
    if provider == "gpt":
        return call_gpt_text(api_key, content, lang)
    if provider == "claude":
        return call_claude_text(api_key, content, lang)
    raise ValueError(provider)


def call_ai_vision(provider: str, api_key: str, image_bytes: bytes, lang: str) -> str:
    if provider == "gemini":
        return call_gemini_vision(api_key, image_bytes, lang)
    if provider == "gpt":
        return call_gpt_vision(api_key, image_bytes, lang)
    if provider == "claude":
        return call_claude_vision(api_key, image_bytes, lang)
    raise ValueError(provider)


# ══════════════════════════════════════════════════════════════════════════════
# 6. 응답 파싱 (한국어·영어 헤더 모두 처리)
# ══════════════════════════════════════════════════════════════════════════════

def parse_ai_response(text: str) -> tuple[str, str]:
    summary = ""
    m = re.search(
        r"## (?:핵심 요약|Key Summary)\s*(.*?)(?=## (?:Mermaid|마인드맵)|\Z)",
        text, re.DOTALL,
    )
    if m:
        summary = m.group(1).strip()

    mermaid_code = ""
    m = re.search(r"```mindmap\s*(.*?)```", text, re.DOTALL)
    if m:
        mermaid_code = m.group(1).strip()
        if not mermaid_code.startswith("mindmap"):
            mermaid_code = "mindmap\n" + mermaid_code

    if not mermaid_code:
        m = re.search(r"(mindmap\s*\n(?:[ \t]+.+\n?)+)", text)
        if m:
            mermaid_code = m.group(1).strip()

    return summary, mermaid_code


# ══════════════════════════════════════════════════════════════════════════════
# 7. Mermaid HTML 렌더러
# ══════════════════════════════════════════════════════════════════════════════

def build_mermaid_html(mermaid_code: str, height: int = 560) -> str:
    safe = mermaid_code.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #ffffff; }}
    #wrap {{
      width: 100%; min-height: {height - 40}px;
      display: flex; align-items: center; justify-content: center; padding: 20px;
    }}
    #mm {{ width: 100%; text-align: center; }}
    #mm svg {{ max-width: 100% !important; height: auto !important; }}
    #loading {{ color: #666; font: 14px/1.5 sans-serif; }}
    #err {{
      display: none; color: #c0392b; background: #fdecea;
      border: 1px solid #e74c3c; border-radius: 6px;
      padding: 12px 16px; font: 13px/1.6 monospace; margin: 10px;
      white-space: pre-wrap; word-break: break-all;
    }}
  </style>
</head>
<body>
  <div id="wrap">
    <span id="loading">🔄 Rendering…</span>
    <div id="mm" style="display:none"></div>
  </div>
  <div id="err"></div>
  <script type="module">
    import mermaid from '{MERMAID_CDN}';
    mermaid.initialize({{
      startOnLoad: false, theme: 'default',
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
      errBox.textContent = '⚠ Render error: ' + e.message + '\\n\\n[Code]\\n' + code;
    }}
  </script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# 8. 사이드바
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    # ── 1. 언어 선택 (가장 먼저) ─────────────────────────────────────────────
    selected_lang: str = st.radio(
        "🌐 Language / 언어",
        options=LANG_OPTIONS,
        horizontal=True,
        key="lang_radio",
        label_visibility="visible",
    )
    T = TRANSLATIONS[selected_lang]

    st.divider()
    st.header(T["settings"])

    # ── 2. AI 모델 선택 ───────────────────────────────────────────────────────
    st.markdown(T["step1"])
    selected_label: str = st.radio(
        "model",
        options=PROVIDER_OPTIONS,
        index=0,
        label_visibility="collapsed",
        key="model_radio",
    )
    provider: str = PROVIDER_KEYS[selected_label]

    st.divider()

    # ── 3. API 키 입력 ────────────────────────────────────────────────────────
    st.markdown(T["step2"])

    if provider == "gemini":
        api_key: str = st.text_input(
            T["gemini_key_label"],
            value=os.getenv("GEMINI_API_KEY", ""),
            type="password",
            placeholder=T["gemini_key_ph"],
            help=T["gemini_key_help"],
        )
        _hint = T["gemini_key_hint"]
    elif provider == "gpt":
        api_key = st.text_input(
            T["gpt_key_label"],
            value=os.getenv("OPENAI_API_KEY", ""),
            type="password",
            placeholder=T["gpt_key_ph"],
            help=T["gpt_key_help"],
        )
        _hint = T["gpt_key_hint"]
    else:
        api_key = st.text_input(
            T["claude_key_label"],
            value=os.getenv("ANTHROPIC_API_KEY", ""),
            type="password",
            placeholder=T["claude_key_ph"],
            help=T["claude_key_help"],
        )
        _hint = T["claude_key_hint"]

    if api_key:
        st.success(T["api_key_ok"])
    else:
        st.warning(T["api_key_missing"].format(hint=_hint))

    st.divider()

    # ── 사이드바 안내 ─────────────────────────────────────────────────────────
    with st.expander(T["how_to_use"], expanded=True):
        st.markdown(T["how_to_use_body"])

    with st.expander(T["key_guide"]):
        st.markdown(T["key_guide_body"])

    with st.expander(T["formats"]):
        st.markdown(T["formats_body"])

    st.divider()
    st.caption(T["sidebar_caption"].format(model=MODEL_LABEL[provider]))


# ══════════════════════════════════════════════════════════════════════════════
# 9. 메인 UI
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f'<p class="main-title">{T["main_title"]}</p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="sub-desc">{T["sub_desc"].format(model=MODEL_LABEL[provider])}</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── 입력 방식 선택 ──────────────────────────────────────────────────────────────
input_mode: str = st.radio(
    "input_mode",
    options=[T["mode_file"], T["mode_text"]],
    horizontal=True,
    label_visibility="collapsed",
    key="input_mode_radio",
)

raw_text: str = ""
vision_bytes: bytes | None = None
use_vision: bool = False

st.markdown("")

# ══════════════════════════════════════════════════════════════════════════════
# 9-A. 파일 업로드
# ══════════════════════════════════════════════════════════════════════════════
if input_mode == T["mode_file"]:
    uploaded = st.file_uploader(
        "file",
        type=["pdf", "txt", "png", "jpg", "jpeg", "webp", "bmp", "gif"],
        help=T["uploader_help"],
        label_visibility="collapsed",
        key="file_uploader",
    )

    if uploaded is not None:
        file_bytes = uploaded.read()
        ext = os.path.splitext(uploaded.name)[1].lower()
        size_kb = len(file_bytes) / 1024
        st.caption(T["file_caption"].format(name=uploaded.name, size=size_kb))

        if ext == ".pdf":
            with st.spinner(T["pdf_spinner"]):
                raw_text = extract_text_from_pdf(file_bytes)
            if raw_text.strip():
                st.success(T["pdf_ok"].format(n=len(raw_text)))
                with st.expander(T["pdf_preview"]):
                    st.text_area(
                        "content", value=raw_text[:3_000] + ("…" if len(raw_text) > 3_000 else ""),
                        height=180, disabled=True, label_visibility="collapsed",
                    )
            else:
                st.error(T["pdf_error"])

        elif ext == ".txt":
            raw_text = extract_text_from_txt(file_bytes)
            st.success(T["txt_ok"].format(n=len(raw_text)))
            with st.expander(T["txt_preview"]):
                st.text_area(
                    "content", value=raw_text[:3_000] + ("…" if len(raw_text) > 3_000 else ""),
                    height=180, disabled=True, label_visibility="collapsed",
                )

        elif ext in SUPPORTED_IMAGE_EXT:
            st.image(file_bytes, caption=uploaded.name, width=420)
            with st.spinner(T["ocr_spinner"]):
                ocr_text = extract_text_via_ocr(file_bytes)
            if ocr_text and len(ocr_text) > 30:
                raw_text = ocr_text
                st.success(T["ocr_ok"].format(n=len(raw_text)))
                with st.expander(T["ocr_preview"]):
                    st.text_area(
                        "ocr", value=ocr_text[:2_000], height=150,
                        disabled=True, label_visibility="collapsed",
                    )
            else:
                st.info(T["ocr_fallback"].format(model=MODEL_LABEL[provider]))
                vision_bytes = file_bytes
                use_vision = True

# ══════════════════════════════════════════════════════════════════════════════
# 9-B. 텍스트 직접 입력
# ══════════════════════════════════════════════════════════════════════════════
else:
    raw_text = st.text_area(
        T["text_label"],
        height=240,
        placeholder=T["text_ph"],
        label_visibility="collapsed",
        key="text_input",
    )
    if raw_text:
        st.caption(T["char_count"].format(n=len(raw_text)))

# ══════════════════════════════════════════════════════════════════════════════
# 10. 생성 버튼
# ══════════════════════════════════════════════════════════════════════════════
st.divider()

has_input = bool(raw_text and raw_text.strip()) or use_vision

btn_col, hint_col = st.columns([2, 5])
with btn_col:
    generate_clicked = st.button(
        T["gen_btn"], type="primary",
        disabled=not has_input, use_container_width=True,
    )
with hint_col:
    if not api_key:
        st.warning(T["hint_no_key"].format(model=MODEL_LABEL[provider]))
    elif not has_input:
        st.info(T["hint_no_input"])
    else:
        st.success(T["hint_ready"].format(model=MODEL_LABEL[provider]))

# ══════════════════════════════════════════════════════════════════════════════
# 11. 생성 실행
# ══════════════════════════════════════════════════════════════════════════════
if generate_clicked:
    if not api_key:
        st.error(T["err_no_key"].format(model=MODEL_LABEL[provider]))
        st.stop()

    mname = MODEL_LABEL[provider]
    bar = st.progress(0, text=T["prog_prepare"].format(model=mname))

    try:
        bar.progress(15, text=T["prog_request"].format(model=mname))

        if use_vision:
            response_text = call_ai_vision(provider, api_key, vision_bytes, selected_lang)
        else:
            response_text = call_ai_text(provider, api_key, raw_text, selected_lang)

        bar.progress(70, text=T["prog_parse"])
        summary, mermaid_code = parse_ai_response(response_text)

        bar.progress(90, text=T["prog_render"])

        if not mermaid_code:
            bar.empty()
            st.error(T["err_parse"])
            with st.expander(T["err_raw"].format(model=mname)):
                st.text(response_text)
            st.stop()

        st.session_state["summary"]      = summary
        st.session_state["mermaid_code"] = mermaid_code
        st.session_state["raw_response"] = response_text

        bar.progress(100, text=T["prog_done"])

    except Exception as exc:
        bar.empty()
        st.error(T["err_general"].format(err=exc))
        st.info(T["err_retry"])
        st.stop()

    bar.empty()
    st.success(T["success"])

# ══════════════════════════════════════════════════════════════════════════════
# 12. 결과 표시
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.get("mermaid_code"):
    st.divider()
    st.subheader(T["results"])

    tab_map, tab_summary, tab_code = st.tabs(
        [T["tab_map"], T["tab_summary"], T["tab_code"]]
    )

    with tab_map:
        components.html(
            build_mermaid_html(st.session_state["mermaid_code"], height=580),
            height=600, scrolling=False,
        )
        st.markdown("")
        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                T["dl_mmd"], data=st.session_state["mermaid_code"],
                file_name="mindmap.mmd", mime="text/plain", use_container_width=True,
            )
        with dl2:
            st.download_button(
                T["dl_md"],
                data="```mermaid\n" + st.session_state["mermaid_code"] + "\n```",
                file_name="mindmap.md", mime="text/markdown", use_container_width=True,
            )

    with tab_summary:
        if st.session_state.get("summary"):
            st.markdown(st.session_state["summary"])
        else:
            st.info(T["summary_empty"])

    with tab_code:
        st.code(st.session_state["mermaid_code"], language="")
        st.markdown(T["code_usage"])
        with st.expander(T["raw_response"]):
            st.text(st.session_state.get("raw_response", ""))
