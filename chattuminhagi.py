#!/usr/bin/env python3
"""
Chat TuminhAGI — có thể đặt ở một trong hai chỗ:

  A) Cạnh thư mục dự án (khuyến nghị — “ngoài” repo khi copy ra):
       I:\\chattuminhagi.py
       I:\\TuminhAgi\\...

  B) Trong gốc dự án:
       I:\\TuminhAgi\\chattuminhagi.py

Luồng model (theo config.py + orchestrator):

  Vai trò              Persona      Model mặc định
  ─────────────────────────────────────────────────────────────
  Phân loại (router)   router       phi4-mini:latest (nhánh validator)
  Trả lời chính        task/code/…  qwen2.5-coder:7b
  Critic               critic       deepseek-r1:7b
  Validator            validator    phi4-mini:latest

Chạy (PowerShell):
  cd I:\\TuminhAgi
  $env:PYTHONIOENCODING=\"utf-8\"
  python chattuminhagi.py

Hoặc nếu file ở I:\\ :
  cd I:\\
  python chattuminhagi.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ─── Tìm thư mục dự án TuminhAgi ───────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
if (_HERE / "config.py").is_file():
    _PROJECT = _HERE
else:
    _PROJECT = _HERE / "TuminhAgi"

if not (_PROJECT / "config.py").is_file():
    print(
        f"[ERROR] Không tìm thấy TuminhAgi (config.py) tại: {_PROJECT}\n"
        "Đặt chattuminhagi.py trong I:\\TuminhAgi HOẶC cạnh thư mục I:\\TuminhAgi\\",
        file=sys.stderr,
    )
    sys.exit(1)

sys.path.insert(0, str(_PROJECT))

import ollama
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from config import (
    MODEL_CRITIC,
    MODEL_TASK,
    MODEL_VALIDATOR,
    OLLAMA_BASE_URL,
    SOUL_CONSTANTS,
    SOUL_VAULT_DIR,
)

try:
    from tools.wikipedia_bridge import format_wiki_grounding_for_context, extract_wiki_entities
except ImportError:

    def format_wiki_grounding_for_context(
        _user_message: str,
        _lang: str = "vi",
        rank_mode: str = "none",
    ) -> str:
        return ""

    def extract_wiki_entities(_msg: str, **_: object) -> list[str]:
        return []


try:
    from tools.search_mandate import (
        TOTAL_SEARCH_MANDATE_RULES,
        STRICT_GROUNDING_PROMPT,
        FACT_CHECKER_INSTRUCTION,
        build_mandate_block,
        grounded_reject_check,
    )

    _MANDATE_AVAILABLE = True
except ImportError:
    _MANDATE_AVAILABLE = False
    TOTAL_SEARCH_MANDATE_RULES = ""

    def build_mandate_block(_msg: str, **_kw):  # type: ignore[misc]
        class _Dummy:
            def render_rich(self) -> str:
                return ""

        return _Dummy()
    STRICT_GROUNDING_PROMPT = ""
    FACT_CHECKER_INSTRUCTION = ""

    def grounded_reject_check(_ans: str, _ctx: str) -> tuple[bool, str]:
        return True, ""

try:
    from tools.learning_layer import inject_learned_context, trigger_learning, filter_wrong
    from tools.learning_layer import _get_entity_key

    _LEARNING_AVAILABLE = True
except ImportError:
    _LEARNING_AVAILABLE = False

    def inject_learned_context(ctx: str, _q: str, **_: object) -> tuple[str, str | None]:
        return ctx, None

    def trigger_learning(*_: object, **__: object) -> bool:
        return False

    def filter_wrong(_ans: str, _ent: str) -> str | None:
        return None

    def _get_entity_key(q: str, **_: object) -> str:
        return (q or "")[:80]

try:
    from tools.neo_personal import build_neo_personal_context

    PERSONAL_NEO_AVAILABLE = True
except ImportError:
    PERSONAL_NEO_AVAILABLE = False

    def build_neo_personal_context(_user_message: str) -> str:
        return ""

try:
    from tools.neo_gs_do_tat_loi import build_neo_gs_do_tat_loi_context

    GS_NEOS_AVAILABLE = True
except ImportError:
    GS_NEOS_AVAILABLE = False

    def build_neo_gs_do_tat_loi_context(_user_message: str) -> str:
        return ""


os.environ.setdefault("OLLAMA_HOST", OLLAMA_BASE_URL)

console = Console()


def _ollama_chat_content(response: object) -> str:
    if response is None:
        return ""
    if isinstance(response, dict):
        msg = response.get("message") or {}
        if isinstance(msg, dict):
            return (msg.get("content") or "").strip()
        return (getattr(msg, "content", None) or "").strip()
    msg = getattr(response, "message", None)
    if msg is None:
        return ""
    if isinstance(msg, dict):
        return (msg.get("content") or "").strip()
    return (getattr(msg, "content", None) or "").strip()


def _available_models() -> list[str]:
    try:
        r = ollama.list()
        return [m.model for m in r.models]
    except Exception:
        return []


def _pick_model(want: str, available: list[str]) -> str:
    if not available:
        return want
    if want in available:
        return want
    if f"{want}:latest" in available:
        return f"{want}:latest"
    for m in available:
        if m == want or (":" in want and m.startswith(want.split(":")[0] + ":")):
            return m
    for m in available:
        if "embed" not in m.lower():
            return m
    return available[0]


def _load_prompt(persona: str) -> str:
    p = SOUL_VAULT_DIR / f"{persona}_agent.txt"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return f"Bạn là agent {persona} của TuminhAGI."


def _soul_block() -> str:
    lines = ["\n\n[SOUL CONSTANTS]\n"]
    for k, v in SOUL_CONSTANTS.items():
        lines.append(f"- {k.upper()}: {v}\n")
    return "".join(lines)


def _resolve_main_persona(domain: str) -> str:
    d = (domain or "task").lower().strip()
    if d in ("code", "coding", "programming"):
        return "task"
    if d in ("task", "data", "med_gen", "philo", "finance", "logic_math"):
        return d
    return "task"


def _parse_router_json(text: str) -> dict:
    if not text:
        return {"domain": "task", "confidence": 0.5}
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    try:
        return json.loads(clean.strip())
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", clean)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {"domain": "task", "confidence": 0.5}


def chat_turn(user_message: str, available: list[str]) -> None:
    # Router → phi4-mini (MODEL_VALIDATOR trong orchestrator)
    router_model = _pick_model(MODEL_VALIDATOR, available)
    router_sys = _load_prompt("router") + _soul_block()
    r_router = ollama.chat(
        model=router_model,
        messages=[
            {"role": "system", "content": router_sys},
            {"role": "user", "content": f"PHÂN LOẠI CÂU HỎI (trả JSON): {user_message}"},
        ],
    )
    router_text = _ollama_chat_content(r_router)
    parsed = _parse_router_json(router_text)
    domain = str(parsed.get("domain", "task")).lower()
    conf = float(parsed.get("confidence", 0.5) or 0.5)
    main_persona = _resolve_main_persona(domain)

    console.print(
        f"[dim]router → {router_model} | domain={domain} | conf={conf:.2f} | agent={main_persona}[/dim]"
    )

    # Tháp canh tri thức — Wikipedia + Total Search Mandate
    wiki_block = ""
    mandate_block = None
    personal_block = ""
    gs_block = ""
    has_grounded_context = False
    entities = extract_wiki_entities(user_message)
    try:
        wiki_block = format_wiki_grounding_for_context(
            user_message, lang="vi", rank_mode="embedding"
        )
        if wiki_block:
            has_grounded_context = True
            console.print("[dim]📚 Wikipedia grounding đã gắn (task/critic/validator).[/dim]")
        if _MANDATE_AVAILABLE:
            mandate_block = build_mandate_block(user_message, lang="vi")

        # ── Neo 2/3: Chuyên môn (GS) + Cá nhân (TUMINH_BRAIN) ───────────────
        if GS_NEOS_AVAILABLE:
            gs_block = build_neo_gs_do_tat_loi_context(user_message)
            if gs_block:
                has_grounded_context = True
                console.print("[dim]🌿 Neo GS. Đỗ Tất Lợi đã gắn vào prompt.[/dim]")
        if PERSONAL_NEO_AVAILABLE:
            personal_block = build_neo_personal_context(user_message)
            if personal_block:
                console.print("[dim]🧠 Neo Cá nhân (TUMINH_BRAIN) đã gắn vào prompt.[/dim]")
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]⚠ Wiki/Mandate: {e}[/yellow]")

    mandate_suffix = f"\n\n{TOTAL_SEARCH_MANDATE_RULES}" if TOTAL_SEARCH_MANDATE_RULES else ""
    strict_prefix = (
        (STRICT_GROUNDING_PROMPT + "\n\n[CONTEXT]\n") if has_grounded_context and STRICT_GROUNDING_PROMPT else ""
    )
    if strict_prefix:
        console.print("[dim]🔒 STRICT GROUNDING: Model chỉ trả lời từ context.[/dim]")

    base_blocks = wiki_block + ("\n\n" + gs_block if gs_block else "") + ("\n\n" + personal_block if personal_block else "")
    entity_key: str | None = None
    if _LEARNING_AVAILABLE:
        base_blocks, entity_key = inject_learned_context(base_blocks, user_message, entities)
        entity_key = entity_key or _get_entity_key(user_message, entities)
        if entity_key and "[ĐÃ HỌC]" in base_blocks:
            console.print("[dim]🧠 Learning Layer: dùng memory đã học.[/dim]")

    # Trả lời chính → qwen2.5-coder:7b
    task_model = _pick_model(MODEL_TASK, available)
    task_sys = (
        strict_prefix
        + _load_prompt(main_persona)
        + _soul_block()
        + base_blocks
        + mandate_suffix
    )
    r_task = ollama.chat(
        model=task_model,
        messages=[
            {"role": "system", "content": task_sys},
            {"role": "user", "content": user_message},
        ],
    )
    answer = _ollama_chat_content(r_task)

    # Reject system — anti-repeat, check_citation, confidence < 0.3, hallucination
    ctx_for_check = (wiki_block + (" " + gs_block if gs_block else "") + (" " + personal_block if personal_block else "")).strip()
    if has_grounded_context and ctx_for_check:
        if _LEARNING_AVAILABLE and entity_key:
            wrong_reason = filter_wrong(answer, entity_key)
            if wrong_reason:
                console.print(f"[bold red]🛡️ Answer rejected: {wrong_reason}[/bold red]")
                if trigger_learning(user_message, answer, ctx_for_check, entities=entities, reason=wrong_reason):
                    console.print("[dim]🧠 Learning Layer: đã cập nhật wrong_facts.[/dim]")
                return
        passed, reason = grounded_reject_check(answer, ctx_for_check)
        if not passed:
            console.print(f"[bold red]🛡️ Answer rejected: {reason}[/bold red]")
            if _LEARNING_AVAILABLE and trigger_learning(user_message, answer, ctx_for_check, entities=entities, reason=reason):
                console.print("[dim]🧠 Learning Layer: đã học từ lỗi.[/dim]")
            return

    # Critic → deepseek-r1:7b
    critic_model = _pick_model(MODEL_CRITIC, available)
    critic_sys = (
        _load_prompt("critic")
        + _soul_block()
        + wiki_block
        + ("\n\n" + gs_block if gs_block else "")
        + ("\n\n" + personal_block if personal_block else "")
        + mandate_suffix
    )
    critic_user = f"Câu hỏi:\n{user_message}\n\nBản nháp trả lời:\n{answer}"
    if has_grounded_context and FACT_CHECKER_INSTRUCTION:
        critic_user += f"\n\n{FACT_CHECKER_INSTRUCTION}"
    r_crit = ollama.chat(
        model=critic_model,
        messages=[
            {"role": "system", "content": critic_sys},
            {"role": "user", "content": critic_user},
        ],
    )
    critique = _ollama_chat_content(r_crit)

    # Validator → phi4-mini
    val_model = _pick_model(MODEL_VALIDATOR, available)
    val_sys = (
        _load_prompt("validator")
        + _soul_block()
        + wiki_block
        + ("\n\n" + gs_block if gs_block else "")
        + ("\n\n" + personal_block if personal_block else "")
        + mandate_suffix
    )
    r_val = ollama.chat(
        model=val_model,
        messages=[
            {"role": "system", "content": val_sys},
            {
                "role": "user",
                "content": f"Q: {user_message}\nA: {answer}\nCritique:\n{critique}",
            },
        ],
    )
    validation = _ollama_chat_content(r_val)

    console.print(
        Panel(
            Markdown(answer),
            title="[bold magenta]Tự Minh — trả lời chính[/bold magenta]",
            subtitle=f"[dim]{task_model} · persona={main_persona}[/dim]",
            border_style="cyan",
        )
    )
    # 🔗 Search Mandate block — in ngay dưới answer chính
    if mandate_block:
        console.print(mandate_block.render_rich())
    console.print(
        Panel(
            f"[bold]Critic[/bold] ({critic_model})\n{critique[:4000]}{'…' if len(critique) > 4000 else ''}",
            title="[yellow]Phản biện (Critic)[/yellow]",
            border_style="yellow",
        )
    )
    console.print(
        Panel(
            f"[bold]Validator[/bold] ({val_model})\n{validation[:4000]}{'…' if len(validation) > 4000 else ''}",
            title="[green]Xác thực (Validator)[/green]",
            border_style="green",
        )
    )


def main() -> None:
    console.print(
        Panel.fit(
            "[bold]Chat TuminhAGI[/bold]\n"
            "[dim]Router: phi4-mini · Task: qwen2.5-coder · Critic: deepseek-r1 · Validator: phi4-mini · Wiki: vi.wikipedia[/dim]\n"
            "Gõ [bold]/exit[/bold] để thoát.",
            title="chattuminhagi.py",
        )
    )
    av = _available_models()
    if not av:
        console.print("[red]Không liệt kê được model Ollama — kiểm tra `ollama serve`.[/red]")
        sys.exit(1)

    while True:
        try:
            line = console.input("\n[bold cyan]Bạn[/bold cyan]: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nTạm biệt.")
            break
        if not line:
            continue
        if line.lower() in ("/exit", "/quit", "exit", "quit"):
            break
        chat_turn(line, av)


if __name__ == "__main__":
    main()
