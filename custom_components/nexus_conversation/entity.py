"""Nexus Conversation entity — re-exports HA core."""

from homeassistant.components.openai_conversation.entity import (  # noqa: F401,F403
    OpenAIBaseLLMEntity,
    async_prepare_files_for_prompt,
)
