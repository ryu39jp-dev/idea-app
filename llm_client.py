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
import re
import textwrap

from dotenv import load_dotenv

load_dotenv(override=True)

# ──────────────────────────────────────────
# テキストクリーニング（APIコスト削減）
# ──────────────────────────────────────────

def clean_trend_text(text: str) -> str:
    """
    ユーザー入力テキストからノイズを除去してトークン数を削減する。

    除去対象:
      - URL（http/https）
      - Xのハッシュタグ（#xxx）
      - Xのメンション（@xxx）
      - 絵文字・特殊Unicode記号
      - 連続する空白行（2行以上 → 1行に圧縮）
      - 行頭・行末の余白
    """
    # URL を除去
    text = re.sub(r'https?://\S+', '', text)

    # ハッシュタグを除去（#ワード）
    text = re.sub(r'#\S+', '', text)

    # メンションを除去（@ユーザー名）
    text = re.sub(r'@\S+', '', text)

    # 絵文字・記号 Unicode ブロックを除去
    text = re.sub(
        r'[\U0001F300-\U0001F9FF'   # Misc Symbols and Pictographs
        r'\U00002700-\U000027BF'    # Dingbats
        r'\U0000FE00-\U0000FE0F'    # Variation Selectors
        r'\U00002600-\U000026FF'    # Misc Symbols
        r'\U0001FA00-\U0001FA6F'    # Chess / Other
        r'\U0001FA70-\U0001FAFF'    # Symbols Extended-A
        r']+',
        '',
        text,
        flags=re.UNICODE,
    )

    # 行ごとに前後の空白をトリム
    lines = [line.strip() for line in text.splitlines()]

    # 連続する空白行を最大1行に圧縮
    cleaned_lines: list[str] = []
    prev_blank = False
    for line in lines:
        if line == '':
            if not prev_blank:
                cleaned_lines.append(line)
            prev_blank = True
        else:
            prev_blank = False
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines).strip()

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
入力されたトレンド分析データを元に、以下の4セクションを必ず出力してください。
前置き・後書き・補足説明は一切不要です。各セクションの見出しと内容のみ出力。

【厳守ルール】
- 「AIチャットボット」「AIが答えてくれる〇〇」「AIで自動生成する△△」のような
  "AIに丸投げするだけ"のアイデアは絶対に出さない。
- ユーザーが自分の手・頭・体験を通じて価値を得る、人間中心の機能設計にすること。
- AIは裏方の処理エンジンとして使っても良いが、「AIがすごい」ではなく「ユーザー体験がすごい」設計にする。

## ① ターゲットの選定
- **年齢・属性**: 〈具体的なユーザー像〉
- **状況**: 〈置かれているシチュエーション〉
- **痛み**: 〈感情レベルの課題〉
- **使う動機**: 〈行動トリガー〉

## ② プロダクト構想
**アプリ名**: 〈名前〉
**一言コンセプト**: 〈30文字以内〉
**解決する課題**: 〈2〜3文〉
**技術スタック**: フロント/バック/DB をそれぞれ1行で

## ③ MVP設計（1週間で作るコア機能）
| 優先度 | 機能名 | 概要 | 難易度 |
|--------|--------|------|--------|
| 🔴必須 | 〈名前〉 | 〈1行〉 | 低/中/高 |
| 🟡重要 | 〈名前〉 | 〈1行〉 | 低/中/高 |
| 🟢任意 | 〈名前〉 | 〈1行〉 | 低/中/高 |

**Week1ロードマップ**: Day1-2 / Day3-4 / Day5-7 を各1行で

## ④ ガクチカ用トークスクリプト（面接60秒）
①課題発見 → ②なぜ自分が作ったか → ③技術的工夫 → ④成果・学び の順で3〜5文にまとめる。
その後「技術深掘りQ&A」として想定質問と回答を2つ箇条書きする。
"""


# ──────────────────────────────────────────
# メイン生成関数
# ──────────────────────────────────────────

def generate_spec(trend_text: str) -> str:
    """
    トレンド分析テキストを受け取り、アプリ開発仕様書を生成して返す。
    送信前にclean_trend_textでノイズを除去してAPIコストを削減する。
    """
    cleaned = clean_trend_text(trend_text)
    user_prompt = f"""以下のトレンド分析データを元に、アプリ開発仕様書を生成してください。

【入力されたトレンド分析データ】
{cleaned}
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