"""Greeting agent – welcomes students and helps them get started."""

from google.adk.agents import LlmAgent

from app import config
from app.agent_repo.greeting_agent.prompt import GREETING_AGENT_INSTRUCTION


greeting_agent = LlmAgent(
    name="greeting_agent",
    model=config.DEFAULT_LLM_MODEL,
    description="Agent that greets users and answers basic questions about itself.",
    instruction=GREETING_AGENT_INSTRUCTION,
)
