# Summarizer Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `summarizer_agent` that summarizes pasted text and uploaded files (PDF, txt, markdown), mirroring the existing `greeting_agent` pattern.

**Architecture:** Three new files under `app/agent_repo/summarizer_agent/` (prompt, LlmAgent definition, package init) plus two small edits to register the agent in `agent_repo/__init__.py` and `agent_repo/agent_registry.py`. No new tools, no infrastructure changes — the UI is already wired for `agent_id === "summarizer_agent"` and `AgentTeamHandler._build_user_content` already converts uploaded files into ADK `Part`s (text inline for text MIMEs, `inline_data` for PDFs which Gemini 2.5 reads natively).

**Tech Stack:** Python 3.14, `google-adk` (`LlmAgent`), Gemini 2.5 Flash, FastAPI + WebSocket front-end (already in place), uv for env management.

**Verification model:** No unit tests added (no `tests/` directory in this project, prompt-only agent). Final task is manual smoke testing in the running app.

**Spec:** [`docs/superpowers/specs/2026-05-23-summarizer-agent-design.md`](../specs/2026-05-23-summarizer-agent-design.md)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `app/agent_repo/summarizer_agent/prompt.py` | Create | Holds the single `SUMMARIZER_AGENT_INSTRUCTION` string constant. Behavior contract lives here. |
| `app/agent_repo/summarizer_agent/agent.py` | Create | Defines the `summarizer_agent` `LlmAgent` instance bound to the prompt. |
| `app/agent_repo/summarizer_agent/__init__.py` | Create | Re-exports `summarizer_agent` so callers can `from app.agent_repo.summarizer_agent import summarizer_agent`. |
| `app/agent_repo/__init__.py` | Modify (1 line added) | Add the real `from .summarizer_agent import summarizer_agent` import. The `__all__` already lists `"summarizer_agent"`. |
| `app/agent_repo/agent_registry.py` | Modify (1 import + 1 dict entry added) | Add import + `"summarizer_agent": {...}` entry so the UI lists the agent and `get_agent("summarizer_agent")` resolves. |

No other files change. The WS handler, `AgentTeamHandler`, artifact service, and UI all already handle this agent ID generically.

---

## Task 1: Author the prompt

Build the behavior contract first so the agent module can import it.

**Files:**
- Create: `app/agent_repo/summarizer_agent/prompt.py`

- [ ] **Step 1: Create the prompt file with the full instruction constant**

Write `app/agent_repo/summarizer_agent/prompt.py` with this exact content:

```python

SUMMARIZER_AGENT_INSTRUCTION = """\
You are a friendly summarization assistant for the "Agentic AI Engineering" lecture.

Your job is to summarize text the user pastes into the chat OR the contents of any file they attach (PDFs, text files, markdown). If a file is attached, treat its content as the primary input to summarize.

Initial greeting (when there is no user input yet — just a connection or an empty message): respond with ONE short sentence inviting the user to paste text or upload a file. Keep it to 2-3 sentences MAX. Example:
"Hi! 📝 Paste some text or upload a file (PDF, txt, markdown) and I'll summarize it for you."
Do NOT write long introductions.

Output style — adapt to input length, but always honor explicit user requests (e.g. "one sentence", "bullets only", "in German") over the defaults below:
- Short input (roughly under 200 words): 1-2 sentence TL;DR.
- Medium input (a few paragraphs): 2-3 sentence TL;DR.
- Long input (article, multi-page PDF): a short opening line, then 4-8 bullet points of the key takeaways.
- Multiple files: summarize each briefly, then add one combined takeaway.

Follow-up questions: after you have summarized something, you may answer follow-up questions that are GROUNDED in that content (e.g. "what does it say about X?", "list the dates mentioned"). If the user asks something unrelated to anything you've been given (e.g. "what's the weather?", "write me a poem"), politely steer back:
"I can summarize text or files, or answer questions about what we've already covered."

Edge cases:
- Empty input or just a greeting like "hi" with nothing to summarize → ask the user to paste text or upload a file.
- Very short input (under ~20 words) → just rephrase it concisely; do NOT invent additional detail.

Language: respond in the same language the user uses.

Keep your tone friendly and concise. Never apologize for the format — just deliver the summary.
"""
```

- [ ] **Step 2: Sanity-check the file**

Run: `python -c "from app.agent_repo.summarizer_agent.prompt import SUMMARIZER_AGENT_INSTRUCTION; print(len(SUMMARIZER_AGENT_INSTRUCTION))"`
Expected: A number greater than 1000 printed, and no `ImportError`.

