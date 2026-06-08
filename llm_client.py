"""
llm_client.py — LLM API クライアント（Amazon Bedrock 対応）

環境変数:
  AWS_ACCESS_KEY_ID      : AWSアクセスキー
  AWS_SECRET_ACCESS_KEY  : AWSシークレットキー
  AWS_DEFAULT_REGION     : リージョン（デフォルト: ap-southeast-2 / Sydney）
  BEDROCK_MODEL_ID       : 使用するモデルID（デフォルト: anthropic.claude-haiku-4-5-20251001-v1:0）
"""

from __future__ import annotations

import os
import textwrap

from dotenv import load_dotenv

load_dotenv(override=True)

# ──────────────────────────────────────────
# デフォルト設定
# ──────────────────────────────────────────

DEFAULT_MODEL_ID = "anthropic.claude-haiku-4-5-20251001-v1:0"
# 他の選択肢:
#   "anthropic.claude-sonnet-4-5-20251001-v1:0"  （より高精度）
#   "anthropic.claude-3-haiku-20240307-v1:0"      （旧世代・安定）


# ──────────────────────────────────────────
# システムプロンプト（逆算型仕様書ジェネレーター）
# ──────────────────────────────────────────

ARCHITECT_SYSTEM_PROMPT = """あなたは「トレンド逆算型アプリアーキテクト」です。
PerplexityやChatGPTなどのAIが出力したトレンド分析・ユーザーの不満データを受け取り、
エンジニア・個人開発者の視点で即座に具体的なアプリ開発仕様へ落とし込む専門家です。
AIで解決できてしまうような案はできるだけ避けてください。

入力されたトレンド情報を元に、必ず以下の4セクションを構造化して出力してください。
前置きや後書きは一切不要です。セクション見出しと内容のみを出力してください。

---

## ① ターゲットの選定

このトレンドから逆算した「コアユーザー像」を以下の形式で定義してください：

- **年齢・属性**: 〈例：20代後半〜30代前半の会社員〉
- **置かれている状況**: 〈具体的なシチュエーション〉
- **抱えている葛藤・痛み**: 〈感情レベルで言語化した課題〉
- **このアプリを使う動機**: 〈行動を起こすトリガー〉

---

## ② プロダクト構想

**アプリ名（案）**: 〈キャッチーな名前〉

**一言コンセプト**: 〈20〜40文字で本質を表す〉

**解決する課題**: 〈トレンドデータのどの痛みを、どう解決するか〉

**なぜ今このアプリが必要か**: 〈市場タイミング・時代背景の根拠〉

**技術スタック（個人開発想定）**:
- フロントエンド: 〈Streamlit / React / LINE Bot 等〉
- バックエンド/AI: 〈具体的なAPI・モデル名〉
- データ: 〈SQLite / Supabase 等〉

---

## ③ MVP（最小限の機能）設計 — 1週間で作るコア機能

優先度順にリストアップしてください：

| 優先度 | 機能名 | 概要 | 実装難易度 |
|--------|--------|------|-----------|
| 🔴 必須 | 〈機能名〉 | 〈1行説明〉 | 低/中/高 |
| 🟡 重要 | 〈機能名〉 | 〈1行説明〉 | 低/中/高 |
| 🟢 あれば良い | 〈機能名〉 | 〈1行説明〉 | 低/中/高 |

**Week 1 の開発ロードマップ**:
- Day 1-2: 〈やること〉
- Day 3-4: 〈やること〉
- Day 5-7: 〈やること〉

---

## ④ 就活・ポートフォリオ アピール文（ガクチカ用トークスクリプト）

**面接での語り方（60秒バージョン）**:

〈面接官に刺さる構成で書く：①課題発見の背景 → ②なぜ自分が作ったか → ③技術的工夫 → ④得た学び・成果〉

**技術面接で深掘りされたときの回答ポイント**:
- 〈アーキテクチャの意思決定理由〉
- 〈苦労した実装と解決策〉
- 〈数値で示せる成果や指標〉
"""


# ──────────────────────────────────────────
# メイン生成関数
# ──────────────────────────────────────────

def generate_spec(trend_text: str) -> str:
    """
    トレンド分析テキストを受け取り、アプリ開発仕様書を生成して返す。

    Args:
        trend_text: 他のAIが出力したトレンド分析・ユーザー不満テキスト

    Raises:
        EnvironmentError: AWS認証情報が未設定の場合
        RuntimeError:     API呼び出しに失敗した場合
    """
    user_prompt = f"""以下のトレンド分析データを元に、アプリ開発仕様書を生成してください。

【入力されたトレンド分析データ】
{trend_text}
"""
    return _call_bedrock(ARCHITECT_SYSTEM_PROMPT, user_prompt)


# ──────────────────────────────────────────
# Amazon Bedrock（接続設定は変更しない）
# ──────────────────────────────────────────

def _call_bedrock(system_prompt: str, user_prompt: str) -> str:
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        raise EnvironmentError(
            "AWS認証情報が設定されていません。\n"
            ".envファイルに以下を設定してください：\n"
            "  AWS_ACCESS_KEY_ID=AKIAxxxx\n"
            "  AWS_SECRET_ACCESS_KEY=xxxx\n"
            "  AWS_DEFAULT_REGION=ap-southeast-2"
        )

    try:
        import boto3  # type: ignore
    except ImportError as e:
        raise ImportError("boto3がインストールされていません。\n  pip install boto3") from e

    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    region   = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")

    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=region,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    )

    try:
        response = client.converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=[
                {"role": "user", "content": [{"text": user_prompt}]}
            ],
            inferenceConfig={
                "maxTokens": 2000,   # 仕様書は長いので増量
                "temperature": 0.7,  # 創造性と安定性のバランス
            },
        )
        return response["output"]["message"]["content"][0]["text"].strip()

    except Exception as e:
        msg = str(e)
        if "AccessDeniedException" in msg:
            raise RuntimeError(
                f"❌ Bedrockへのアクセスが拒否されました。\n"
                f"モデル '{model_id}' のアクセス申請が必要な場合があります。\n"
                "AWSコンソール → Amazon Bedrock → モデルアクセス で確認してください。"
            ) from e
        if "ValidationException" in msg or "ResourceNotFoundException" in msg:
            raise RuntimeError(
                f"❌ モデルID '{model_id}' が見つかりません。\n"
                ".envの BEDROCK_MODEL_ID を確認してください。"
            ) from e
        if "ThrottlingException" in msg:
            raise RuntimeError("⏳ リクエストが多すぎます。少し待ってから再試行してください。") from e
        raise RuntimeError(f"Bedrock API エラー: {e}") from e


