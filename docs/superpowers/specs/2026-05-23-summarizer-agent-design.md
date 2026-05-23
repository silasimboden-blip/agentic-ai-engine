# Summarizer Agent — Design

**Date:** 2026-05-23
**Status:** Approved, ready for implementation plan

## Goal

Add a `summarizer_agent` that summarizes text the user pastes into the chat or uploads as a file (PDF, txt, markdown, JSON, etc.). The agent mirrors the existing `greeting_agent` pattern so the lecture can demonstrate adding a second agent with minimal new code.

## Context

The project already has scaffolding that anticipates this agent:

- `app/agent_repo/__init__.py` lists `"summarizer_agent"` in `__all__` (with no actual import yet).
- `app/ui/js/chat.js:90-91` hides the file-upload button unless `agentId === "summarizer_agent"`.
- `app/handlers/ws_connection_handler.py:_handle_message` already accepts a `files` array, base64-decodes it, and passes it to `AgentTeamHandler.stream_agent_response(text, files=...)`.
- `AgentTeamHandler._build_user_content` already converts uploaded files into ADK `Part`s: text-like MIMEs are inlined as text; binary (PDF, images) is sent as `inline_data`, which Gemini 2.5 understands natively.
- The artifact service (`GcsArtifactService` over the configured GCS bucket) is initialized and wired into the `Runner` for every agent.

Consequence: **no new infrastructure is required.** The work is creating the agent package and registering it.

## Non-goals

- No A2A critic integration (the `CRITIC_A2A_*` env vars and external critic agent are deferred to a separate task).
- No tools attached to the agent — Gemini's native multimodal input handles file content.
- No unit tests — the project has no `tests/` directory yet; verification is manual.
- No changes to `agent_registry.py`'s commented-out `has_artifact_tools` / `has_memory_tools` / `has_rag_tools` detection helpers. The artifact-panel tab will stay hidden, which is acceptable for this iteration.

## File layout

```
app/agent_repo/summarizer_agent/
  __init__.py          # re-exports summarizer_agent
  agent.py             # LlmAgent definition
  prompt.py            # SUMMARIZER_AGENT_INSTRUCTION constant
```

Mirrors `app/agent_repo/greeting_agent/` exactly.

## Components

### `agent.py`

```python
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

Identical shape to `greeting_agent`, no `tools=`.

### `prompt.py` — behavior contract

The prompt encodes:

- **Role:** friendly summarization assistant.
- **Initial greeting** (no input yet): one short sentence inviting the user to paste text or upload a file. Same length discipline as the greeting agent (2–3 sentences max). Example: *"Hi! 📝 Paste some text or upload a file (PDF, txt, markdown) and I'll summarize it for you."*
- **Adaptive output length:**
  - Short input (≲ 200 words) → 1–2 sentence TL;DR.
  - Medium input (a few paragraphs) → 2–3 sentence TL;DR.
  - Long input (article / multi-page PDF) → short opening line + 4–8 bullet points of key takeaways.
- **User override beats default:** explicit requests like "one sentence", "bullets only", "in German" always win.
- **Follow-up Q&A (loose scope):** after summarizing, answer questions grounded in the previously summarized content. If the user asks something unrelated to what's been summarized, politely steer back: *"I can summarize text or files, or answer questions about what we've already covered."*
- **Language:** respond in the user's language (same convention as `greeting_agent`).
- **Files:** "if a file was attached, summarize its content" — no tool-call instructions.
- **Edge cases:**
  - Empty / greeting-only input → ask for text or a file.
  - Very short input (< ~20 words) → rephrase concisely; do not fabricate detail.
  - Multiple files → summarize each briefly, then a combined takeaway.

### `__init__.py`

```python
from .agent import summarizer_agent

__all__ = ["summarizer_agent"]
```

## Registration changes

### `app/agent_repo/agent_registry.py`

Add the import:

```python
from app.agent_repo.summarizer_agent import summarizer_agent
```

Add an entry to `AGENT_REGISTRY`:

```python
"summarizer_agent": {
    "agent": summarizer_agent,
    "label": "Summarize",
    "description": "Summarizes text or uploaded files (PDF, txt).",
    "icon": "📝",
},
```

### `app/agent_repo/__init__.py`

Add the real import next to `greeting_agent`:

```python
from .summarizer_agent import summarizer_agent
```

(The `__all__` already contains `"summarizer_agent"`.)

## Data flow

1. User selects "📝 Summarize" in the sidebar → UI sends `{"action": "select_agent", "agent_id": "summarizer_agent"}` over the existing WebSocket.
2. UI reveals the upload button (already gated on this exact agent ID).
3. User pastes text and/or attaches files; UI sends `{"action": "message", "message": "...", "files": [{"name", "mime", "data": <base64>}]}`.
4. `WebSocketConnectionHandler._handle_message` base64-decodes file data and calls `AgentTeamHandler.stream_agent_response(text, files=...)`.
5. `_build_user_content` builds a `Content` with text parts for text-like MIMEs and `inline_data` parts for binaries (PDFs).
6. `Runner.run_async` streams events; the agent (Gemini 2.5 Flash) ingests the full multimodal `Content` and produces the summary per the prompt.
7. Streamed `partial` / `final` events flow back to the browser unchanged.

No code on this path needs to change.

## Error handling

Inherited from existing infrastructure:

- Malformed file attachments are skipped with a warning log in `_handle_message`.
- Empty input is rejected at the WS layer (`"Empty message."`).
- Runner exceptions surface as `{"type": "error", "author": "system"}` events.
- Prompt handles the "no usable input received" case by asking the user for text or a file.

## Verification (manual)

1. Uvicorn `--reload` should pick up the new files automatically; check the log for restart.
2. Open `http://localhost:8000`, confirm "📝 Summarize" appears in the sidebar.
3. Select it → file-upload button becomes visible.
4. Smoke tests:
   - **Greeting:** fresh select → one-line invitation.
   - **Short text:** paste a paragraph → 1–2 sentence TL;DR.
   - **Long PDF:** upload a multi-page PDF → short intro + bullet points.
   - **Follow-up:** ask "what did it say about X" → content-grounded answer.
   - **Off-topic:** ask "what's the weather" → polite redirect back to summarization scope.

## Risks / open questions

- **GCS region:** the bucket is in `europe-north1` but the auto-created Agent Engine landed in `us-central1`. This does not affect the summarizer agent itself (no agent-engine call path here), but is a latent latency / data-residency concern for the project overall. Out of scope for this work.
- **PDF size limits:** Gemini 2.5 Flash has a per-request token limit; very large PDFs may be rejected by the model. The prompt does not preemptively warn — failures will surface as model errors. Acceptable for the lecture demo.
- **Artifact panel stays hidden** until `has_artifact_tools` detection in `agent_registry.py` is restored. Not a blocker; the upload button is enough for the summarizer.
