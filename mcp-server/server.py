#!/usr/bin/env python3
"""Samvit MCP server — exposes Samvit's core operations over the Model Context Protocol.

Dependency-free (standard library only), matching Samvit's own design. Speaks
JSON-RPC 2.0 over stdio and implements the `tools` capability, so any MCP client
(Claude Desktop, opencode, Cursor, ...) can drive Samvit through tools.

Transport: stdio. Protocol messages are newline-delimited JSON-RPC on stdout;
all diagnostics go to stderr so stdout stays a clean protocol channel.

Run:  python3 mcp-server/server.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

SERVER_NAME = "samvit-mcp"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_TIMEOUT = 180

# Allow running from a source checkout (python3 mcp-server/server.py) where the
# package is not pip-installed: put the repo root ahead of the script directory.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _schema(properties=None, required=None):
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


def _str(desc):
    return {"type": "string", "description": desc}


def _int(desc):
    return {"type": "integer", "description": desc}


def _bool(desc):
    return {"type": "boolean", "description": desc}


# Each tool declares a JSON schema plus a builder that maps arguments to CLI argv.
# Global flags (--json, --profile) precede the subcommand; see samvit/cli.py.
TOOLS = {
    "samvit_ask": {
        "description": "Ask Samvit a one-shot question and return its grounded/partial/ungrounded answer.",
        "inputSchema": _schema(
            {"query": _str("The question to ask."), "fast": _bool("Run critical ULTRON checks only.")},
            ["query"],
        ),
        "build": lambda a: _with_globals(a, ["ask", str(a["query"])] + (["--fast"] if a.get("fast") else [])),
    },
    "samvit_remember": {
        "description": "Store a claim in Samvit's shared memory graph.",
        "inputSchema": _schema({"text": _str("The claim to remember.")}, ["text"]),
        "build": lambda a: _with_globals(a, ["remember", str(a["text"])]),
    },
    "samvit_memory_list": {
        "description": "List the most recent claims in the memory graph.",
        "inputSchema": _schema({"limit": _int("Maximum number of claims to return.")}),
        "build": lambda a: _with_globals(a, ["memory", "list", "--limit", str(int(a.get("limit", 10)))]),
    },
    "samvit_memory_stats": {
        "description": "Return claim counts from the memory graph.",
        "inputSchema": _schema(),
        "build": lambda a: _with_globals(a, ["memory", "stats"]),
    },
    "samvit_memory_recall": {
        "description": "Search stored claims for a query.",
        "inputSchema": _schema({"query": _str("Text to search for.")}, ["query"]),
        "build": lambda a: _with_globals(a, ["memory", "recall", str(a["query"])]),
    },
    "samvit_persona_list": {
        "description": "List the available Samvit profiles/personas.",
        "inputSchema": _schema(),
        "build": lambda a: _with_globals(a, ["persona", "list"]),
    },
    "samvit_persona_show": {
        "description": "Show the current persona state.",
        "inputSchema": _schema(),
        "build": lambda a: _with_globals(a, ["persona", "show"]),
    },
    "samvit_persona_drift": {
        "description": "Report persona drift per axis and compound drift.",
        "inputSchema": _schema(),
        "build": lambda a: _with_globals(a, ["persona", "drift"]),
    },
    "samvit_persona_diff": {
        "description": "Show what changed in the persona since its anchor.",
        "inputSchema": _schema(),
        "build": lambda a: _with_globals(a, ["persona", "diff"]),
    },
    "samvit_tools_list": {
        "description": "List Samvit's allowlisted tools with their tiers.",
        "inputSchema": _schema(),
        "build": lambda a: _with_globals(a, ["tools", "list"]),
    },
    "samvit_tool_call": {
        "description": "Invoke one of Samvit's allowlisted tools by name.",
        "inputSchema": _schema(
            {"name": _str("Allowlisted tool name."), "args": _str("JSON object of tool arguments.")},
            ["name"],
        ),
        "build": lambda a: _with_globals(a, ["tools", "call", str(a["name"]), "--args", a.get("args", "{}")]),
    },
    "samvit_status": {
        "description": "Return Samvit system status.",
        "inputSchema": _schema(),
        "build": lambda a: _with_globals(a, ["status"]),
    },
    "samvit_audit": {
        "description": "Query or verify Samvit's audit log.",
        "inputSchema": _schema({"limit": _int("Maximum entries."), "verify": _bool("Verify the audit log.")}),
        "build": lambda a: _with_globals(
            a, ["audit", "--limit", str(int(a.get("limit", 50)))] + (["--verify"] if a.get("verify") else [])
        ),
    },
    "samvit_config_get": {
        "description": "Read a Samvit configuration key.",
        "inputSchema": _schema({"key": _str("Configuration key.")}, ["key"]),
        "build": lambda a: _with_globals(a, ["config", "get", str(a["key"])]),
    },
    "samvit_app_info": {
        "description": "Return metadata about this Samvit installation and the MCP server.",
        "inputSchema": _schema(),
        "build": lambda a: None,
    },
}


def _with_globals(args, command):
    argv = ["--json"]
    profile = args.get("profile")
    if profile:
        argv += ["--profile", str(profile)]
    if args.get("authorized"):
        argv.append("--authorized")
    return argv + command


def call_cli(argv):
    cmd = [sys.executable, "-m", "samvit"] + argv
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=CLI_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"samvit CLI timed out after {CLI_TIMEOUT}s"
    text = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return (text + ("\n" if text and err else "") + err).strip() or f"samvit exited with code {proc.returncode}"
    return text or "(no output)"


def app_info():
    try:
        import samvit

        version = getattr(samvit, "__version__", "unknown")
        author = getattr(samvit, "__author__", "unknown")
        license_name = getattr(samvit, "__license__", "unknown")
    except Exception:  # package not importable — still advertise the server
        version = author = license_name = "unknown"
    return json.dumps(
        {
            "name": "samvit",
            "version": version,
            "author": author,
            "license": license_name,
            "repo_root": REPO_ROOT,
            "mcp_server": {"name": SERVER_NAME, "version": SERVER_VERSION, "protocol": PROTOCOL_VERSION},
            "tools": sorted(TOOLS),
        },
        indent=2,
    )


def dispatch_tool(name, args):
    spec = TOOLS.get(name)
    if spec is None:
        raise ValueError(f"Unknown tool: {name}")
    if name == "samvit_app_info":
        return app_info()
    argv = spec["build"](args)
    return call_cli(argv)


def make_result(text):
    return {"content": [{"type": "text", "text": text}], "isError": False}


def make_error(msg):
    return {"content": [{"type": "text", "text": msg}], "isError": True}


def handle(request):
    method = request.get("method")
    req_id = request.get("id")
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    elif method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {
            "tools": [
                {"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
                for name, spec in TOOLS.items()
            ]
        }
    elif method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = make_result(dispatch_tool(name, arguments))
        except Exception as exc:  # keep the server alive on tool failure
            result = make_error(f"{type(exc).__name__}: {exc}")
    elif method == "resources/list":
        result = {"resources": []}
    elif method == "prompts/list":
        result = {"prompts": []}
    else:
        if req_id is None:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    if req_id is None:
        return None
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}), flush=True)
            continue
        response = handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
