"""
GIAO THỨC TRUY XUẤT THỰC CHỨNG — TOTAL SEARCH MANDATE
=======================================================
Sau mỗi câu trả lời của TuminhAGI, tự động xây dựng khối:

  🔗 HỆ THỐNG TRA CỨU NHANH (SEARCH LINKS)
  ├─ Nguồn Wikipedia : <link thực>
  ├─ Tài liệu chính quy : <docs / GitHub / PubMed>
  └─ Google Search : <link tìm kiếm thực>

Nguyên tắc:
- KHÔNG bao giờ hallucinate URL.
- Wikipedia URL: chỉ dùng link đã xác nhận qua wikipedia_bridge.search_wiki.
- Docs URL: dùng bảng tra cứu tĩnh (KNOWN_DOCS); nếu không khớp → bỏ qua.
- Google Search URL: luôn hợp lệ vì chỉ dùng
  https://www.google.com/search?q=<encoded>
- Nếu không có nguồn nào: in cảnh báo "chưa tìm thấy nguồn xác thực".
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Bảng tra cứu tài liệu chính quy (keyword → (tên hiển thị, URL))
# ---------------------------------------------------------------------------
KNOWN_DOCS: dict[str, tuple[str, str]] = {
    # AI / ML
    "ollama":             ("Ollama Docs",            "https://ollama.com/library"),
    "langchain":          ("LangChain Docs",          "https://python.langchain.com/docs/"),
    "transformers":       ("HuggingFace Transformers","https://huggingface.co/docs/transformers/"),
    "huggingface":        ("HuggingFace Hub",         "https://huggingface.co/"),
    "openai":             ("OpenAI API Reference",    "https://platform.openai.com/docs/"),
    "gemini":             ("Google Gemini API",       "https://ai.google.dev/docs"),
    "anthropic":          ("Anthropic Claude Docs",   "https://docs.anthropic.com/"),
    "llama":              ("Meta Llama GitHub",       "https://github.com/meta-llama/llama"),
    "mistral":            ("Mistral AI Docs",         "https://docs.mistral.ai/"),
    "deepseek":           ("DeepSeek GitHub",         "https://github.com/deepseek-ai"),
    "qwen":               ("Qwen GitHub",             "https://github.com/QwenLM/Qwen"),
    "phi":                ("Microsoft Phi GitHub",    "https://huggingface.co/microsoft"),
    "chromadb":           ("ChromaDB Docs",           "https://docs.trychroma.com/"),
    "qdrant":             ("Qdrant Docs",             "https://qdrant.tech/documentation/"),
    "faiss":              ("FAISS GitHub",            "https://github.com/facebookresearch/faiss"),
    "unsloth":            ("Unsloth GitHub",          "https://github.com/unslothai/unsloth"),
    # Python libs
    "numpy":              ("NumPy Docs",              "https://numpy.org/doc/stable/"),
    "pandas":             ("Pandas Docs",             "https://pandas.pydata.org/docs/"),
    "matplotlib":         ("Matplotlib Docs",         "https://matplotlib.org/stable/"),
    "scipy":              ("SciPy Docs",              "https://docs.scipy.org/doc/scipy/"),
    "scikit":             ("scikit-learn Docs",       "https://scikit-learn.org/stable/"),
    "pytorch":            ("PyTorch Docs",            "https://pytorch.org/docs/stable/"),
    "tensorflow":         ("TensorFlow Docs",         "https://www.tensorflow.org/api_docs"),
    "fastapi":            ("FastAPI Docs",            "https://fastapi.tiangolo.com/"),
    "flask":              ("Flask Docs",              "https://flask.palletsprojects.com/"),
    "django":             ("Django Docs",             "https://docs.djangoproject.com/"),
    "sqlalchemy":         ("SQLAlchemy Docs",         "https://docs.sqlalchemy.org/"),
    "pydantic":           ("Pydantic Docs",           "https://docs.pydantic.dev/"),
    "rich":               ("Rich Docs",               "https://rich.readthedocs.io/"),
    "asyncio":            ("asyncio Docs (Python)",   "https://docs.python.org/3/library/asyncio.html"),
    "python":             ("Python 3 Docs",           "https://docs.python.org/3/"),
    "wikipedia":          ("Wikipedia-API PyPI",      "https://pypi.org/project/Wikipedia-API/"),
    "wikipediaapi":       ("Wikipedia-API Docs",      "https://github.com/martin-majlis/Wikipedia-API"),
    # DevOps / Tools
    "docker":             ("Docker Docs",             "https://docs.docker.com/"),
    "git":                ("Git Reference",           "https://git-scm.com/docs"),
    "github":             ("GitHub Docs",             "https://docs.github.com/"),
    "kubernetes":         ("Kubernetes Docs",         "https://kubernetes.io/docs/"),
    "vscode":             ("VS Code Docs",            "https://code.visualstudio.com/docs"),
    "cursor":             ("Cursor Docs",             "https://docs.cursor.com/"),
    # Y học
    "pubmed":             ("PubMed",                  "https://pubmed.ncbi.nlm.nih.gov/"),
    "icd":                ("ICD-11 WHO",              "https://icd.who.int/"),
    "who":                ("WHO Publications",        "https://www.who.int/publications/"),
    "dược":               ("Dược điển Việt Nam",      "https://www.dav.gov.vn/"),
    "thuốc":              ("Tra cứu thuốc — DAV",     "https://www.dav.gov.vn/"),
}


def google_search_url(query: str) -> str:
    """Luôn hợp lệ — chỉ encode URL, không bịa nội dung."""
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(query.strip())


def google_scholar_url(query: str) -> str:
    return "https://scholar.google.com/scholar?q=" + urllib.parse.quote_plus(query.strip())


@dataclass
class MandateLink:
    label: str
    url: str
    source_type: str  # "wiki" | "docs" | "google" | "scholar"


@dataclass
class SearchMandateBlock:
    query: str
    links: list[MandateLink] = field(default_factory=list)

    def has_authoritative_source(self) -> bool:
        return any(k.source_type in ("wiki", "docs") for k in self.links)

    def render_rich(self) -> str:
        lines = ["\n[bold blue]🔗 HỆ THỐNG TRA CỨU NHANH (SEARCH LINKS)[/bold blue]"]
        wiki_links  = [k for k in self.links if k.source_type == "wiki"]
        doc_links   = [k for k in self.links if k.source_type == "docs"]
        google_links = [k for k in self.links if k.source_type == "google"]
        scholar_links = [k for k in self.links if k.source_type == "scholar"]

        if wiki_links:
            for k in wiki_links[:3]:
                lines.append(f"  [bold]Nguồn Wikipedia :[/bold] {k.label} → {k.url}")
        else:
            lines.append("  [dim]Nguồn Wikipedia : (không tìm thấy bài liên quan)[/dim]")

        if doc_links:
            for k in doc_links[:3]:
                lines.append(f"  [bold]Tài liệu chính quy :[/bold] {k.label} → {k.url}")

        if google_links:
            for k in google_links[:2]:
                lines.append(f"  [bold]Google Search :[/bold] {k.label} → {k.url}")

        if scholar_links:
            for k in scholar_links[:1]:
                lines.append(f"  [dim]Google Scholar :[/dim] {k.label} → {k.url}")

        if not self.has_authoritative_source():
            lines.append(
                "\n  [bold yellow]⚠ Đệ hiện chưa tìm thấy nguồn xác thực uy tín cho "
                "thông tin này, huynh vui lòng cẩn trọng khi sử dụng.[/bold yellow]"
            )
        return "\n".join(lines)

    def render_plain(self) -> str:
        lines = ["\n🔗 HỆ THỐNG TRA CỨU NHANH (SEARCH LINKS)"]
        wiki_links   = [k for k in self.links if k.source_type == "wiki"]
        doc_links    = [k for k in self.links if k.source_type == "docs"]
        google_links = [k for k in self.links if k.source_type == "google"]

        if wiki_links:
            for k in wiki_links[:3]:
                lines.append(f"  Nguồn Wikipedia    : {k.label}\n    {k.url}")
        else:
            lines.append("  Nguồn Wikipedia    : (không tìm thấy bài liên quan)")

        for k in doc_links[:3]:
            lines.append(f"  Tài liệu chính quy : {k.label}\n    {k.url}")

        for k in google_links[:2]:
            lines.append(f"  Google Search      : {k.label}\n    {k.url}")

        if not self.has_authoritative_source():
            lines.append(
                "\n  ⚠ Đệ hiện chưa tìm thấy nguồn xác thực uy tín cho "
                "thông tin này, huynh vui lòng cẩn trọng khi sử dụng."
            )
        return "\n".join(lines)


def _match_known_docs(text: str) -> list[MandateLink]:
    """Khớp bảng KNOWN_DOCS theo từ khóa (case-insensitive, không cần spaCy)."""
    lower = text.lower()
    seen: set[str] = set()
    out: list[MandateLink] = []
    for keyword, (label, url) in KNOWN_DOCS.items():
        if keyword in lower and url not in seen:
            seen.add(url)
            out.append(MandateLink(label=label, url=url, source_type="docs"))
    return out


def _is_medical_or_history(text: str) -> bool:
    markers = (
        "bệnh", "thuốc", "điều trị", "triệu chứng", "y học", "icd",
        "lịch sử", "triều", "thời", "vua", "chiến tranh", "nhà", "đời",
    )
    low = text.lower()
    return any(m in low for m in markers)


def build_mandate_block(
    user_message: str,
    *,
    wiki_results: Optional[list] = None,  # list[WikiSearchResult]
    lang: str = "vi",
) -> "SearchMandateBlock":
    """
    Xây dựng SearchMandateBlock đã xác thực cho `user_message`.

    `wiki_results` nếu đã tra từ bước Wikipedia grounding (tái dùng, không gọi lại).
    Nếu None → tự tra (tối đa MAX_QUERIES_PER_TURN).
    """
    from tools.wikipedia_bridge import (
        WikiSearchResult,
        extract_wiki_entities,
        gather_wiki_summaries_sync,
        search_wiki,
    )

    block = SearchMandateBlock(query=user_message)

    # ── 1. Wikipedia ────────────────────────────────────────────────────────
    if wiki_results is None:
        # Dùng extract_wiki_entities (LLM) thay vì heuristic — tránh search "X là ai?"
        # vì Wikipedia cần entity thuần ("Hải Thượng Lãn Ông" chứ không phải "Hải Thượng Lãn Ông là ai?")
        queries = extract_wiki_entities(user_message)
        raw_results: list[WikiSearchResult] = []
        if queries:
            _, _ = gather_wiki_summaries_sync(queries, lang=lang)
            # collect individually for urls
            for q in queries[:3]:
                r = search_wiki(q, lang=lang)
                raw_results.append(r)
        wiki_results = raw_results

    seen_wiki_urls: set[str] = set()
    for r in wiki_results:
        if getattr(r, "ok", False) and r.url and r.url not in seen_wiki_urls:
            seen_wiki_urls.add(r.url)
            block.links.append(
                MandateLink(label=r.title, url=r.url, source_type="wiki")
            )

    # ── 2. Tài liệu chính quy (từ bảng tra) ────────────────────────────────
    doc_links = _match_known_docs(user_message)
    block.links.extend(doc_links)

    # ── 3. Google Search — luôn hợp lệ ─────────────────────────────────────
    # Query chính
    main_q = (user_message[:120] + "…" if len(user_message) > 120 else user_message).strip()
    block.links.append(
        MandateLink(
            label=f'Tìm: "{main_q[:60]}"',
            url=google_search_url(user_message),
            source_type="google",
        )
    )

    # Query rút gọn nếu dài
    if len(user_message) > 60:
        short = user_message[:60].rsplit(" ", 1)[0]
        block.links.append(
            MandateLink(
                label=f'Tìm (rút gọn): "{short}"',
                url=google_search_url(short),
                source_type="google",
            )
        )

    # Scholar cho y học / lịch sử
    if _is_medical_or_history(user_message):
        block.links.append(
            MandateLink(
                label=f'Scholar: "{user_message[:50]}"',
                url=google_scholar_url(user_message),
                source_type="scholar",
            )
        )

    return block


# --------------------------------------------------------------------------
# Luật sắt — injected vào system prompt của LLM
# --------------------------------------------------------------------------
TOTAL_SEARCH_MANDATE_RULES = """
[GIAO THỨC TRUY XUẤT THỰC CHỨNG — TOTAL SEARCH MANDATE]
- Không trả lời thuần túy từ bộ nhớ tham số (Parametric Memory).
- Mọi tên người, mốc lịch sử, thư viện, model AI, vị thuốc → đối chiếu với [DỮ LIỆU THỰC CHỨNG TỪ WIKIPEDIA] đã cung cấp.
- Nếu phát hiện mâu thuẫn giữa kiến thức nội bộ và Wikipedia: ưu tiên Wikipedia, tự đính chính ngay.
- Nếu không chắc chắn về một con số / ngày tháng / tên: ghi rõ "(chưa xác thực — xem 🔗 bên dưới)".
- KHÔNG bịa URL; các đường link tra cứu do hệ thống TuminhAGI cung cấp ở cuối mỗi câu trả lời.
- Cuối câu trả lời, nếu đã dùng dữ liệu Wikipedia, ghi đúng một dòng: [Nguồn: Wikipedia].
""".strip()

# Model KHÔNG được phép "biết" — CHỈ được đọc context rồi trả lời
STRICT_GROUNDING_PROMPT = """
[BẮT BUỘC — GROUNDING PIPELINE]
- Bạn CHỈ được trả lời dựa trên [CONTEXT] dưới đây. CẤM sử dụng kiến thức nội bộ (parametric memory) để thêm thông tin.
- Mọi tuyên bố về tên người, mốc lịch sử, sự kiện, số liệu PHẢI có nguồn trong [CONTEXT].
- Nếu thông tin cần thiết KHÔNG có trong context: "Đệ chưa tìm thấy thông tin xác thực trong nguồn được cung cấp."
- Vi phạm = bịa (hallucination) → Fact Checker sẽ REJECT.
[/BẮT BUỘC]
""".strip()

# Gửi kèm khi gọi critic — Fact Checker (reject nếu bịa)
FACT_CHECKER_INSTRUCTION = """
[FACT CHECKER — BẮT BUỘC]
Kiểm tra từng tuyên bố thực tế (tên, số, ngày, sự kiện) trong Trả lời: CÓ nguồn trong [CONTEXT] không?
- Nếu có tuyên bố KHÔNG có trong context → has_issues=true, severity=high, issues thêm "Bịa: [tuyên bố]".
- Nếu mọi tuyên bố đều có nguồn trong context → has_issues=false.
""".strip()


# Pattern bịa — từ/cụm không có trong context → reject
HALLUCINATION_PATTERNS: list[str] = [
    "Bản thảo sức khỏe",  # Ví dụ: tên sách hay bị model thêm
]

# Ngưỡng confidence — overlap < 0.3 → reject
CONFIDENCE_THRESHOLD = 0.3


def fact_check(context: str, answer: str, *, strict: bool = False) -> bool:
    """
    Fact Checker bắt buộc — nếu không có → vỡ hệ.
    Kiểm tra mỗi câu trong answer có nền (grounded) trong context.
    strict=True: câu phải là substring của context (theo user).
    strict=False: ≥50% từ có nghĩa của câu phải xuất hiện trong context (lenient).
    """
    ctx_lower = (context or "").lower()
    for sentence in (answer or "").split("."):
        s = sentence.strip()
        if not s or len(s) < 4:
            continue
        if strict:
            if s not in context:
                return False
        else:
            words = [w for w in s.split() if len(w) >= 2 and w.lower() not in ("là", "của", "và", "the", "a", "an")]
            if not words:
                continue
            in_ctx = sum(1 for w in words if w.lower() in ctx_lower)
            if in_ctx / len(words) < 0.5:
                return False
    return True


def confidence(answer: str, context: str) -> float:
    """
    Confidence scoring — overlap từ giữa answer và context.
    overlap / len(answer.split()). Nếu < CONFIDENCE_THRESHOLD (0.3) → reject.
    """
    a_words = [w.lower() for w in (answer or "").split() if len(w) >= 2]
    c_set = {w.lower() for w in (context or "").split()}
    if not a_words:
        return 1.0
    overlap = len(set(a_words) & c_set)
    return overlap / len(a_words)


def check_citation(answer: str, context: str) -> bool:
    """
    Kiểm tra answer có grounded trong context không.
    Không có citation (không nền trong context) → reject.
    """
    return fact_check(context, answer)


# Phản hồi hợp lệ khi không có trong context — không reject
NO_INFO_PHRASES = ("chưa tìm thấy thông tin xác thực", "đệ chưa tìm thấy", "không có trong")


def grounded_reject_check(answer: str, context: str) -> tuple[bool, str]:
    """
    Reject system — rất quan trọng.
    Trả về (passed, reason). passed=False → reject, reason là thông báo.
    """
    ans_lower = (answer or "").lower().strip()
    if any(p in ans_lower for p in NO_INFO_PHRASES):
        return True, ""  # Hợp lệ: model thừa nhận không biết

    if not check_citation(answer, context):
        return False, "❌ Not grounded"
    conf = confidence(answer, context)
    if conf < CONFIDENCE_THRESHOLD:
        return False, f"⚠️ Low confidence ({conf:.2f} < {CONFIDENCE_THRESHOLD})"
    bad = detect_hallucination_pattern(answer)
    if bad:
        return False, f"❌ Hallucination pattern: «{bad}»"
    return True, ""


def detect_hallucination_pattern(answer: str) -> str | None:
    """
    Phát hiện pattern bịa — thêm tên sách, số liệu, nhận định không có trong context.
    Trả về phrase vi phạm, hoặc None nếu không phát hiện.
    """
    ans = answer or ""
    for phrase in HALLUCINATION_PATTERNS:
        if phrase in ans:
            return phrase
    return None


def build_prompt(context: str, question: str, *, span_grounding: bool = True) -> str:
    """
    Prompt khóa model — QUAN TRỌNG NHẤT.
    Chỉ được dùng context, CẤM prior, không biết thì nói "chưa tìm thấy".
    span_grounding: yêu cầu trích Source từ context (pro level).
    """
    source_rule = (
        "\n- Kèm theo trả lời, trích dẫn đoạn nguồn: Source: \"...\" (copy từng từ từ CONTEXT)."
        if span_grounding
        else ""
    )
    return f"""
