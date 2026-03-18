import re
import json

class ConsensusEngine:
    def parse_json(self, data, agent_role: str = "agent") -> dict:
        """Robustly parses JSON data, extracting from text if necessary."""
        if isinstance(data, dict):
            return data
            
        if not data or not isinstance(data, str):
            return self.get_fallback(agent_role, "Empty or invalid input")
            
        # 1. Clean thinking tags (common in DeepSeek)
        clean_data = re.sub(r'<think>.*?</think>', '', data, flags=re.DOTALL)
        
        # 2. Try direct parse
        try:
            return json.loads(clean_data.strip())
        except json.JSONDecodeError:
            pass
            
        # 3. Robust Regex Extraction: Look for anything between first { and last }
        # Re-using DOTALL to handle multilines
        match = re.search(r'(\{.*\})', clean_data, re.DOTALL)
        if match:
            try:
                # We try to clean common issues like leading/trailing markdown characters
                json_str = match.group(1).strip()
                return json.loads(json_str)
            except Exception:
                pass
                
        # 4. Final Fallback: Return safe defaults instead of erroring out to keep pipeline alive
        return self.get_fallback(agent_role, "JSON parsing failed")

    def get_fallback(self, role: str, error_reason: str) -> dict:
        """Provides a safe default JSON for different agent roles."""
        if role == "critic":
            return {
                "status": "error",
                "has_issues": False,  # Default to no issues if we can't parse critique
                "severity": "low",
                "issues": [f"Critic parsing failed: {error_reason}"],
                "suggestions": []
            }
        # Default for Validator or Others
        if role == "router":
            return {"domain": "task", "confidence": 0.5, "reason": "Router failure fallback"}
            
        return {
            "status": "error",
            "approved": True,  # Default to approved to prevent stuck loops
            "confidence": 0.5,
            "reason": f"Validator parsing failed: {error_reason}. Proceeding with caution.",
            "soul_check": "passed",
            "has_issues": False # For general compatibility
        }

    def check(self, critique_data, validation_data) -> tuple[bool, float]:
        critique = self.parse_json(critique_data, "critic")
        validation = self.parse_json(validation_data, "validator")

        severity = critique.get("severity", "medium").lower()
        critic_ok = not critique.get("has_issues", True) and critique.get("status") != "error"
        validator_ok = validation.get("approved", False) and validation.get("status") != "error"
        
        try:
            confidence = float(validation.get("confidence", 0.5))
        except (ValueError, TypeError):
            confidence = 0.5

        if severity == "high": 
            return False, 0.0
        
        # Consensus 2/3 logic: 
        # Votes: Task Agent (Assumed Yes) + Critic + Validator
        if critic_ok and validator_ok:
            # 3/3 Consensus
            bonus = 0.1 if severity == "low" else 0.0
            return True, min(confidence + bonus, 1.0)
            
        if critic_ok or validator_ok:
            # 2/3 Consensus - Still Approved but with lower confidence
            return True, confidence * 0.8
            
        # 1/3 - Only Task Agent says yes, both reviewers disagree
        return False, confidence * 0.3

    def should_ask_human(self, attempt: int, max_retry: int, confidence: float, min_confidence: float) -> bool:
        return attempt >= max_retry - 1 and confidence < min_confidence

    def format_feedback(self, critique_data, validation_data) -> str:
        critique = self.parse_json(critique_data, "critic")
        validation = self.parse_json(validation_data, "validator")
        
        res = []
        if critique.get("status") == "error":
            res.append(f"CRITIQUE [FALLBACK]: {critique.get('issues', ['Error'])[0]}")
        elif critique.get("has_issues"):
            res.append(f"CRITIQUE [{critique.get('severity', 'high').upper()}]:")
            for iss in critique.get("issues", []):
                res.append(f" - {iss}")
            for sug in critique.get("suggestions", []):
                res.append(f" * {sug}")
        else:
            res.append("CRITIQUE: Passed.")
            
        if validation.get("status") == "error":
            res.append(f"VALIDATION [FALLBACK]: {validation.get('reason', 'Error')}")
        else:
            res.append(f"VALIDATION [Conf: {validation.get('confidence', 0)}]:")
            res.append(f" > {validation.get('reason', '')}")
            
        return "\n".join(res)
