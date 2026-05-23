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
