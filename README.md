Built at AGI House MCP Hackathon March 15 2025

# Quickstart

1. Install UV (Python package installer)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create and activate virtual environment
```bash
uv venv
source .venv/bin/activate
```

3. Install dependencies
```bash
uv sync
```

4. Run the script
```bash
uv run browser-use.py
```

# Usage

Configure your MCP settings in `claude_desktop_config.json`:

```json
{
    "mcpServers": {
        "browser-use": {
            "command": "uv", // Absolute path might be needed otherwise
            "args":[
                "--directory",
                "/path/to/your/project/", // Absolute path
                "run",
                "browser-use.py"
            ]
        }
    }
}
```

Replace `/path/to/uv` with your UV installation path and `/path/to/your/project/` with your project directory path.

