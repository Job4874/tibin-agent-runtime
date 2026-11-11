# Tibin Agent Runtime — Command Reference

## OpenRouter & Autonomous

### Plan replay (no API key)
```bash
python tibin.py cli --run-loop examples/safe_code_plan.json --max-turns 10
```

### Autonomous goal (OpenRouter only)
```bash
python tibin.py cli --run-autonomous "List all .py files in the project root" --max-turns 10
```
Fails with `failed_no_brain` if `OPENROUTER_API_KEY` is missing — no BoodleBox fallback.

### Dashboard & launcher
```bash
python tibin.py server          # starts http://127.0.0.1:5000/
python tibin.py gui            # desktop GUI launcher
python tibin.py gui --no-gui   # headless start
```

### Stop / audit
```bash
python tibin.py cli --stop-all
python tibin.py server --stop
python scripts/audit_install.py
```

Windows find duplicate clones:
```powershell
powershell -File scripts\windows\Find-TibinCopies.ps1
powershell -File scripts\windows\Stop-TibinRuntime.ps1
```

---

### Check Status
```bash
python tibin.py cli --browser-provider-status
```
Shows current provider status, pending responses, inbox paths.

### Generate Prompt
```bash
python tibin.py cli --generate-browser-model-prompt
```
Creates `state/model_prompt.md` with your task for the LLM.

### Open Provider
```bash
python tibin.py cli --open-browser-provider
```
Opens https://box.boodle.ai/launch/chat in default browser.

### Ingest Response
```bash
python tibin.py cli --ingest-browser-model-response
```
Processes response from `inbox/provider_responses/`.
Archives raw response, validates plan JSON.

### Manual Cycle
```bash
python tibin.py cli --browser-model-cycle-once
```
Walks through: generate → open → wait → ingest.

### Supervised Loop
```bash
python tibin.py cli --supervised-browser-loop
```
Default: 1 safe cycle with all guards.

```bash
python tibin.py cli --supervised-browser-loop --max-browser-cycles 5
```
Run up to 5 cycles (stops early if needed).

### Execute Plan
```bash
python tibin.py cli --run-next
```
Runs the newest validated plan with Defender checks.

### Check Health
```bash
python tibin.py cli --doctor
```
Verifies all system components.

### Run Tests
```bash
python -m pytest tests/ -q
```
Runs all tests (should all pass).

---

## Workflow Example

### One Complete Cycle

```bash
# Step 1: Generate prompt
python tibin.py cli --generate-browser-model-prompt

# Step 2: Open browser
python tibin.py cli --open-browser-provider

# Step 3: User interaction
# - Log in to BoodleBox
# - Handle captcha if needed
# - Copy prompt from state/model_prompt.md
# - Paste into BoodleBox chat
# - Get response (should be JSON plan)
# - Copy response
# - Save to inbox/provider_responses/response.txt

# Step 4: Ingest response
python tibin.py cli --ingest-browser-model-response

# Step 5: Check what was created
python tibin.py cli --browser-provider-status

# Step 6: Execute
python tibin.py cli --run-next

# Step 7: Done!
# Check reports in reports/ directory
```

---

## Directory Reference

### State Files
```
state/
├── model_prompt.md              (your prompt for BoodleBox)
├── browser_provider_status.json (provider status)
└── browser_loop_status.json     (loop status if running)
```

### Inbox Directories
```
inbox/
├── provider_responses/          (raw responses from BoodleBox)
│   ├── response.txt             (your pasted response)
│   ├── response.txt.processed   (archived after processing)
│   └── archive/                 (permanent archive)
├── candidate_plans/             (extracted but not validated)
├── validated_plans/             (validated, ready to run)
└── rejected_plans/              (failed validation)
```

### Reports
```
reports/
├── latest_report.md             (most recent execution report)
└── *.md                         (historical reports)
```

---

## Configuration

### Current Mode: Manual Handoff
```
config/browser_llm_providers.json
├─ active_browser_provider: "boodlebox"
├─ mode: "manual_handoff"
├─ url: "https://box.boodle.ai/launch/chat"
├─ requires_user_login: true
├─ allow_browser_automation: false
└─ safety:
   ├─ never_bypass_login: true
   ├─ never_bypass_captcha: true
   ├─ never_read_passwords: true
   └─ raw_response_never_executes: true
```

