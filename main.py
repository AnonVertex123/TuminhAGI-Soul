#!/usr/bin/env python3
"""
TuminhAGI — Sovereign AI Orchestrator v2-Pre
Authorized by: Hùng Đại (Eric) | Partner: Tự Minh (Lucian)
Feature: Sensory Engine (Voice & Ear) Integrated
"""

import sys
import os
import subprocess
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

# Đảm bảo import đúng cấu trúc
sys.path.insert(0, str(Path(__file__).parent))

from config import MAX_RETRY, CONTEXT_TOP_K, USE_LEARNING_V2, FULL_EVALUATE_V2
from nexus_core.weighted_rag import WeightedRAG
from nexus_core.vital_memory import VitalMemory
from nexus_core.consensus import ConsensusEngine
from nexus_core.llm_client import LLMClient

# --- [GIÁC QUAN] ---
try:
    from tools.sensory.voice import tuminh_voice
    from tools.sensory.ear import tuminh_ear
    SENSORY_AVAILABLE = True
except ImportError:
    SENSORY_AVAILABLE = False

try:
    from tools.wikipedia_bridge import format_wiki_grounding_for_context, extract_wiki_entities

    WIKI_GROUNDING_AVAILABLE = True
except ImportError:
    WIKI_GROUNDING_AVAILABLE = False

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
        SearchMandateBlock,
        TOTAL_SEARCH_MANDATE_RULES,
        STRICT_GROUNDING_PROMPT,
        FACT_CHECKER_INSTRUCTION,
        build_mandate_block,
        build_prompt,
        grounded_reject_check,
    )

    MANDATE_AVAILABLE = True
except ImportError:
    MANDATE_AVAILABLE = False

    class SearchMandateBlock:  # type: ignore[no-redef]
        def render_rich(self) -> str:
            return ""

    def build_mandate_block(_msg: str, **_kw) -> "SearchMandateBlock":  # type: ignore[misc]
        return SearchMandateBlock()

    TOTAL_SEARCH_MANDATE_RULES = ""
    STRICT_GROUNDING_PROMPT = ""
    FACT_CHECKER_INSTRUCTION = ""

    def build_prompt(_ctx: str, _q: str, **_: object) -> str:
        return f"Câu hỏi: {_q}"

    def grounded_reject_check(_ans: str, _ctx: str) -> tuple[bool, str]:
        return True, ""

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

try:
    from tools.learning_layer import (
        trigger_learning,
        inject_learned_context,
        filter_wrong,
        update_memory,
        _get_entity_key,
    )

    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False

    def trigger_learning(*_: object, **__: object) -> bool:
        return False

    def inject_learned_context(ctx: str, _q: str, **_: object) -> tuple[str, str | None]:
        return ctx, None

    def filter_wrong(_ans: str, _ent: str) -> str | None:
        return None

    def update_memory(*_: object, **__: object) -> None:
        pass

    def _get_entity_key(q: str, **_: object) -> str:
        return (q or "")[:80]

try:
    from tools.learning_layer_v2 import (
        learning_v2,
        get_policy_block,
        retrieve_knowledge_v2,
        filter_wrong_v2,
        update_memory_v2,
        extract_fact,
        EVAL_SCORE_THRESHOLD,
    )
    LEARNING_V2_AVAILABLE = True
except ImportError:
    LEARNING_V2_AVAILABLE = False

    def get_policy_block() -> str:
        return ""

    def retrieve_knowledge_v2(_q: str, entities=None, **_):  # noqa: ARG001
        return None, (_q or "")[:80]

    def filter_wrong_v2(_ans: str, _ent: str) -> str | None:
        return None

    def update_memory_v2(*_: object, **__: object) -> None:
        pass

console = Console()
client = LLMClient()

# Trạng thái hệ thống
VOICE_ON = False
MIC_ON = False

def run_sync():
    """Đồng bộ dữ liệu từ GitHub."""
    console.print("[bold yellow]🔄 Đang đồng bộ tri thức từ GitHub...[/bold yellow]")
    try:
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[bold green]✅ Đồng bộ thành công![/bold green]")
            console.print(f"[dim]{result.stdout}[/dim]")
        else:
            console.print(f"[bold red]❌ Lỗi đồng bộ: {result.stderr}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]💥 Lỗi thực thi git: {e}[/bold red]")

