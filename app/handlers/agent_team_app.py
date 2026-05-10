"""App factory for agent management and orchestration."""

from google.adk.agents import LlmAgent
from google.adk.apps.app import App
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin


def create_agent_app(agent: LlmAgent) -> App:
    """Create an ADK App wrapping the given agent."""
    return App(
        name=f"{agent.name}_app",
        root_agent=agent,
        plugins=[SaveFilesAsArtifactsPlugin()],
    )
