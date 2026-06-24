# Nexus — Home Assistant Integration

**Authored by the [FutureProof Homes Team](https://futureproofhomes.com)** for the **Nexus AI Base Station** platform.

[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/ms1design/convo-test)](https://github.com/ms1design/convo-test/releases)

## Overview

Nexus is a Home Assistant custom integration that connects your home to the **Nexus AI Base Station** — a private, open-source, locally-run AI voice assistant built by [FutureProof Homes](https://futureproofhomes.com).

Where Alexa listens and sells, where Google Home guesses and forgets — Nexus *understands*. Through a native **Model Context Protocol (MCP)** bridge, Nexus pulls live context from every light, climate zone, shutter, and media player into a structured, real-world map of your home. Everything stays local. Your voice, your schedule, your habits — behind your firewall.

This integration replaces the legacy STT/TTS pipeline with a pure text-based conversation engine, enriched with home context (area, floor, user identity, sensors) so the assistant knows *where* and *who* it's talking to.

## Key Differences vs. Native `openai_conversation`

| Feature | Native HA OpenAI | Nexus |
|---------|-----------------|-------|
| **Backend** | Cloud LLM API | Local Nexus AI Base Station |
| **Privacy** | Data leaves your network | Zero cloud — everything stays local |
| **Legacy STT/TTS** | Assumed built-in | Handled via Wyoming protocol separately |
| **Context enrichment** | Basic (area name only) | Area name, floor name, user identity, sensor data |
| **Structured output** | Limited | Full JSON schema generation via AI Tasks |
| **Smart tool correction** | None | Auto-correction improves SLM accuracy up to 30% |
| **Zero-conf discovery** | None | mDNS/zeroconf auto-discovery of Nexus servers |
| **Subentry architecture** | Flat config | Parent config → child conversation agents + AI tasks |

### Context Enrichment Detail

When a conversation is initiated through Nexus, the integration resolves:

- **Area name & floor** — from the Home Assistant area/device registry, injected into the system prompt so the assistant knows the physical context.
- **User identity** — resolved from the authenticating user's account, enabling personalized interactions.
- **Sensor data** — ambient sensors tied to the active area (light, humidity, presence) are surfaced to the model as context.

These enrichments happen transparently before the request reaches Nexus — no prompt manipulation required.

## Features

- **Conversation Agent** — Full Responses API support (streaming, tool calls, reasoning)
- **AI Tasks** — Structured data generation with JSON schema output
- **Zero-conf Discovery** — mDNS auto-discovers Nexus servers on the local network
- **Tool Calling** — Web search, code interpreter, intelligent auto-correction for small models
- **Multi-language** — Locale-aware responses via configurable system prompts
- **Parent/Sub-entry Config** — One API key, multiple conversation agents and AI tasks

## Perfect Pair: Nexus × Satellite1.1

<table width="100%">
  <tr>
    <td width="20%" valign="top" align="center">
      <a href="https://futureproofhomes.net/products/satellite1-smart-speaker" target="_blank"><img src="https://futureproofhomes.net/cdn/shop/files/IMG_E8879.jpg?v=1775097549&width=450" alt="FutureProofHomes Satellite1.1 Smart Speaker" /></a>
    </td>
    <td width="80%" valign="top" align="left">
    <p>The <strong><a href="https://futureproofhomes.net/products/satellite1-smart-speaker">Satellite1.1 Smart Speaker</a></strong> is the voice companion Nexus was forged to accompany. Four-mic far-field array, 20W two-way speaker, optional mmWave presence sensor. Plug in the Satellite1.1, wire it to Nexus, and you don't have a smart speaker anymore — you have a continuous, private intelligence woven into your home.</p>
    </td>
  </tr>
</table>

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
   - **Manual** — enter your Nexus endpoint URL and API key
   - **Auto-discover** — click a Nexus server found on your network (requires Nexus server broadcasting via mDNS)

### Available Options

| Option | Description | Default |
|--------|-------------|---------|
| `base_url` | Nexus API endpoint | `http://<NEXUS_HOST>:5015/ha/v1` |
| `api_key` | Your API key | `sk-1` |
| `chat_model` | Model for conversations | _(default)_ |
| `prompt` | System prompt / instructions | _(empty)_ |
| `temperature` | Sampling temperature | `1.0` |
| `max_tokens` | Maximum output tokens | `3000` |
| `reasoning_effort` | Effort for reasoning models | `low` |
| `code_interpreter` | Enable code execution tool | `false` |
| `web_search` | Enable web search tool | `false` |

## Setting Up Nexus

For a complete end-to-end setup:

1. **Install Nexus OS** — Flash the [Nexus AI Base Station](https://github.com/FutureProofHomes/Internal-Nexus/releases) ISO to an NVMe drive and run `nexus up`
2. **Install this HACS Integration** — as described above
3. **Create the Conversation Agent** — configure `base_url` pointing to your Nexus host
4. **Activate the MCP Server** — add the Home Assistant MCP Server integration to expose LLM Tools for Nexus
5. **Connect STT & TTS** — configure Wyoming STT/TTS integrations with your Nexus host
6. **Configure Assist Pipeline** — route your default pipeline through the Nexus Conversation Agent

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