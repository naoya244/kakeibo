"""
物件のランク付けモジュール
コスパ重視: 「XXの割に安い」を高評価
"""

from __future__ import annotations

from config import RANKING_WEIGHTS, RANK_THRESHOLDS, MARKET_RENT


def calculate_cost_performance_score(prop: dict) -> float:
    """
    相場に対する割安度を計算（0-100）
    相場より安いほど高スコア
    """
    station = prop["station"]
    layout = prop["layout"]
    total_cost = prop["total_cost"]

    # 相場を取得
    market = MARKET_RENT.get(station, {})
    # レイアウトに応じた相場。マッチしなければ全体平均
    if "2LDK" in layout:
        market_rent = market.get("2LDK", 16.0)
    elif "1LDK" in layout:
        market_rent = market.get("1LDK", 12.0)
    else:
        market_rent = sum(market.values()) / len(market) if market else 14.0

    # 割安率（相場との差分の割合）
    # 例: 相場16万で家賃14万 → (16-14)/16 = 12.5% 割安
    discount_rate = (market_rent - total_cost) / market_rent

    # -30%（相場より高い）～+30%（相場より安い）を 0-100 にマッピング
    score = ((discount_rate + 0.30) / 0.60) * 100
    return max(0, min(100, score))


def calculate_space_per_cost_score(prop: dict) -> float:
    """
    家賃あたりの広さスコア（0-100）
    広い割に安い = 高スコア
    """
    area = prop["area"]
    total_cost = prop["total_cost"]

    if total_cost <= 0:
        return 0

    # 平米/万円 を計算
    space_ratio = area / total_cost

    # 2.0 平米/万円（狭い/高い）～ 4.0 平米/万円（広い/安い）を 0-100 にマッピング
    score = ((space_ratio - 2.0) / 2.0) * 100
    return max(0, min(100, score))


def calculate_station_distance_score(prop: dict) -> float:
    """
    駅距離スコア（0-100）
    近いほど高スコア
    """
    walk_time = prop.get("walk_time")
    if walk_time is None:
        return 50  # 不明な場合は中間値

    # 1分=100, 15分=0 の線形スコア
    score = ((15 - walk_time) / 14) * 100
    return max(0, min(100, score))


def calculate_building_age_score(prop: dict) -> float:
    """
    築年数スコア（0-100）
    築浅ほど高スコア
    """
    age = prop.get("building_age")
    if age is None:
        return 50  # 不明な場合は中間値

    # 新築=100, 築40年=0 の線形スコア
    score = ((40 - age) / 40) * 100
    return max(0, min(100, score))


def calculate_floor_score(prop: dict) -> float:
    """
    階数スコア（0-100）
    高層階ほど高スコア
    """
    floor = prop.get("floor")
    if floor is None:
        return 50

    # 1階=20, 2階=40, 5階以上=100
    if floor <= 1:
        return 20
    elif floor <= 2:
        return 40
    elif floor <= 3:
        return 60
    elif floor <= 5:
        return 80
    else:
        return 100


def calculate_total_score(prop: dict) -> float:
    """総合スコアを計算（0-100）"""
    weights = RANKING_WEIGHTS

    scores = {
        "cost_performance": calculate_cost_performance_score(prop),
        "space_per_cost": calculate_space_per_cost_score(prop),
        "station_distance": calculate_station_distance_score(prop),
        "building_age": calculate_building_age_score(prop),
        "floor": calculate_floor_score(prop),
    }

    total = sum(scores[key] * weights[key] for key in weights)

    # デバッグ用にスコア詳細を保存
    prop["scores"] = scores
    prop["total_score"] = round(total, 1)

    return total


def assign_rank(score: float) -> str:
    """スコアからランクを判定"""
    thresholds = RANK_THRESHOLDS
    if score >= thresholds["A"]:
        return "A"
    elif score >= thresholds["B"]:
        return "B"
    elif score >= thresholds["C"]:
        return "C"
    else:
        return "D"


def rank_properties(properties: list[dict]) -> list[dict]:
    """物件リストにスコアとランクを付与"""
    for prop in properties:
        score = calculate_total_score(prop)
        prop["rank"] = assign_rank(score)

    # スコア降順でソート
    properties.sort(key=lambda x: x["total_score"], reverse=True)

    return properties


def get_top_properties(properties: list[dict], ranks: list[str] = None) -> list[dict]:
    """指定ランクの物件のみ抽出"""
    if ranks is None:
        ranks = ["A", "B"]

    return [p for p in properties if p["rank"] in ranks]


def format_property_summary(prop: dict) -> str:
    """物件情報を人間が読みやすい形式にフォーマット"""
    scores = prop.get("scores", {})

    # コスパの表現
    cp_score = scores.get("cost_performance", 0)
    if cp_score >= 70:
        cp_label = "かなり割安"
    elif cp_score >= 55:
        cp_label = "やや割安"
    elif cp_score >= 45:
        cp_label = "相場並み"
    else:
        cp_label = "やや割高"

    lines = [
        f"{'⭐' * ('ABCD'.index(prop['rank']) * -1 + 4)} ランク{prop['rank']}（スコア: {prop['total_score']}）",
        f"",
        f"📍 {prop['building_name']}",
        f"   {prop['address']}",
        f"   {prop.get('access', '')}",
        f"",
        f"💰 家賃 {prop['rent']}万円（管理費込 {prop['total_cost']:.1f}万円）",
        f"   敷金: {prop['deposit']} / 礼金: {prop['gratuity']}",
        f"   → {cp_label}",
        f"",
        f"🏠 {prop['layout']} / {prop['area']}m² / {prop.get('floor_text', '?')}",
        f"   {prop.get('building_age_text', '')}",
        f"",
    ]

    if prop.get("detail_url"):
        lines.append(f"🔗 {prop['detail_url']}")

    # スコア内訳（数値 + 5段階評価）
    lines.append("")
    lines.append("[スコア内訳]")
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
        lines.append("  {} {} ({:.0f})".format(label, grade, s))

    return "\n".join(lines)
