"""
Bridge behavior against fake Serial Studio servers. Standard library only; no
running app is needed, and SERIAL_STUDIO_API_PORT keeps the bridge away from a
real one.

Run with: python -m unittest discover -s tests -v
"""

import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

BRIDGE = Path(__file__).parents[1] / "bridge.py"
TIMEOUT = 15.0
FIX = "Enable API Server"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "tests", "version": "0"},
    },
}


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def tool_call(request_id, name="io.getStatus"):
    params = {"name": name, "arguments": {}}
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": params,
    }


class FakeApp:
    """A stand-in for Serial Studio's API server"""

    def __init__(self, port=0):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", port))
        self.server.listen(1)
        self.server.settimeout(TIMEOUT)
        self.port = self.server.getsockname()[1]
        self.conn = None
        self.buffer = b""

    def accept(self):
        self.conn, _ = self.server.accept()
        self.conn.settimeout(TIMEOUT)
        self.buffer = b""

    def read(self):
        while b"\n" not in self.buffer:
            chunk = self.conn.recv(65536)
            if not chunk:
                raise ConnectionError("bridge closed the connection")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return json.loads(line)

    def send(self, data):
        self.conn.sendall(data)

    def reply(self, message):
        self.send(json.dumps(message).encode() + b"\n")

    def drop(self):
        self.conn.close()
        self.conn = None

    def close(self):
        if self.conn is not None:
            self.conn.close()
        self.server.close()


