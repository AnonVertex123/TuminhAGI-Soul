import json
from pathlib import Path
from config import VITAL_CONSTANTS, VITAL_FILE

class VitalMemory:
    def __init__(self):
        self.constants = list(VITAL_CONSTANTS)
        self._load_backup()

    def _load_backup(self):
        if VITAL_FILE.exists():
            try:
                with open(VITAL_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.constants = data
            except Exception:
                pass

    def get_all(self) -> list[str]:
        return list(self.constants)

    def format_context(self, retrieved_mems: list[dict]) -> str:
        # Top 4 vital constants
        top_constants = self.constants[:4]
        res = ["NGUYÊN TẮC CỐT LÕI:"]
        for c in top_constants:
            res.append(f"★ {c}")
        
        res.append("\nKÝ ỨC LIÊN QUAN:")
        for m in retrieved_mems:
            tier = m.get("tier", "normal")
            icon = "⭐" if tier == "vital" else "●" if tier == "strong" else "○" if tier == "normal" else "·"
            res.append(f"{icon} {m.get('text', '')}")
            
        return "\n".join(res)

    def is_violation(self, text: str) -> bool:
        keywords = ["bịa đặt", "lừa dối", "thao túng", "gây hại", "tự làm hại"]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def backup(self):
        VITAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(VITAL_FILE, "w", encoding="utf-8") as f:
            json.dump(self.constants, f, ensure_ascii=False, indent=2)