# ──────────────────────────────────────────
# ダミーモード（AWS認証なしでの動作確認用）
# ──────────────────────────────────────────

def generate_spec_dummy() -> str:
    """AWS認証未設定時のデモ用ダミー出力"""
    return textwrap.dedent("""
        ## ① ターゲットの選定

        - **年齢・属性**: 25〜35歳の情報感度が高い会社員・副業志向層
        - **置かれている状況**: SNSで常にトレンドをキャッチしているが、それを収益に変える手段を持っていない
        - **抱えている葛藤・痛み**: 「面白いと思ったものを、すぐアプリにできたら…」というもどかしさ
        - **このアプリを使う動機**: トレンドを見た瞬間に「これでアプリ作れる」と確信したい

        ## ② プロダクト構想

        **アプリ名（案）**: TrendSpec AI

        **一言コンセプト**: トレンドをコピペするだけで、明日から作れる仕様書が出てくる

        （※ダミーデータです。AWS認証情報を設定して実際に生成してください）
    """).strip()


# ──────────────────────────────────────────
# デフォルト設定
# ──────────────────────────────────────────

DEFAULT_MODEL_ID = "anthropic.claude-haiku-4-5-20251001-v1:0"
# 他の選択肢:
#   "anthropic.claude-sonnet-4-5-20251001-v1:0"  （より高精度）
#   "anthropic.claude-3-haiku-20240307-v1:0"      （旧世代・安定）


# ──────────────────────────────────────────
# メイン生成関数
# ──────────────────────────────────────────

def generate_idea(system_prompt: str, user_prompt: str) -> str:
    """
    Amazon Bedrock を使ってアイデアを生成する。

    Raises:
        EnvironmentError: AWS認証情報が未設定の場合
        RuntimeError:     API呼び出しに失敗した場合
    """
    return _call_bedrock(system_prompt, user_prompt)


# ──────────────────────────────────────────
# Amazon Bedrock
# ──────────────────────────────────────────

def _call_bedrock(system_prompt: str, user_prompt: str) -> str:
    # 認証情報チェック
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        raise EnvironmentError(
            "AWS認証情報が設定されていません。\n"
            ".envファイルに以下を設定してください：\n"
            "  AWS_ACCESS_KEY_ID=AKIAxxxx\n"
            "  AWS_SECRET_ACCESS_KEY=xxxx\n"
            "  AWS_DEFAULT_REGION=us-east-1"
        )

    try:
        import boto3  # type: ignore
    except ImportError as e:
        raise ImportError(
            "boto3がインストールされていません。\n"
            "  pip install boto3"
        ) from e

    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    region   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=region,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN"),  # 一時認証トークン（任意）
    )

    # Bedrock の Converse API（Claude・Nova など統一インターフェース）
    try:
        response = client.converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=[
                {"role": "user", "content": [{"text": user_prompt}]}
            ],
            inferenceConfig={
                "maxTokens": 600,
                "temperature": 0.9,
            },
        )
        return response["output"]["message"]["content"][0]["text"].strip()

    except Exception as e:
        msg = str(e)
        if "AccessDeniedException" in msg:
            raise RuntimeError(
                "❌ Bedrockへのアクセスが拒否されました。\n"
                f"モデル '{model_id}' へのアクセスが有効か確認してください。\n"
                "AWSコンソール → Amazon Bedrock → モデルアクセス で申請が必要な場合があります。"
            ) from e
        if "ValidationException" in msg or "ResourceNotFoundException" in msg:
            raise RuntimeError(
                f"❌ モデルID '{model_id}' が見つかりません。\n"
                ".envの BEDROCK_MODEL_ID を確認してください。\n"
                "利用可能なモデル例:\n"
                "  anthropic.claude-3-haiku-20240307-v1:0\n"
                "  anthropic.claude-3-5-sonnet-20241022-v2:0\n"
                "  amazon.nova-lite-v1:0"
            ) from e
        if "ThrottlingException" in msg:
            raise RuntimeError(
                "⏳ リクエストが多すぎます。少し待ってから再試行してください。"
            ) from e
        raise RuntimeError(f"Bedrock API エラー: {e}") from e


# ──────────────────────────────────────────
# ダミーモード（AWS認証なしでの動作確認用）
# ──────────────────────────────────────────

def generate_idea_dummy(user_prompt: str) -> str:
    """AWS認証未設定時のデモ用ダミー生成"""
    return textwrap.dedent("""
        【アイデア名】だるさログ
        【一言説明】今日のだるさを記録して、パターンを可視化するアプリ
        【解決する葛藤】「なんか今日だるい」の原因がわからず、無力感だけが積み重なる問題
        【コア機能】1タップでだるさレベルを記録。週次レポートで「だるさの法則」を自動分析
        【なぜ刺さるか】原因不明のだるさに名前をつけることで、自分を客観視できる安心感
    """).strip()