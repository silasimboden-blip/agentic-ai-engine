"""Summarizer agent – summarizes pasted text, uploaded files, and topics looked up via Google Search."""

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from app import config
from app.agent_repo.summarizer_agent.prompt import SUMMARIZER_AGENT_INSTRUCTION


summarizer_agent = LlmAgent(
    name="summarizer_agent",
    model=config.DEFAULT_LLM_MODEL,
    description="Summarizes documents and researches topics via Google Search.",
    instruction=SUMMARIZER_AGENT_INSTRUCTION,
    tools=[google_search],
)
