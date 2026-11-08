# 習題 1：類似 curl 的專案程式 — pycurl

用 Python **標準函式庫**（`socket`、`ssl`）從零實作的 HTTP 命令列用戶端，不使用 `requests` 或 `urllib.request`，自己組 HTTP/1.1 請求、自己解析回應。

## 檔案

檔案 | 說明
-----|-----
[pycurl.py](pycurl.py) | 主程式
[test_pycurl.py](test_pycurl.py) | 單元測試（在本機啟動測試用 HTTP 伺服器）

## 支援功能

參數 | 功能 | 對應 curl
-----|------|---------
`-X METHOD` | 指定 HTTP 方法 | `curl -X`
`-H "K: V"` | 自訂 header（可重複） | `curl -H`
`-d DATA` / `-d @file` | 送出 body，預設改成 POST | `curl -d`
`-i` | 輸出包含回應 header | `curl -i`
`-I` | 只發 HEAD 請求 | `curl -I`
`-L` | 跟隨 3xx 重新導向 | `curl -L`
`-o FILE` | 存到檔案 | `curl -o`
`-v` | 顯示連線、請求、回應細節 | `curl -v`
`-k` | 不驗證 TLS 憑證 | `curl -k`
`-s` | 安靜模式 | `curl -s`

另外處理了：

* HTTPS（`ssl.wrap_socket` + SNI）
* `Transfer-Encoding: chunked`
* `Content-Encoding: gzip / deflate` 自動解壓
* 相對路徑的 `Location`（`urljoin`）
* 303 / POST 被 301、302 導向時改成 GET（跟 curl 行為一致）

## 使用範例

```bash
python pycurl.py https://example.com
python pycurl.py -i https://httpbin.org/get
python pycurl.py -I https://www.google.com
python pycurl.py -X POST -H "Content-Type: application/json" -d '{"name":"pinyue"}' https://httpbin.org/post
python pycurl.py -L http://github.com -o github.html
python pycurl.py -v https://example.com
```

`-v` 輸出範例：

```
* Trying example.com:443...
* Connected to example.com port 443
* TLS connection using TLSv1.3 / TLS_AES_256_GCM_SHA384
> GET / HTTP/1.1
> Host: example.com
> User-Agent: pycurl/1.0
> Accept: */*
> Accept-Encoding: gzip, deflate
> Connection: close
>
< HTTP/1.1 200 OK
< Content-Type: text/html
...
```

## 測試

```bash
python -m unittest test_pycurl -v
```

```
test_connection_error ... ok
test_custom_method ... ok
test_get ... ok
test_gzip_and_chunked ... ok
test_head ... ok
test_include ... ok
test_post_json ... ok
test_redirect ... ok
test_url_parse ... ok
test_user_agent ... ok
----------------------------------------------------------------------
Ran 10 tests

OK
```

## 程式架構

```
main()
 ├─ parse_args()      解析命令列參數
 ├─ URL()             拆出 scheme / host / port / path
 └─ send()            一次 HTTP 往返
     ├─ socket.create_connection → (https) ssl.wrap_socket
     ├─ build_request()   組出 "GET /path HTTP/1.1\r\nHost: ...\r\n\r\n"
     ├─ read_until()      讀到 \r\n\r\n 取得狀態列與 header
     ├─ read_chunked() / Content-Length / 讀到連線關閉
     └─ decode_body()     gzip / deflate 解壓
```

## 學到的東西

1. HTTP 只是 TCP 上的純文字協定，header 跟 body 用一個空行 `\r\n\r\n` 隔開。
2. 讀 body 有三種情況：`Content-Length`、`chunked`、讀到連線關閉。
3. HTTPS 就是在 TCP socket 外面包一層 TLS，必須帶 `server_hostname` 才能做 SNI 跟憑證驗證。
4. curl 的離開碼 7 代表連不上主機，本程式也沿用。