def run_pipeline(question: str, rag: WeightedRAG, vital: VitalMemory, consensus: ConsensusEngine):
    """Quy trình đa Agent tập trung."""
    global VOICE_ON, MIC_ON
    entities = extract_wiki_entities(question) if WIKI_GROUNDING_AVAILABLE else []
    retrieved = rag.retrieve(question, top_k=CONTEXT_TOP_K)
    context = vital.format_context(retrieved)
    raw_context = context
    entity_key = None

    # ── Tháp canh tri thức: Wikipedia + Total Search Mandate ────────────────
    mandate_block = None
    has_grounded_context = False  # wiki hoặc neo GS → bật STRICT PROMPT + Fact Checker
    try:
        wiki_ctx = format_wiki_grounding_for_context(
            question, lang="vi", rank_mode="embedding"
        )
        if wiki_ctx:
            context = context + wiki_ctx
            has_grounded_context = True
            console.print("[dim]📚 Wikipedia grounding gắn vào ngữ cảnh.[/dim]")
        if MANDATE_AVAILABLE:
            context = context + f"\n\n{TOTAL_SEARCH_MANDATE_RULES}\n"
            mandate_block = build_mandate_block(question, lang="vi")

        # ── Neo 2/3: Chuyên môn (GS) + Cá nhân (TUMINH_BRAIN) ───────────────
        if GS_NEOS_AVAILABLE:
            gs_ctx = build_neo_gs_do_tat_loi_context(question)
            if gs_ctx:
                context = context + "\n\n" + gs_ctx
                has_grounded_context = True
                console.print("[dim]🌿 Neo GS. Đỗ Tất Lợi gắn vào ngữ cảnh.[/dim]")

        if PERSONAL_NEO_AVAILABLE:
            personal_ctx = build_neo_personal_context(question)
            if personal_ctx:
                context = context + "\n\n" + personal_ctx
                console.print("[dim]🧠 Neo Cá nhân (TUMINH_BRAIN) gắn vào ngữ cảnh.[/dim]")

        # Learning Layer: inject memory đã học (V2 weighted hoặc V1)
        raw_context = context
        if USE_LEARNING_V2 and LEARNING_V2_AVAILABLE:
            mem_ctx, entity_key = retrieve_knowledge_v2(question, entities)
            if mem_ctx:
                context = "[ĐÃ HỌC — ƯU TIÊN]\n" + mem_ctx + "\n\n[CONTEXT MỚI]\n" + context
                console.print("[dim]🧠 Learning V2: dùng memory có trọng số.[/dim]")
            entity_key = entity_key or _get_entity_key(question, entities)
            policy_block = get_policy_block()
            if policy_block:
                context = policy_block + context
                console.print("[dim]📋 Policy: áp dụng quy tắc học từ lỗi.[/dim]")
        elif LEARNING_AVAILABLE:
            context, entity_key = inject_learned_context(context, question, entities)
            entity_key = entity_key or _get_entity_key(question, entities)
            if entity_key and "[ĐÃ HỌC]" in context:
                console.print("[dim]🧠 Learning Layer: dùng memory đã học.[/dim]")

        # STRICT PROMPT: Model CHỈ đọc context, CẤM prior — khi có grounded data
        if has_grounded_context and STRICT_GROUNDING_PROMPT:
            context = STRICT_GROUNDING_PROMPT + "\n\n[CONTEXT]\n" + context
            console.print("[dim]🔒 STRICT GROUNDING: Model chỉ trả lời từ context.[/dim]")
    except Exception as _e:  # noqa: BLE001
        console.print(f"[yellow]⚠ Wiki/Mandate bỏ qua: {_e}[/yellow]")

    for attempt in range(MAX_RETRY):
        console.print(f"\n[bold yellow]Lần suy nghĩ {attempt + 1}/{MAX_RETRY}[/bold yellow]")

        # BƯỚC 1: TASK AGENT (dùng build_prompt khi grounded — khóa model)
        if has_grounded_context and MANDATE_AVAILABLE:
            task_msg = build_prompt(context, question, span_grounding=True)
            answer = client.call("task", task_msg, "")
        else:
            answer = client.call("task", f"Câu hỏi: {question}", context)

        # BƯỚC 2: Reject system — anti-repeat, check_citation, confidence, hallucination
        if has_grounded_context:
            wrong_reason = None
            if USE_LEARNING_V2 and LEARNING_V2_AVAILABLE and entity_key:
                wrong_reason = filter_wrong_v2(answer, entity_key)
            elif LEARNING_AVAILABLE and entity_key:
                wrong_reason = filter_wrong(answer, entity_key)
            if wrong_reason:
                console.print(f"[bold red]🛡️ Answer rejected: {wrong_reason}[/bold red]")
                if USE_LEARNING_V2 and LEARNING_V2_AVAILABLE:
                    try:
                        _, _ = learning_v2(
                            question, raw_context, answer,
                            entities=entities,
                            call_llm=lambda p, m, c: client.call(p, m, c),
                            call_critic=lambda m, c: client.call("critic", m, c),
                            call_refine=lambda m, c: client.call("task", m, c),
                            full_evaluate=FULL_EVALUATE_V2,
                        )
                        console.print("[dim]🧠 Learning V2: đã cập nhật memory + policy.[/dim]")
                    except Exception:
                        if LEARNING_AVAILABLE:
                            trigger_learning(question, answer, raw_context, entities=entities, reason=wrong_reason)
                elif LEARNING_AVAILABLE:
                    trigger_learning(question, answer, raw_context, entities=entities, reason=wrong_reason)
                continue
            passed, reason = grounded_reject_check(answer, context)
            if not passed:
                console.print(f"[bold red]🛡️ Answer rejected: {reason}[/bold red]")
                if USE_LEARNING_V2 and LEARNING_V2_AVAILABLE:
                    try:
                        _, updated = learning_v2(
                            question, raw_context, answer,
                            entities=entities,
                            call_llm=lambda p, m, c: client.call(p, m, c),
                            call_critic=lambda m, c: client.call("critic", m, c),
                            call_refine=lambda m, c: client.call("task", m, c),
                            full_evaluate=FULL_EVALUATE_V2,
                        )
                        console.print(f"[dim]🧠 Learning V2: đã học (score, policy).{' Debate→refined' if updated else ''}[/dim]")
                    except Exception:
                        if LEARNING_AVAILABLE:
                            trigger_learning(question, answer, raw_context, entities=entities, reason=reason)
                elif LEARNING_AVAILABLE:
                    trigger_learning(question, answer, raw_context, entities=entities, reason=reason)
                continue

        console.print(Panel(Markdown(answer), title="Tự Minh Phản hồi", border_style="cyan"))
        # Khối tra cứu thực chứng
        if mandate_block:
            console.print(mandate_block.render_rich())
        
        # PHÁT ÂM THANH NẾU BẬT
        if VOICE_ON and SENSORY_AVAILABLE:
            # Chỉ nói đoạn tóm tắt hoặc 200 ký tự đầu để tránh quá dài nếu cần
            # Ở đây ta cho nói hết nhưng có thể ngắt bằng Ctrl+C
            tuminh_voice.speak(answer)

        # XÁC NHẬN TỪ HOA TIÊU
        console.print("\n[bold green]⚓ XÁC NHẬN TỪ HÙNG ĐẠI:[/bold green]")
        console.print("[dim]  [y]: Chấp nhận | [n]: Soi lỗi | [v]: Bật/Tắt Giọng nói | [m]: Bật/Tắt Micro[/dim]")
        
        user_choice = Prompt.ask("[Duyệt]", choices=["y", "n", "exit", "v", "m"], default="y")

        if user_choice == "v":
            VOICE_ON = not VOICE_ON
            msg = f"Đã {'BẬT' if VOICE_ON else 'TẮT'} giọng nói."
            console.print(f"[bold magenta]{msg}[/bold magenta]")
            if VOICE_ON: tuminh_voice.speak(msg)
            continue

        if user_choice == "m":
            MIC_ON = not MIC_ON
            console.print(f"[bold magenta]Đã {'BẬT' if MIC_ON else 'TẮT'} chế độ Micro lắng nghe.[/bold magenta]")
            continue

        if user_choice.lower() == "y":
            rag.add_memory(question, answer, score=100)
            if USE_LEARNING_V2 and LEARNING_V2_AVAILABLE and entity_key:
                facts = extract_fact(raw_context) if raw_context else []
                if not facts:
                    facts = [raw_context[:200]] if raw_context else []
                update_memory_v2(entity_key, facts, EVAL_SCORE_THRESHOLD)
            elif LEARNING_AVAILABLE and entity_key:
                update_memory(entity_key, is_correct=True)
            console.print("[bold green]✅ Đã lưu vào Tinh hoa.[/bold green]")
            return answer
        
        elif user_choice.lower() == "n":
            console.print("[bold red]🔴 Phê bình Agent (Critic) đang làm việc...[/bold red]")
            critic_msg = f"Câu hỏi: {question}\nTrả lời: {answer}"
            if has_grounded_context and FACT_CHECKER_INSTRUCTION:
                critic_msg += f"\n\n{FACT_CHECKER_INSTRUCTION}"
            critique = client.call("critic", critic_msg, context)
            
            validation = client.call("validator", f"Câu hỏi: {question}\nTrả lời: {answer}\nNhận xét: {critique}", context)
            
            is_approved, confidence = consensus.check(critique, validation)
            feedback = consensus.format_feedback(critique, validation)
            console.print(Panel(feedback, title="Kết quả phản biện", border_style="yellow"))
            continue

        elif user_choice == "exit":
            sys.exit(0)
            
    return answer

