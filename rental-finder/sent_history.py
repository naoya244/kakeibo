"""
送信済み物件の履歴管理モジュール
GitHub Actions Cacheを利用して、既に通知した物件を追跡する
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta

HISTORY_FILE = Path(__file__).parent / "sent_history.json"
# 30日を超えた履歴は自動削除（SUUMOから消えた物件の掃除）
EXPIRY_DAYS = 30


def load_history() -> dict:
    """送信済み履歴を読み込む"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"sent": {}}
    return {"sent": {}}


def save_history(history: dict):
    """送信済み履歴を保存"""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def make_property_key(prop: dict) -> str:
    """物件のユニークキーを生成（建物名+間取り+面積+階数）"""
    return f"{prop['building_name']}|{prop['layout']}|{prop['area']}|{prop.get('floor_text', '')}"


def filter_new_properties(properties: list[dict]) -> list[dict]:
    """
    送信済み物件を除外し、新着物件のみを返す
    """
    history = load_history()
    sent = history.get("sent", {})

    # 期限切れの履歴を削除
    cutoff = (datetime.now() - timedelta(days=EXPIRY_DAYS)).isoformat()
    sent = {k: v for k, v in sent.items() if v.get("date", "") >= cutoff}

    new_properties = []
    for prop in properties:
        key = make_property_key(prop)
        if key not in sent:
            new_properties.append(prop)

    return new_properties


def mark_as_sent(properties: list[dict]):
    """物件を送信済みとして記録"""
    history = load_history()
    sent = history.get("sent", {})

    # 期限切れの履歴を削除
    cutoff = (datetime.now() - timedelta(days=EXPIRY_DAYS)).isoformat()
    sent = {k: v for k, v in sent.items() if v.get("date", "") >= cutoff}

    now = datetime.now().isoformat()
    for prop in properties:
        key = make_property_key(prop)
        sent[key] = {
            "date": now,
            "name": prop["building_name"],
            "rent": prop["rent"],
        }

    history["sent"] = sent
    save_history(history)
    print(f"送信済み履歴を更新: {len(sent)}件")
