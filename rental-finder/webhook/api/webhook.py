"""
LINE Webhook受信 → GitHub Actions起動
Vercel Serverless Function
"""

import hashlib
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request


def verify_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """LINE署名を検証"""
    hash_value = hmac.new(
        channel_secret.encode("utf-8"), body, hashlib.sha256
    ).digest()
    import base64
    expected = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(signature, expected)


def reply_message(reply_token: str, text: str):
    """LINEにリプライを返す"""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['LINE_CHANNEL_ACCESS_TOKEN']}",
    }
    data = json.dumps({
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.status


def trigger_github_actions():
    """GitHub Actionsのworkflow_dispatchを起動"""
    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]
    token = os.environ["GITHUB_PAT"]

    url = f"https://api.github.com/repos/{owner}/{repo}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = json.dumps({
        "event_type": "line_on_demand",
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.status


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # LINE署名検証
        signature = self.headers.get("X-Line-Signature", "")
        channel_secret = os.environ.get("LINE_CHANNEL_SECRET", "")

        if channel_secret and not verify_signature(body, signature, channel_secret):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        # イベント解析
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        events = data.get("events", [])
        for event in events:
            if event.get("type") != "message":
                continue
            if event.get("message", {}).get("type") != "text":
                continue

            text = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            # 物件検索トリガーワード
            trigger_words = ["物件", "探して", "検索", "部屋"]
            if any(word in text for word in trigger_words):
                try:
                    # 即座に「検索中」と返信
                    reply_message(reply_token, "🔍 物件を検索中です...\n完了したら通知します！（1〜2分）")
                    # GitHub Actions起動
                    trigger_github_actions()
                except Exception as e:
                    print(f"Error: {e}")
            else:
                reply_message(
                    reply_token,
                    "🏠 物件探しbot\n\n"
                    "「物件探して」と送ると最新の物件を検索します！"
                )

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Rental Finder Webhook is running")
