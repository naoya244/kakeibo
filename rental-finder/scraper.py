"""
SUUMOから賃貸物件情報をスクレイピングするモジュール
"""

from __future__ import annotations

import re
import time
import requests
from bs4 import BeautifulSoup
from config import STATIONS, SEARCH_CONDITIONS, SCRAPING_CONFIG


def build_station_search_url(station_name: str, page: int = 1) -> str:
    """駅コードベースのSUUMO検索URLを構築する"""
    cond = SEARCH_CONDITIONS
    station_info = STATIONS[station_name]
    ek = station_info["ek"]
    area = station_info["area"]

    # 駅コードベースのURL: /chintai/{area}/ek_{code}/
    base_url = "https://suumo.jp/chintai/{area}/ek_{ek}/".format(
        area=area, ek=ek
    )

    # 条件パラメータ
    params = {
        "cb": str(cond["rent_min"]),
        "ct": str(cond["rent_max"]),
        "mb": str(cond["area_min"]),
        "mt": "9999999",
        "et": str(cond["walk_max"]),
        "cn": "9999999",
        "pc": "50",
        "page": str(page),
    }

    # 間取り: md=04 (1LDK), md=07 (2LDK)
    extra_params = ""
    layout_map = {"1LDK": "04", "2LDK": "07", "3LDK": "10"}
    for layout in cond["layouts"]:
        if layout in layout_map:
            extra_params += "&md=" + layout_map[layout]

    # ペット可
    if cond["pet_ok"]:
        extra_params += "&tc=0401102"

    query_string = "&".join("{}={}".format(k, v) for k, v in params.items())
    query_string += extra_params

    return base_url + "?" + query_string


def parse_rent(rent_text: str) -> float | None:
    """家賃テキストから万円単位の数値を抽出"""
    # "15.5万円" -> 15.5
    match = re.search(r"([\d.]+)\s*万円", rent_text)
    if match:
        return float(match.group(1))
    # "155,000円" -> 15.5
    match = re.search(r"([\d,]+)\s*円", rent_text)
    if match:
        yen = int(match.group(1).replace(",", ""))
        return yen / 10000
    return None


def parse_area(area_text: str) -> float | None:
    """面積テキストから平米数を抽出"""
    match = re.search(r"([\d.]+)\s*m", area_text)
    if match:
        return float(match.group(1))
    return None


def parse_walk_time(access_text: str) -> int | None:
    """アクセステキストから徒歩分数を抽出"""
    match = re.search(r"歩(\d+)分", access_text)
    if match:
        return int(match.group(1))
    return None


def parse_building_age(age_text: str) -> int | None:
    """築年数テキストから年数を抽出"""
    if "新築" in age_text:
        return 0
    match = re.search(r"築(\d+)年", age_text)
    if match:
        return int(match.group(1))
    return None


def parse_floor(floor_text: str) -> int | None:
    """階数テキストから階数を抽出"""
    match = re.search(r"(\d+)階", floor_text)
    if match:
        return int(match.group(1))
    return None


def parse_layout(layout_text: str) -> str | None:
    """間取りテキストからレイアウトを抽出"""
    match = re.search(r"(\d[LDKS]+)", layout_text)
    if match:
        return match.group(1)
    return None


