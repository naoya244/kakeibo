"""
賃貸物件検索の設定ファイル
"""

# 検索対象の駅とSUUMOの駅コード (ek_XXXXX)
STATIONS = {
    # 既存
    "蒲田": {"ek": "08940", "area": "tokyo"},
    "川崎": {"ek": "09920", "area": "kanagawa"},
    "鶴見": {"ek": "25070", "area": "kanagawa"},
    "東神奈川": {"ek": "31790", "area": "kanagawa"},
    "横浜": {"ek": "40940", "area": "kanagawa"},
    "武蔵小杉": {"ek": "38720", "area": "kanagawa"},
    # 追加: 蒲田〜横浜周辺の割安エリア
    "大森": {"ek": "06160", "area": "tokyo"},
    "大井町": {"ek": "05410", "area": "tokyo"},
    "戸塚": {"ek": "24550", "area": "kanagawa"},
    "保土ケ谷": {"ek": "37630", "area": "kanagawa"},
    "新子安": {"ek": "17760", "area": "kanagawa"},
    "矢向": {"ek": "39740", "area": "kanagawa"},
    "尻手": {"ek": "17560", "area": "kanagawa"},
    "菊名": {"ek": "10670", "area": "kanagawa"},
    "綱島": {"ek": "25190", "area": "kanagawa"},
    "日吉": {"ek": "31380", "area": "kanagawa"},
    "新丸子": {"ek": "18410", "area": "kanagawa"},
    "元住吉": {"ek": "39260", "area": "kanagawa"},
    "平間": {"ek": "31690", "area": "kanagawa"},
}

# 検索条件
SEARCH_CONDITIONS = {
    "rent_min": 15.0,      # 万円
    "rent_max": 25.0,      # 万円
    "area_min": 45,         # 平米
    "walk_max": 15,         # 分
    "pet_ok": True,         # ペット相談
    "layouts": ["1LDK", "2LDK"],  # 間取り
}

# ランク付けの重み（コスパ重視）
# スコアが高いほど良い物件
RANKING_WEIGHTS = {
    "cost_performance": 0.40,  # 相場に対する割安度（最重要）
    "space_per_cost": 0.20,    # 家賃あたりの広さ
    "station_distance": 0.15,  # 駅からの距離
    "building_age": 0.15,      # 築年数
    "floor": 0.10,             # 階数
}

# ランクの閾値
RANK_THRESHOLDS = {
    "A": 63,  # スコア63以上
    "B": 55,  # スコア55以上
    "C": 35,  # スコア35以上
    "D": 0,   # それ以下
}

# スクレイピング設定
SCRAPING_CONFIG = {
    "request_interval": 3,  # リクエスト間隔（秒）- robots.txt準拠
    "max_pages_per_station": 5,  # 駅あたりの最大取得ページ数
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# 各駅の家賃相場（1LDK/2LDK、参考値）
# コスパ計算に使用。定期的に更新推奨
MARKET_RENT = {
    "蒲田": {"1LDK": 13.0, "2LDK": 16.5},
    "川崎": {"1LDK": 12.5, "2LDK": 16.0},
    "鶴見": {"1LDK": 11.0, "2LDK": 14.0},
    "東神奈川": {"1LDK": 11.5, "2LDK": 14.5},
    "横浜": {"1LDK": 14.0, "2LDK": 18.0},
    "武蔵小杉": {"1LDK": 14.5, "2LDK": 18.5},
    "大森": {"1LDK": 13.5, "2LDK": 17.0},
    "大井町": {"1LDK": 14.0, "2LDK": 18.0},
    "戸塚": {"1LDK": 10.0, "2LDK": 13.0},
    "保土ケ谷": {"1LDK": 10.0, "2LDK": 13.0},
    "新子安": {"1LDK": 11.0, "2LDK": 14.0},
    "矢向": {"1LDK": 10.0, "2LDK": 13.0},
    "尻手": {"1LDK": 10.5, "2LDK": 13.5},
    "菊名": {"1LDK": 11.5, "2LDK": 15.0},
    "綱島": {"1LDK": 11.0, "2LDK": 14.5},
    "日吉": {"1LDK": 12.0, "2LDK": 15.5},
    "新丸子": {"1LDK": 13.0, "2LDK": 16.0},
    "元住吉": {"1LDK": 12.5, "2LDK": 15.5},
    "平間": {"1LDK": 10.5, "2LDK": 13.5},
}

# 未知の駅の場合のデフォルト相場（東京/神奈川の平均的な値）
DEFAULT_MARKET_RENT = {"1LDK": 12.0, "2LDK": 15.0, "default": 13.0}