def main():
    global VOICE_ON, MIC_ON
    
    console.print(Panel.fit(
        "[bold magenta]🪷 TuminhAGI: PHIÊN BẢN TIẾN HÓA (SENSORY)[/bold magenta]\n"
        "[dim]Hệ thống Thính giác (Vosk) & Tiếng nói (Edge-TTS): Cài đặt xong[/dim]",
        subtitle="Dành riêng cho Hùng Đại"
    ))
    
    rag, vital = WeightedRAG(), VitalMemory()
    consensus_engine = ConsensusEngine()
    
    # Chào hỏi bằng giọng nói nếu khởi tạo thành công
    if SENSORY_AVAILABLE:
        welcome_msg = "Chào Hùng Đại, Tự Minh đã sẵn sàng đồng hành cùng anh."
        console.print(f"[italic magenta]({welcome_msg})[/italic magenta]")
        # Mặc định chưa bật để tránh làm phiền, nhưng sẵn sàng
        # tuminh_voice.speak(welcome_msg) 

    while True:
        try:
            if MIC_ON and SENSORY_AVAILABLE:
                user_input = tuminh_ear.listen()
                if not user_input: 
                    MIC_ON = False # Tự tắt nếu không nghe thấy gì để quay lại phím
                    continue
                console.print(f"[bold cyan]Hùng Đại (Nói):[/bold cyan] {user_input}")
            else:
                user_input = Prompt.ask("\n[bold cyan]Hùng Đại (Eric)[/bold cyan]")
            
            if not user_input.strip(): continue
            
            # Lệnh bẻ lái khẩn cấp
            if user_input.startswith("!"):
                correction = user_input[1:].strip()
                console.print(f"[bold red]🔄 HIỆU CHỈNH KHẨN CẤP: {correction}[/bold red]")
                answer = client.call("task", f"LỆNH SỬA SAI: {correction}")
                console.print(Panel(Markdown(answer), title="Tự Minh (Đã sửa)", border_style="bold red"))
                if VOICE_ON: tuminh_voice.speak(answer)
                rag.add_memory("Correction", answer, score=98)
                continue

            # Lệnh hệ thống
            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd == "/exit": break
                elif cmd == "/sync": run_sync()
                elif cmd == "/voice": 
                    VOICE_ON = not VOICE_ON
                    console.print(f"[magenta]Giọng nói: {'BẬT' if VOICE_ON else 'TẮT'}[/magenta]")
                elif cmd == "/mic":
                    MIC_ON = not MIC_ON
                    console.print(f"[magenta]Micro: {'BẬT' if MIC_ON else 'TẮT'}[/magenta]")
                elif cmd == "/stats": console.print(rag.stats())
                continue

            run_pipeline(user_input, rag, vital, consensus_engine)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Hệ thống tạm nghỉ.[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]System Error: {e}[/bold red]")

if __name__ == "__main__":
    main()