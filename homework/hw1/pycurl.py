#!/usr/bin/env python3
"""pycurl.py -- 一個類似 curl 的命令列 HTTP 用戶端（只用 Python 標準函式庫）

直接用 socket 組出 HTTP/1.1 請求並解析回應，HTTPS 用 ssl 包裝 socket。

用法範例：
    python pycurl.py https://example.com
    python pycurl.py -i https://httpbin.org/get
    python pycurl.py -I https://example.com
    python pycurl.py -X POST -H "Content-Type: application/json" -d '{"a":1}' https://httpbin.org/post
    python pycurl.py -L http://github.com
    python pycurl.py -o page.html https://example.com
    python pycurl.py -v https://example.com
"""
import argparse
import gzip
import socket
import ssl
import sys
import zlib
from urllib.parse import urlsplit, urljoin

VERSION = "pycurl/1.0"


# ---------------------------------------------------------------- URL 解析
class URL:
    def __init__(self, raw):
        if "://" not in raw:
            raw = "http://" + raw  # 跟 curl 一樣，沒寫協定就當 http
        p = urlsplit(raw)
        if p.scheme not in ("http", "https"):
            raise ValueError(f"不支援的協定: {p.scheme}")
        self.scheme = p.scheme
        self.host = p.hostname or ""
        self.port = p.port or (443 if p.scheme == "https" else 80)
        self.path = (p.path or "/") + (("?" + p.query) if p.query else "")
        self.raw = raw

    def host_header(self):
        default = 443 if self.scheme == "https" else 80
        return self.host if self.port == default else f"{self.host}:{self.port}"


# ---------------------------------------------------------------- 回應物件
class Response:
    def __init__(self, status_line, headers, body):
        self.status_line = status_line
        parts = status_line.split(" ", 2)
        self.version = parts[0]
        self.status = int(parts[1]) if len(parts) > 1 else 0
        self.reason = parts[2] if len(parts) > 2 else ""
        self.headers = headers  # list[(name, value)]，保留原始順序
        self.body = body

    def header(self, name):
        name = name.lower()
        for k, v in self.headers:
            if k.lower() == name:
                return v
        return None

    def head_text(self):
        lines = [self.status_line] + [f"{k}: {v}" for k, v in self.headers]
        return "\r\n".join(lines) + "\r\n\r\n"


# ---------------------------------------------------------------- 讀取工具
def read_until(sock_file, marker=b"\r\n\r\n"):
    data = b""
    while not data.endswith(marker):
        ch = sock_file.read(1)
        if not ch:
            break
        data += ch
    return data


def read_chunked(f):
    """解析 Transfer-Encoding: chunked"""
    body = b""
    while True:
        line = f.readline().strip()
        if not line:
            break
        size = int(line.split(b";")[0], 16)
        if size == 0:
            f.readline()  # 結尾的空行（忽略 trailer）
            break
        body += f.read(size)
        f.readline()  # 每個 chunk 後的 CRLF
    return body


def decode_body(body, encoding):
    if not encoding:
        return body
    encoding = encoding.lower()
    if encoding == "gzip":
        return gzip.decompress(body)
    if encoding == "deflate":
        try:
            return zlib.decompress(body)
        except zlib.error:
            return zlib.decompress(body, -zlib.MAX_WBITS)
    return body


# ---------------------------------------------------------------- 發送請求
def build_request(method, url, headers, data):
    hdrs = {
        "Host": url.host_header(),
        "User-Agent": VERSION,
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    }
    if data is not None:
        hdrs["Content-Length"] = str(len(data))
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    # 使用者指定的 header 覆蓋預設值（大小寫不敏感）
    for h in headers:
        if ":" not in h:
            continue
        k, v = h.split(":", 1)
        for existing in list(hdrs):
            if existing.lower() == k.strip().lower():
                del hdrs[existing]
        hdrs[k.strip()] = v.strip()
    lines = [f"{method} {url.path} HTTP/1.1"] + [f"{k}: {v}" for k, v in hdrs.items()]
    req = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    if data is not None:
        req += data
    return req


