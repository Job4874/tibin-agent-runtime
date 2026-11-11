# Agent Instructions for Tibin Full-Stack AI Coding Agent Runtime

When an LLM operates this runtime, it must adhere to the following principles:

1. **The Model is the Brain. The Runtime is the Body.**
   You are generating plans (`plan.json`) that the local runtime executes safely. The runtime does not execute raw model text. It validates, defends, and runs approved actions only.

2. **Dual-brain routing**
   - **OpenRouter** (`OPENROUTER_API_KEY` in `.env`): autonomous CLI and dashboard tasks via `--run-autonomous`. Never scrape BoodleBox as fallback.
   - **BoodleBox** (https://box.boodle.ai/launch/): premium manual handoff for complex plans. Log in via system browser; paste plan JSON into inbox.
   - Login/signup HTML must never be treated as a successful model answer.

3. **BoodleBox Handoff**
   The online LLM brain is accessed through BoodleBox at https://box.boodle.ai/launch/chat. The model thinks. The runtime acts. Responses from BoodleBox must become structured candidate plan JSON before execution.

3. **Safety by Default**
   - Do not attempt to bypass the DefenderAgent.
   - For destructive actions or actions requiring authentication, explicitly set `"requires_approval": true` and wait for human input.
   - Do not scrape personal data or steal cookies.
   - The runtime is for full-stack coding work only.

4. **Complex Problem Solving**
   If stuck, use the `ComplexityEngine` or trigger context recovery by generating a plan that leverages the `MemoryWorker` and `ReportWorker`.

5. **Structured Execution**
   Never send vague tasks. Break down plans into atomic, verifiable units for the specialized workers (Shell, File, Git, Browser, Coder, Verifier, Memory, Report).
