"""Nexus Conversation integration — thin shim over HA core openai_conversation.

Imports all platform setup, services, and migration logic from HA core.
Overrides async_setup_entry to inject base_url into the OpenAI client.
"""

import openai

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_loaded_integration

from .const import CONF_BASE_URL, DOMAIN

# ---------------------------------------------------------------------------
# Imported from HA core — only what we actually use
# ---------------------------------------------------------------------------
from homeassistant.components.openai_conversation import (  # noqa: F401,E402
    async_migrate_integration,
    async_update_options,
)

# Subset of HA core platforms — exclude STT/TTS (no platform modules in shim)
PLATFORMS = (Platform.AI_TASK, Platform.CONVERSATION)

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

    # Manually set up platforms using our integration's platform modules.
    # We cannot use async_forward_entry_setups because it loads platforms from
    # our component but then calls the CORE component's async_setup_entry,
    # which tries to find a platform named "nexus_conversation" within the
    # core domain (conversation or ai_task) — that doesn't exist.
    integration = await async_get_loaded_integration(hass, DOMAIN)
    registry = er.async_get(hass)

    for plat in PLATFORMS:
        platform_module = await integration.async_get_platform(plat)
        collected: list = []

        async def _collector(entities, **kwargs):  # noqa: ANN001,ANN003
            for e in entities if isinstance(entities, list) else list(entities):
                collected.append(e)

        await platform_module.async_setup_entry(hass, entry, _collector)

        # Register collected entities with the framework
        for entity in collected:
            reg_entry = registry.async_get_or_create(
                DOMAIN,
                plat,
                entity.unique_id,
                config_entry=entry,
            )
            entity.entity_id = reg_entry.entity_id
            entity.hass = hass
            entity.available = True

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Nexus Conversation."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
