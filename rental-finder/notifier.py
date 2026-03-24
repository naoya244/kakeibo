"""
LINE Messaging APIで物件情報を通知するモジュール
"""

from __future__ import annotations

import os
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)


def get_line_config():
    """LINE API設定を取得"""
    access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")

    if not access_token:
        raise ValueError(
            "LINE_CHANNEL_ACCESS_TOKEN が設定されていません。\n"
            ".env ファイルに LINE_CHANNEL_ACCESS_TOKEN=xxx を設定してください。"
        )
    if not user_id:
        raise ValueError(
            "LINE_USER_ID が設定されていません。\n"
            ".env ファイルに LINE_USER_ID=xxx を設定してください。"
        )

    return access_token, user_id


def send_line_message(text: str) -> bool:
    """LINEにテキストメッセージを送信"""
    access_token, user_id = get_line_config()

    configuration = Configuration(access_token=access_token)

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            push_request = PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text)],
            )
            line_bot_api.push_message(push_request)
            print("LINE通知を送信しました")
            return True
    except Exception as e:
        print(f"LINE通知の送信に失敗: {e}")
        return False


def send_property_notifications(properties: list[dict]) -> int:
    """
    物件リストをLINEで通知する
    LINE Messaging APIの制限:
    - 1メッセージ最大5000文字
    - 1リクエスト最大5メッセージ
    """
    from ranker import format_property_summary

    if not properties:
        send_line_message(
            "🏠 本日の物件通知\n\n"
            "条件に合うA/Bランク物件は見つかりませんでした。"
        )
        return 0

    # ヘッダーメッセージ
    header = (
        f"🏠 本日の物件通知\n"
        f"A/Bランク: {len(properties)}件\n"
        f"{'─' * 20}"
    )

    # 物件ごとにメッセージを構築
    messages = [header]
    current_message = ""

    for i, prop in enumerate(properties):
        summary = format_property_summary(prop)
        entry = f"\n\n{'═' * 25}\n{summary}"

        # 5000文字制限のチェック
        if len(current_message + entry) > 4500:
            messages.append(current_message)
            current_message = entry
        else:
            current_message += entry

    if current_message:
        messages.append(current_message)

    # LINEに送信（5メッセージずつ）
    sent_count = 0
    for i in range(0, len(messages), 1):  # 1メッセージずつ送信（安全のため）
        msg = messages[i]
        if msg.strip():
            if send_line_message(msg):
                sent_count += 1

    return sent_count
