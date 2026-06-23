"""The Nexus Conversation integration."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
import urllib.parse

import httpx
import openai
from openai.types.images_response import ImagesResponse
from openai.types.responses import (
    EasyInputMessageParam,
    Response,
    ResponseInputMessageContentListParam,
    ResponseInputParam,
    ResponseInputTextParam,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_PROMPT, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
    selector,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_FILENAMES,
    CONF_MAX_TOKENS,
    CONF_REASONING_EFFORT,
    CONF_REASONING_SUMMARY,
    CONF_STORE_RESPONSES,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_AI_TASK_NAME,
    DOMAIN,
    LOGGER,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_REASONING_SUMMARY,
    RECOMMENDED_STORE_RESPONSES,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)
from .entity import async_prepare_files_for_prompt

SERVICE_GENERATE_IMAGE = "generate_image"
SERVICE_GENERATE_CONTENT = "generate_content"

PLATFORMS = (Platform.CONVERSATION, Platform.AI_TASK)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type NexusConfigEntry = ConfigEntry[openai.AsyncClient]


def _get_image_model(entry: NexusConfigEntry) -> str:
    """Get the configured image model from the conversation subentry."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "conversation":
            return subentry.data.get(CONF_IMAGE_MODEL, RECOMMENDED_IMAGE_MODEL)
    return RECOMMENDED_IMAGE_MODEL


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Nexus Conversation."""
    # No migration needed — zero active users
    # await async_migrate_integration(hass)

    async def render_image(call: ServiceCall) -> ServiceResponse:
        """Generate an image with the configured model."""
        LOGGER.warning(
            "Action '%s.%s' is deprecated and will be removed in the 2026.9.0 release. "
            "Please use the 'ai_task.generate_image' action instead",
            DOMAIN,
            SERVICE_GENERATE_IMAGE,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_generate_image",
            breaks_in_ha_version="2026.9.0",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_generate_image",
        )

        entry_id = call.data["config_entry"]
        entry = hass.config_entries.async_get_entry(entry_id)

        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_config_entry",
                translation_placeholders={"config_entry": entry_id},
            )

        client: openai.AsyncClient = entry.runtime_data

        try:
            response: ImagesResponse = await client.images.generate(
                model=_get_image_model(entry),
                prompt=call.data[CONF_PROMPT],
                size=call.data["size"],
                quality=call.data["quality"],
                style=call.data["style"],
                response_format="url",
                n=1,
            )
        except openai.AuthenticationError as err:
            entry.async_start_reauth(hass)
            raise HomeAssistantError("Authentication error") from err
        except openai.OpenAIError as err:
            raise HomeAssistantError(f"Error generating image: {err}") from err

        if not response.data or not response.data[0].url:
            raise HomeAssistantError("No image returned")

        return response.data[0].model_dump(exclude={"b64_json"})

    async def send_prompt(call: ServiceCall) -> ServiceResponse:
        """Send a prompt to Nexus and return the response."""
        LOGGER.warning(
            "Action '%s.%s' is deprecated and will be removed in the 2026.9.0 release. "
            "Please use the 'ai_task.generate_data' action instead",
            DOMAIN,
            SERVICE_GENERATE_CONTENT,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_generate_content",
            breaks_in_ha_version="2026.9.0",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_generate_content",
        )

        entry_id = call.data["config_entry"]
        entry = hass.config_entries.async_get_entry(entry_id)

        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_config_entry",
                translation_placeholders={"config_entry": entry_id},
            )

        # Get first conversation subentry for options
        conversation_subentry = next(
            (
                sub
                for sub in entry.subentries.values()
                if sub.subentry_type == "conversation"
            ),
            None,
        )
        if not conversation_subentry:
            raise ServiceValidationError("No conversation configuration found")

        model: str = conversation_subentry.data.get(
            CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL
        )
        client: openai.AsyncClient = entry.runtime_data

        content: ResponseInputMessageContentListParam = [
            ResponseInputTextParam(type="input_text", text=call.data[CONF_PROMPT])
        ]

        if filenames := call.data.get(CONF_FILENAMES):
            for filename in filenames:
                if not hass.config.is_allowed_path(filename):
                    raise HomeAssistantError(
                        f"Cannot read `{filename}`, no access to path; "
                        "`allowlist_external_dirs` may need to be adjusted in "
                        "`configuration.yaml`"
                    )

            content.extend(
                await async_prepare_files_for_prompt(
                    hass, [(Path(filename), None) for filename in filenames]
                )
            )

        messages: ResponseInputParam = [
            EasyInputMessageParam(type="message", role="user", content=content)
        ]

        model_args = {
            "model": model,
            "input": messages,
            "max_output_tokens": conversation_subentry.data.get(
                CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS
            ),
            "top_p": conversation_subentry.data.get(CONF_TOP_P, RECOMMENDED_TOP_P),
            "temperature": conversation_subentry.data.get(
                CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
            ),
            "user": call.context.user_id,
            "store": conversation_subentry.data.get(
                CONF_STORE_RESPONSES, RECOMMENDED_STORE_RESPONSES
            ),
        }

        if model.startswith("o"):
            model_args["reasoning"] = {
                "effort": conversation_subentry.data.get(
                    CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT
                )
            }

        try:
            response: Response = await client.responses.create(**model_args)
        except openai.AuthenticationError as err:
            entry.async_start_reauth(hass)
            raise HomeAssistantError("Authentication error") from err
        except openai.OpenAIError as err:
            raise HomeAssistantError(f"Error generating content: {err}") from err
        except FileNotFoundError as err:
            raise HomeAssistantError(f"Error generating content: {err}") from err

        return {"text": response.output_text}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_CONTENT,
        send_prompt,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required(CONF_PROMPT): cv.string,
                vol.Optional(CONF_FILENAMES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_IMAGE,
        render_image,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required(CONF_PROMPT): cv.string,
                vol.Optional("size", default="1024x1024"): vol.In(
                    ("1024x1024", "1024x1792", "1792x1024")
                ),
                vol.Optional("quality", default="standard"): vol.In(("standard", "hd")),
                vol.Optional("style", default="vivid"): vol.In(("vivid", "natural")),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: NexusConfigEntry) -> bool:
    """Set up Nexus Conversation from a config entry."""
    # Build LLM client with base_url support
    base_url = entry.data.get(CONF_BASE_URL)
    if base_url == "":
        base_url = None
    client = openai.AsyncOpenAI(
        api_key=entry.data[CONF_API_KEY],
        base_url=base_url,
        http_client=get_async_client(hass),
    )

    # Cache current platform data which gets added to each request
    # (caching done by library)
    _ = await hass.async_add_executor_job(client.platform_headers)

    # Lightweight health check against /v1/health endpoint
    parsed = urllib.parse.urlparse(base_url)
    http_client = client._client
    try:
        resp = await http_client.get(
            f"{parsed.scheme}://{parsed.netloc}/v1/health",
            headers={"Authorization": f"Bearer {entry.data[CONF_API_KEY]}"},
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as err:
        if err.response.status_code == 401:
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady(err) from err
    except httpx.ConnectError as err:
        raise ConfigEntryNotReady(err) from err
    except httpx.TimeoutException as err:
        raise ConfigEntryNotReady(err) from err

    LOGGER.info("Connected to Nexus at %s", base_url)

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NexusConfigEntry) -> bool:
    """Unload Nexus Conversation."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: NexusConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


