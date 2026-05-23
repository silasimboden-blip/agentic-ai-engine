"""Summarizer agent – summarizes pasted text, uploaded files, and topics looked up via Google Search."""

from google.adk.agents import LlmAgent
from google.adk.tools.google_search_agent_tool import (
    GoogleSearchAgentTool,
    create_google_search_agent,
)

from app import config
from app.agent_repo.summarizer_agent.prompt import SUMMARIZER_AGENT_INSTRUCTION


# google_search is a Gemini built-in tool that the ADK does not allow to coexist
# with other tools on the same LlmAgent. Wrapping it in an AgentTool keeps that
# constraint isolated to its own sub-agent so more tools can be added here later.
_search_sub_agent = create_google_search_agent(model=config.DEFAULT_LLM_MODEL)
_google_search_tool = GoogleSearchAgentTool(_search_sub_agent)


summarizer_agent = LlmAgent(
    name="summarizer_agent",
    model=config.DEFAULT_LLM_MODEL,
    description="Summarizes documents and researches topics via Google Search.",
    instruction=SUMMARIZER_AGENT_INSTRUCTION,
    tools=[_google_search_tool],
)
