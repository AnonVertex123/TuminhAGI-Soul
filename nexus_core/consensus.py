import re
import json

class ConsensusEngine:
    def check(self, critique_text: str, validation_text: str) -> tuple[bool, float]:
        def parse_json(text):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(1))
                    except:
                        pass
                return {}

        critique = parse_json(critique_text)
        validation = parse_json(validation_text)

        severity = critique.get("severity", "medium").lower()
        critic_ok = not critique.get("has_issues", True)
        validator_ok = validation.get("approved", False)
        
        try:
            confidence = float(validation.get("confidence", 0.5))
        except (ValueError, TypeError):
            confidence = 0.5

        if severity == "high": 
            return False, 0.0
        
        if critic_ok and validator_ok:
            bonus = 0.1 if severity == "low" else 0.0
            return True, min(confidence + bonus, 1.0)
            
        if critic_ok or validator_ok:
            return False, confidence * 0.6
            
        return False, confidence * 0.3

    def should_ask_human(self, attempt: int, max_retry: int, confidence: float, min_confidence: float) -> bool:
        return attempt >= max_retry - 1 and confidence < min_confidence

    def format_feedback(self, critique: dict, validation: dict) -> str:
        res = []
        if critique.get("has_issues"):
            res.append(f"CRITIQUE [{critique.get('severity', 'high').upper()}]:")
            for iss in critique.get("issues", []):
                res.append(f" - {iss}")
            for sug in critique.get("suggestions", []):
                res.append(f" * {sug}")
        else:
            res.append("CRITIQUE: Passed.")
            
        res.append(f"VALIDATION [Conf: {validation.get('confidence', 0)}]:")
        res.append(f" > {validation.get('reason', '')}")
        return "\n".join(res)
