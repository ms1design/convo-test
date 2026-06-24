# Nexus — Home Assistant Integration

**Authored by the [FutureProof Homes Team](https://futureproofhomes.com)** for the **Nexus AI Assistant** platform.

[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/ms1design/convo-test)](https://github.com/ms1design/convo-test/releases)

## Overview

Nexus is a Home Assistant custom integration that delivers OpenAI-powered conversation and task automation to your smart home. Under the hood it speaks the **OpenAI Responses API** schema — the same protocol used by `gpt-4o`, `o-series`, and `gpt-5` models — but tailored specifically for the Nexus AI Assistant self-hosted backend.

Unlike the official HA `openai_conversation` integration, Nexus **strips away the legacy STT/TTS pipeline** and focuses purely on text-based conversation and structured data generation. Where the stock OpenAI integration stops at model parameters, Nexus enriches every request with rich home-context metadata (room, floor, user identity) so the assistant understands *where* and *who* it's talking to.

## Key Differences vs. Native `openai_conversation`

| Feature | Native HA OpenAI | Nexus |
|---------|-----------------|-------|
| **Protocol** | Assist Pipeline (STT → LLM → TTS) | Pure Responses API (text-in, text-out) |
| **Legacy STT/TTS** | Included | Stripped — text-only |
| **Context enrichment** | Basic (area name only) | Area name, floor name, user identity, room sensor data |
| **Structured output** | Limited | Full JSON schema generation via AI Tasks |
| **Self-hosted Nexus** | Not supported | First-class (`base_url` flips to local Nexus server) |
| **Zero-conf discovery** | None | mDNS/zeroconf auto-discovery of Nexus servers |
| **Subentry architecture** | Flat config | Parent config → child conversation agents + AI tasks |

### Context Enrichment Detail

When a conversation is initiated through Nexus, the integration resolves:

- **Area name & floor** — from the Home Assistant area/device registry, injected into the system prompt so the assistant knows the physical context.
- **User identity** — resolved from the authenticating user's account, enabling personalized interactions.
- **Sensor data** — ambient sensors tied to the active area (light, humidity, presence) are surfaced to the model as context.

These enrichments happen transparently before the request reaches the model — no prompt manipulation required.

## Features

- **Conversation Agent** — Full OpenAI Responses API support (streaming, tool calls, reasoning)
- **AI Tasks** — Structured data generation with JSON schema output
- **Zero-conf Discovery** — mDNS auto-discovers Nexus servers on the local network
- **Tool Calling** — Web search, code interpreter
- **Multi-language** — Locale-aware responses via configurable system prompts
- **Parent/Sub-entry Config** — One API key, multiple conversation agents and AI tasks

## Installation

### HACS (Recommended)

1. Open HACS → Integrations → "+" → **Explore & Download Repositories**
2. Search for **"Nexus"** or add this repository: `https://github.com/ms1design/convo-test`
3. Click **Download** and restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration** → search for **"Nexus"**

### Manual

1. Download the latest release
2. Copy the `nexus_conversation` folder into your `custom_components/` directory
3. Restart Home Assistant

## Configuration

After installing, add the Nexus integration through the HA UI:

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Nexus"**
3. Choose one of:
   - **Manual** — enter your API endpoint URL and API key
   - **Auto-discover** — click a Nexus server found on your network (requires Nexus server broadcasting via mDNS)

### Available Options

| Option | Description | Default |
|--------|-------------|---------|
| `base_url` | OpenAI-compatible API endpoint | `https://api.openai.com/v1` |
| `api_key` | Your API key | _(required)_ |
| `chat_model` | Model for conversations | `gpt-4o-mini` |
| `prompt` | System prompt / instructions | _(empty)_ |
| `temperature` | Sampling temperature | `1.0` |
| `max_tokens` | Maximum output tokens | `3000` |
| `reasoning_effort` | Effort for reasoning models (o-series, gpt-5) | `low` |
| `code_interpreter` | Enable code execution tool | `false` |
| `web_search` | Enable web search tool | `false` |

## Supported Models

All OpenAI chat, reasoning, and vision models:

| Type | Models |
|------|--------|
| Chat | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo` |
| Reasoning | `o1`, `o3-mini`, `gpt-5` series |
| Vision | `gpt-4o`, `gpt-4o-mini` (with image inputs) |

See the [OpenAI models documentation](https://platform.openai.com/docs/models) for the complete list.

## Debug Logging

Enable debug output in `configuration.yaml`:

```yaml
logger:
  default: warn
  logs:
    custom_components.nexus_conversation: debug
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Credits

Built by the [FutureProof Homes Team](https://futureproofhomes.com) with inspiration from [Home Assistant](https://www.home-assistant.io/) and the [openai_conversation](https://www.home-assistant.io/integrations/openai_conversation) core integration.