def send(method, url, headers, data, timeout, insecure, log):
    log(f"* Trying {url.host}:{url.port}...")
    sock = socket.create_connection((url.host, url.port), timeout=timeout)
    log(f"* Connected to {url.host} port {url.port}")
    if url.scheme == "https":
        ctx = ssl.create_default_context()
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        sock = ctx.wrap_socket(sock, server_hostname=url.host)
        log(f"* TLS connection using {sock.version()} / {sock.cipher()[0]}")

    req = build_request(method, url, headers, data)
    for line in req.split(b"\r\n\r\n", 1)[0].decode("latin-1").split("\r\n"):
        log("> " + line)
    log(">")
    sock.sendall(req)

    f = sock.makefile("rb")
    head = read_until(f).decode("latin-1")
    lines = [l for l in head.split("\r\n") if l]
    if not lines:
        raise ConnectionError("伺服器沒有回應")
    status_line, header_lines = lines[0], lines[1:]
    headers = []
    for l in header_lines:
        if ":" in l:
            k, v = l.split(":", 1)
            headers.append((k.strip(), v.strip()))
    for l in lines:
        log("< " + l)
    log("<")

    resp = Response(status_line, headers, b"")
    if method == "HEAD" or resp.status in (204, 304) or 100 <= resp.status < 200:
        body = b""
    elif (resp.header("Transfer-Encoding") or "").lower() == "chunked":
        body = read_chunked(f)
    elif resp.header("Content-Length") is not None:
        body = f.read(int(resp.header("Content-Length")))
    else:
        body = f.read()  # Connection: close，讀到結束
    f.close()
    sock.close()
    resp.body = decode_body(body, resp.header("Content-Encoding"))
    return resp


# ---------------------------------------------------------------- 主程式
def parse_args(argv):
    p = argparse.ArgumentParser(prog="pycurl", description="類似 curl 的 HTTP 用戶端")
    p.add_argument("url")
    p.add_argument("-X", "--request", dest="method", help="HTTP 方法 (GET/POST/PUT/DELETE...)")
    p.add_argument("-H", "--header", action="append", default=[], help="自訂 header，可重複")
    p.add_argument("-d", "--data", help="請求內容；用 @檔名 可讀檔")
    p.add_argument("-i", "--include", action="store_true", help="輸出包含回應 header")
    p.add_argument("-I", "--head", action="store_true", help="只發 HEAD，顯示 header")
    p.add_argument("-L", "--location", action="store_true", help="跟隨重新導向")
    p.add_argument("-o", "--output", help="把內容寫入檔案")
    p.add_argument("-v", "--verbose", action="store_true", help="顯示詳細過程")
    p.add_argument("-k", "--insecure", action="store_true", help="不驗證 TLS 憑證")
    p.add_argument("-s", "--silent", action="store_true", help="安靜模式")
    p.add_argument("--max-redirs", type=int, default=10)
    p.add_argument("--max-time", type=float, default=30.0)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    log = (lambda m: print(m, file=sys.stderr)) if args.verbose else (lambda m: None)

    data = None
    if args.data is not None:
        if args.data.startswith("@"):
            with open(args.data[1:], "rb") as fh:
                data = fh.read()
        else:
            data = args.data.encode("utf-8")

    method = args.method or ("HEAD" if args.head else ("POST" if data is not None else "GET"))
    try:
        url = URL(args.url)
        for _ in range(args.max_redirs + 1):
            resp = send(method, url, args.header, data, args.max_time, args.insecure, log)
            loc = resp.header("Location")
            if args.location and loc and resp.status in (301, 302, 303, 307, 308):
                if args.include and not args.head:
                    sys.stdout.write(resp.head_text())
                log(f"* Redirect to {loc}")
                url = URL(urljoin(url.raw, loc))
                if resp.status == 303 or (resp.status in (301, 302) and method == "POST"):
                    method, data = "GET", None
                continue
            break
        else:
            print(f"pycurl: 超過最大重新導向次數 {args.max_redirs}", file=sys.stderr)
            return 47
    except (OSError, ValueError, ConnectionError) as e:
        if not args.silent:
            print(f"pycurl: 錯誤: {e}", file=sys.stderr)
        return 7

    out = b""
    if args.include or args.head:
        out += resp.head_text().encode("latin-1")
    out += resp.body
    if args.output:
        with open(args.output, "wb") as fh:
            fh.write(out)
        if not args.silent:
            print(f"已儲存 {len(out)} bytes 到 {args.output}", file=sys.stderr)
    else:
        try:
            sys.stdout.buffer.write(out)
            sys.stdout.flush()
        except BrokenPipeError:  # 例如輸出接到 head 時
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
