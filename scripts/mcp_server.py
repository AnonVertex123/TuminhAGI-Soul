"""
scripts/mcp_server.py — TuminhAGI MCP Server
=============================================
Implements Model Context Protocol (MCP) over stdio.
Cursor se coi TuminhAGI la mot "Co van toi cao" co the:

  brain_query     — Tim kiem kien thuc trong TUMINH_BRAIN.jsonl
  brain_inject    — Nap 1 nep nhan moi vao brain qua gate
  brain_stats     — Xem thong ke nao bo
  diagnose_hint   — Lay goi y chan doan tu MedicalDiagnosticTool (neu Ollama chay)
  get_patterns    — Lay danh sach cac pattern theo category

Cau hinh trong Cursor Settings > Features > MCP:
  Name   : TuminhAGI
  Command: python scripts/mcp_server.py
  (chay tu thu muc i:/TuminhAgi)
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

# MCP hoat dong qua stdio — KHONG duoc print bat ky gi ngoai JSON-RPC responses
# Tat moi redirect stdout/stderr tru stderr cho debug
_real_stderr = sys.stderr

PROJECT_ROOT = Path(__file__).parent.parent
BRAIN_FILE   = PROJECT_ROOT / "memory" / "TUMINH_BRAIN.jsonl"
GATE_FILE    = PROJECT_ROOT / "memory" / "brain_gate.json"


# ── Brain helpers ────────────────────────────────────────────────────────────

def _load_brain() -> list[dict[str, Any]]:
    if not BRAIN_FILE.exists():
        return []
    entries = []
    with open(BRAIN_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def _brain_query(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    kw = keyword.lower()
    results = []
    for e in _load_brain():
        blob = json.dumps(e, ensure_ascii=False).lower()
        if kw in blob:
            results.append(e)
            if len(results) >= limit:
                break
    return results


def _brain_stats() -> dict[str, Any]:
    from collections import Counter
    entries = _load_brain()
    cats = Counter(e.get("category", "?") for e in entries)
    return {
        "total_entries": len(entries),
        "categories": dict(cats.most_common()),
        "last_updated": entries[-1]["timestamp"] if entries else "N/A",
    }


def _brain_inject(entry: dict[str, Any]) -> dict[str, Any]:
    import datetime
    required = {"category", "logic_pattern", "core_syntax", "lesson"}
    missing = required - set(entry.keys())
    if missing:
        return {"success": False, "error": f"Missing fields: {missing}"}

    # Kiem tra trung lap
    existing = {(e.get("category"), e.get("logic_pattern")) for e in _load_brain()}
    key = (entry.get("category"), entry.get("logic_pattern"))
    if key in existing:
        return {"success": False, "error": f"Already exists: {key}"}

    entry.setdefault("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    entry.setdefault("source", "MCP Direct Inject")
    entry.setdefault("tags", [])

    # Ghi qua gate (de brain_watcher xu ly) hoac truc tiep vao brain
    BRAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BRAIN_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {"success": True, "injected": entry["logic_pattern"]}


def _get_patterns(category: str | None = None) -> list[dict[str, Any]]:
    entries = _load_brain()
    if category:
        entries = [e for e in entries if e.get("category", "").lower() == category.lower()]
    return [
        {
            "pattern": e.get("logic_pattern"),
            "category": e.get("category"),
            "lesson": e.get("lesson"),
            "tags": e.get("tags", []),
        }
        for e in entries
    ]


# ── MCP Tool Definitions ─────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "brain_query",
        "description": "Tim kiem kien thuc trong TUMINH_BRAIN.jsonl theo tu khoa. "
                       "Su dung khi can tim pattern, lesson, hoac syntax da hoc truoc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Tu khoa tim kiem (VD: 'threshold', 'cosine', 'cache')"},
                "limit":   {"type": "integer", "description": "So ket qua toi da (default 5)", "default": 5},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "brain_inject",
        "description": "Nap 1 nep nhan tri thuc moi vao TUMINH_BRAIN. "
                       "Goi sau khi hoan thanh mot logic toi uu de luu lai permanently.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category":      {"type": "string", "description": "Phan loai (Optimization/Safety/Caching/Architecture/Medical Logic/NumPy-Math/NLP-Embedding/Testing)"},
                "logic_pattern": {"type": "string", "description": "Ten ngan gon cua pattern"},
                "core_syntax":   {"type": "string", "description": "Doan code tieu bieu nhat (1-3 dong)"},
                "lesson":        {"type": "string", "description": "Tai sao lam vay lai thang (nguyen nhan goc re)"},
                "tags":          {"type": "array", "items": {"type": "string"}, "description": "Danh sach tags"},
            },
            "required": ["category", "logic_pattern", "core_syntax", "lesson"],
        },
    },
    {
        "name": "brain_stats",
        "description": "Xem tong quan nao bo TuminhAGI: so luong nep nhan, phan loai, thoi gian cap nhat.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_patterns",
        "description": "Lay danh sach cac pattern da hoc, co the loc theo category.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Loc theo category (bo trong = lay tat ca)"},
            },
        },
    },
    {
        "name": "diagnose_hint",
        "description": "Lay goi y chan doan nhanh dua tren trieu chung (Tieng Viet hoac Tieng Anh). "
                       "Tra ve cac ma ICD-10 va do tuong dong.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symptoms": {"type": "string", "description": "Chuoi trieu chung (VD: 'dau nguc trai, kho tho')"},
                "top_k":    {"type": "integer", "description": "So ket qua (default 3)", "default": 3},
            },
            "required": ["symptoms"],
        },
    },
]


# ── Tool Handlers ────────────────────────────────────────────────────────────

def _handle_tool(name: str, args: dict[str, Any]) -> Any:
    if name == "brain_query":
        results = _brain_query(args.get("keyword", ""), args.get("limit", 5))
        if not results:
            return f"Khong tim thay ket qua cho: '{args.get('keyword')}'"
        lines = []
        for i, e in enumerate(results, 1):
            lines.append(
                f"[{i}] {e.get('category')} | {e.get('logic_pattern')}\n"
                f"     Lesson: {e.get('lesson')}\n"
                f"     Syntax: {e.get('core_syntax', '')[:100]}"
            )
        return "\n\n".join(lines)

    elif name == "brain_inject":
        result = _brain_inject(dict(args))
        if result["success"]:
            return f"[OK] Da nap: '{result['injected']}' vao TUMINH_BRAIN"
        return f"[FAIL] {result['error']}"

    elif name == "brain_stats":
        stats = _brain_stats()
        lines = [
            f"Nao bo TuminhAGI: {stats['total_entries']} nep nhan",
            f"Cap nhat: {stats['last_updated']}",
            "Phan loai:",
        ]
        for cat, cnt in stats["categories"].items():
            lines.append(f"  {cat}: {cnt}")
        return "\n".join(lines)

    elif name == "get_patterns":
        patterns = _get_patterns(args.get("category"))
        if not patterns:
            return "Chua co pattern nao."
        return "\n".join(
            f"- [{p['category']}] {p['pattern']}: {p['lesson']}"
            for p in patterns
        )

    elif name == "diagnose_hint":
        return _diagnose_hint(args.get("symptoms", ""), args.get("top_k", 3))

    return f"Unknown tool: {name}"


def _diagnose_hint(symptoms: str, top_k: int = 3) -> str:
    """Chay nhanh qua medical_diagnostic_tool neu co the."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from missions_hub.medical_diagnostic_tool import MedicalDiagnosticTool
        tool = MedicalDiagnosticTool()
        if tool.df is None:
            tool.load_vault()
        if tool.embeddings is None:
            return "Vault chua duoc load. Hay chay server truoc."

        translated = tool.translate_query(symptoms)
        results = tool.tuminh_multi_diagnostic_loop(translated, max_diagnoses=top_k)
        if not results:
            return f"Khong tim thay chan doan cho: '{symptoms}'"

        lines = [f"Chan doan goi y cho '{symptoms}':"]
        for i, r in enumerate(results[:top_k], 1):
            code = r.get("icd_code", "?")
            desc = r.get("description", "?")
            score = r.get("score", 0)
            lines.append(f"  {i}. {code} — {desc} (score: {score:.3f})")
        return "\n".join(lines)
    except Exception as e:
        return f"[ERROR] diagnose_hint: {e}"


