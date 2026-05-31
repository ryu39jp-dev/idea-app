# 💡 アイデア出し＆評価ループアプリ

AIが生成したアプリ企画を評価することで、あなた好みのアイデアを磨き続けるフィードバックループアプリです。

## 仕組み

```
[AIアイデア生成] → [ユーザー評価] → [評価をDBに保存] → [動的プロンプト生成] → [AIアイデア生成] → ...
```

過去の高評価・低評価データを元にプロンプトを自動調整し、あなたの好みに近づくアイデアを生成し続けます。

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

Gemini を使う場合は追加でインストール:
```bash
pip install google-generativeai
```

### 2. APIキーの設定

```bash
cp .env.example .env
```

`.env` ファイルを編集してAPIキーを入力:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxx
```

### 3. アプリを起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が開きます。

---

## ファイル構成

```
.
├── app.py              # Streamlit メインアプリ（UI・セッション管理）
├── database.py         # SQLite CRUD 操作
├── llm_client.py       # LLM API クライアント（OpenAI / Gemini 対応）
├── prompt_builder.py   # 動的プロンプト組み立てロジック
├── requirements.txt    # 依存パッケージ
├── .env.example        # 環境変数テンプレート
└── idea_eval.db        # SQLite DB（起動時に自動生成）
```

---

## 評価項目

| 項目 | 説明 |
|------|------|
| ① 自分ニーズ度 | 自分が実際に欲しいと思えるか |
| ② 感情のシンクロ度 | 共感できる・わかるという感覚 |
| ③ 負の感情解消度 | モヤモヤ・だるさが解消されそうか |
| ④ 意外性 | 驚きや新鮮さがあるか |

4項目の平均スコアが高いアイデアを Few-shot 例として、低いアイデアを「避けるべき例」として動的プロンプトに組み込みます。

---

## LLM プロバイダー切り替え

`.env` の `LLM_PROVIDER` を変更するだけで切り替えられます:

```env
# OpenAI の場合
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Gemini の場合
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...
```

---

## APIキーなしでの動作確認

APIキーが設定されていない場合、自動的にダミーデータモードで動作します。UIや評価フローの確認に使えます。

---

## DB スキーマ

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