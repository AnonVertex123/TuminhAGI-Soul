"""
Tháp canh tri thức — Wikipedia (Wikimedia) cho TuminhAGI.
Giảm ảo giác về lịch sử / thực thể bằng dữ liệu trích từ Wikipedia.

Phụ thuộc: Wikipedia-API (import wikipediaapi) + MediaWiki HTTP API (stdlib).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Theo chính sách Wikimedia — luôn gửi User-Agent có mô tả
DEFAULT_USER_AGENT = (
    "TuminhAGI/1.0 (https://github.com/; grounded-rag) "
    "Python-urllib/wikipedia_bridge"
)

# Giới hạn để phản hồi nhanh (RAG nhẹ)
MAX_QUERIES_PER_TURN = 4
# Context "đủ nhưng không dư": 200–500 tokens ≈ 800 ký tự, 1–3 đoạn
SUMMARY_MAX_CHARS = 800
HTTP_TIMEOUT_SEC = 12.0


@dataclass
class WikiSearchResult:
    ok: bool
    query: str
    title: str
    summary: str
    url: str
    error: str | None = None


def _strip_think_and_surrounding(text: str) -> str:
    """Loại bỏ block <think> để parse JSON ổn định."""
    if not text:
        return ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _parse_json_obj(text: str) -> dict[str, Any]:
    clean = _strip_think_and_surrounding(text)
    try:
        obj = json.loads(clean)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{[\s\S]*\}", clean)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return {}


def _llm_chat(model: str, system_prompt: str, user_prompt: str) -> str:
    """
    Gọi Ollama cho mục đích trích xuất entity.

    Lazy-import để không vỡ khi module bị import trước khi có thư viện/cấu hình.
    """
    try:
        import ollama
    except Exception as e:  # noqa: BLE001
        logger.warning("ollama import failed: %s", e)
        return ""

    # config có thể chưa load được ở vài ngữ cảnh; dùng env fallback
    try:
        from config import OLLAMA_BASE_URL  # type: ignore

        os.environ.setdefault("OLLAMA_HOST", OLLAMA_BASE_URL)
    except Exception:
        pass

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = ollama.chat(model=model, messages=messages)
        if isinstance(response, dict):
            msg = response.get("message") or {}
            if isinstance(msg, dict):
                return (msg.get("content") or "").strip()
        msg = getattr(response, "message", None)
        if isinstance(msg, dict):
            return (msg.get("content") or "").strip()
        return (getattr(msg, "content", None) or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.warning("llm_chat failed: %s", e)
        return ""


def _translate_wikipedia_summary(text: str, *, src_lang: str, dst_lang: str) -> str:
    """
    Dịch summary Wikipedia để phục vụ người dùng đích.

    Ràng buộc chống ảo giác:
    - Chỉ dịch, không thêm/chỉnh sửa dữ kiện.
    - Giữ nguyên tên riêng, số liệu, ngày tháng.
    """
    if not text:
        return ""
    if src_lang.lower() == dst_lang.lower():
        return text

    try:
        from config import MODEL_TASK  # type: ignore

        model = MODEL_TASK
    except Exception:
        model = "qwen2.5-coder:7b"

    system_prompt = (
        "Bạn là bộ dịch chỉ dịch thuật (faithful translator). "
        "Nhiệm vụ: dịch văn bản Wikipedia từ ngôn ngữ src sang dst. "
        "Bắt buộc: KHÔNG thêm thông tin mới, KHÔNG bỏ thông tin, "
        "KHÔNG suy đoán; chỉ dịch giữ nguyên dữ kiện."
    )
    user_prompt = f"src_lang={src_lang}\ndst_lang={dst_lang}\n\nNội dung cần dịch:\n{text}"
    translated = _llm_chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    return translated.strip() or text


def _llm_extract_wiki_entities(user_message: str, *, max_entities: int = 3) -> list[str]:
    """
    Trích "thực thể chuẩn" để search Wikipedia.
    - KHÔNG trả về nguyên câu hỏi.
    - Ưu tiên tên người / địa danh / sự kiện / mốc lịch sử / triều đại.
    """
    if not user_message or len(user_message.strip()) < 3:
        return []

    try:
        from config import MODEL_VALIDATOR  # type: ignore

        model = MODEL_VALIDATOR
    except Exception:
        model = "phi4-mini:latest"

    system_prompt = (
        "Bạn là bộ trích xuất thực thể chuẩn cho Wikipedia. "
        f"Trả về JSON duy nhất dạng {{\"entities\": [\"...\", \"...\"]}} "
        f"với tối đa {max_entities} phần tử."
    )
    user_prompt = (
        "Người dùng hỏi:\n"
        f"{user_message}\n\n"
        "Hãy trích các thực thể có khả năng là tiêu đề bài Wikipedia. "
        "KHÔNG được copy nguyên câu hỏi vào output. "
        "Mỗi entity tối đa 80 ký tự."
    )

    raw = _llm_chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    obj = _parse_json_obj(raw)
    entities = obj.get("entities", [])
    if not isinstance(entities, list):
        return []

    original = user_message.strip().casefold()
    out: list[str] = []
    for e in entities:
        if not isinstance(e, str):
            continue
        s = e.strip()
        if not s:
            continue
        if s.casefold() == original:
            continue
        if len(s) > 80:
            continue
        if s not in out:
            out.append(s)
        if len(out) >= max_entities:
            break
    return out


def _llm_shorten_entity(entity: str) -> str:
    """
    Rút gọn entity để tăng xác suất match Wikipedia.
    Chỉ dùng trong retry lần 2 khi search lần 1 không ra.
    """
    if not entity or len(entity.strip()) < 3:
        return entity

    try:
        from config import MODEL_VALIDATOR  # type: ignore

        model = MODEL_VALIDATOR
    except Exception:
        model = "phi4-mini:latest"

    system_prompt = (
        "Bạn là bộ rút gọn tiêu đề Wikipedia. "
        "Trả về JSON duy nhất dạng {\"short\": \"...\"}. Không giải thích."
    )
    user_prompt = f"Rút gọn entity thành cụm từ khóa gần tiêu đề Wikipedia nhất: {entity}"
    raw = _llm_chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    obj = _parse_json_obj(raw)
    short = obj.get("short")
    if isinstance(short, str):
        s = short.strip()
        if s and s != entity:
            return s
    return entity


def extract_wiki_entities(user_message: str, *, max_entities: int = MAX_QUERIES_PER_TURN) -> list[str]:
    """
    Entity extraction ưu tiên LLM trước khi search.
    Nếu LLM fail: fallback heuristic và vẫn tránh search nguyên câu hỏi.
    """
    entities = _llm_extract_wiki_entities(user_message, max_entities=max_entities)
    if entities:
        return entities

    # fallback: heuristic nhưng không cho phép full-question
    heuristic = extract_wiki_queries(user_message, max_queries=max_entities)
    original = (user_message or "").strip()
    out: list[str] = []
    for s in heuristic:
        if not s:
            continue
        if s.strip().casefold() == original.casefold():
            continue
        if len(s) > 80:
            continue
        if s not in out:
            out.append(s)
        if len(out) >= max_entities:
            break

    # Nếu heuristic trả rỗng (vd: câu ngắn "X là ai?" bị lọc vì trùng full question),
    # strip hậu tố câu hỏi thường gặp để lấy entity: "Hải Thượng Lãn Ông là ai?" → "Hải Thượng Lãn Ông"
    if not out and original:
        stripped = re.sub(
            r"\s+(là\s*ai\??|la\s*ai\??|là\s*gì\??|la\s*gi\??|ở\s*đâu\??|o\s*dau\??|khi\s*nào\??|của\s*ai\??)\s*$",
            "",
            original,
            flags=re.IGNORECASE,
        ).strip()
        if stripped and len(stripped) >= 3 and stripped != original:
            out.append(stripped)

    return out[:max_entities]


def _http_get_json(url: str, timeout: float = HTTP_TIMEOUT_SEC) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def get_wiki(title: str, lang: str = "en") -> str:
    """
    Fetch nội dung thật từ Wikipedia REST API.
    URL: https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}
    Trả về extract (plain text), rỗng nếu lỗi.
    Context cắt tại SUMMARY_MAX_CHARS (800) — đủ nhưng không dư.
    """
    t = (title or "").strip().replace(" ", "_")
    if not t:
        return ""
    safe_title = urllib.parse.quote(t, safe="")
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{safe_title}"
    try:
        data = _http_get_json(url, timeout=HTTP_TIMEOUT_SEC)
        extract = (data.get("extract") or "").strip()
        if not extract:
            return ""
        return extract[:SUMMARY_MAX_CHARS] + ("…" if len(extract) > SUMMARY_MAX_CHARS else "")
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError) as e:
        logger.warning("get_wiki REST API lỗi: %s — %s", title, e)
        return ""


def _opensearch_titles(query: str, lang: str, limit: int = 3) -> list[str]:
    """Trả về danh sách title gợi ý từ opensearch (không cần khớp tuyệt đối)."""
    q = urllib.parse.quote(query)
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?"
        f"action=opensearch&search={q}&limit={limit}&namespace=0&format=json"
    )
    try:
        data = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        logger.warning("opensearch lỗi: %s — %s", query, e)
        return []
    if not isinstance(data, list) or len(data) < 2:
        return []
    titles = data[1]
    return [t for t in titles if isinstance(t, str) and t.strip()]


def _wiki_client(lang: str) -> Any:
    try:
        import wikipediaapi
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "Cần cài: pip install Wikipedia-API"
        ) from e
    return wikipediaapi.Wikipedia(
        user_agent=DEFAULT_USER_AGENT,
        language=lang,
        extract_format=wikipediaapi.ExtractFormat.WIKI,
    )


def _search_wiki_single_lang(query: str, lang: str) -> WikiSearchResult:
    """Search Wikipedia theo 1 ngôn ngữ — ưu tiên REST API (nội dung thật), fallback Wikipedia-API."""
    q = (query or "").strip()
    if len(q) < 2:
        return WikiSearchResult(
            ok=False,
            query=q,
            title="",
            summary="",
            url="",
            error="query_quá_ngắn",
        )

    # Ưu tiên: REST API — fetch nội dung thật, context 200–500 tokens
    titles = _opensearch_titles(q, lang, limit=3)
    for cand in (titles if titles else [q.replace(" ", "_")]):
        summary = get_wiki(cand, lang)
        if summary:
            title_clean = cand.replace(" ", "_")
            url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title_clean, safe='')}"
            return WikiSearchResult(
                ok=True,
                query=q,
                title=cand,
                summary=summary,  # get_wiki đã cắt tại SUMMARY_MAX_CHARS (800)
                url=url,
                error=None,
            )

    # Fallback: Wikipedia-API (khi REST API không trả extract)
    try:
        wiki = _wiki_client(lang)
    except ImportError as e:
        return WikiSearchResult(
            ok=False,
            query=q,
            title="",
            summary="",
            url="",
            error=f"thiếu_Wikipedia-API: {e!s}",
        )

    try:
        title = titles[0] if titles else q.replace(" ", "_")
        page = wiki.page(title)

        if not page.exists():
            for alt in titles[1:]:
                p2 = wiki.page(alt)
                if p2.exists():
                    page = p2
                    title = alt
                    break

        if not page.exists():
            return WikiSearchResult(
                ok=False,
                query=q,
                title=title,
                summary="",
                url="",
                error="không_tìm_thấy_trang",
            )

        summary = (page.summary or "").strip()
        if not summary:
            try:
                titles_api = urllib.parse.quote(page.title, safe="")
                api_url = (
                    f"https://{lang}.wikipedia.org/w/api.php?"
                    "action=query&prop=extracts&exintro=1&explaintext=1&redirects=1&"
                    f"titles={titles_api}&format=json"
                )
                data = _http_get_json(api_url)
                pages = ((data.get("query") or {}).get("pages")) or {}
                for _k, pg in (pages or {}).items():
                    extract = (pg or {}).get("extract") or ""
                    if str(extract).strip():
                        summary = str(extract).strip()
                        break
            except Exception:  # noqa: BLE001
                pass

        if not summary:
            return WikiSearchResult(
                ok=False,
                query=q,
                title=page.title,
                summary="",
                url="",
                error="trang_tồn_tại_nhưng_không_có_summary",
            )

        summary = summary[: SUMMARY_MAX_CHARS - 1] + "…" if len(summary) > SUMMARY_MAX_CHARS else summary
        url = page.fullurl or f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"

        return WikiSearchResult(
            ok=True,
            query=q,
            title=page.title,
            summary=summary,
            url=url,
            error=None,
        )
    except Exception as e:  # noqa: BLE001 — surface lỗi cho caller
        logger.exception("search_wiki_single_lang: %s", q)
        return WikiSearchResult(
            ok=False,
            query=q,
            title="",
            summary="",
            url="",
            error=f"lỗi_hệ_thống: {e!s}",
        )


def search_wiki(query: str, lang: str = "vi") -> WikiSearchResult:
    """
    Search Wikipedia theo cơ chế bắt buộc:
    - Ưu tiên vi.wikipedia.org; nếu không thấy thì thử en.wikipedia.org.
    - Nếu lần 1 không thấy: rút gọn từ khóa và thử lại lần 2.
    - Không search nguyên câu hỏi người dùng (entity extractor phải đảm bảo điều này).
    """
    q = (query or "").strip()
    if len(q) < 2:
        return WikiSearchResult(
            ok=False,
            query=q,
            title="",
            summary="",
            url="",
            error="query_quá_ngắn",
        )

    requested_lang = lang.lower().strip()

    # Always prefer vi, then fallback en (bảo toàn yêu cầu "vi ưu tiên")
    langs = ["vi", "en"] if requested_lang != "en" else ["en", "vi"]

    # Round 1 (original query)
    for l in langs:
        r = _search_wiki_single_lang(q, l)
        if r.ok and r.summary and r.url:
            # If fell back to a different language, translate summary back.
            if l != requested_lang:
                try:
                    r.summary = _translate_wikipedia_summary(
                        r.summary, src_lang=l, dst_lang=requested_lang
                    )
                except Exception:  # noqa: BLE001
                    pass
            return r

    # Round 2 (shortened query)
    q2 = _llm_shorten_entity(q)
    q2 = (q2 or "").strip()
    if not q2 or q2.casefold() == q.casefold():
        return WikiSearchResult(
            ok=False,
            query=q,
            title="",
            summary="",
            url="",
            error="không_tìm_thấy_trang",
        )

    for l in langs:
        r2 = _search_wiki_single_lang(q2, l)
        if r2.ok and r2.summary and r2.url:
            # Keep original query in result.query for traceability
            r2.query = q
            if l != requested_lang:
                try:
                    r2.summary = _translate_wikipedia_summary(
                        r2.summary, src_lang=l, dst_lang=requested_lang
                    )
                except Exception:  # noqa: BLE001
                    pass
            return r2

    return WikiSearchResult(
        ok=False,
        query=q,
        title="",
        summary="",
        url="",
        error="không_tìm_thấy_trang",
    )


async def search_wiki_async(query: str, lang: str = "vi") -> WikiSearchResult:
    """Phiên bản async: chạy search_wiki trong thread pool (I/O-bound)."""
    return await asyncio.to_thread(search_wiki, query, lang)


def extract_wiki_queries(text: str, max_queries: int = MAX_QUERIES_PER_TURN) -> list[str]:
    """
    Trích các chuỗi ứng viên để tra Wikipedia (heuristic, không cần spaCy).
    - Cả câu / đoạn ngắn đầu
    - Cụm trong ngoặc kép
    - Một số đoạn tách bởi dấu câu (độ dài vừa phải)
    """
    raw = (text or "").strip()
    if not raw:
        return []

    seen: set[str] = set()
    out: list[str] = []

    def push(s: str) -> None:
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) < 3 or s in seen:
            return
        seen.add(s)
        out.append(s)

    # 1) Câu hỏi rút gọn (tránh gửi cả khối dài)
    head = raw[:200]
    if len(head) < len(raw):
        push(head.rsplit(" ", 1)[0] if " " in head else head)
    else:
        # IMPORTANT: không trả về nguyên câu hỏi người dùng
        candidate = raw[:80] if len(raw) > 80 else raw
        if candidate.strip().casefold() != raw.strip().casefold():
            push(candidate)

    # 2) Trích trong ngoặc kép
    for m in re.finditer(r'["«»]([^"«»]{3,80})["»]', raw):
        push(m.group(1))

    # 3) Mẫu địa danh / triều đại tiếng Việt thường gặp
    for m in re.finditer(
        r"(?:thời|triều|vua|đời)\s+([A-Za-zÀ-ỹ0-9\s]{2,40}?)(?:\s*[,.;]|$)",
        raw,
        flags=re.IGNORECASE,
    ):
        push(m.group(0).strip())

    # 4) Các mảnh sau dấu phẩy / chấm (cụm có thể là thực thể)
    for part in re.split(r"[\n;]+", raw):
        part = part.strip()
        if 8 <= len(part) <= 90:
            push(part)

    return out[:max_queries]


def _format_results_block(results: list[WikiSearchResult]) -> str:
    lines: list[str] = []
    seen_titles: set[str] = set()
    for r in results:
        if not r.ok:
            continue
        key = r.title.strip().casefold()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        lines.append(f"- **{r.title}** ({r.url})\n  {r.summary}")
    return "\n\n".join(lines)


def _split_into_sentences(text: str, *, max_sentences: int = 20) -> list[str]:
    """
    Tách summary thành câu (heuristic) để rank.

    Lưu ý: heuristic cho tiếng Việt, không cố gắng 100% chính xác ngữ pháp.
    """
    if not text:
        return []
    t = str(text).replace("...", "…").strip()
    # split by sentence-ending punctuation
    sents = re.split(r"(?<=[\.\!\?\u2026])\s+|\n+", t)
    sents = [s.strip() for s in sents if s and len(s.strip()) >= 8]
    return sents[:max_sentences]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += float(x) * float(y)
        na += float(x) * float(x)
        nb += float(y) * float(y)
    if na <= 0.0 or nb <= 0.0:
        return -1.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def _rank_sentences_by_embeddings(
    question: str,
    summary: str,
    *,
    top_n: int = 3,
    max_sentences: int = 10,
) -> str:
    """
    Accuracy mode: rank câu trong summary theo embedding similarity.
    Trả về chuỗi chứa top_n câu (không bịa ngoài text gốc).
    """
    sents = _split_into_sentences(summary, max_sentences=max_sentences)
    if len(sents) <= top_n:
        return summary

    try:
        import ollama  # local import để không vỡ khi thiếu runtime

        from config import MODEL_EMBED, OLLAMA_BASE_URL  # type: ignore

        os.environ.setdefault("OLLAMA_HOST", OLLAMA_BASE_URL)

        q_emb_resp = ollama.embeddings(model=MODEL_EMBED, prompt=question)
        q_emb = q_emb_resp.get("embedding")
        if not isinstance(q_emb, list) or not q_emb:
            return summary

        cache: dict[str, list[float]] = {}
        scored: list[tuple[float, str]] = []
        for s in sents:
            if s in cache:
                s_emb = cache[s]
            else:
                e_resp = ollama.embeddings(model=MODEL_EMBED, prompt=s)
                s_emb = e_resp.get("embedding")
                if not isinstance(s_emb, list) or not s_emb:
                    continue
                cache[s] = s_emb
            sim = _cosine_similarity(q_emb, s_emb)
            scored.append((sim, s))

        if not scored:
            return summary

        scored.sort(key=lambda x: x[0], reverse=True)
        top_sents = [s for _, s in scored[:top_n]]
        return " ".join(top_sents).strip()
    except Exception:
        # Nếu embedding fail: fallback về summary gốc để không làm mất fact.
        return summary


def _format_results_block_ranked(
    results: list[WikiSearchResult],
    *, user_message: str,
    rank_mode: str,
) -> str:
    lines: list[str] = []
    seen_titles: set[str] = set()
    for r in results:
        if not r.ok:
            continue
        key = r.title.strip().casefold()
        if key in seen_titles:
            continue
        seen_titles.add(key)

        summary_text = r.summary
        if rank_mode == "embedding":
            summary_text = _rank_sentences_by_embeddings(user_message, summary_text)

        lines.append(f"- **{r.title}** ({r.url})\n  {summary_text}")
    return "\n\n".join(lines)


async def gather_wiki_summaries_async(
    queries: list[str],
    lang: str = "vi",
) -> tuple[str, bool]:
    """
    Gọi song song các truy vấn Wiki; trả về (khối markdown, có_dữ_liệu).
    """
    if not queries:
        return "", False
    tasks = [search_wiki_async(q, lang) for q in queries]
    done = await asyncio.gather(*tasks, return_exceptions=True)
    ok_results: list[WikiSearchResult] = []
    for item in done:
        if isinstance(item, WikiSearchResult) and item.ok:
            ok_results.append(item)
        elif isinstance(item, Exception):
            logger.warning("gather wiki: %s", item)

    block = _format_results_block(ok_results)
    return block, bool(block.strip())


def gather_wiki_summaries_sync(queries: list[str], lang: str = "vi") -> tuple[str, bool]:
    """Sync wrapper (dùng trong main.py / CLI không async)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(gather_wiki_summaries_async(queries, lang))
    # Đã có loop (hiếm) — chạy tuần tự
    results: list[WikiSearchResult] = []
    for q in queries:
        results.append(search_wiki(q, lang))
    block = _format_results_block(results)
    return block, bool(block.strip())


