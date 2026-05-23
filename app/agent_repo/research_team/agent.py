"""Deep research agent team — Sequential pipeline with parallel researchers."""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools.google_search_agent_tool import (
    GoogleSearchAgentTool,
    create_google_search_agent,
)
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from app import config
from app.agent_repo.research_team.prompt import (
    COORDINATOR_INSTRUCTION,
    CRITIC_INSTRUCTION,
    RESEARCHER_A_INSTRUCTION,
    RESEARCHER_B_INSTRUCTION,
    WRITER_INSTRUCTION,
)
from app.agent_repo.research_team.schemas import Critique, ResearchPlan


def _researcher_tools() -> list:
    """Build the tool list shared by both researchers.

    Each researcher gets its own freshly-wrapped Google search sub-agent
    (the wrapping is required because Gemini's built-in google_search cannot
    coexist with other tools on the same LlmAgent). The MCP toolset is added
    only when MCP_FETCH_URL is configured.
    """
    tools: list = [
        GoogleSearchAgentTool(
            create_google_search_agent(model=config.DEFAULT_LLM_MODEL)
        ),
    ]
    if config.MCP_FETCH_URL:
        tools.append(
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=config.MCP_FETCH_URL,
                ),
            )
        )
    return tools


_coordinator = LlmAgent(
    name="research_coordinator",
    model=config.DEFAULT_LLM_MODEL,
    description="Decomposes the user's question into two sub-questions.",
    instruction=COORDINATOR_INSTRUCTION,
    output_schema=ResearchPlan,
    output_key="research_plan",
)

_researcher_a = LlmAgent(
    name="researcher_a",
    model=config.DEFAULT_LLM_MODEL,
    description="Researches sub_question_a using google_search and fetch_url.",
    instruction=RESEARCHER_A_INSTRUCTION,
    tools=_researcher_tools(),
    output_key="research_a",
)

_researcher_b = LlmAgent(
    name="researcher_b",
    model=config.DEFAULT_LLM_MODEL,
    description="Researches sub_question_b using google_search and fetch_url.",
    instruction=RESEARCHER_B_INSTRUCTION,
    tools=_researcher_tools(),
    output_key="research_b",
)

_researchers = ParallelAgent(
    name="researchers",
    description="Two researchers running in parallel on the two sub-questions.",
    sub_agents=[_researcher_a, _researcher_b],
)

_critic = LlmAgent(
    name="research_critic",
    model=config.DEFAULT_LLM_MODEL,
    description="Reviews research outputs for gaps, contradictions, and weak sources.",
    instruction=CRITIC_INSTRUCTION,
    output_schema=Critique,
    output_key="critique",
)

_writer = LlmAgent(
    name="research_writer",
    model=config.DEFAULT_LLM_MODEL,
    description="Synthesizes the final cited brief.",
    instruction=WRITER_INSTRUCTION,
)

research_team = SequentialAgent(
    name="research_team",
    description="Multi-agent team that researches a question and writes a cited brief.",
    sub_agents=[_coordinator, _researchers, _critic, _writer],
)