class BridgeProcess:
    """The bridge under test, with its stdio on queues"""

    def __init__(self, port):
        self.proc = subprocess.Popen(
            [sys.executable, "-I", str(BRIDGE)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(os.environ, SERIAL_STUDIO_API_PORT=str(port)),
        )
        self.stdout = queue.Queue()
        self.stderr = []
        threading.Thread(target=self._drain_stdout, daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _drain_stdout(self):
        with self.proc.stdout:
            for line in self.proc.stdout:
                self.stdout.put(line)

    def _drain_stderr(self):
        with self.proc.stderr:
            for line in self.proc.stderr:
                self.stderr.append(line.decode("utf-8", "replace"))

    def send(self, message):
        self.send_raw(json.dumps(message).encode() + b"\n")

    def send_raw(self, data):
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def read_raw(self, timeout=TIMEOUT):
        return self.stdout.get(timeout=timeout)

    def read(self, timeout=TIMEOUT):
        return json.loads(self.read_raw(timeout))

    def log_lines(self):
        return [line for line in list(self.stderr) if line.strip()]

    def wait_for_log(self, text, timeout=TIMEOUT):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(text in line for line in self.log_lines()):
                return True
            time.sleep(0.02)
        return False

    def finish(self):
        """Close stdin, as a departing client does, and return the exit status"""
        self.proc.stdin.close()
        status = self.proc.wait(timeout=TIMEOUT)
        time.sleep(0.05)
        return status

    def kill(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=TIMEOUT)
        try:
            self.proc.stdin.close()
        except OSError:
            pass


class BridgeTest(unittest.TestCase):
    def start_bridge(self, port):
        bridge = BridgeProcess(port)
        self.addCleanup(bridge.kill)
        return bridge

    def start_app(self, port=0):
        app = FakeApp(port)
        self.addCleanup(app.close)
        return app

    def connected_pair(self):
        app = self.start_app()
        bridge = self.start_bridge(app.port)
        app.accept()
        return app, bridge

    def assert_no_abort(self, bridge):
        log = "".join(bridge.log_lines())
        self.assertNotIn("Fatal Python error", log, log)


class WhileTheAppIsAway(BridgeTest):
    def test_initialize_is_answered_at_once(self):
        bridge = self.start_bridge(free_port())
        bridge.send(INITIALIZE)
        reply = bridge.read()["result"]
        self.assertEqual(reply["protocolVersion"], "2025-06-18")
        self.assertTrue(reply["capabilities"]["tools"]["listChanged"])
        self.assertIn(FIX, reply["instructions"])

    def test_the_fix_is_the_last_log_line(self):
        bridge = self.start_bridge(free_port())
        self.assertTrue(bridge.wait_for_log(FIX))
        self.assertIn(FIX, bridge.log_lines()[-1])

    def test_only_the_status_tool_is_listed(self):
        bridge = self.start_bridge(free_port())
        bridge.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = bridge.read()["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["bridge.getStatus"])

    def test_the_status_tool_names_the_fix(self):
        bridge = self.start_bridge(free_port())
        bridge.send(tool_call(3, "bridge.getStatus"))
        result = bridge.read()["result"]
        self.assertFalse(result["isError"])
        self.assertIn(FIX, result["content"][0]["text"])

    def test_a_tool_call_fails_with_the_fix(self):
        bridge = self.start_bridge(free_port())
        bridge.send(tool_call(4))
        result = bridge.read()["result"]
        self.assertTrue(result["isError"])
        self.assertIn(FIX, result["content"][0]["text"])

    def test_an_unknown_method_is_refused_not_ignored(self):
        bridge = self.start_bridge(free_port())
        bridge.send({"jsonrpc": "2.0", "id": 5, "method": "server/discover"})
        self.assertEqual(bridge.read()["error"]["code"], -32601)

    def test_closing_stdin_exits_cleanly(self):
        bridge = self.start_bridge(free_port())
        self.assertTrue(bridge.wait_for_log(FIX))
        self.assertEqual(bridge.finish(), 0)
        self.assert_no_abort(bridge)


class Reconnecting(BridgeTest):
    def serve_replay(self, app):
        """Accept the bridge and answer its replayed handshake; returns the request"""
        app.accept()
        request = app.read()
        self.assertEqual(request["method"], "initialize")
        self.assertIsInstance(request["id"], str)
        app.reply({"jsonrpc": "2.0", "id": request["id"], "result": {}})
        self.assertEqual(app.read()["method"], "notifications/initialized")
        return request

    def assert_lists_changed(self, bridge):
        methods = {bridge.read()["method"] for _ in range(3)}
        expected = {
            f"notifications/{kind}/list_changed"
            for kind in ("tools", "resources", "prompts")
        }
        self.assertEqual(methods, expected)

    def test_an_app_that_starts_late_is_picked_up(self):
        port = free_port()
        bridge = self.start_bridge(port)
        bridge.send(INITIALIZE)
        bridge.read()

        app = self.start_app(port)
        request = self.serve_replay(app)
        self.assertEqual(request["params"], INITIALIZE["params"])
        self.assert_lists_changed(bridge)

        bridge.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(app.read()["method"], "tools/list")
        app.reply({"jsonrpc": "2.0", "id": 2, "result": {"tools": []}})
        self.assertEqual(bridge.read()["id"], 2)

    def test_the_replay_never_reaches_the_client(self):
        port = free_port()
        bridge = self.start_bridge(port)
        bridge.send(INITIALIZE)
        bridge.read()

        app = self.start_app(port)
        self.serve_replay(app)
        for _ in range(3):
            self.assertIn("method", bridge.read())

    def test_an_app_restart_mid_session_is_survived(self):
        app, bridge = self.connected_pair()
        bridge.send(INITIALIZE)
        self.assertEqual(app.read()["method"], "initialize")
        app.reply({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}})
        bridge.read()

        app.drop()
        self.assertTrue(bridge.wait_for_log("closed connection"))
        self.assertEqual(bridge.proc.poll(), None)

        self.serve_replay(app)
        self.assert_lists_changed(bridge)

    def test_a_refused_replay_is_retried(self):
        port = free_port()
        bridge = self.start_bridge(port)
        bridge.send(INITIALIZE)
        bridge.read()

        app = self.start_app(port)
        app.accept()
        request = app.read()
        error = {"code": -32603, "message": "no"}
        app.reply({"jsonrpc": "2.0", "id": request["id"], "error": error})
        self.assertTrue(bridge.wait_for_log("refused the reconnect handshake"))

        self.serve_replay(app)
        self.assert_lists_changed(bridge)


class WhileConnected(BridgeTest):
    def test_initialize_gains_list_changed(self):
        app, bridge = self.connected_pair()
        bridge.send(INITIALIZE)
        self.assertEqual(app.read()["id"], 1)
        capabilities = {"tools": {}, "resources": {}, "prompts": {}}
        result = {"protocolVersion": "2025-06-18", "capabilities": capabilities}
        app.reply({"jsonrpc": "2.0", "id": 1, "result": result})

        capabilities = bridge.read()["result"]["capabilities"]
        for name in ("tools", "resources", "prompts"):
            self.assertTrue(capabilities[name]["listChanged"])

    def test_other_replies_pass_through_byte_for_byte(self):
        app, bridge = self.connected_pair()
        reply = b'{ "jsonrpc": "2.0",  "id": 9, "result": {} }\n'
        app.send(reply)
        self.assertEqual(bridge.read_raw(), reply)

    def test_only_jsonrpc_lines_are_forwarded(self):
        app, bridge = self.connected_pair()
        reply = b'{"jsonrpc":"2.0","id":1,"result":{}}\n'
        app.send(b'{"frames":[]}\n{"data":"AA=="}\nnot json\n' + reply)
        self.assertEqual(bridge.read_raw(), reply)
        app.drop()
        self.assertTrue(bridge.wait_for_log("Dropped 3 non-JSON-RPC"))

    def test_a_call_in_flight_fails_when_the_link_drops(self):
        app, bridge = self.connected_pair()
        bridge.send(tool_call(7))
        self.assertEqual(app.read()["id"], 7)
        app.drop()

        reply = bridge.read()
        self.assertEqual(reply["id"], 7)
        self.assertTrue(reply["result"]["isError"])
        self.assertIn(FIX, reply["result"]["content"][0]["text"])

    def test_a_call_after_the_link_drops_fails_with_the_fix(self):
        app, bridge = self.connected_pair()
        app.drop()
        self.assertTrue(bridge.wait_for_log("closed connection"))
        bridge.send(tool_call(8))
        self.assertIn(FIX, bridge.read()["result"]["content"][0]["text"])

    def test_the_status_tool_reports_the_link(self):
        _, bridge = self.connected_pair()
        time.sleep(0.2)
        bridge.send(tool_call(3, "bridge.getStatus"))
        self.assertIn("Connected", bridge.read()["result"]["content"][0]["text"])

    def test_a_large_request_survives_a_stalled_app(self):
        app, bridge = self.connected_pair()
        request = dict(tool_call(6), padding="a" * 1193417)
        bridge.send(request)

        time.sleep(1.5)
        self.assertEqual(app.read()["padding"], request["padding"])
        self.assertIsNone(bridge.proc.poll())
        log = "".join(bridge.log_lines())
        self.assertNotIn("send error", log, log)

    def test_the_app_leaving_never_aborts_python(self):
        app, bridge = self.connected_pair()
        app.drop()
        self.assertTrue(bridge.wait_for_log("closed connection"))

        # stdin stays open here: exiting with a thread blocked on it is what aborted
        time.sleep(1.0)
        self.assertIsNone(bridge.proc.poll())
        self.assert_no_abort(bridge)

        self.assertEqual(bridge.finish(), 0)
        self.assert_no_abort(bridge)


if __name__ == "__main__":
    unittest.main()