def gather_wiki_results_sync(queries: list[str], lang: str = "vi") -> list[WikiSearchResult]:
    """
    Sync helper: trả về list WikiSearchResult (không format thành string).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # no running loop => sequential is fine
        return [search_wiki(q, lang) for q in queries]

    # Nếu đang chạy event loop, tránh asyncio.run; dùng tuần tự
    return [search_wiki(q, lang) for q in queries]


# --- Luật sắt + inject prompt ---

WIKI_IRON_RULES_VI = """
[LUẬT SẮT — THÁP CANH TRI THỨC / WIKIMEDIA]
- Khi có khối [DỮ LIỆU THỰC CHỨNG TỪ WIKIPEDIA] trong ngữ cảnh: đối chiếu với suy luận của bạn.
- Nếu mâu thuẫn giữa “kiến thức nội bộ / ước đoán” và Wikipedia: **ưu tiên Wikipedia** và **đính chính ngay** trong câu trả lời.
- Không bịa sự kiện, niên đại, quan hệ nhân vật khi Wikipedia đã nêu khác; hãy theo Wikipedia.
- Cuối câu trả lời, nếu đã dựa vào dữ liệu Wikipedia ở trên: ghi **một dòng** nguồn: `[Nguồn: Wikipedia]`.
""".strip()


def format_wiki_grounding_for_context(
    user_message: str,
    lang: str = "vi",
    rank_mode: str = "none",
) -> str:
    """
    Trả về chuỗi để nối vào [CONTEXT] của LLM (task/critic/validator).
    Rỗng nếu không lấy được dữ liệu.
    """
    # Entity extraction ưu tiên LLM, để KHÔNG search nguyên câu hỏi người dùng.
    queries = extract_wiki_entities(user_message, max_entities=MAX_QUERIES_PER_TURN)
    if not queries:
        return ""

    results = gather_wiki_results_sync(queries, lang=lang)
    ok_results = [r for r in results if getattr(r, "ok", False) and r.summary and r.url]
    if not ok_results:
        return ""

    if rank_mode == "embedding":
        block = _format_results_block_ranked(
            ok_results, user_message=user_message, rank_mode=rank_mode
        )
    else:
        block = _format_results_block(ok_results)

    if not block.strip():
        return ""

    return (
        "\n\n[DỮ LIỆU THỰC CHỨNG TỪ WIKIPEDIA]\n"
        f"{block}\n"
        "[/DỮ LIỆU THỰC CHỨNG TỪ WIKIPEDIA]\n\n"
        f"{WIKI_IRON_RULES_VI}\n"
    )


__all__ = [
    "WikiSearchResult",
    "get_wiki",
    "search_wiki",
    "search_wiki_async",
    "extract_wiki_queries",
    "extract_wiki_entities",
    "gather_wiki_summaries_async",
    "gather_wiki_summaries_sync",
    "gather_wiki_results_sync",
    "format_wiki_grounding_for_context",
    "WIKI_IRON_RULES_VI",
]
