"""
賃貸物件検索＆LINE通知 メインスクリプト

使い方:
  python main.py          # 通常実行（スクレイピング＋LINE通知）
  python main.py --dry    # ドライラン（スクレイピングのみ、通知なし）
  python main.py --test   # テスト通知（ダミーデータでLINE通知テスト）
"""

from __future__ import annotations

import sys
import json
import os
from datetime import datetime
from pathlib import Path

# .envファイルがあれば読み込む
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

from scraper import scrape_all_stations
from ranker import rank_properties, get_top_properties, format_property_summary
from notifier import send_line_message, send_property_notifications
from sent_history import filter_new_properties, mark_as_sent
from config import SCRAPING_CONFIG


def save_results(properties: list[dict], filename: str = None):
    """結果をJSONファイルに保存"""
    if filename is None:
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"results_{date_str}.json"

    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    filepath = output_dir / filename

    # JSON保存用にscoresを文字列化
    save_data = []
    for prop in properties:
        p = prop.copy()
        if "scores" in p:
            p["scores"] = {k: round(v, 1) for k, v in p["scores"].items()}
        save_data.append(p)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    print(f"結果を保存: {filepath}")
    return filepath


def run_test_notification():
    """テスト通知を送信"""
    print("テスト通知を送信します...")
    send_line_message(
        "🏠 賃貸物件通知テスト\n\n"
        "このメッセージが届いていればLINE通知の設定は成功です！\n"
        f"送信時刻: {datetime.now().strftime('%Y/%m/%d %H:%M')}"
    )


def main():
    dry_run = "--dry" in sys.argv
    test_mode = "--test" in sys.argv

    if test_mode:
        run_test_notification()
        return

    print(f"{'='*60}")
    print(f"  賃貸物件検索 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"{'='*60}")

    # 1. スクレイピング
    print("\n[1/4] 物件情報を取得中...")
    properties = scrape_all_stations()

    if not properties:
        print("物件が見つかりませんでした。")
        if not dry_run:
            send_line_message("🏠 本日の物件通知\n\n条件に合う物件は見つかりませんでした。")
        return

    # 2. 一次ランク付け（設備情報なし）
    print("\n[2/5] 一次ランク付け中...")
    ranked = rank_properties(properties)

    # A/B/C上位を候補として抽出（詳細取得対象）
    candidates = get_top_properties(ranked, ["A", "B"])
    # C上位も含める（設備加点でBに上がる可能性）
    c_props = [p for p in ranked if p["rank"] == "C" and p["total_score"] >= 50]
    candidates.extend(c_props[:10])  # C上位10件まで

    # 3. 候補物件の詳細ページから設備情報を取得
    print(f"\n[3/5] 候補{len(candidates)}件の設備情報を取得中...")
    from ranker import fetch_equipment_from_detail
    import time as _time
    for i, prop in enumerate(candidates):
        url = prop.get("detail_url", "")
        if url:
            print(f"  [{i+1}/{len(candidates)}] {prop['building_name'][:20]}...")
            equipment = fetch_equipment_from_detail(url)
            prop["equipment"] = equipment
            if equipment:
                print(f"    設備: {len(equipment)}項目")
            _time.sleep(SCRAPING_CONFIG["request_interval"])

    # 4. 再ランク付け（設備情報込み）
    print("\n[4/5] 最終ランク付け中...")
    ranked = rank_properties(properties)

    # ランク別集計
    rank_counts = {}
    for prop in ranked:
        rank = prop["rank"]
        rank_counts[rank] = rank_counts.get(rank, 0) + 1
    print(f"  ランク分布: {rank_counts}")

    # 結果保存
    save_results(ranked)

    # A/Bランクのみ抽出
    top = get_top_properties(ranked, ["A", "B"])
    print(f"  A/Bランク: {len(top)}件")

    # 3.5. 新着フィルター（送信済み物件を除外）
    new_top = filter_new_properties(top)
    print(f"  うち新着: {len(new_top)}件（既送信: {len(top) - len(new_top)}件）")

    # コンソールに表示
    for prop in new_top:
        print(f"\n{'─'*40}")
        print(format_property_summary(prop))

    # 4. LINE通知
    if dry_run:
        print(f"\n[4/4] ドライラン: LINE通知をスキップ")
        print(f"  通知対象: {len(new_top)}件の新着A/Bランク物件")
    else:
        print(f"\n[4/4] LINE通知を送信中...")
        if new_top:
            sent = send_property_notifications(new_top)
            mark_as_sent(new_top)
            print(f"  {sent}件のメッセージを送信しました")
        else:
            print("  新着物件なし。通知をスキップ。")

    print(f"\n{'='*60}")
    print(f"  完了！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
