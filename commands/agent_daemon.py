import os
import time
import json
from datetime import datetime
from model_providers.provider_registry import ProviderRegistry
from model_providers.response_parser import ResponseParser
from model_loop.prompt_builder import PromptBuilder
from model_loop.plan_validator import PlanValidator

class AgentDaemon:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.provider_registry = ProviderRegistry(base_dir)
        self.prompt_builder = PromptBuilder(base_dir)
        self.plan_validator = PlanValidator(base_dir)
        self.response_parser = ResponseParser()
        self.val_dir = os.path.join(base_dir, "inbox", "validated_plans")
        self.rej_dir = os.path.join(base_dir, "inbox", "rejected_plans")
        self.responses_dir = os.path.join(base_dir, "inbox", "provider_responses")
        
        os.makedirs(self.val_dir, exist_ok=True)
        os.makedirs(self.rej_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def run(self, max_loops: int = -1):
        print(f"Starting Agent Daemon (max_loops={max_loops})")
        loops = 0
        while max_loops == -1 or loops < max_loops:
            # Only generate a new plan if validated_plans is empty
            if os.listdir(self.val_dir):
                time.sleep(5)
                continue
                
            provider = self.provider_registry.get_active_provider()
            
            # Health check
            health = provider.health_check()
            if health.get("status") != "ok":
                print(f"Provider {provider.name} is not healthy: {health}. Waiting...")
                time.sleep(10)
                continue
            
            print(f"--- Agent Loop {loops + 1} ---")
            print(f"Building prompt...")
            prompt_path, req_path = self.prompt_builder.build_prompt()
            
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    prompt_text = f.read()
            except Exception as e:
                print(f"Failed to read prompt: {e}")
                time.sleep(5)
                continue
                
            print(f"Querying provider: {provider.name}")
            result = provider.generate(prompt_text)
            
            if result.get("status") == "success":
                raw_text = result.get("raw_text", "")
                
                # Write raw response for records
                response_filename = f"response_{int(datetime.now().timestamp())}.txt"
                response_path = os.path.join(self.responses_dir, response_filename)
                with open(response_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
                
                print(f"Parsing response...")
                parse_status, plan, err = self.response_parser.parse(raw_text)
                if parse_status == "parsed":
                    temp_path = os.path.join(self.base_dir, "inbox", "temp_cand.json")
                    with open(temp_path, "w", encoding="utf-8") as f:
                        json.dump(plan, f, indent=2)
                        
                    print(f"Validating plan...")
                    is_valid, msg = self.plan_validator.ingest_candidate(temp_path, self.val_dir, self.rej_dir)
                    
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        
                    if is_valid:
                        print(f"Plan validated and queued: {msg}")
                    else:
                        print(f"Plan validation failed: {msg}")
                else:
                    print(f"Failed to parse JSON plan from response: {err}")
            else:
                print(f"Provider failed: {result.get('error')}")
                
            loops += 1
            if max_loops != -1 and loops >= max_loops:
                print("Agent Daemon max loops reached. Exiting.")
                break
                
            # Wait before next cycle
            time.sleep(10)

if __name__ == '__main__':
    daemon = AgentDaemon(os.path.dirname(os.path.abspath(__file__)))
    daemon.run()
