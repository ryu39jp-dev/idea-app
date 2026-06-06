# 💡 アイデア出し＆評価ループアプリ

AIが生成したアプリ企画を評価するたびに、あなたの好みを学習して次のアイデアを磨き続けるフィードバックループアプリです。

## 仕組み

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   [AIアイデア生成]                                           │
│        ↓                                                    │
│   [ユーザーが4軸で評価 + 本音フィードバック]                   │
│        ↓                                                    │
│   [評価をSQLiteに保存]                                       │
│        ↓                                                    │
│   [高評価例・低評価例・直近の不満 → 動的プロンプト生成]         │
│        ↓                                                    │
│   [Amazon Bedrock (Claude Haiku 4.5) でアイデア再生成]  ←──┘
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

評価を重ねるほど「あなたにとって刺さるアイデア」に近づいていきます。

---

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| フロントエンド | Streamlit |
| データベース | SQLite（起動時に自動生成） |
| LLM | Amazon Bedrock — Claude Haiku 4.5 |
| 認証 | AWS IAM（アクセスキー or IAMロール） |

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
python -m pip install -r requirements.txt   
```

### 2. AWS側の準備

#### ① IAMユーザーにBedrockの権限を付与

IAMポリシーに以下のアクションを許可してください：

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": "*"
}
```

#### ② Bedrockでモデルアクセスを有効化

AWSコンソール → **Amazon Bedrock** → **モデルアクセス** →
`Claude Haiku 4.5` を選択して **アクセスをリクエスト**

> ほとんどのモデルは即時承認されます。

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を開いて以下を入力：

```env
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_DEFAULT_REGION=ap-southeast-2
BEDROCK_MODEL_ID=anthropic.claude-haiku-4-5-20251001-v1:0
```

### 4. アプリを起動

```bash
streamlit run app.py
```

ブラウザで http://localhost:8501 が開きます。

---

## ファイル構成

```
.
├── app.py              # Streamlit メインアプリ（UI・セッション管理）
├── database.py         # SQLite CRUD（テーブル定義・挿入・取得）
├── llm_client.py       # Amazon Bedrock クライアント
├── prompt_builder.py   # 評価履歴から動的プロンプトを組み立てるロジック
├── requirements.txt    # 依存パッケージ
├── .env.example        # 環境変数テンプレート
├── .env                # 実際の認証情報（gitignore 推奨）
└── idea_eval.db        # SQLite DB（初回起動時に自動生成）
```

---

## 評価項目（4軸）

| # | 項目 | 問いかけ |
|---|------|----------|
| ① | 自分ニーズ度 | 自分が実際に欲しいと思えるか？ |
| ② | 感情のシンクロ度 | 「わかる」と共感できるか？ |
| ③ | 負の感情解消度 | モヤモヤ・だるさが解消されそうか？ |
| ④ | 意外性 | 驚きや新鮮さがあるか？ |

4項目の**平均スコアが高い**アイデアは Few-shot 例（目指すべき方向）として、
**平均スコアが低い**アイデアは「避けるべき例」としてプロンプトに自動組み込みされます。

---

## 使用モデルの変更

`.env` の `BEDROCK_MODEL_ID` を書き換えるだけで切り替えられます：

```env
# 高速・低コスト（デフォルト）
BEDROCK_MODEL_ID=anthropic.claude-haiku-4-5-20251001-v1:0

# より高精度にしたい場合
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20251001-v1:0

# 旧世代（モデルアクセスが通らないときの代替）
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

---

## AWS認証なしでの動作確認

AWS認証情報が未設定の場合、自動的に**ダミーデータモード**で起動します。
UIのレイアウトや評価フローの確認に使えます。

---

## トラブルシューティング

| エラー | 原因 | 対処 |
|--------|------|------|
| `AccessDeniedException` | IAM権限不足 or モデルアクセス未申請 | AWSコンソールでモデルアクセスをリクエスト |
| `ResourceNotFoundException` | モデルIDが間違っている | `.env` の `BEDROCK_MODEL_ID` を確認 |
| `ThrottlingException` | リクエスト過多 | 少し待ってから再試行 |
| AWS認証情報が読まれない | `.env` の場所が違う | `app.py` と同じディレクトリに `.env` を置く |

---

## DBスキーマ

```sql
CREATE TABLE ideas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_text         TEXT    NOT NULL,
    generation_prompt TEXT    NOT NULL,
    generated_at      TEXT    NOT NULL
);

CREATE TABLE evaluations (
    id                            INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id                       INTEGER NOT NULL,
    self_need_score               INTEGER NOT NULL CHECK (self_need_score BETWEEN 1 AND 5),
    emotion_sync_score            INTEGER NOT NULL CHECK (emotion_sync_score BETWEEN 1 AND 5),
    negative_emotion_relief_score INTEGER NOT NULL CHECK (negative_emotion_relief_score BETWEEN 1 AND 5),
    originality_score             INTEGER NOT NULL CHECK (originality_score BETWEEN 1 AND 5),
    feedback_text                 TEXT    NOT NULL DEFAULT '',
    evaluated_at                  TEXT    NOT NULL,
    FOREIGN KEY (idea_id) REFERENCES ideas(id)
);
```

---

## .gitignore 推奨設定

```gitignore
.env
idea_eval.db
__pycache__/
*.pyc
```
