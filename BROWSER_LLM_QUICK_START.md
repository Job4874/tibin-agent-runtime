# Browser LLM Quick Start Guide

## What is This?

The Tibin runtime can now use browser-accessible LLMs (like BoodleBox) as the model brain. You (human) stay in control, the runtime handles safe execution.

## Quick Start (5 Minutes)

### Step 1: Generate Prompt
```bash
python tibin.py cli --generate-browser-model-prompt
```
This creates `state/model_prompt.md` with your task.

**Output:**
```
Prompt file: C:\...\state\model_prompt.md
Mode: manual_handoff
```

### Step 2: Open BoodleBox
```bash
python tibin.py cli --open-browser-provider
```
Your default browser opens to https://box.boodle.ai/launch/chat

**What to do:**
- Log in with your credentials
- Handle any captcha
- The runtime does NOT bypass these

### Step 3: Manual Handoff (Copy/Paste)
1. Copy the prompt from `state/model_prompt.md`
2. Paste into BoodleBox chat
3. Wait for model response (should be JSON plan)
4. Copy the **full response** (including JSON)
5. Save to a file: `inbox/provider_responses/response.txt`

**Pro tip:** Save as plain text, not PDF or image

### Step 4: Ingest Response
```bash
python tibin.py cli --ingest-browser-model-response
```
The runtime:
- Reads your response file
- Archives the raw text
- Extracts the JSON plan
- Validates it
- Stores valid plans in `inbox/validated_plans/`

**Output:**
```json
{
  "status": "success",
  "candidate_plan_path": "...",
  "raw_response_archive": "..."
}
```

### Step 5: Check Status
```bash
python tibin.py cli --browser-provider-status
```
Shows:
- Provider: BoodleBox
- Mode: manual_handoff
- Pending responses
- Validated plans

### Step 6: Execute
```bash
python tibin.py cli --run-next
```
The runtime:
- Runs the validated plan
- DefenderAgent checks every action
- Workers execute safe tasks
- Reports results

---

## Common Workflows

### Full Manual Cycle (Start to Finish)
```bash
# 1. Generate prompt
python tibin.py cli --generate-browser-model-prompt

# 2. User opens browser and interacts with BoodleBox
python tibin.py cli --open-browser-provider

# 3. User pastes response file
# (manually save to inbox/provider_responses/response.txt)

# 4. Ingest response
python tibin.py cli --ingest-browser-model-response

# 5. Run
python tibin.py cli --run-next
```

### Keep It Simple: One Cycle
```bash
# All-in-one
python tibin.py cli --browser-model-cycle-once
```
This guides you through: generate → open → wait → ingest

### Advanced: Supervised Loop (5 Cycles)
```bash
python tibin.py cli --supervised-browser-loop --max-browser-cycles 5
```
- Automatically cycles 5 times
- You paste response each time
- Runtime validates and executes
- Stops if anything requires approval

---

## What Gets Saved?

### state/
- `model_prompt.md` - Your prompt to the LLM
- `browser_provider_status.json` - Current status

### inbox/provider_responses/
- `response.txt` - Your pasted response (temporary)
- `archive/` - Archived raw responses (permanent)

### inbox/candidate_plans/
- Plans extracted from responses (before validation)

### inbox/validated_plans/
- Plans that passed Defender checks (ready to execute)

### inbox/rejected_plans/
- Plans that failed validation (why not used)

---

## Safety Guarantees

✓ **Login is manual** - No stored passwords
✓ **Captcha is manual** - Not bypassed
✓ **Responses are archived** - Full audit trail
✓ **Plans are validated** - Schema checked
✓ **Defender checks all actions** - No raw execution
✓ **Results are verified** - Proof documented

**Nothing ever bypasses:**
- User login
- Captcha challenges
- Browser password managers
- Defender approval requirements

---

## Troubleshooting

### Error: "No response file found"
- **Problem:** You forgot to save the response
- **Solution:** Save response to `inbox/provider_responses/response.txt`

### Error: "No valid JSON found in response"
- **Problem:** Response doesn't contain JSON
- **Solution:** Make sure BoodleBox gave you a plan in JSON format

### Plan rejected
- **Problem:** Plan validation failed
- **Solution:** Check `inbox/rejected_plans/` for why it failed

### Defender blocked an action
- **Problem:** An action is too risky
- **Solution:** Check `state/` for Defender decision details

### Browser didn't open
- **Problem:** No default browser configured
- **Solution:** Manually visit https://box.boodle.ai/launch/chat

---

## Understanding the Modes

### Manual Handoff (Current)
- You: Copy/paste prompts and responses
- Runtime: Validates and executes
- **Use when:** First-time testing, high control needed

### Browser-Assisted Handoff (Coming)
- Runtime: Injects prompt into chat automatically
- You: Handle login/captcha once
- Runtime: Captures response automatically
- **Use when:** Ready for more automation

### Supervised Autonomous Loop (Coming)
- Runtime: Handles multiple cycles automatically
- Defender: Validates everything
- **Use when:** High confidence in models + Defender

---

## Next Steps

1. **Try manual cycle once:** `python tibin.py cli --browser-model-cycle-once`
2. **Check status:** `python tibin.py cli --browser-provider-status`
3. **Run a full cycle:** Steps 1-6 above
4. **When ready for more automation:** We'll enable browser-assisted mode

---

## Questions?

Check `BROWSER_LLM_BRIDGE_COMPLETE.md` for full technical details.

The core idea:
- **Your browser** = Access to BoodleBox
- **Local runtime** = Trusted execution
- **Defender** = Safety checks
- **You** = Ultimate control
