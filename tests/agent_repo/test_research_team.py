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
