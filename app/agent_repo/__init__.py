"""Agent repository – central registry of all available agents."""

from .agent_registry import AGENT_REGISTRY, get_agent, list_agents
from .greeting_agent import greeting_agent
from .summarizer_agent import summarizer_agent

__all__ = [
	"greeting_agent",
	"summarizer_agent",
	"AGENT_REGISTRY",
	"get_agent",
	#"has_artifact_tools",
	#"has_memory_tools",
	#"has_rag_tools",
	"list_agents",
]
