# Samvit MCP server

Samvit exposes its core operations through a
[Model Context Protocol](https://modelcontextprotocol.io) server, so agentic
clients can drive Samvit's memory graph, personas, and validation layers as
first-class tools.

- **Transport:** stdio (newline-delimited JSON-RPC 2.0)
- **Dependencies:** none (standard library only, matching Samvit's design)
- **Entry point:** `mcp-server/server.py`
- **Tools:** 15 — see [mcp-server/README.md](../mcp-server/README.md)

## What an MCP client can do

| Tool | Maps to Samvit CLI |
|------|--------------------|
| `samvit_ask` | `samvit ask <query> --json` |
| `samvit_remember` | `samvit remember <text> --json` |
| `samvit_memory_list` | `samvit memory list --limit N --json` |
| `samvit_memory_stats` | `samvit memory stats --json` |
| `samvit_memory_recall` | `samvit memory recall <query> --json` |
| `samvit_persona_list` | `samvit persona list --json` |
| `samvit_persona_show` | `samvit persona show --json` |
| `samvit_persona_drift` | `samvit persona drift --json` |
| `samvit_persona_diff` | `samvit persona diff --json` |
| `samvit_tools_list` | `samvit tools list --json` |
| `samvit_tool_call` | `samvit tools call <name> --args <json> --json` |
| `samvit_status` | `samvit status --json` |
| `samvit_audit` | `samvit audit --limit N [--verify] --json` |
| `samvit_config_get` | `samvit config get <key> --json` |
| `samvit_app_info` | server + installation metadata |

## Connect a client

The repository includes `.mcp.json` at its root:

```json
{
  "mcpServers": {
    "samvit": { "command": "python3", "args": ["mcp-server/server.py"] }
  }
}
```

Claude Desktop, opencode, Cursor, and other MCP clients read an equivalent
`mcpServers` block. Because tools shell out to the installed Samvit CLI, install
the package first (`pip install -e .`) or run the server from the repository
root so `python3 -m samvit` resolves.

## Verify

```bash
python3 -m unittest discover -s tests -p "test_mcp_server.py" -v
```

The tests speak the MCP protocol directly (initialize → tools/list →
tools/call), so they validate the server without an MCP client.
