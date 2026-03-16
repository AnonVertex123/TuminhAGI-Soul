import re
import json

class ConsensusEngine:
    def parse_json(self, data) -> dict:
        if isinstance(data, dict):
            return data
        if not isinstance(data, str):
            return {"status": "error", "has_issues": True, "approved": False, "severity": "high"}
            
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', data, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            return {"status": "error", "has_issues": True, "approved": False, "severity": "high"}

    def check(self, critique_data, validation_data) -> tuple[bool, float]:
        critique = self.parse_json(critique_data)
        validation = self.parse_json(validation_data)

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

    def format_feedback(self, critique_data, validation_data) -> str:
        critique = self.parse_json(critique_data)
        validation = self.parse_json(validation_data)
        
        res = []
        if critique.get("status") == "error":
            res.append("CRITIQUE [ERROR]: Invalid JSON response format from Critic.")
        elif critique.get("has_issues"):
            res.append(f"CRITIQUE [{critique.get('severity', 'high').upper()}]:")
            for iss in critique.get("issues", []):
                res.append(f" - {iss}")
            for sug in critique.get("suggestions", []):
                res.append(f" * {sug}")
        else:
            res.append("CRITIQUE: Passed.")
            
        if validation.get("status") == "error":
            res.append("VALIDATION [ERROR]: Invalid JSON response format from Validator.")
        else:
            res.append(f"VALIDATION [Conf: {validation.get('confidence', 0)}]:")
            res.append(f" > {validation.get('reason', '')}")
            
        return "\n".join(res)
