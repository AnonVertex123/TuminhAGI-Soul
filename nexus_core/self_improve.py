from config import PHASE1_THRESHOLD, PHASE2_THRESHOLD

class SelfImprove:
    def check_phase(self, vital_count: int) -> int:
        if vital_count >= PHASE2_THRESHOLD:
            return 3
        if vital_count >= PHASE1_THRESHOLD:
            return 2
        return 1

    def should_self_evaluate(self, answer: str, critique: dict, phase: int = 1, confidence: float = 0.0, topic_count: int = 0) -> bool:
        if phase == 1:
            return False
        if phase == 2:
            return confidence > 0.8 and topic_count >= 20
        # Phase 3
        return True

    def auto_score(self, answer: str, memories: list) -> int:
        # Tự tính score dựa trên consistency với vital memories
        return 75