Bạn là hệ thống QA thực tế nghiêm ngặt (strict factual QA).

QUY TẮC BẮT BUỘC:
- Chỉ dùng THÔNG TIN trong CONTEXT được cung cấp dưới đây.
- CẤM dùng kiến thức nội bộ (prior knowledge).
- Nếu câu trả lời KHÔNG có trong context → nói: "Đệ chưa tìm thấy thông tin xác thực trong nguồn được cung cấp."
- Không thêm sự kiện ngoài context.{source_rule}

CONTEXT:
{context}

CÂU HỎI:
{question}

TRẢ LỜI (kèm Source: "..." nếu có):""".strip()


def grounded_v2(question: str, context: str, call_llm: Callable[[str], str]) -> str:
    """
    Full pipeline Grounded V2:
    build_prompt → call_llm → check_citation → confidence → return answer or reject.
    """
    prompt = build_prompt(context, question, span_grounding=True)
    answer = call_llm(prompt)

    passed, reason = grounded_reject_check(answer, context)
    if not passed:
        return reason  # "❌ Not grounded" | "⚠️ Low confidence" | "❌ Hallucination..."
    return answer


__all__ = [
    "MandateLink",
    "SearchMandateBlock",
    "build_mandate_block",
    "build_prompt",
    "grounded_v2",
    "fact_check",
    "check_citation",
    "confidence",
    "grounded_reject_check",
    "detect_hallucination_pattern",
    "HALLUCINATION_PATTERNS",
    "CONFIDENCE_THRESHOLD",
    "google_search_url",
    "google_scholar_url",
    "TOTAL_SEARCH_MANDATE_RULES",
    "STRICT_GROUNDING_PROMPT",
    "FACT_CHECKER_INSTRUCTION",
    "KNOWN_DOCS",
]
