"""
llm_client.py — LLM API クライアント（Amazon Bedrock 対応）

環境変数:
  AWS_ACCESS_KEY_ID      : AWSアクセスキー
  AWS_SECRET_ACCESS_KEY  : AWSシークレットキー
  AWS_DEFAULT_REGION     : リージョン（デフォルト: us-east-1）
  BEDROCK_MODEL_ID       : 使用するモデルID（デフォルト: anthropic.claude-3-haiku-20240307-v1:0）
"""

from __future__ import annotations

import json
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