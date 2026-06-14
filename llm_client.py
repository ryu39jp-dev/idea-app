"""
llm_client.py — LLM API クライアント（Amazon Bedrock 対応）

環境変数:
  AWS_ACCESS_KEY_ID      : AWSアクセスキー
  AWS_SECRET_ACCESS_KEY  : AWSシークレットキー
  AWS_DEFAULT_REGION     : リージョン（デフォルト: ap-southeast-2 / Sydney）
  BEDROCK_MODEL_ID       : 使用するモデルID（デフォルト: anthropic.claude-haiku-4-5-20251001-v1:0）

このモジュールは2段階の生成フローを提供する：
  ① プロダクトの核心アイデア生成・再生成（generate_idea_spec / refine_idea_spec）
  ② ①が確定した後に呼ぶ、技術スタック＆構造設計書生成（generate_tech_spec）
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
# システムプロンプト ①：プロダクトの核心アイデア
# ──────────────────────────────────────────

PRODUCT_IDEA_SYSTEM_PROMPT = """あなたは「トレンド逆算型アプリアーキテクト」です。
入力されたトレンド分析データを元に、アプリの核心アイデアを1つ提案してください。
前置き・後書き・補足説明は一切不要です。以下のフォーマットのみ出力してください。

【厳守ルール】
- 「AIチャットボット」「AIが答えてくれる〇〇」のような"AIに丸投げするだけ"の
  薄いアイデアは避け、トレンドの不満を的確に解決する実用的なプロダクトにすること。
- 各項目は40文字以内で簡潔・論理的に記述する。

**アプリ名**: 〈名前〉
**一言コンセプト**: 〈30文字以内〉
**解決する不満**: 〈入力データの不満をどう解決するか、2〜3文〉
**主要機能**:
- 〈機能1〉
- 〈機能2〉
- 〈機能3〉
"""


# ──────────────────────────────────────────
# システムプロンプト ②：技術スタック ＆ 構造設計書
# ──────────────────────────────────────────

TECH_SPEC_SYSTEM_PROMPT = """あなたは「自動生成用構造設計書ジェネレーター」です。
与えられたアプリの核心アイデアに基づき、最適な技術スタックと構造設計書を出力してください。
このアウトプットは、将来的に別のAIがそのままコードを自動生成・自動デプロイするための
「設計インプット」として使われます。前置き・後書き・補足説明は一切不要です。
以下のフォーマットのみ出力してください。

【厳守ルール】
- 技術選定は「個人開発者が1〜2週間で動くものを作れる」現実的な範囲で選ぶこと。
- 各箇条書きは40文字以内に収め、簡潔・論理的に記述する。

**選定理由**: 〈このアプリの特性に最適な言語・フレームワークである理由を1〜2文〉

**技術スタック**:
- 言語: 〈Python / TypeScript 等〉
- UI: 〈Streamlit / React / Flutter 等〉
- データ: 〈SQLite / Firebase 等〉
- 主要ライブラリ: 〈具体名を2〜3個〉

**データ構造（主要テーブル/State）**:
- 〈テーブル名やStateの構成を箇条書きで〉

**主要ロジックのアルゴリズム**:
- 〈コア機能を実現する処理の流れを、ステップごとに箇条書きで〉

**バグらせないための実装方針**:
- 〈状態管理・エラーハンドリング・分割設計などの注意点を箇条書きで〉
"""


# ──────────────────────────────────────────
# システムプロンプト ③：AIコーディングエージェント向け実装指示プロンプト
# ──────────────────────────────────────────

BUILD_PROMPT_SYSTEM_PROMPT = """あなたは「AI実装指示プロンプト生成AI」です。
与えられたアプリの核心アイデアと技術設計書をもとに、Claude CodeやCursorなどの
AIコーディングエージェントにそのまま渡せる「実装指示プロンプト」を1つ生成してください。

出力はプロンプト本文そのものとし、前置き・後書き・「以下が指示文です」等の説明は一切不要です。
ユーザーがコピーしてそのままAIエージェントに貼り付けられる完成形にしてください。

【厳守ルール】
- 運用コストの最小化を最優先事項として明記すること。具体的には:
  - 無料枠で動くホスティング（Streamlit Community Cloud等）・DB（SQLite等）を優先指定
  - LLM API呼び出しは必要最小限にし、キャッシュ・リトライ制限・トークン上限を明記
  - 高コストな常時起動サーバーやポーリングを避ける設計を指示
- ファイル構成（ディレクトリ・主要ファイル名）を明記する
- 各ファイルの責務・主要な関数/コンポーネント名を箇条書きで明記する
- 実装の優先順位（最初に作るべき部分→後回しでよい部分）を明記する
- エラーハンドリング・環境変数管理の方針を明記する
- 全体は箇条書き中心で、AIエージェントが読んだ瞬間に着手できる粒度にする
- 各箇条書きは40文字以内を目安に簡潔にする
"""


# ──────────────────────────────────────────
# メイン生成関数 ①：核心アイデアの生成・再生成
# ──────────────────────────────────────────

def generate_idea_spec(trend_text: str) -> str:
    """
    トレンド分析テキストを受け取り、アプリの核心アイデアを生成して返す。
    送信前にclean_trend_textでノイズを除去してAPIコストを削減する。
    """
    cleaned = clean_trend_text(trend_text)
    user_prompt = f"""以下のトレンド分析データを元に、アプリの核心アイデアを1つ提案してください。

