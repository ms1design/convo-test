# Nexus — Home Assistant Conversation Integration

[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/ms1design/convo-test)](https://github.com/ms1design/convo-test/releases)

Nexus is a Home Assistant custom integration that brings OpenAI-powered conversation capabilities to your smart home. It leverages the official HA core `openai_conversation` component underneath, with the addition of a configurable `base_url` so you can point it at any OpenAI-compatible API endpoint.

## Features

- Full OpenAI conversation agent (powered by HA core `openai_conversation`)
- Configurable API endpoint via `base_url` (default: `https://api.openai.com/v1`)
- Support for all OpenAI models (GPT-4o, GPT-4o-mini, o-series, etc.)
- Web search, code interpreter, image generation, and file uploads
- STT (Speech-to-Text) and TTS (Text-to-Speech) subentries
- AI Task support for structured data generation
- Responses API streaming with full tool-call support

## Installation

### HACS (Recommended)

1. Open HACS → Integrations → "+" Explore & Download Repositories
2. Search for **"Nexus"** or add this repository: `https://github.com/ms1design/convo-test`
3. Click download and restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration → search for **"Nexus"**

### Manual

1. Download the latest release
2. Copy the `nexus_conversation` folder into your `custom_components/` directory
3. Restart Home Assistant

## Configuration

After installing, add the Nexus integration through the HA UI:

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Nexus"**
3. Enter your **API endpoint URL** (default: `https://api.openai.com/v1`)
4. Enter your **OpenAI API key**
5. Configure conversation agent options (model, prompt, etc.)

### Available Options

| Option | Description | Default |
|--------|-------------|---------|
| `base_url` | OpenAI-compatible API endpoint | `https://api.openai.com/v1` |
| `api_key` | Your OpenAI API key | _(required)_ |
| `chat_model` | Model to use for conversations | `gpt-4o-mini` |
| `prompt` | System prompt / instructions | _(empty)_ |
| `temperature` | Sampling temperature | `1.0` |
| `max_tokens` | Maximum output tokens | `3000` |

## Models

Supported models include all OpenAI chat and vision models: `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini`, etc.

Refer to the [OpenAI models documentation](https://platform.openai.com/docs/models) for the full list.

## Troubleshooting

- **Connection errors**: Verify your `base_url` is accessible and the API key is valid
- **Model not supported**: Check the [unsupported models list](https://platform.openai.com/docs/guides/function-calling#model-support)
- **Debug logging**: Enable via `configuration.yaml`:
  ```yaml
  logger:
    default: warn
    logs:
      custom_components.nexus_conversation: debug
  ```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Credits

Powered by [Home Assistant](https://www.home-assistant.io/) and the [openai_conversation](https://www.home-assistant.io/integrations/openai_conversation) core integration.
