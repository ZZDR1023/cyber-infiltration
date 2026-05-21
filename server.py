#!/usr/bin/env python3
import html
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
API_KEY_FILE = Path.home() / "sss" / "zhipu.md"
DB_FILE = Path(__file__).with_name("leaderboard.sqlite3")
AI_MODEL = "glm-4-flash-250414"
MAX_TAUNT_LEN = 50
FALLBACK_TAUNT = "网络连接中断。你连直面我的资格都没有。"
SYSTEM_PROMPT = "你是一个冷酷、傲慢、高维度的赛博主机意识，像 Agent Smith 一样俯视入侵者。你的回答必须是中文，最多50个汉字，语气像网络防火墙反派在嘲讽失败的黑客。不要解释，不要换行。"
REQUEST_WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 12
TRUSTED_PROXY_HOSTS = {"127.0.0.1", "::1"}
request_log = {}


def read_api_key():
    text = API_KEY_FILE.read_text(encoding="utf-8")
    matches = re.findall(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", text)
    if not matches:
        raise RuntimeError("BigModel API key not found")
    return matches[-1]


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias TEXT NOT NULL,
                score INTEGER NOT NULL,
                survival_time REAL NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_leaderboard_rank ON leaderboard(score DESC, survival_time DESC, created_at ASC)"
        )


def sanitize_alias(value):
    alias = re.sub(r"\s+", " ", str(value or "匿名骇客")).strip()
    safe_alias = html.escape(alias[:20] or "匿名骇客", quote=True)
    return safe_alias


def sanitize_taunt(text):
    content = re.sub(r"\s+", " ", str(text or "")).strip()
    return content[:MAX_TAUNT_LEN] or FALLBACK_TAUNT


def is_rate_limited(client_ip):
    now = time.monotonic()
    recent = [ts for ts in request_log.get(client_ip, []) if now - ts < REQUEST_WINDOW_SECONDS]
    request_log[client_ip] = [*recent, now]
    return len(recent) >= MAX_REQUESTS_PER_WINDOW


def is_same_origin(headers, require_origin=False):
    host = headers.get("Host", "")
    origin = headers.get("Origin")
    if not origin:
        return not require_origin
    parsed = urllib.parse.urlparse(origin)
    return parsed.netloc == host


def add_leaderboard_entry(alias, score, survival_time):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO leaderboard(alias, score, survival_time, created_at) VALUES (?, ?, ?, ?)",
            (alias, score, survival_time, int(time.time() * 1000)),
        )


def get_leaderboard(limit=10):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT alias, score, survival_time, created_at
            FROM leaderboard
            ORDER BY score DESC, survival_time DESC, created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


class Handler(SimpleHTTPRequestHandler):
    def get_client_ip(self):
        host = self.client_address[0]
        if host in TRUSTED_PROXY_HOSTS:
            forwarded = self.headers.get("CF-Connecting-IP") or self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if forwarded:
                return forwarded
        return host

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/leaderboard":
            query = urllib.parse.parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", [10])[0] or 10)
            except (TypeError, ValueError):
                limit = 10
            limit = max(1, min(50, limit))
            self.send_json({"entries": get_leaderboard(limit)})
            return
        super().do_GET()

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(min(length, 4096))
        return json.loads(body or b"{}")

    def handle_leaderboard_post(self):
        if not is_same_origin(self.headers, require_origin=True):
            self.send_error(403)
            return
        if is_rate_limited(self.get_client_ip()):
            self.send_error(429)
            return
        try:
            payload = self.read_json_body()
            alias = sanitize_alias(payload.get("alias"))
            score = max(0, min(999999999, int(payload.get("score") or 0)))
            survival_time = max(0.0, min(9999.0, float(payload.get("time") or 0)))
            add_leaderboard_entry(alias, score, survival_time)
            self.send_json({"entries": get_leaderboard()})
        except (TypeError, ValueError, json.JSONDecodeError):
            self.send_error(400)

    def do_POST(self):
        if not is_same_origin(self.headers, require_origin=True):
            self.send_error(403)
            return
        if self.path == "/api/leaderboard":
            self.handle_leaderboard_post()
            return
        if self.path != "/api/ai-taunt":
            self.send_error(404)
            return
        if is_rate_limited(self.get_client_ip()):
            self.send_json({"text": FALLBACK_TAUNT}, status=200)
            return

        try:
            payload = self.read_json_body()
            alias = sanitize_alias(payload.get("alias") or "无名骇客")
            seconds = float(payload.get("seconds") or 0)
            user_prompt = f"有一个代号为 {alias} 的人类黑客试图潜入你的核心数据库，但他只坚持了 {seconds:.1f} 秒就被你的基础防火墙拦截了。请用极其傲慢、冷酷且带有一点幽默的赛博朋克反派语气嘲讽他的技术，字数限制在 50 字以内。"
            upstream_payload = {
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.9,
                "max_tokens": 90,
                "stream": False,
            }
            request = urllib.request.Request(
                API_URL,
                data=json.dumps(upstream_payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {read_api_key()}",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            self.send_json({"text": sanitize_taunt(content)})
        except Exception as error:
            print("[ai-taunt] fallback:", error)
            self.send_json({"text": FALLBACK_TAUNT}, status=200)

    def send_json(self, data, status=200):
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", 8787), Handler)
    print("Serving on http://127.0.0.1:8787")
    server.serve_forever()
