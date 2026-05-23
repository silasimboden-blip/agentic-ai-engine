"""Tests for the deep research agent team."""

import pytest
from pydantic import ValidationError

from app.agent_repo.research_team.schemas import (
    Critique,
    ResearchOutput,
    ResearchPlan,
    Source,
)


# ---------------------------------------------------------------------------
# Section 1: schema tests
# ---------------------------------------------------------------------------

def test_research_plan_accepts_three_fields():
    plan = ResearchPlan(
        original_question="What is RAG?",
        sub_question_a="Define RAG.",
        sub_question_b="What is RAG used for?",
    )
    assert plan.original_question == "What is RAG?"
    assert plan.sub_question_a == "Define RAG."
    assert plan.sub_question_b == "What is RAG used for?"


def test_research_plan_requires_all_fields():
    with pytest.raises(ValidationError):
        ResearchPlan(original_question="x", sub_question_a="y")  # missing sub_question_b


def test_source_defaults_to_empty_title_and_snippet():
    s = Source(url="https://example.com")
    assert s.url == "https://example.com"
    assert s.title == ""
    assert s.snippet == ""


def test_source_requires_url():
    with pytest.raises(ValidationError):
        Source()  # url is required


def test_research_output_defaults_to_empty_sources():
    r = ResearchOutput(findings="something")
    assert r.findings == "something"
    assert r.sources == []


def test_research_output_accepts_source_list():
    r = ResearchOutput(
        findings="some finding",
        sources=[Source(url="https://example.com", title="ex", snippet="s")],
    )
    assert len(r.sources) == 1
    assert r.sources[0].title == "ex"


def test_critique_all_three_lists_default_to_empty():
    c = Critique()
    assert c.gaps == []
    assert c.contradictions == []
    assert c.weak_sources == []


# ---------------------------------------------------------------------------
# Section 2: prompt sanity tests
# ---------------------------------------------------------------------------

from app.agent_repo.research_team.prompt import (
    COORDINATOR_INSTRUCTION,
    CRITIC_INSTRUCTION,
    RESEARCHER_A_INSTRUCTION,
    RESEARCHER_B_INSTRUCTION,
    WRITER_INSTRUCTION,
)


def test_coordinator_prompt_requires_json_and_three_fields():
    text = COORDINATOR_INSTRUCTION.lower()
    assert "json" in text
    for field in ("original_question", "sub_question_a", "sub_question_b"):
        assert field in COORDINATOR_INSTRUCTION


def test_researcher_a_references_plan_and_sub_question_a():
    assert "{research_plan}" in RESEARCHER_A_INSTRUCTION
    assert "sub_question_a" in RESEARCHER_A_INSTRUCTION
    assert "sub_question_b" in RESEARCHER_A_INSTRUCTION  # told to ignore it


def test_researcher_b_references_plan_and_sub_question_b():
    assert "{research_plan}" in RESEARCHER_B_INSTRUCTION
    assert "sub_question_b" in RESEARCHER_B_INSTRUCTION
    assert "sub_question_a" in RESEARCHER_B_INSTRUCTION  # told to ignore it


def test_critic_references_all_three_upstream_keys():
    for key in ("{research_plan}", "{research_a}", "{research_b}"):
        assert key in CRITIC_INSTRUCTION
    for field in ("gaps", "contradictions", "weak_sources"):
        assert field in CRITIC_INSTRUCTION


def test_writer_references_all_four_keys_and_format():
    for key in ("{research_plan}", "{research_a}", "{research_b}", "{critique}"):
        assert key in WRITER_INSTRUCTION
    assert "## Sources" in WRITER_INSTRUCTION


# ---------------------------------------------------------------------------
# Section 3: agent wiring tests
# ---------------------------------------------------------------------------

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from app.agent_repo.research_team import agent as agent_module
from app.agent_repo.research_team import research_team


def test_research_team_is_sequential_with_four_stages():
    assert isinstance(research_team, SequentialAgent)
    assert research_team.name == "research_team"
    assert len(research_team.sub_agents) == 4


def test_research_team_stage_types_and_names():
    coord, researchers, critic, writer = research_team.sub_agents
    assert isinstance(coord, LlmAgent) and coord.name == "research_coordinator"
    assert isinstance(researchers, ParallelAgent) and researchers.name == "researchers"
    assert len(researchers.sub_agents) == 2
    a, b = researchers.sub_agents
    assert isinstance(a, LlmAgent) and a.name == "researcher_a"
    assert isinstance(b, LlmAgent) and b.name == "researcher_b"
    assert isinstance(critic, LlmAgent) and critic.name == "research_critic"
    assert isinstance(writer, LlmAgent) and writer.name == "research_writer"


def test_coordinator_and_critic_have_output_keys():
    coord = research_team.sub_agents[0]
    critic = research_team.sub_agents[2]
    assert coord.output_key == "research_plan"
    assert critic.output_key == "critique"


def test_researchers_have_output_keys():
    researchers = research_team.sub_agents[1]
    a, b = researchers.sub_agents
    assert a.output_key == "research_a"
    assert b.output_key == "research_b"


def test_writer_has_no_output_key():
    writer = research_team.sub_agents[3]
    assert getattr(writer, "output_key", None) in (None, "")


def test_researcher_tools_search_only_when_mcp_disabled(monkeypatch):
    monkeypatch.setattr(agent_module.config, "MCP_FETCH_URL", "")
    tools = agent_module._researcher_tools()
    assert len(tools) == 1


def test_researcher_tools_include_mcp_when_configured(monkeypatch):
    monkeypatch.setattr(agent_module.config, "MCP_FETCH_URL", "http://localhost:8765/mcp")
    tools = agent_module._researcher_tools()
    assert len(tools) == 2


# ---------------------------------------------------------------------------
# Section 4: registry tests
# ---------------------------------------------------------------------------

from app.agent_repo.agent_registry import AGENT_REGISTRY, get_agent, list_agents


def test_research_team_registered():
    assert "research_team" in AGENT_REGISTRY


def test_get_agent_returns_research_team_instance():
    assert get_agent("research_team") is research_team


def test_list_agents_includes_research_team_metadata():
    metas = list_agents()
    entry = next((m for m in metas if m["id"] == "research_team"), None)
    assert entry is not None
    assert entry["label"] == "Research"
    assert entry["icon"] == "🔍"
    assert "research" in entry["description"].lower()


# ---------------------------------------------------------------------------
# Section 5: integration smoke (requires GCP creds + optional MCP server)
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_research_team_produces_cited_brief():
    """Drive the full team on a known-good question and validate output shape."""
    from google.adk.runners import InMemoryRunner
    from google.genai.types import Content, Part

    runner = InMemoryRunner(agent=research_team, app_name="test_research_team")
    session = await runner.session_service.create_session(
        app_name="test_research_team",
        user_id="test_user",
    )
    user_msg = Content(
        role="user",
        parts=[Part.from_text(text="What is retrieval-augmented generation?")],
    )

    final = ""
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=user_msg,
    ):
        if (
            event.is_final_response()
            and getattr(event, "author", None) == "research_writer"
            and event.content
            and event.content.parts
        ):
            for part in event.content.parts:
                if getattr(part, "text", None):
                    final += part.text

    assert "## Sources" in final
    # at least three bullets — markdown dash bullets at column 0
    bullet_count = sum(1 for line in final.splitlines() if line.startswith("- "))
    assert bullet_count >= 3, f"expected >=3 bullets, got {bullet_count}; output:\n{final}"