# No migration needed — zero active users
# async def async_migrate_integration(hass: HomeAssistant) -> None:
#     """Migrate integration entry structure."""
#     entries = sorted(
#         hass.config_entries.async_entries(DOMAIN),
#         key=lambda e: e.disabled_by is not None,
#     )
#     if not any(entry.version == 1 for entry in entries):
#         return
#
#     api_keys_entries: dict[str, tuple[NexusConfigEntry, bool]] = {}
#     entity_registry = er.async_get(hass)
#     device_registry = dr.async_get(hass)
#
#     for entry in entries:
#         use_existing = False
#         subentry = ConfigSubentry(
#             data=entry.options,
#             subentry_type="conversation",
#             title="Nexus",
#             unique_id=None,
#         )
#         if entry.data[CONF_API_KEY] not in api_keys_entries:
#             use_existing = True
#             all_disabled = all(
#                 e.disabled_by is not None
#                 for e in entries
#                 if e.data[CONF_API_KEY] == entry.data[CONF_API_KEY]
#             )
#             api_keys_entries[entry.data[CONF_API_KEY]] = (entry, all_disabled)
#
#         parent_entry, all_disabled = api_keys_entries[entry.data[CONF_API_KEY]]
#
#         hass.config_entries.async_add_subentry(parent_entry, subentry)
#         conversation_entity_id = entity_registry.async_get_entity_id(
#             "conversation",
#             DOMAIN,
#             entry.entry_id,
#         )
#         device = device_registry.async_get_device(
#             identifiers={(DOMAIN, entry.entry_id)}
#         )
#
#         if conversation_entity_id is not None:
#             conversation_entity_entry = entity_registry.entities[conversation_entity_id]
#             entity_disabled_by = conversation_entity_entry.disabled_by
#             if (
#                 entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
#                 and not all_disabled
#             ):
#                 entity_disabled_by = (
#                     er.RegistryEntryDisabler.DEVICE
#                     if device
#                     else er.RegistryEntryDisabler.USER
#                 )
#             entity_registry.async_update_entity(
#                 conversation_entity_id,
#                 config_entry_id=parent_entry.entry_id,
#                 config_subentry_id=subentry.subentry_id,
#                 disabled_by=entity_disabled_by,
#                 new_unique_id=subentry.subentry_id,
#             )
#
#         if device is not None:
#             device_disabled_by = device.disabled_by
#             if (
#                 device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
#                 and not all_disabled
#             ):
#                 device_disabled_by = dr.DeviceEntryDisabler.USER
#             device_registry.async_update_device(
#                 device.id,
#                 disabled_by=device_disabled_by,
#                 new_identifiers={(DOMAIN, subentry.subentry_id)},
#                 add_config_subentry_id=subentry.subentry_id,
#                 add_config_entry_id=parent_entry.entry_id,
#             )
#             if parent_entry.entry_id != entry.entry_id:
#                 device_registry.async_update_device(
#                     device.id,
#                     remove_config_entry_id=entry.entry_id,
#                 )
#             else:
#                 device_registry.async_update_device(
#                     device.id,
#                     remove_config_entry_id=entry.entry_id,
#                     remove_config_subentry_id=None,
#                 )
#
#         if not use_existing:
#             await hass.config_entries.async_remove(entry.entry_id)
#         else:
#             _add_ai_task_subentry(hass, entry)
#             hass.config_entries.async_update_entry(
#                 entry,
#                 title="Nexus",
#                 options={},
#                 version=2,
#                 minor_version=7,
#             )
#
#
# async def async_migrate_entry(hass: HomeAssistant, entry: NexusConfigEntry) -> bool:
#     """Migrate entry."""
#     LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)
#
#     if entry.version == 2 and entry.minor_version == 1:
#         device_registry = dr.async_get(hass)
#         for device in dr.async_entries_for_config_entry(
#             device_registry, entry.entry_id
#         ):
#             device_registry.async_update_device(
#                 device.id,
#                 remove_config_entry_id=entry.entry_id,
#                 remove_config_subentry_id=None,
#             )
#         hass.config_entries.async_update_entry(entry, minor_version=2)
#
#     if entry.version == 2 and entry.minor_version == 2:
#         _add_ai_task_subentry(hass, entry)
#         hass.config_entries.async_update_entry(entry, minor_version=3)
#
#     if entry.version == 2 and entry.minor_version == 3:
#         device_registry = dr.async_get(hass)
#         entity_registry = er.async_get(hass)
#         devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
#         entity_entries = er.async_entries_for_config_entry(
#             entity_registry, entry.entry_id
#         )
#         if entry.disabled_by is None:
#             for device in devices:
#                 if device.disabled_by is not dr.DeviceEntryDisabler.CONFIG_ENTRY:
#                     continue
#                 device_registry.async_update_device(
#                     device.id,
#                     disabled_by=dr.DeviceEntryDisabler.USER,
#                 )
#             for entity in entity_entries:
#                 if entity.disabled_by is not er.RegistryEntryDisabler.CONFIG_ENTRY:
#                     continue
#                 entity_registry.async_update_entity(
#                     entity.entity_id,
#                     disabled_by=er.RegistryEntryDisabler.DEVICE,
#                 )
#         hass.config_entries.async_update_entry(entry, minor_version=4)
#
#     if entry.version == 2 and entry.minor_version == 4:
#         hass.config_entries.async_update_entry(entry, minor_version=5)
#
#     if entry.version == 2 and entry.minor_version == 5:
#         hass.config_entries.async_update_entry(entry, minor_version=6)
#
#     if entry.version == 2 and entry.minor_version == 6:
#         for subentry in entry.subentries.values():
#             if subentry.subentry_type in ("conversation", "ai_task_data"):
#                 data = dict(subentry.data)
#                 updated = False
#                 if data.get(CONF_REASONING_SUMMARY) == "short":
#                     data[CONF_REASONING_SUMMARY] = "concise"
#                     updated = True
#                 if data.get(CONF_REASONING_SUMMARY) == "concise" and not data.get(
#                     CONF_CHAT_MODEL, ""
#                 ).startswith("gpt-5"):
#                     data[CONF_REASONING_SUMMARY] = RECOMMENDED_REASONING_SUMMARY
#                     updated = True
#                 if updated:
#                     hass.config_entries.async_update_subentry(
#                         entry, subentry, data=data
#                     )
#         hass.config_entries.async_update_entry(entry, minor_version=7)
#
#     LOGGER.debug(
#         "Migration to version %s:%s successful", entry.version, entry.minor_version
#     )
#
#     return True


def _add_ai_task_subentry(hass: HomeAssistant, entry: NexusConfigEntry) -> None:
    """Add AI Task subentry to the config entry."""
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(RECOMMENDED_AI_TASK_OPTIONS),
            subentry_type="ai_task_data",
            title=DEFAULT_AI_TASK_NAME,
            unique_id=None,
        ),
    )
