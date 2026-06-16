"""Nexus Conversation integration — thin shim over HA core openai_conversation.

Imports all platform setup, services, and migration logic from HA core.
Overrides async_setup_entry to inject base_url into the OpenAI client.
"""

import openai

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_BASE_URL, DOMAIN

# ---------------------------------------------------------------------------
# Imported from HA core — only what we actually use
# ---------------------------------------------------------------------------
from homeassistant.components.openai_conversation import (  # noqa: F401,E402
    async_migrate_integration,
    async_update_options,
    PLATFORMS,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Nexus Conversation."""
    await async_migrate_integration(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nexus Conversation from a config entry."""
    # Build OpenAI client with base_url support (patch over HA core)
    client = openai.AsyncOpenAI(
        base_url=entry.data.get(CONF_BASE_URL),
        api_key=entry.data[CONF_API_KEY],
        http_client=get_async_client(hass),
    )

    # Cache platform headers (mirrors HA core)
    _ = await hass.async_add_executor_job(client.platform_headers)

    try:
        await client.with_options(timeout=10.0).models.list()
    except openai.AuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err
    except openai.OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Nexus Conversation."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
