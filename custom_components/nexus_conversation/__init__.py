"""The Nexus Conversation integration."""

from __future__ import annotations

import os
import re
import urllib.parse
from functools import partial
from pathlib import Path
from types import MappingProxyType

import httpx
import openai
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
)
from homeassistant.helpers import (
    issue_registry as ir,
)
from homeassistant.helpers import (
    selector,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.typing import ConfigType
from openai.types.responses import (
    EasyInputMessageParam,
    Response,
    ResponseInputMessageContentListParam,
    ResponseInputParam,
    ResponseInputTextParam,
)

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
    DASHBOARD_PATH,
    DOMAIN,
    LOGGER,
    PANEL_ICON,
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

SERVICE_GENERATE_CONTENT = "generate_content"

PLATFORMS = (Platform.CONVERSATION, Platform.AI_TASK)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type NexusConfigEntry = ConfigEntry[openai.AsyncClient]


# ---------------------------------------------------------------------------
# Panel helpers
# ---------------------------------------------------------------------------

_PANEL_TRACKER: dict[str, str] = {}


def _derive_dashboard_url(base_url: str) -> str:
    """Derive the Nexus dashboard URL from the API base_url."""
    try:
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            return base_url
        return f"{parsed.scheme}://{parsed.netloc}"
    except (ValueError, AttributeError):
        return base_url


def _sanitize_for_js(value: str) -> str:
    """Escape a string for safe insertion into a JavaScript string literal."""
    return (
        value
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _render_panel_js(template_src: str, dashboard_url: str, target: str) -> None:
    """Render and write the panel JS file (runs in executor)."""
    os.makedirs(os.path.dirname(target), exist_ok=True)
    rendered = template_src.replace("__NEXUS_DASHBOARD_URL__", _sanitize_for_js(dashboard_url))
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(rendered)


def _cleanup_entry_www(entry_id: str) -> None:
    """Remove per-entry www directory (runs in executor)."""
    base_www = os.path.join(os.path.dirname(__file__), "www", entry_id)
    if os.path.isdir(base_www):
        import shutil
        shutil.rmtree(base_www, ignore_errors=True)


async def _register_panel_for_entry(
    hass: HomeAssistant, entry: NexusConfigEntry
) -> None:
    """Register a panel_custom panel for the given config entry."""
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.components.panel_custom import async_register_panel

    base_url = entry.data.get(CONF_BASE_URL, "")
    dashboard_url = _derive_dashboard_url(base_url)
    panel_slug = f"{entry.entry_id[:8]}"
    panel_id = f"{DOMAIN}_{entry.entry_id}"
    frontend_url_path = f"{DASHBOARD_PATH}_{panel_slug}"
    webcomponent_name = f"nexus-dashboard-{panel_slug}"

    base_www = os.path.join(os.path.dirname(__file__), "www")
    entry_www = os.path.join(base_www, entry.entry_id)
    target_path = os.path.join(entry_www, "panel.js")

    # Read template in executor
    template_path = os.path.join(base_www, "panel.tmpl.js")
    try:
        template_src = await hass.async_add_executor_job(Path(template_path).read_text)
    except OSError:
        template_src = "// panel.js template missing\nconst dashboardUrl = '';\n"

    # Render and write panel JS in executor
    await hass.async_add_executor_job(
        _render_panel_js, template_src, dashboard_url, target_path
    )

    try:
        # Register static file serving
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path=f"/{frontend_url_path}",
                path=entry_www,
                cache_headers=False,
            ),
        ])

        # Register the panel
        async_register_panel(
            hass,
            frontend_url_path,
            webcomponent_name,
            sidebar_title=entry.title,
            sidebar_icon=PANEL_ICON,
            module_url=f"/{frontend_url_path}/panel.js",
            require_admin=False,
            config={
                "entry_id": entry.entry_id,
                "dashboard_url": dashboard_url,
            },
        )

        _PANEL_TRACKER[panel_id] = frontend_url_path
        LOGGER.info(
            "Registered Nexus dashboard panel [%s] (%s) -> %s",
            panel_slug,
            entry.title,
            dashboard_url,
        )
    except Exception:
        LOGGER.exception("Failed to register dashboard panel for %s", entry.entry_id)


async def _unregister_panel_for_entry_by_id(
    hass: HomeAssistant, entry_id: str
) -> None:
    """Unregister a panel and clean up files by entry_id string."""
    from homeassistant.components.panel_custom import async_unregister_panel

    panel_id = f"{DOMAIN}_{entry_id}"
    frontend_url_path = _PANEL_TRACKER.pop(panel_id, None)

    if frontend_url_path:
        try:
            await hass.async_add_executor_job(
                async_unregister_panel, hass, frontend_url_path
            )
        except Exception:
            LOGGER.exception("Failed to unregister panel %s", panel_id)

    # Clean up orphaned www directory
    await hass.async_add_executor_job(_cleanup_entry_www, entry_id)


async def _unregister_panel_for_entry(hass: HomeAssistant, entry: NexusConfigEntry) -> None:
    """Unregister a panel_custom panel for the given config entry."""
    await _unregister_panel_for_entry_by_id(hass, entry.entry_id)


async def _on_config_entry_changed(
    hass: HomeAssistant, change, entry: ConfigEntry
) -> None:
    """Reactive to config entry updates (including renames)."""
    from homeassistant.config_entries import ConfigEntryChange

    if change is not ConfigEntryChange.UPDATED:
        return
    if entry.domain != DOMAIN:
        return

    panel_id = f"{DOMAIN}_{entry.entry_id}"
    if panel_id not in _PANEL_TRACKER:
        return

    old_title = entry.title
    # Re-register with updated title
    await _register_panel_for_entry(hass, entry)
    LOGGER.info("Updated dashboard panel title for %s: %s", entry.entry_id, old_title)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def _check_health(
    http_client: httpx.AsyncClient, base_url: str
) -> None:
    """Lightweight health check against /v1/health endpoint."""
    parsed = urllib.parse.urlparse(base_url)
    try:
        resp = await http_client.get(
            f"{parsed.scheme}://{parsed.netloc}/v1/health",
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as err:
        raise _HealthCheckError(err.response.status_code, str(err)) from err
    except (httpx.ConnectError, httpx.TimeoutException) as err:
        raise _HealthCheckError(0, str(err)) from err


class _HealthCheckError(Exception):
    """Raised when health check fails."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Async setup
# ---------------------------------------------------------------------------

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Nexus Conversation."""

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
            "user": getattr(call.context, "user_id", None),
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

    # Warm up platform headers cache
    await hass.async_add_executor_job(client.platform_headers)

    # Health check
    http_client = client._client
    try:
        await _check_health(http_client, base_url)
    except _HealthCheckError as err:
        if err.status_code == 401:
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady(err) from err

    LOGGER.info("Connected to Nexus at %s", base_url)

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register dashboard panel
    await _register_panel_for_entry(hass, entry)

    # Listen for config entry updates (covers renames)
    unsub = async_dispatcher_connect(
        hass,
        "config_entry_updated",
        lambda chg, ent: _on_config_entry_changed(hass, chg, ent),
    )
    entry.async_on_unload(unsub)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NexusConfigEntry) -> bool:
    """Unload Nexus Conversation."""
    await _unregister_panel_for_entry(hass, entry)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: NexusConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


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