#!/usr/bin/env python3
"""Model Context Protocol server for this repository.

A dependency-free stdio MCP server (JSON-RPC 2.0) exposing read-only tools so
assistants, agents and glama.ai can inspect project metadata, files and docs.
Standard library only; runs with ``python3 mcp_server.py``.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = os.path.basename(ROOT.rstrip(os.sep)) or "repository"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", ".next", ".pytest_cache", ".mypy_cache", ".ruff_cache",
             ".turbo", "coverage", ".idea", ".vscode"}
TEXT_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json",
            ".md", ".markdown", ".txt", ".rst", ".yml", ".yaml", ".toml",
            ".cfg", ".ini", ".html", ".css", ".sql", ".sh", ".env", ".example"}
MAX_READ = 200_000
MAX_SCAN = 600_000


def _iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            yield rel, full


def _all_files():
    return sorted(rel for rel, _ in _iter_files())


def _read_manifest():
    info = {"name": SERVER_NAME, "version": None, "description": None}
    pyproject = os.path.join(ROOT, "pyproject.toml")
    if os.path.isfile(pyproject):
        try:
            import tomllib
            with open(pyproject, "rb") as fh:
                data = tomllib.load(fh)
            proj = data.get("project", {})
            info["name"] = proj.get("name", info["name"])
            info["version"] = proj.get("version")
            info["description"] = proj.get("description")
            return info
        except Exception:
            pass
    for cand in ("package.json", "frontend/package.json", "backend/package.json"):
        path = os.path.join(ROOT, cand)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                info["name"] = data.get("name", info["name"])
                info["version"] = data.get("version")
                info["description"] = data.get("description")
                return info
            except Exception:
                pass
    return info


def _languages(files):
    counts = {}
    for rel in files:
        ext = os.path.splitext(rel)[1].lower()
        if ext in TEXT_EXT:
            counts[ext] = counts.get(ext, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:8])


def _safe_path(rel):
    if not rel:
        return None
    candidate = os.path.realpath(os.path.join(ROOT, rel))
    if candidate != ROOT and not candidate.startswith(ROOT + os.sep):
        return None
    return candidate


def _is_text(rel):
    return os.path.splitext(rel)[1].lower() in TEXT_EXT


def _info_text():
    files = _all_files()
    manifest = _read_manifest()
    return json.dumps({
        "name": manifest["name"],
        "version": manifest["version"],
        "description": manifest["description"],
        "files": len(files),
        "languages": _languages(files),
        "docs": [f for f in files if f.startswith(("docs/", "documentation/"))][:20],
    }, indent=2)


def _list_text(arg):
    files = _all_files()
    if arg:
        files = [f for f in files if fnmatch.fnmatch(f, arg) or arg.lower() in f.lower()]
    total = len(files)
    return "\n".join(files[:200]) + (f"\n... ({total} files total)" if total > 200 else "")


def _read_text(arg):
    rel = str(arg or "")
    path = _safe_path(rel)
    if path is None or not os.path.isfile(path):
        return f"File not found: {rel}"
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_READ + 1)
    except Exception as exc:
        return f"Cannot read {rel}: {exc}"
    text = raw[:MAX_READ].decode("utf-8", "replace")
    if len(raw) > MAX_READ:
        text += "\n... (truncated)"
    return text


def _search_text(arg):
    query = str(arg or "")
    if len(query) < 2:
        return "Provide a search string of at least 2 characters."
    needle = query.lower()
    hits = []
    for rel, full in _iter_files():
        if not _is_text(rel) or len(hits) >= 60:
            continue
        try:
            if os.path.getsize(full) > MAX_SCAN:
                continue
            with open(full, encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    if needle in line.lower():
                        hits.append(f"{rel}:{i}: {line.strip()[:160]}")
                        if len(hits) >= 60:
                            break
        except OSError:
            continue
    return "\n".join(hits) if hits else f"No matches for {query!r}"


def _health_text():
    return json.dumps({
        "status": "ok",
        "server": SERVER_NAME,
        "protocol": PROTOCOL_VERSION,
        "root": ROOT,
        "files": len(_all_files()),
    }, indent=2)


TOOLS = [
    {"name": "repo_info",
     "description": "Project metadata: manifest name/version/description, file count, languages and docs.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "list_files",
     "description": "List repository files, optionally filtered by a glob or substring.",
     "inputSchema": {"type": "object", "properties": {"filter": {"type": "string"}},
                     "additionalProperties": False}},
    {"name": "read_file",
     "description": "Return the text of a repository file (path is confined to the repository).",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}},
                     "required": ["path"], "additionalProperties": False}},
    {"name": "search",
     "description": "Case-insensitive substring search across text files, returning path:line matches.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}},
                     "required": ["query"], "additionalProperties": False}},
    {"name": "health",
     "description": "Server health and repository availability check.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


def _dispatch(name, args):
    args = args or {}
    if name == "repo_info":
        return _info_text()
    if name == "list_files":
        return _list_text(args.get("filter"))
    if name == "read_file":
        return _read_text(args.get("path"))
    if name == "search":
        return _search_text(args.get("query"))
    if name == "health":
        return _health_text()
    return None


def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _handle(msg):
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        return _send({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": _read_manifest()["version"] or "1.0.0"},
        }})
    if method in ("notifications/initialized", "initialized"):
        return
    if method == "ping":
        return _send({"jsonrpc": "2.0", "id": mid, "result": {}})
    if method == "tools/list":
        return _send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
    if method == "tools/call":
        out = _dispatch(params.get("name"), params.get("arguments"))
        if out is None:
            return _send({"jsonrpc": "2.0", "id": mid,
                          "error": {"code": -32602, "message": "Unknown tool: %s" % params.get("name")}})
        return _send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": out}]}})
    if mid is None:
        return
    _send({"jsonrpc": "2.0", "id": mid,
           "error": {"code": -32601, "message": "Method not found: %s" % method}})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            _send({"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": "Parse error"}})
            continue
        try:
            _handle(msg)
        except Exception as exc:
            _send({"jsonrpc": "2.0", "id": msg.get("id"),
                   "error": {"code": -32603, "message": "Internal error: %s" % exc}})


if __name__ == "__main__":
    main()
