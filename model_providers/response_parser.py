import json
import re
from typing import Dict, Any, Tuple

class ResponseParser:
    def parse(self, raw_text: str) -> Tuple[str, Dict[str, Any], str]:
        """
        Returns (status, plan_dict, error_msg)
        status: 'parsed', 'ambiguous', 'failed'
        """
        if not raw_text or not raw_text.strip():
            return "failed", {}, "Empty response"

        # Look for code blocks
        json_blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
        
        candidates = []
        
        if json_blocks:
            for block in json_blocks:
                try:
                    obj = json.loads(block)
                    if isinstance(obj, dict):
                        candidates.append(obj)
                except json.JSONDecodeError:
                    pass
        else:
            # Try to parse the entire text as JSON
            try:
                obj = json.loads(raw_text)
                if isinstance(obj, dict):
                    candidates.append(obj)
            except json.JSONDecodeError:
                # Look for { ... } as fallback
                start_idx = raw_text.find('{')
                end_idx = raw_text.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    try:
                        obj = json.loads(raw_text[start_idx:end_idx+1])
                        if isinstance(obj, dict):
                            candidates.append(obj)
                    except json.JSONDecodeError:
                        pass

        if not candidates:
            return "failed", {}, "No valid JSON found in response."
            
        # Filter for actual plans (must have plan_id and actions)
        plan_candidates = [c for c in candidates if "plan_id" in c and "actions" in c]
        
        if not plan_candidates:
            return "failed", {}, "JSON found but it is not a valid plan (missing plan_id or actions)."
            
        if len(plan_candidates) > 1:
            return "ambiguous", {}, "Multiple plan JSON objects found in response."
            
        return "parsed", plan_candidates[0], ""
