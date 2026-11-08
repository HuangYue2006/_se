"""pycurl 的測試：啟動一個本地 HTTP 伺服器，再用 pycurl 打它。

執行：python -m unittest test_pycurl.py -v
"""
import gzip
import io
import json
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pycurl


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/hello":
            self._send(200, b"hello world", {"Content-Type": "text/plain"})
        elif self.path == "/redirect":
            self._send(302, b"", {"Location": "/hello"})
        elif self.path == "/gzip":
            self._send(200, gzip.compress(b"compressed!"), {"Content-Encoding": "gzip"})
        elif self.path == "/chunked":
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for part in (b"ab", b"cde"):
                self.wfile.write(b"%x\r\n%s\r\n" % (len(part), part))
            self.wfile.write(b"0\r\n\r\n")
        elif self.path == "/headers":
            self._send(200, json.dumps(dict(self.headers)).encode())
        else:
            self._send(404, b"not found")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "11")
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        self._send(201, json.dumps({"method": "POST", "body": body.decode(),
                                    "type": self.headers.get("Content-Type")}).encode())

    def do_DELETE(self):
        self._send(200, b"deleted")


class TestPycurl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_curl(self, *args):
        buf = io.BytesIO()

        class Out:
            buffer = buf

            def write(self, s):
                buf.write(s.encode("latin-1"))

            def flush(self):
                pass

        with redirect_stdout(Out()):
            code = pycurl.main(list(args))
        return code, buf.getvalue()

    def test_url_parse(self):
        u = pycurl.URL("https://example.com:8443/a/b?x=1")
        self.assertEqual((u.scheme, u.host, u.port, u.path), ("https", "example.com", 8443, "/a/b?x=1"))
        self.assertEqual(pycurl.URL("example.com").port, 80)

    def test_get(self):
        code, out = self.run_curl(self.base + "/hello")
        self.assertEqual(code, 0)
        self.assertEqual(out, b"hello world")

    def test_include(self):
        _, out = self.run_curl("-i", self.base + "/hello")
        self.assertTrue(out.startswith(b"HTTP/1.1 200"))
        self.assertTrue(out.endswith(b"hello world"))

    def test_head(self):
        _, out = self.run_curl("-I", self.base + "/hello")
        self.assertIn(b"Content-Length: 11", out)
        self.assertFalse(out.endswith(b"hello world"))

    def test_post_json(self):
        _, out = self.run_curl("-H", "Content-Type: application/json", "-d", '{"a":1}', self.base + "/x")
        r = json.loads(out)
        self.assertEqual(r["body"], '{"a":1}')
        self.assertEqual(r["type"], "application/json")

    def test_custom_method(self):
        _, out = self.run_curl("-X", "DELETE", self.base + "/x")
        self.assertEqual(out, b"deleted")

    def test_redirect(self):
        _, out = self.run_curl(self.base + "/redirect")
        self.assertEqual(out, b"")  # 沒有 -L 不跟隨
        _, out = self.run_curl("-L", self.base + "/redirect")
        self.assertEqual(out, b"hello world")

    def test_gzip_and_chunked(self):
        self.assertEqual(self.run_curl(self.base + "/gzip")[1], b"compressed!")
        self.assertEqual(self.run_curl(self.base + "/chunked")[1], b"abcde")

    def test_user_agent(self):
        _, out = self.run_curl("-H", "User-Agent: test-agent", self.base + "/headers")
        self.assertEqual(json.loads(out)["User-Agent"], "test-agent")

    def test_connection_error(self):
        code, _ = self.run_curl("-s", "http://127.0.0.1:1/")
        self.assertEqual(code, 7)


if __name__ == "__main__":
    unittest.main()
