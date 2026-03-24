"""
SUUMO物件URLから割安度を分析するモジュール

使い方:
  python analyzer.py                          # 環境変数 PROPERTY_URL から取得（GitHub Actions用）
  python analyzer.py "https://suumo.jp/..."   # コマンドライン引数で指定
  python analyzer.py --dry "https://..."      # ドライラン（LINE通知なし）
"""

from __future__ import annotations

import json
import os
import re
import sys
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

import requests
from bs4 import BeautifulSoup

from config import STATIONS, SCRAPING_CONFIG, DEFAULT_MARKET_RENT
from scraper import (
    parse_rent,
    parse_area,
    parse_walk_time,
    parse_building_age,
    parse_floor,
    parse_layout,
)
from ranker import calculate_total_score, assign_rank
from notifier import send_line_message


def validate_suumo_url(url: str) -> bool:
    """SUUMO賃貸物件URLかどうかを検証"""
    return bool(re.match(r"https?://suumo\.jp/chintai/", url))


def extract_js_property_data(html: str) -> dict | None:
    """
    ページ内のJavaScriptオブジェクト gapSuumoPcForFr からデータを抽出。
    HTMLパースより信頼性が高い。
    """
    # gapSuumoPcForFr = [{...}] を探す
    match = re.search(
        r"gapSuumoPcForFr\s*=\s*\[(\{.*?\})\]", html, re.DOTALL
    )
    if not match:
        return None

    obj_str = match.group(1)

    # JavaScriptオブジェクトリテラルをJSONに変換
    # キー名にクォートがないので追加する
    json_str = re.sub(r'(\w+)\s*:', r'"\1":', obj_str)
    # シングルクォートをダブルクォートに
    json_str = json_str.replace("'", '"')
    # 末尾カンマを除去
    json_str = re.sub(r",\s*}", "}", json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def extract_property_name(soup: BeautifulSoup) -> str:
    """物件名をHTMLから抽出"""
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.text.strip()
        # 【SUUMO】プレフィックスを除去
        title_text = re.sub(r"^【SUUMO】\s*", "", title_text)
        # "物件名／住所／駅名" or "物件名の賃貸情報..." のフォーマットから物件名を取得
        for sep in ["／", "の賃貸", "｜", "|"]:
            if sep in title_text:
                return title_text.split(sep)[0].strip()
        return title_text

    return "（物件名不明）"


def extract_address(soup: BeautifulSoup) -> str:
    """住所をHTMLから抽出"""
    # dt/ddリストから「所在地」を探す
    for dt in soup.find_all("dt"):
        if "所在地" in dt.text:
            dd = dt.find_next_sibling("dd")
            if dd:
                return dd.text.strip()

    # テーブルからも探す
    for th in soup.find_all("th"):
        if "所在地" in th.text:
            td = th.find_next_sibling("td")
            if td:
                return td.text.strip()

    return ""


def find_matching_station(js_data: dict) -> str | None:
    """JSデータの駅コードから既知の駅名を特定"""
    # JSデータの ekiCd1, ekiCd2, ekiCd3 と config.STATIONS を照合
    for i in range(1, 4):
        eki_cd = js_data.get(f"ekiCd{i}", "")
        for station_name, info in STATIONS.items():
            if info["ek"] == eki_cd:
                return station_name
    return None


def scrape_property_detail(url: str) -> dict:
    """
    SUUMO物件詳細ページをスクレイピングして物件データを返す。
    ページ内のJavaScriptオブジェクトから構造化データを取得する。
    """
    headers = {
        "User-Agent": SCRAPING_CONFIG["user_agent"],
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # JavaScriptオブジェクトからデータ取得（最も信頼性が高い）
    js_data = extract_js_property_data(html)

    if js_data:
        return _build_property_from_js(js_data, soup, url)
    else:
        # JSデータがない場合はHTMLから抽出を試みる
        return _build_property_from_html(soup, url)


def _build_property_from_js(js_data: dict, soup: BeautifulSoup, url: str) -> dict:
    """JavaScriptオブジェクトから物件データを構築"""
    # 家賃（円 → 万円）
    chinryo = int(js_data.get("chinryo", 0))
    rent = chinryo / 10000 if chinryo else None

    # 管理費（円 → 万円）
    kanrihi = int(js_data.get("kanrihi", 0))
    admin_fee = kanrihi / 10000

    # 敷金・礼金（円表示用）
    shikikin = int(js_data.get("shikikin", 0))
    reikin = int(js_data.get("reikin", 0))
    deposit = f"{shikikin / 10000:.1f}万円" if shikikin else "-"
    gratuity = f"{reikin / 10000:.1f}万円" if reikin else "-"

    # 間取り
    layout = js_data.get("madoriDisp", "")

    # 面積
    menseki = js_data.get("mensekiDisp", "")
    area = float(menseki) if menseki else None

    # 築年数
    chikugonensu = js_data.get("chikugonensu", "")
    building_age = int(chikugonensu) if chikugonensu else None
    building_age_text = f"築{building_age}年" if building_age is not None else ""
    if building_age == 0:
        building_age_text = "新築"

    # 駅情報（最寄り駅 = 徒歩時間が最短の駅）
    best_walk_time = None
    best_access = ""
    all_access_lines = []

    for i in range(1, 4):
        ensen = js_data.get(f"ensenNm{i}", "")
        eki = js_data.get(f"ekiNm{i}", "")
        toho = js_data.get(f"tohoJikan{i}", "")

        if not ensen or not eki:
            continue

        walk_min = int(toho) if toho else None
        access_text = f"{ensen}/{eki}駅 歩{walk_min}分" if walk_min else f"{ensen}/{eki}駅"
        all_access_lines.append(access_text)

        if walk_min is not None and (best_walk_time is None or walk_min < best_walk_time):
            best_walk_time = walk_min
            best_access = access_text

    # 駅名の特定（既知の駅との照合）
    station = find_matching_station(js_data)
    if not station:
        # 既知の駅に一致しなければ、最寄り駅名をそのまま使う
        station = js_data.get("ekiNm1", "不明")

    # 階数はJSデータに含まれないのでHTMLから取得
    floor = None
    floor_text = ""
    for dt in soup.find_all("dt"):
        if "階" == dt.text.strip():
            dd = dt.find_next_sibling("dd")
            if dd:
                floor_text = dd.text.strip()
                floor = parse_floor(floor_text)
                break
    # テーブルからも試す
    if floor is None:
        for th in soup.find_all("th"):
            if "階" in th.text and "階建" not in th.text:
                td = th.find_next_sibling("td")
                if td:
                    floor_text = td.text.strip()
                    floor = parse_floor(floor_text)
                    break

    # 物件名
    building_name = extract_property_name(soup)

    # 住所
    address = extract_address(soup)
    if not address:
        todofuken = js_data.get("todofukenNm", "")
        shikugun = js_data.get("shikugunNm", "")
        address = f"{todofuken}{shikugun}"

    if rent is None:
        raise ValueError("家賃情報を取得できませんでした")

    return {
        "station": station,
        "building_name": building_name,
        "address": address,
        "access": best_access,
        "all_access": " / ".join(all_access_lines),
        "walk_time": best_walk_time,
        "building_age": building_age,
        "building_age_text": building_age_text,
        "floor": floor,
        "floor_text": floor_text,
        "rent": rent,
        "admin_fee": admin_fee,
        "total_cost": rent + admin_fee,
        "deposit": deposit,
        "gratuity": gratuity,
        "layout": layout,
        "area": area,
        "detail_url": url,
    }


def _build_property_from_html(soup: BeautifulSoup, url: str) -> dict:
    """
    HTMLのdt/ddリストから物件データを構築（JSデータがない場合のフォールバック）
    """
    data = {}

    # dt/ddペアを全て取得
    for dt in soup.find_all("dt"):
        label = dt.text.strip()
        dd = dt.find_next_sibling("dd")
        if dd:
            data[label] = dd.text.strip()

    # th/tdペアも取得
    for th in soup.find_all("th"):
        label = th.text.strip()
        td = th.find_next_sibling("td")
        if td:
            data[label] = td.text.strip()

    # 各フィールドを抽出
    rent_text = data.get("賃料", data.get("家賃", ""))
    rent = parse_rent(rent_text)

    admin_text = data.get("管理費・共益費", data.get("管理費", ""))
    admin_fee = parse_rent(admin_text) or 0

    deposit = data.get("敷金", "-")
    gratuity = data.get("礼金", "-")

    layout_text = data.get("間取り", "")
    layout = parse_layout(layout_text) or layout_text

    area_text = data.get("専有面積", data.get("面積", ""))
    area = parse_area(area_text)

    age_text = data.get("築年月", data.get("築年数", ""))
    building_age = parse_building_age(age_text)
    building_age_text = age_text

    floor_text = data.get("階", "")
    floor = parse_floor(floor_text)

    # アクセス情報
    access_text = data.get("交通", data.get("アクセス", ""))
    walk_time = parse_walk_time(access_text)

    # 駅名を推定
    station = "不明"
    for station_name in STATIONS:
        if station_name in access_text:
            station = station_name
            break

    building_name = extract_property_name(soup)
    address = extract_address(soup) or data.get("所在地", "")

    if rent is None:
        raise ValueError("家賃情報を取得できませんでした")

    return {
        "station": station,
        "building_name": building_name,
        "address": address,
        "access": access_text,
        "all_access": access_text,
        "walk_time": walk_time,
        "building_age": building_age,
        "building_age_text": building_age_text,
        "floor": floor,
        "floor_text": floor_text,
        "rent": rent,
        "admin_fee": admin_fee,
        "total_cost": rent + admin_fee,
        "deposit": deposit,
        "gratuity": gratuity,
        "layout": layout,
        "area": area,
        "detail_url": url,
    }


def format_analysis_result(prop: dict) -> str:
    """物件分析結果を読みやすくフォーマット"""
    scores = prop.get("scores", {})
    rank = prop.get("rank", "?")
    total_score = prop.get("total_score", 0)

    # ランクに応じた星の数
    rank_stars = {"A": 4, "B": 3, "C": 2, "D": 1}.get(rank, 0)
    stars = "⭐" * rank_stars

    # コスパ判定ラベル
    cp_score = scores.get("cost_performance", 0)
    if cp_score >= 70:
        cp_comment = " ← 相場より割安！"
    elif cp_score >= 55:
        cp_comment = " ← やや割安"
    elif cp_score >= 45:
        cp_comment = ""
    else:
        cp_comment = " ← やや割高"

    # 総評
    verdicts = {
        "A": "非常にお得な物件です！早めの検討をおすすめします。",
        "B": "コスパの良い物件です。検討の価値あり。",
        "C": "平均的な物件です。他の物件と比較してみましょう。",
        "D": "条件に対してやや割高です。",
    }
    verdict = verdicts.get(rank, "判定不能")

    # アクセス表示
    access_display = prop.get("all_access", prop.get("access", ""))

    lines = [
        "📊 物件分析レポート",
        "",
        f"🏠 {prop['building_name']}",
        f"📍 {prop['address']}",
        f"🚃 {access_display}",
        "",
        f"💰 家賃: {prop['rent']:.1f}万円（管理費込 {prop['total_cost']:.1f}万円）",
        f"   敷金: {prop['deposit']} / 礼金: {prop['gratuity']}",
    ]

    # 間取り・面積・階数
    specs = []
    if prop.get("layout"):
        specs.append(prop["layout"])
    if prop.get("area"):
        specs.append(f"{prop['area']}m²")
    if prop.get("floor_text"):
        specs.append(prop["floor_text"])
    if specs:
        lines.append(f"📐 {' / '.join(specs)}")

    if prop.get("building_age_text"):
        lines.append(f"🏗️ {prop['building_age_text']}")

    lines.extend([
        "",
        "━━━ 割安判定 ━━━",
        f"{stars} ランク{rank}（スコア: {total_score}/100）",
        f"→ {verdict}",
        "",
        "[スコア内訳]",
    ])

    # スコア内訳
    score_labels = {
        "cost_performance": "コスパ",
        "space_per_cost": "広さ/家賃",
        "station_distance": "駅近",
        "building_age": "築年数",
        "floor": "階数",
    }
    for key, label in score_labels.items():
        s = scores.get(key, 0)
        if s >= 80:
            grade = "◎"
        elif s >= 60:
            grade = "○"
        elif s >= 40:
            grade = "△"
        else:
            grade = "×"
        comment = cp_comment if key == "cost_performance" else ""
        lines.append(f"  {label:<6} {grade} ({s:.0f}){comment}")

    lines.extend([
        "",
        f"🔗 {prop['detail_url']}",
    ])

    return "\n".join(lines)


def analyze_property(url: str, dry_run: bool = False) -> dict:
    """物件URLを分析してLINE通知を送信"""
    print(f"物件URL: {url}")

    if not validate_suumo_url(url):
        error_msg = "⚠️ SUUMOの賃貸物件URLを指定してください。\n例: https://suumo.jp/chintai/jnc_XXXXXX/"
        if not dry_run:
            send_line_message(error_msg)
        print(error_msg)
        return {}

    print("物件ページを取得中...")
    try:
        prop = scrape_property_detail(url)
    except Exception as e:
        error_msg = f"⚠️ 物件情報の取得に失敗しました。\n{e}\n\nURLを確認してください:\n{url}"
        if not dry_run:
            send_line_message(error_msg)
        print(error_msg)
        return {}

    print(f"物件名: {prop['building_name']}")
    print(f"家賃: {prop['rent']}万円 (管理費込: {prop['total_cost']:.1f}万円)")
    print(f"駅: {prop['station']}")

    # スコアリング
    print("スコアリング中...")
    calculate_total_score(prop)
    prop["rank"] = assign_rank(prop["total_score"])

    print(f"スコア: {prop['total_score']} → ランク{prop['rank']}")

    # 分析結果をフォーマット
    message = format_analysis_result(prop)
    print(f"\n{message}")

    # LINE通知
    if not dry_run:
        print("\nLINE通知を送信中...")
        send_line_message(message)
        print("送信完了！")
    else:
        print("\n[ドライラン] LINE通知をスキップ")

    return prop


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry" in sys.argv

    # URLの取得: コマンドライン引数 > 環境変数
    url = args[0] if args else os.environ.get("PROPERTY_URL", "")

    if not url:
        print("使い方:")
        print('  python analyzer.py "https://suumo.jp/chintai/jnc_XXXXX/"')
        print('  python analyzer.py --dry "https://suumo.jp/chintai/jnc_XXXXX/"')
        print("  PROPERTY_URL=... python analyzer.py")
        sys.exit(1)

    analyze_property(url, dry_run=dry_run)


if __name__ == "__main__":
    main()
