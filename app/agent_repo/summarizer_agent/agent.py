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
