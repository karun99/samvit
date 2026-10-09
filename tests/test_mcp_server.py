"""Smoke tests for the Samvit MCP server (mcp-server/server.py).

These tests speak the MCP JSON-RPC protocol directly over stdio, so they verify
the server is a valid MCP endpoint without needing any MCP client installed.
Standard library only, matching Samvit's dependency policy.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(REPO_ROOT, "mcp-server", "server.py")


class MCPTest(unittest.TestCase):
    def setUp(self):
        self.proc = subprocess.Popen(
            [sys.executable, SERVER],
            cwd=REPO_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def tearDown(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
        finally:
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass

    def rpc(self, method, params=None, req_id=1):
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        self.assertTrue(line, "server closed stdout without a response")
        return json.loads(line)

    def test_initialize(self):
        resp = self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})
        self.assertEqual(resp["result"]["serverInfo"]["name"], "samvit-mcp")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_tools_list(self):
        self.rpc("initialize", {})
        resp = self.rpc("tools/list", {}, req_id=2)
        names = {t["name"] for t in resp["result"]["tools"]}
        self.assertIn("samvit_ask", names)
        self.assertIn("samvit_memory_recall", names)
        for tool in resp["result"]["tools"]:
            self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_tools_call_app_info(self):
        self.rpc("initialize", {})
        resp = self.rpc("tools/call", {"name": "samvit_app_info", "arguments": {}}, req_id=3)
        self.assertFalse(resp["result"]["isError"])
        self.assertIn("samvit", resp["result"]["content"][0]["text"])

    def test_unknown_method_is_reported(self):
        resp = self.rpc("does/not/exist", {}, req_id=4)
        self.assertEqual(resp["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
