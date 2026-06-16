"""Config flow for Nexus Conversation — extends HA core with base_url field."""

import logging
from typing import Any

import openai
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_BASE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Re-export subentry flow handlers from HA core
# ---------------------------------------------------------------------------
from homeassistant.components.openai_conversation.config_flow import (  # noqa: F401,E402
    OpenAISubentryFlowHandler,
    OpenAISubentrySTTFlowHandler,
    OpenAISubentryTTSFlowHandler,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default="https://api.openai.com/v1"): str,
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    client = openai.AsyncOpenAI(
        base_url=data.get(CONF_BASE_URL),
        api_key=data[CONF_API_KEY],
        http_client=get_async_client(hass),
    )
    await client.models.list(timeout=10.0)
    return data


class NexusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nexus Conversation."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                await validate_input(self.hass, user_input)
            except openai.APIConnectionError:
                errors["base"] = "cannot_connect"
            except openai.AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )
                return self.async_create_entry(title="Nexus", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "instructions_url": "https://platform.openai.com/api-keys",
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA
            )

        return await self.async_step_user(user_input)

    @classmethod
    def async_get_supported_subentry_types(cls, config_entry):  # type: ignore[no-untyped-def]
        """Return subentries supported by this integration."""
        return {
            "conversation": OpenAISubentryFlowHandler,
            "ai_task_data": OpenAISubentryFlowHandler,
            "stt": OpenAISubentrySTTFlowHandler,
            "tts": OpenAISubentryTTSFlowHandler,
        }
