# Samvit MCP server

Samvit ships a dependency-free [Model Context Protocol](https://modelcontextprotocol.io)
server that exposes its core operations to any MCP client (Claude Desktop,
opencode, Cursor, VS Code, ...). It speaks JSON-RPC 2.0 over stdio and uses the
standard library only, so it adds no runtime dependencies to Samvit.

## Run

```bash
python3 mcp-server/server.py
```

The server reads newline-delimited JSON-RPC from stdin and writes responses to
stdout; diagnostics go to stderr.

## Tools

| Tool | Purpose |
|------|---------|
| `samvit_ask` | Ask a one-shot question (VISION + ULTRON applied). |
| `samvit_remember` | Store a claim in the memory graph. |
| `samvit_memory_list` | List recent claims. |
| `samvit_memory_stats` | Claim counts. |
| `samvit_memory_recall` | Search stored claims. |
| `samvit_persona_list` | List profiles. |
| `samvit_persona_show` | Current persona state. |
| `samvit_persona_drift` | Per-axis and compound drift. |
| `samvit_persona_diff` | What changed since the anchor. |
| `samvit_tools_list` | Allowlisted tools with tiers. |
| `samvit_tool_call` | Invoke an allowlisted tool by name. |
| `samvit_status` | System status. |
| `samvit_audit` | Query or verify the audit log. |
| `samvit_config_get` | Read a config key. |
| `samvit_app_info` | Server + installation metadata. |

Every tool except `samvit_app_info` shells out to the Samvit CLI with `--json`
and returns its output, so the MCP surface stays in lockstep with the CLI.

## Client configuration

A ready-to-use `.mcp.json` is included at the repository root:

```json
{
  "mcpServers": {
    "samvit": { "command": "python3", "args": ["mcp-server/server.py"] }
  }
}
```

## Tests

```bash
python3 -m unittest discover -s tests -p "test_mcp_server.py" -v
```
