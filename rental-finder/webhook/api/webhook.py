"""
LINE Webhook受信 → GitHub Actions起動
Vercel Serverless Function
"""

import hashlib
import hmac
import json
import os
import re
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


def push_message(text: str):
    """LINEにPushメッセージを送る（reply_tokenなしで送信）"""
    url = "https://api.line.me/v2/bot/message/push"
    user_id = os.environ.get("LINE_USER_ID", "")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['LINE_CHANNEL_ACCESS_TOKEN']}",
    }
    data = json.dumps({
        "to": user_id,
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


def trigger_property_analyze(property_url: str, reply_to: str = ""):
    """物件分析用のGitHub Actionsを起動"""
    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]
    token = os.environ["GITHUB_PAT"]

    url = f"https://api.github.com/repos/{owner}/{repo}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"url": property_url}
    if reply_to:
        payload["reply_to"] = reply_to
    data = json.dumps({
        "event_type": "property_analyze",
        "client_payload": payload,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.status


def extract_suumo_url(text: str) -> str | None:
    """テキストからSUUMO賃貸URLを抽出"""
    match = re.search(r"https?://suumo\.jp/chintai/[^\s]+", text)
    return match.group(0) if match else None


def is_other_realestate_url(text: str) -> bool:
    """SUUMO以外の不動産サイトURLが含まれるか判定"""
    pattern = r"https?://(www\.)?(homes\.co\.jp|athome\.co\.jp|chintai\.net|realestate\.yahoo\.co\.jp)"
    return bool(re.search(pattern, text))


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

            # 送信元を特定（グループ > ルーム > 個人）
            source = event.get("source", {})
            source_type = source.get("type", "")
            if source_type == "group":
                reply_to = source.get("groupId", "")
            elif source_type == "room":
                reply_to = source.get("roomId", "")
            else:
                reply_to = source.get("userId", "")

            # 1. SUUMO URL検出 → 物件分析
            suumo_url = extract_suumo_url(text)
            if suumo_url:
                try:
                    reply_message(
                        reply_token,
                        "🔍 物件を分析中です...\n"
                        "割安かどうか判定して結果をお送りします！（1〜2分）"
                    )
                except Exception as e:
                    print(f"Reply error: {e}")
                try:
                    status = trigger_property_analyze(suumo_url, reply_to=reply_to)
                    print(f"Property analyze triggered: {status}")
                except Exception as e:
                    print(f"Property analyze error: {e}")
                    try:
                        # エラー詳細にトークン等が含まれる可能性があるため、概要のみ通知
                        push_message("⚠️ 物件分析の起動に失敗しました。\nしばらく経ってから再度お試しください。")
                    except Exception:
                        pass
                continue

            # 2. 他の不動産サイトURL → 未対応メッセージ
            if is_other_realestate_url(text):
                reply_message(
                    reply_token,
                    "🏠 現在SUUMOの物件URLのみ対応しています。\n"
                    "SUUMOの物件ページURLを送ってください。\n\n"
                    "例: https://suumo.jp/chintai/jnc_XXXXXX/"
                )
                continue

            # 3. 物件検索トリガーワード
            trigger_words = ["物件", "探して", "検索", "部屋"]
            if any(word in text for word in trigger_words):
                # 即座に「検索中」と返信
                try:
                    reply_message(reply_token, "🔍 物件を検索中です...\n完了したら通知します！（1〜2分）")
                except Exception as e:
                    print(f"Reply error: {e}")
                # GitHub Actions起動
                try:
                    status = trigger_github_actions()
                    print(f"GitHub Actions triggered: {status}")
                except Exception as e:
                    print(f"GitHub Actions error: {e}")
                    # エラーをPushメッセージで通知
                    try:
                        push_message("⚠️ 検索の起動に失敗しました。\nしばらく経ってから再度お試しください。")
                    except Exception:
                        pass
            else:
                reply_message(
                    reply_token,
                    "🏠 物件探しbot\n\n"
                    "「物件探して」と送ると最新の物件を検索します！\n\n"
                    "📊 SUUMOのURLを送ると割安度を判定します！\n"
                    "例: https://suumo.jp/chintai/jnc_XXXXXX/"
                )

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Rental Finder Webhook is running")