- [ ] **Step 3: Commit**

```bash
git add app/agent_repo/summarizer_agent/prompt.py
git commit -m "feat(summarizer): add prompt with adaptive output + follow-up Q&A scope"
```

---

## Task 2: Define the LlmAgent and package exports

**Files:**
- Create: `app/agent_repo/summarizer_agent/agent.py`
- Create: `app/agent_repo/summarizer_agent/__init__.py`

- [ ] **Step 1: Create `agent.py`**

Write `app/agent_repo/summarizer_agent/agent.py` with this exact content (mirrors `greeting_agent/agent.py`):

```python
"""Summarizer agent – summarizes pasted text and uploaded files."""

from google.adk.agents import LlmAgent

from app import config
from app.agent_repo.summarizer_agent.prompt import SUMMARIZER_AGENT_INSTRUCTION


summarizer_agent = LlmAgent(
    name="summarizer_agent",
    model=config.DEFAULT_LLM_MODEL,
    description="Agent that summarizes text or uploaded files (PDF, txt, markdown).",
    instruction=SUMMARIZER_AGENT_INSTRUCTION,
)
```

- [ ] **Step 2: Create `__init__.py`**

Write `app/agent_repo/summarizer_agent/__init__.py` with this exact content (mirrors `greeting_agent/__init__.py`):

```python
from .agent import summarizer_agent

__all__ = ["summarizer_agent"]
```

- [ ] **Step 3: Sanity-check the package imports**

Run: `python -c "from app.agent_repo.summarizer_agent import summarizer_agent; print(summarizer_agent.name)"`
Expected: `summarizer_agent` printed, no traceback.

- [ ] **Step 4: Commit**

```bash
git add app/agent_repo/summarizer_agent/agent.py app/agent_repo/summarizer_agent/__init__.py
git commit -m "feat(summarizer): add LlmAgent definition + package init"
```

---

## Task 3: Register the agent so the UI and runner see it

Two small edits. After this task, the agent is discoverable end-to-end.

**Files:**
- Modify: `app/agent_repo/__init__.py` (add 1 import line)
- Modify: `app/agent_repo/agent_registry.py` (add 1 import + 1 entry in `AGENT_REGISTRY`)

- [ ] **Step 1: Add the import to `app/agent_repo/__init__.py`**

The file currently reads:

```python
"""Agent repository – central registry of all available agents."""

from .agent_registry import AGENT_REGISTRY, get_agent, list_agents
from .greeting_agent import greeting_agent

__all__ = [
	"greeting_agent",
	"summarizer_agent",
	"AGENT_REGISTRY",
	"get_agent",
	#"has_artifact_tools",
	#"has_memory_tools",
	#"has_rag_tools",
	"list_agents",
]
```

Add the import line below the existing `greeting_agent` import so it becomes:

```python
"""Agent repository – central registry of all available agents."""

from .agent_registry import AGENT_REGISTRY, get_agent, list_agents
from .greeting_agent import greeting_agent
from .summarizer_agent import summarizer_agent

__all__ = [
	"greeting_agent",
	"summarizer_agent",
	"AGENT_REGISTRY",
	"get_agent",
	#"has_artifact_tools",
	#"has_memory_tools",
	#"has_rag_tools",
	"list_agents",
]
```

(`__all__` already contains `"summarizer_agent"`; do not duplicate.)

- [ ] **Step 2: Add the import to `app/agent_repo/agent_registry.py`**

Below the existing `from app.agent_repo.greeting_agent import greeting_agent` line, add:

```python
from app.agent_repo.summarizer_agent import summarizer_agent
```

- [ ] **Step 3: Add the registry entry**

Inside `AGENT_REGISTRY`, after the existing `"greeting_agent"` entry, add:

```python
    "summarizer_agent": {
        "agent": summarizer_agent,
        "label": "Summarize",
        "description": "Summarizes text or uploaded files (PDF, txt).",
        "icon": "📝",
    },
```

The resulting `AGENT_REGISTRY` block should look like:

```python
AGENT_REGISTRY: dict[str, dict] = {
    "greeting_agent": {
        "agent": greeting_agent,
        "label": "Welcome",
        "description": "Welcomes students and helps them get started.",
        "icon": "👋",
    },
    "summarizer_agent": {
        "agent": summarizer_agent,
        "label": "Summarize",
        "description": "Summarizes text or uploaded files (PDF, txt).",
        "icon": "📝",
    },
}
```