def scrape_station(station_name: str) -> list[dict]:
    """指定駅の物件情報をスクレイピングする"""
    properties = []
    config = SCRAPING_CONFIG

    headers = {
        "User-Agent": config["user_agent"],
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }

    for page in range(1, config["max_pages_per_station"] + 1):
        url = build_station_search_url(station_name, page)
        print(f"  [{station_name}] ページ {page} を取得中...")

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"  [{station_name}] エラー: {e}")
            break

        soup = BeautifulSoup(response.text, "html.parser")

        # 物件カセット（建物単位）
        cassetteItems = soup.find_all("div", class_="cassetteitem")

        if not cassetteItems:
            print(f"  [{station_name}] ページ {page} に物件なし。終了。")
            break

        for cassette in cassetteItems:
            # 建物情報
            building_name_tag = cassette.find("div", class_="cassetteitem_content-title")
            building_name = building_name_tag.text.strip() if building_name_tag else ""

            address_tag = cassette.find("li", class_="cassetteitem_detail-col1")
            address = address_tag.text.strip() if address_tag else ""

            # アクセス情報（複数路線の場合あり）
            access_col = cassette.find("li", class_="cassetteitem_detail-col2")
            access_items = access_col.find_all("div", class_="cassetteitem_detail-text") if access_col else []

            # 築年数・階建
            detail_col3 = cassette.find("li", class_="cassetteitem_detail-col3")
            age_and_floors = detail_col3.find_all("div") if detail_col3 else []
            building_age_text = age_and_floors[0].text.strip() if len(age_and_floors) > 0 else ""
            building_age = parse_building_age(building_age_text)

            # 各部屋の情報
            rooms = cassette.find_all("table", class_="cassetteitem_other")
            for room in rooms:
                tds = room.find_all("td")
                if len(tds) < 7:
                    continue

                # 階数
                floor_text = tds[2].text.strip()
                floor = parse_floor(floor_text)

                # 家賃
                rent_tag = tds[3].find("span", class_="cassetteitem_other-emphasis")
                rent_text = rent_tag.text.strip() if rent_tag else ""
                rent = parse_rent(rent_text)

                # 管理費
                admin_tag = tds[3].find("span", class_="cassetteitem_price--administration")
                admin_text = admin_tag.text.strip() if admin_tag else ""
                admin_fee = parse_rent(admin_text) or 0

                # 敷金・礼金
                deposit_tag = tds[4].find_all("span", class_="cassetteitem_price--deposit") if len(tds) > 4 else []
                gratuity_tag = tds[4].find_all("span", class_="cassetteitem_price--gratuity") if len(tds) > 4 else []
                deposit = deposit_tag[0].text.strip() if deposit_tag else "-"
                gratuity = gratuity_tag[0].text.strip() if gratuity_tag else "-"

                # 間取り・面積
                layout_tag = tds[5].find("span", class_="cassetteitem_madori") if len(tds) > 5 else None
                layout_text = layout_tag.text.strip() if layout_tag else ""
                layout = parse_layout(layout_text)

                area_tag = tds[5].find("span", class_="cassetteitem_menseki") if len(tds) > 5 else None
                area_text = area_tag.text.strip() if area_tag else ""
                area = parse_area(area_text)

                # 詳細リンク
                link_tag = room.find("a", class_="js-cassette_link_href")
                detail_url = ""
                if link_tag and link_tag.get("href"):
                    href = link_tag["href"]
                    if href.startswith("/"):
                        detail_url = f"https://suumo.jp{href}"
                    else:
                        detail_url = href

                # アクセス（最寄り駅と徒歩分数）
                walk_time = None
                access_info = ""
                all_access_text = ""
                for acc in access_items:
                    text = acc.text.strip()
                    all_access_text += text + " "
                    wt = parse_walk_time(text)
                    if wt is not None:
                        if walk_time is None or wt < walk_time:
                            walk_time = wt
                            access_info = text

                if rent is None or area is None:
                    continue

                prop = {
                    "station": station_name,
                    "building_name": building_name,
                    "address": address,
                    "access": access_info,
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
                    "layout": layout or layout_text,
                    "area": area,
                    "detail_url": detail_url,
                }
                properties.append(prop)

        # リクエスト間隔を守る
        time.sleep(config["request_interval"])

        # 次のページがあるか確認
        pagination = soup.find("div", class_="pagination-parts")
        if pagination:
            next_link = pagination.find("a", string=re.compile("次へ"))
            if not next_link:
                break
        else:
            break

    print(f"  [{station_name}] {len(properties)}件の物件を取得")
    return properties


def scrape_all_stations() -> list[dict]:
    """全駅の物件情報をスクレイピングする"""
    all_properties = []

    for station_name in STATIONS:
        print(f"\n{'='*50}")
        print(f"  {station_name}駅 の物件を検索中...")
        print(f"{'='*50}")
        properties = scrape_station(station_name)
        all_properties.extend(properties)

        # 駅間でも間隔を空ける
        time.sleep(SCRAPING_CONFIG["request_interval"])

    # 重複除去（建物名+階数+家賃+面積で判定）
    seen = set()
    unique = []
    for prop in all_properties:
        key = (prop["building_name"], prop["floor_text"], prop["rent"], prop["area"])
        if key not in seen:
            seen.add(key)
            unique.append(prop)

    print(f"\n合計: {len(unique)}件（重複除去後）")
    return unique
