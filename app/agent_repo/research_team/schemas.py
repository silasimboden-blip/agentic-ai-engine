"""Pydantic schemas for research_team session-state values."""

from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    original_question: str
    sub_question_a: str
    sub_question_b: str


class Source(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""


class ResearchOutput(BaseModel):
    findings: str
    sources: list[Source] = Field(default_factory=list)


class Critique(BaseModel):
    gaps: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    weak_sources: list[str] = Field(default_factory=list)
