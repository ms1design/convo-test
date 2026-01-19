# Home Assistant Integration

*WIP*

## Development

For detailed development setup and running linting/validation locally, see [DEVELOPMENT.md](DEVELOPMENT.md).

Quick setup:
```bash
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt
```

Run linter:
```bash
python -m ruff check .
```

Run formatter:
```bash
python -m ruff format .
```

## Usage

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Nexus"
4. Follow the on-screen instructions to complete setup:
    - enter `base_url`
    - enter `api_key`

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
