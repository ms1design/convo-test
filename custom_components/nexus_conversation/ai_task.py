"""Nexus AI Task platform — re-exports HA core."""

from homeassistant.components.openai_conversation.ai_task import (  # noqa: F401,F403
    OpenAITaskEntity,
    async_setup_entry,
)