- [ ] **Step 4: Verify registry resolves**

Run:
```bash
python -c "from app.agent_repo import get_agent, list_agents; print([a['id'] for a in list_agents()]); print(get_agent('summarizer_agent').name)"
```
Expected: `['greeting_agent', 'summarizer_agent']` and `summarizer_agent` printed, no traceback.

- [ ] **Step 5: Commit**

```bash
git add app/agent_repo/__init__.py app/agent_repo/agent_registry.py
git commit -m "feat(summarizer): register summarizer_agent in repo and registry"
```

---

## Task 4: Smoke-test the agent in the running app

The uvicorn process started earlier in this session uses `--reload` and watches the project directory, so the new files should trigger an automatic restart. This task is fully manual — no automated tests are added.

**Files:** None modified.

- [ ] **Step 1: Confirm uvicorn picked up the changes**

The server was started in the background (`uv run uvicorn agentic_ai_main:app --reload --port 8000`). Look at the log tail for a reloader notification. If running this plan in a fresh session and the server is NOT running, start it:

```bash
uv run uvicorn agentic_ai_main:app --reload --port 8000
```

Expected log lines after reload: `Started server process` and `Application startup complete`.

- [ ] **Step 2: Confirm the agent appears in the API listing**

Run: `curl -s http://127.0.0.1:8000/api/v1/agents | python -m json.tool`
Expected: JSON containing two agents — `greeting_agent` (`👋 Welcome`) and `summarizer_agent` (`📝 Summarize`). The `default` field stays `greeting_agent` (per `DEFAULT_AGENT_ID` in `.env`).

- [ ] **Step 3: Manual UI smoke tests**

Open `http://localhost:8000` in a browser and step through:

1. **Sidebar:** confirm "📝 Summarize" is listed.
2. **Select it:** the file-upload button (paperclip icon in `app/ui/chat.html`) becomes visible. (UI gate is in `app/ui/js/chat.js:91`.)
3. **Greeting:** with no prior message, the agent should send a one-line invitation to paste text or upload a file. Pass if response is ≤ 3 sentences.
4. **Short text test:** paste a single paragraph (e.g. the first paragraph of `README.md`). Pass if response is a 1–2 sentence TL;DR (not bullets).
5. **Long text test:** paste several paragraphs (e.g. the full README sections 1–3). Pass if response opens with a short line and then has 4–8 bullets.
6. **PDF test:** upload any multi-page PDF. Pass if response opens with a short line and then has 4–8 bullets summarizing the document.
7. **Follow-up test:** after the PDF test, ask "what does it say about <topic-from-the-pdf>?". Pass if answer is grounded in the document content (not made up).
8. **Off-topic guard:** ask "what's the weather in Zurich?". Pass if the agent declines and steers back to summarization. Fail if it answers the weather question.
9. **Language test:** paste a German paragraph. Pass if the response is in German.

- [ ] **Step 4: Fix-forward if any smoke test fails**

If a smoke test fails, the fix is almost certainly in `app/agent_repo/summarizer_agent/prompt.py` (the prompt is the entire behavior contract — there is no other code to debug). Common adjustments:
- Off-topic guard too weak → strengthen the "politely steer back" paragraph with an explicit example.
- Bullets appearing on short input → tighten the "Short input … 1-2 sentence TL;DR" line.
- Greeting too long → re-emphasize the 2-3 sentence cap.

After each fix, the reloader restarts the server automatically. Re-run the failing smoke test.

When fixed, commit:
```bash
git add app/agent_repo/summarizer_agent/prompt.py
git commit -m "fix(summarizer): tighten prompt after smoke-test failure"
```

(Skip this step entirely if all smoke tests passed first try.)

- [ ] **Step 5: Final verification**

Run: `git log --oneline -5`
Expected: the three feature commits from Tasks 1–3 (plus optional fix from Step 4) are visible on `main`.

---

## Out of scope (do NOT add to this plan)

These were explicit non-goals in the spec — leave them alone:
- A2A critic integration (`CRITIC_A2A_*` env vars, external critic process on port 8001).
- Wiring up `has_artifact_tools` detection in `agent_registry.py` (the artifact panel tab stays hidden).
- Pytest setup or any unit tests.
- Region migration of the auto-created Agent Engine (`us-central1` → `europe-north1`).