# ── MCP JSON-RPC Protocol ────────────────────────────────────────────────────

def _send(obj: dict[str, Any]) -> None:
    line = json.dumps(obj, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _error(req_id: Any, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _result(req_id: Any, result: Any) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _handle_request(req: dict[str, Any]) -> None:
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "initialize":
        _result(req_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "TuminhAGI", "version": "9.1"},
            "capabilities": {"tools": {}},
        })

    elif method == "notifications/initialized":
        pass  # no response needed

    elif method == "tools/list":
        _result(req_id, {"tools": TOOLS})

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args  = params.get("arguments", {})
        try:
            output = _handle_tool(tool_name, tool_args)
            _result(req_id, {
                "content": [{"type": "text", "text": str(output)}]
            })
        except Exception as e:
            _error(req_id, -32603, f"Tool error: {e}")

    elif method == "ping":
        _result(req_id, {})

    else:
        if req_id is not None:
            _error(req_id, -32601, f"Method not found: {method}")


# ── Stdio Loop ───────────────────────────────────────────────────────────────

def main() -> None:
    # Stdio binary mode on Windows to avoid CRLF corruption
    if sys.platform == "win32":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)  # type: ignore[attr-defined]
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)  # type: ignore[attr-defined]

    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _send({"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": f"Parse error: {e}"}})
            continue

        try:
            _handle_request(req)
        except Exception as e:
            print(f"[MCP Internal] {e}", file=_real_stderr)


if __name__ == "__main__":
    import os
    main()
