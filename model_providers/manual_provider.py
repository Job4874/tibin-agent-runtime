import os
from datetime import datetime, timezone
from typing import Dict, Any
from .base_provider import BaseModelProvider

class ManualProvider(BaseModelProvider):
    name = "manual"

    def __init__(self, config: Dict[str, Any], base_dir: str):
        super().__init__(config)
        self.base_dir = base_dir

    def generate(self, prompt: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        # Write to outbox/model_prompts/latest_prompt.md
        outbox_dir = os.path.join(self.base_dir, "outbox", "model_prompts")
        os.makedirs(outbox_dir, exist_ok=True)
        
        # also we should ensure state/model_prompt.md is what we have or read from it if prompt is empty?
        # Typically the system passes the prompt. We'll write it out.
        prompt_path = os.path.join(outbox_dir, "latest_prompt.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
            
        print(f"\n[ManualProvider] Prompt written to: {prompt_path}")
        print("[ManualProvider] Please copy this prompt, send it to the model manually,")
        print("[ManualProvider] and save the raw response into: inbox/provider_responses/\n")
        
        return {
            "provider": self.name,
            "status": "manual_handoff",
            "raw_text": "",
            "usage": {},
            "error": "Manual handoff required. Please paste response into inbox/provider_responses/.",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
