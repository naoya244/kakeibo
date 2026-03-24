# 賃貸物件検索＆LINE通知

SUUMOから条件に合う賃貸物件を自動検索し、コスパの良い物件をLINEで通知するサービス。

## 対象駅
蒲田 / 川崎 / 鶴見 / 東神奈川 / 横浜 / 武蔵小杉

## 検索条件
- 家賃: 15〜21万円
- 面積: 45m²以上
- 駅徒歩: 15分以内
- ペット相談可
- 間取り: 1LDK or 2LDK

## ランク付け（コスパ重視）
| ランク | 基準 | 通知 |
|-------|------|------|
| A | スコア75以上（かなりお得） | ✅ |
| B | スコア55以上（お得） | ✅ |
| C | スコア35以上（普通） | ❌ |
| D | スコア35未満 | ❌ |

スコアの算出:
- **コスパ（40%）**: 相場に対する割安度
- **広さ/家賃（20%）**: 家賃あたりの平米数
- **駅近（15%）**: 駅からの距離
- **築年数（15%）**: 築浅ほど高評価
- **階数（10%）**: 高層階ほど高評価

## セットアップ

### 1. LINE Messaging API の設定

1. [LINE Developers](https://developers.line.biz/console/) にログイン
2. プロバイダー → 新規チャネル → 「Messaging API」を選択
3. チャネル作成後:
   - 「Messaging API」タブ → **チャネルアクセストークン**を発行
   - 「チャネル基本設定」タブ → **あなたのユーザーID** を確認
4. 作成したLINE公式アカウントを友だち追加（QRコードから）

### 2. ローカル実行

```bash
cd rental-finder
pip install -r requirements.txt

# .envファイルを作成
cp .env.example .env
# .env を編集して LINE_CHANNEL_ACCESS_TOKEN と LINE_USER_ID を設定

# テスト通知
python main.py --test

# ドライラン（通知なし、スクレイピングのみ）
python main.py --dry

# 通常実行
python main.py
```

### 3. GitHub Actions で日次自動実行

1. GitHubリポジトリの Settings → Secrets and variables → Actions
2. 以下のシークレットを追加:
   - `LINE_CHANNEL_ACCESS_TOKEN`: チャネルアクセストークン
   - `LINE_USER_ID`: ユーザーID
3. pushすれば毎朝8時（JST）に自動実行
4. Actions タブから手動実行も可能（Run workflow）

## ファイル構成

```
rental-finder/
├── main.py          # メインスクリプト
├── scraper.py       # SUUMOスクレイピング
├── ranker.py        # ランク付けロジック
├── notifier.py      # LINE通知
├── config.py        # 設定（駅・条件・重み）
├── requirements.txt
├── .env.example
└── results/         # 検索結果JSON（自動生成）
```