---

## Troubleshooting

### Error: "No response file found"
**Problem:** You didn't save the response
**Solution:** Save response to `inbox/provider_responses/response.txt`

### Error: "No valid JSON found"
**Problem:** Response doesn't contain JSON plan
**Solution:** Make sure BoodleBox gave you a plan in JSON format

### Error: "Plan validation failed"
**Problem:** Plan JSON doesn't have required fields
**Solution:** Check `inbox/rejected_plans/` for details

### Defender: "Action blocked"
**Problem:** Defender considered action too risky
**Solution:** Check logs or modify plan to be less risky

### Browser didn't open
**Problem:** No default browser set
**Solution:** Manually visit https://box.boodle.ai/launch/chat

---

## Advanced Usage

### Run Multiple Cycles
```bash
# Run up to 10 safe cycles
python tibin.py cli --supervised-browser-loop --max-browser-cycles 10
```

### Just Generate Prompt (No User Interaction)
```bash
python tibin.py cli --generate-browser-model-prompt
# Now you can share the prompt via email, etc.
```

### Just Ingest (Pre-saved Response)
```bash
# If you already have response in inbox/provider_responses/
python tibin.py cli --ingest-browser-model-response
```

### Check What's Pending
```bash
python tibin.py cli --browser-provider-status | grep pending
```

---

## Safety Features

### Always Protected By
- ✓ Login required (manual)
- ✓ Captcha handling (manual)
- ✓ Response validation (automatic)
- ✓ Plan schema check (automatic)
- ✓ Defender approval (automatic)
- ✓ Result verification (automatic)
- ✓ Audit trail (automatic)

### Never Bypassed
- ✗ Browser login
- ✗ Captcha challenges
- ✗ Password managers
- ✗ Raw output execution

---

## Performance Notes

- Prompt generation: <1 second
- Response ingestion: <1 second
- Plan validation: <1 second
- Full cycle: ~5 minutes (mostly waiting for user)
- Supervised loop (1 cycle): ~5 minutes

---

## Output Examples

### --browser-provider-status
```json
{
  "provider": "browser_llm",
  "active_provider": "boodlebox",
  "mode": "manual_handoff",
  "url": "https://box.boodle.ai/launch/chat",
  "pending_responses": 1,
  "pending_candidate_plans": 0,
  "response_inbox_path": "...",
  "candidate_plans_path": "...",
  "validated_plans_path": "...",
  "rejected_plans_path": "..."
}
```

### --generate-browser-model-prompt
```json
{
  "status": "success",
  "action": "prompt_generated",
  "prompt_file": "state/model_prompt.md",
  "provider_url": "https://box.boodle.ai/launch/chat",
  "mode": "manual_handoff",
  "instructions": "1. Open URL...\n2. Log in...\n..."
}
```

### --ingest-browser-model-response
```json
{
  "status": "success",
  "action": "response_ingested",
  "raw_response_archive": "inbox/provider_responses/archive/...",
  "candidate_plan_path": "inbox/candidate_plans/...",
  "next_step": "Validate and approve plan"
}
```

---

## Common Patterns

### Pattern 1: Quick Cycle
```bash
python tibin.py cli --browser-model-cycle-once
```

### Pattern 2: Full Supervised Cycle
```bash
python tibin.py cli --supervised-browser-loop --max-browser-cycles 1
```

### Pattern 3: Multi-Step Task
```bash
# Run 3 cycles (for complex tasks)
python tibin.py cli --supervised-browser-loop --max-browser-cycles 3
```

### Pattern 4: Manual Control
```bash
# Step by step
python tibin.py cli --generate-browser-model-prompt
python tibin.py cli --open-browser-provider
# User does their thing
python tibin.py cli --ingest-browser-model-response
python tibin.py cli --run-next
```

---

## Getting Help

### Verify Setup
```bash
python tibin.py cli --doctor
```

### See All Commands
```bash
python tibin.py cli --help
```

### Run Tests
```bash
python -m pytest tests/ -v
```

### Check Documentation
- `YOU_ARE_HERE.md` - Overview
- `BROWSER_LLM_QUICK_START.md` - Getting started
- `BROWSER_LLM_BRIDGE_COMPLETE.md` - Full technical details

---

**Ready to start? Run:**
```bash
python tibin.py cli --generate-browser-model-prompt
```
