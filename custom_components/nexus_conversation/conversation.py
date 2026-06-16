"""Nexus Conversation platform — re-exports HA core."""

from homeassistant.components.openai_conversation.conversation import (  # noqa: F401,F403
    OpenAIConversationEntity,
    async_setup_entry,
)