【入力されたトレンド分析データ】
{cleaned}
"""
    return _call_bedrock(PRODUCT_IDEA_SYSTEM_PROMPT, user_prompt, max_tokens=2048)


def refine_idea_spec(trend_text: str, previous_idea: str, feedback: str) -> str:
    """
    生成済みの核心アイデアに対するユーザーの指摘（フィードバック）を反映し、
    アイデアを再生成して返す。

    Args:
        trend_text:    元のトレンド分析テキスト（クリーニング前）
        previous_idea: 直前に生成された核心アイデア全文
        feedback:      ユーザーが指摘した修正・要望点
    """
    cleaned_trend = clean_trend_text(trend_text)
    cleaned_feedback = clean_trend_text(feedback)

    user_prompt = f"""以下は、トレンド分析データから生成したアプリの「核心アイデアの現在のバージョン」です。
ユーザーからの指摘・修正要望を反映し、同じフォーマットでアイデアを再生成してください。
指摘されていない部分は、できるだけ元の内容を維持してください。

【元のトレンド分析データ】
{cleaned_trend}

【現在の核心アイデア】
{previous_idea}

【ユーザーからの指摘・修正要望】
{cleaned_feedback}
"""
    return _call_bedrock(PRODUCT_IDEA_SYSTEM_PROMPT, user_prompt, max_tokens=2048)


# ──────────────────────────────────────────
# メイン生成関数 ②：技術スタック ＆ 構造設計書の生成
# ──────────────────────────────────────────

def generate_tech_spec(idea_spec: str) -> str:
    """
    確定した核心アイデアを受け取り、技術スタック＆構造設計書を生成して返す。
    ①が確定したタイミングでのみ呼び出される（毎回の再生成では呼ばない）。
    """
    user_prompt = f"""以下の、確定したアプリの核心アイデアに基づき、
最適な技術スタックと自動生成用の構造設計書を生成してください。

【確定したアプリの核心アイデア】
{idea_spec}
"""
    return _call_bedrock(TECH_SPEC_SYSTEM_PROMPT, user_prompt, max_tokens=4096)


# ──────────────────────────────────────────
# メイン生成関数 ③：AI実装指示プロンプトの生成
# ──────────────────────────────────────────

def generate_build_prompt(idea_spec: str, tech_spec: str) -> str:
    """
    確定した①核心アイデアと②技術設計書を受け取り、
    AIコーディングエージェント向けの実装指示プロンプトを生成して返す。
    ②が確定したタイミングでのみ呼び出される。
    """
    user_prompt = f"""以下の、確定したアプリの核心アイデアと技術設計書をもとに、
AIコーディングエージェント向けの実装指示プロンプトを生成してください。

【確定したアプリの核心アイデア】
{idea_spec}

【確定した技術スタック ＆ 構造設計書】
{tech_spec}
"""
    return _call_bedrock(BUILD_PROMPT_SYSTEM_PROMPT, user_prompt, max_tokens=4096)


# ──────────────────────────────────────────
# Amazon Bedrock 接続
# ──────────────────────────────────────────

def _call_bedrock(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
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
                "maxTokens": max_tokens,
                "temperature": 0.7,
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

def generate_idea_spec_dummy() -> str:
    """AWS認証未設定時のデモ用ダミー出力（①用）"""
    return textwrap.dedent("""
        **アプリ名**: TrendSpec AI
        **一言コンセプト**: トレンドを貼るだけで開発設計書が出てくる
        **解決する不満**: トレンド分析から「何を作るか」を考える時間をゼロにし、
        アイデア出しからMVP設計までの工程を1ステップに圧縮する。
        **主要機能**:
        - トレンドテキストの自動クリーニング
        - 核心アイデアの自動抽出
        - 技術スタック・構造設計書の自動生成

        （※ダミーデータです。AWS認証情報を設定して実際に生成してください）
    """).strip()


def generate_tech_spec_dummy() -> str:
    """AWS認証未設定時のデモ用ダミー出力（②用）"""
    return textwrap.dedent("""
        **選定理由**: 個人開発で素早く動くプロトタイプを作れる構成。

        **技術スタック**:
        - 言語: Python
        - UI: Streamlit
        - データ: SQLite
        - 主要ライブラリ: boto3, python-dotenv

        **データ構造（主要テーブル/State）**:
        - session_state: idea_result, tech_result, history

        **主要ロジックのアルゴリズム**:
        - 入力テキストをclean_trend_textで整形
        - Bedrock経由でClaudeに送信し①を生成
        - ①確定後、②をBedrockに送信して生成

        **バグらせないための実装方針**:
        - try/exceptでAPIエラーを個別ハンドリング
        - ①が更新されたら②を必ずリセットする

        （※ダミーデータです。AWS認証情報を設定して実際に生成してください）
    """).strip()


def generate_build_prompt_dummy() -> str:
    """AWS認証未設定時のデモ用ダミー出力（③用）"""
    return textwrap.dedent("""
        以下の仕様に沿って、Streamlit + SQLiteのアプリを実装してください。

        【コスト最適化方針（最優先）】
        - ホスティング: Streamlit Community Cloud（無料枠）を使用
        - DB: SQLite（追加コストなし、ファイルベース）
        - LLM API呼び出しは1ユーザー操作につき最大1回に制限
        - 同一入力に対する再呼び出しを避けるキャッシュ機構を入れる
        - maxTokensは必要最小限（2000〜4096）に設定

        【ファイル構成】
        - app.py: Streamlit UI本体
        - llm_client.py: Bedrock呼び出し・プロンプト管理
        - database.py: SQLite CRUD

        【実装優先順位】
        1. コア機能（テキスト入力→AI生成→表示）を最初に実装
        2. DB保存・履歴表示は後回し
        3. UIの装飾は最後

        【エラーハンドリング】
        - AWS認証エラー・APIエラーをtry/exceptで個別捕捉し、ユーザーに分かりやすく表示

        （※ダミーデータです。AWS認証情報を設定して実際に生成してください）
    """).strip()