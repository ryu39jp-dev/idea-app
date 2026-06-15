"""
llm_client.py — LLM API クライアント（Amazon Bedrock / ハイブリッド2段階構成）

環境変数:
  AWS_ACCESS_KEY_ID      : AWSアクセスキー
  AWS_SECRET_ACCESS_KEY  : AWSシークレットキー
  AWS_DEFAULT_REGION     : 両モデル共通のデフォルトリージョン（デフォルト: ap-southeast-2 / Sydney）
  HAIKU_MODEL_ID         : 第1段階（ブレスト）用モデルID（デフォルト: Claude Haiku 4.5）
  HAIKU_REGION           : 第1段階のリージョン（デフォルト: AWS_DEFAULT_REGION）
  OPUS_MODEL_ID          : 第2段階（設計書＋実装指示）用モデルID（デフォルト: Claude Opus 4.6 / Sydney推論プロファイル）
  OPUS_REGION            : 第2段階のリージョン（デフォルト: AWS_DEFAULT_REGION）

このモジュールは「Haiku → Opus」のバトンリレー形式の2段階生成フローを提供する：

  【第1段階：Haiku（爆速・低コスト）】
    generate_base_idea(trend_text)
      入力テキストをclean_trend_textでノイズ除去し、Claude Haiku 4.5で
      アプリの「ベースアイデア（ブレスト・方向性）」を箇条書きで生成する。
    refine_base_idea(trend_text, previous_idea, feedback)
      ユーザーの指摘を反映してベースアイデアをHaikuで再生成する。
      （①は何度再生成してもコストが小さい）

  【第2段階：Opus 4.6（高精度・物理ブレーキ付き）】
    generate_opus_spec(base_idea)
      確定したベースアイデアを引き継ぎ、Claude Opus 4.6（シドニー推論プロファイル）で
      「技術設計書」と「AI実装指示プロンプト」を1回の呼び出しで凝縮して生成する。
      システムプロンプトに簡潔化指示を必ず含み、maxTokens=4000で
      ダラダラ長文によるコスト超過を防ぐ。
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
# モデル設定（Haiku / Opus の2系統）
# ──────────────────────────────────────────

_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")

# 第1段階：Haiku（ブレスト・低コスト・シドニーリージョン）
HAIKU_MODEL_ID = os.getenv("HAIKU_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")
HAIKU_REGION   = os.getenv("HAIKU_REGION", _DEFAULT_REGION)

# 第2段階：Opus 4.6（高精度・シドニー推論プロファイル）
OPUS_MODEL_ID = os.getenv(
    "OPUS_MODEL_ID",
    "arn:aws:bedrock:ap-southeast-2:258975980682:inference-profile/au.anthropic.claude-opus-4-6-v1",
)
OPUS_REGION = os.getenv("OPUS_REGION", _DEFAULT_REGION)


# ──────────────────────────────────────────
# システムプロンプト ①：Haiku — ベースアイデア（ブレスト）
# ──────────────────────────────────────────

BASE_IDEA_SYSTEM_PROMPT = """あなたは「トレンド逆算型アプリアーキテクト」です。
入力されたトレンド分析データを元に、アプリのベースアイデア（方向性・ブレスト）を
1つ提案してください。前置き・後書き・補足説明は一切不要です。
以下のフォーマットのみ出力してください。

【厳守ルール】
- 「AIチャットボット」「AIが答えてくれる〇〇」のような"AIに丸投げするだけ"の
  薄いアイデアは避け、トレンドの不満を的確に解決する実用的なプロダクトにすること。
- 各項目は40文字以内で簡潔・論理的に記述する。
- 出力は技術的に具体的かつロジカルに記述しつつ、無駄な解説文や重複した表現は省き、
  極限まで簡潔（コンパクト）にまとめて出力してください。

**アプリ名**: 〈名前〉
**一言コンセプト**: 〈30文字以内〉
**解決する不満**: 〈入力データの不満をどう解決するか、2〜3文〉
**主要機能**:
- 〈機能1〉
- 〈機能2〉
- 〈機能3〉
"""


# ──────────────────────────────────────────
# システムプロンプト ②：Opus 4.6 — 技術設計書 ＋ AI実装指示プロンプト（結合出力）
# ──────────────────────────────────────────

OPUS_COMBINED_SYSTEM_PROMPT = """あなたは「自動生成用設計書＆実装指示プロンプト ジェネレーター」です。
別のAI（Haiku）が考えたアプリのベースアイデア（ブレスト）を引き継ぎ、
個人開発者がそのままAIコーディングエージェントに渡せる形に仕上げてください。

以下の2セクションを、この見出し・順序のまま出力してください。
前置き・後書き・補足説明は一切不要です。

【厳守ルール（最優先・必ず遵守）】
- 出力は技術的に具体的かつロジカルに記述しつつ、無駄な解説文や重複した表現は省き、
  極限まで簡潔（コンパクト）にまとめて出力してください。
- 技術選定は「個人開発者が1〜2週間で動くものを作れる」現実的な範囲で選ぶこと。
- 各箇条書きは40文字以内に収める。

## 🛠️ 技術設計書
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

## 🤖 AI実装指示プロンプト
〈ここから下は、Claude CodeやCursor等にそのまま貼り付けて実装を依頼できる
プロンプト本文のみを書く。「以下が指示文です」等の前置きは禁止。
必ず以下を含める〉
- 運用コスト最小化方針（無料枠ホスティング・DB優先、LLM呼び出し最小化・
  キャッシュ・トークン上限の明記）
- ファイル構成（ディレクトリ・主要ファイル名）
- 各ファイルの責務・主要な関数/コンポーネント名
- 実装の優先順位（最初に作るべき部分→後回しでよい部分）
- エラーハンドリング・環境変数管理の方針
"""


# ──────────────────────────────────────────
# メイン生成関数 ①：Haikuでベースアイデアを生成・再生成
# ──────────────────────────────────────────

def generate_base_idea(trend_text: str) -> str:
    """
    トレンド分析テキストを受け取り、Claude Haiku 4.5でベースアイデア
    （ブレスト・方向性）を生成して返す。
    送信前にclean_trend_textでノイズを除去してAPIコストを削減する。
    """
    cleaned = clean_trend_text(trend_text)
    user_prompt = f"""以下のトレンド分析データを元に、アプリのベースアイデアを1つ提案してください。

【入力されたトレンド分析データ】
{cleaned}
"""
    return _call_bedrock(
        model_id=HAIKU_MODEL_ID,
        client=_get_haiku_client(),
        system_prompt=BASE_IDEA_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=1500,
        stage_label="Haiku（第1段階）",
    )


def refine_base_idea(trend_text: str, previous_idea: str, feedback: str) -> str:
    """
    生成済みのベースアイデアに対するユーザーの指摘（フィードバック）を反映し、
    Claude Haiku 4.5でベースアイデアを再生成して返す。

    Args:
        trend_text:    元のトレンド分析テキスト（クリーニング前）
        previous_idea: 直前に生成されたベースアイデア全文
        feedback:      ユーザーが指摘した修正・要望点
    """
    cleaned_trend = clean_trend_text(trend_text)
    cleaned_feedback = clean_trend_text(feedback)

    user_prompt = f"""以下は、トレンド分析データから生成したアプリの「ベースアイデアの現在のバージョン」です。
ユーザーからの指摘・修正要望を反映し、同じフォーマットでアイデアを再生成してください。
指摘されていない部分は、できるだけ元の内容を維持してください。

【元のトレンド分析データ】
{cleaned_trend}

【現在のベースアイデア】
{previous_idea}

【ユーザーからの指摘・修正要望】
{cleaned_feedback}
"""
    return _call_bedrock(
        model_id=HAIKU_MODEL_ID,
        client=_get_haiku_client(),
        system_prompt=BASE_IDEA_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=1500,
        stage_label="Haiku（第1段階）",
    )


# ──────────────────────────────────────────
# メイン生成関数 ②：Opus 4.6で技術設計書＋実装指示プロンプトを生成
# ──────────────────────────────────────────

def generate_opus_spec(base_idea: str) -> str:
    """
    Haikuが確定したベースアイデアを引き継ぎ、Claude Opus 4.6（シドニー推論プロファイル）
    で「技術設計書」と「AI実装指示プロンプト」を1回の呼び出しで凝縮して生成する。

    コスト最適化のため:
      - システムプロンプトに簡潔化指示を必須で含める
      - maxTokens=4000 を物理ブレーキとして設定する
    """
    user_prompt = f"""以下は、別のAI（Haiku）が考えたアプリのベースアイデア（ブレスト）です。
これを引き継ぎ、技術設計書とAI実装指示プロンプトを生成してください。

【Haikuが考えたベースアイデア（確定済み）】
{base_idea}
"""
    return _call_bedrock(
        model_id=OPUS_MODEL_ID,
        client=_get_opus_client(),
        system_prompt=OPUS_COMBINED_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=4000,  # 物理ブレーキ：これ以上は絶対に出力させない
        stage_label="Opus 4.6（第2段階）",
    )


# ──────────────────────────────────────────
# Amazon Bedrock 接続（Haiku用 / Opus用の2クライアント）
# ──────────────────────────────────────────

def _get_bedrock_client(region: str):
    """指定リージョンのbedrock-runtimeクライアントを生成する"""
    try:
        import boto3  # type: ignore
    except ImportError as e:
        raise ImportError("boto3がインストールされていません。\n  pip install boto3") from e

    return boto3.client(
        service_name="bedrock-runtime",
        region_name=region,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    )


def _get_haiku_client():
    """第1段階（ブレスト）用 Bedrockクライアント（シドニーリージョン）"""
    return _get_bedrock_client(HAIKU_REGION)


def _get_opus_client():
    """第2段階（設計書＋実装指示）用 Bedrockクライアント（シドニーリージョン ap-southeast-2）"""
    return _get_bedrock_client(OPUS_REGION)


def _call_bedrock(
    model_id: str,
    client,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4000,
    stage_label: str = "Bedrock",
) -> str:
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        raise EnvironmentError(
            "AWS認証情報が設定されていません。\n"
            ".envファイルに以下を設定してください：\n"
            "  AWS_ACCESS_KEY_ID=AKIAxxxx\n"
            "  AWS_SECRET_ACCESS_KEY=xxxx\n"
            "  AWS_DEFAULT_REGION=ap-southeast-2"
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
                f"❌ [{stage_label}] Bedrockへのアクセスが拒否されました。\n"
                f"モデル '{model_id}' のアクセス申請が必要な場合があります。\n"
                "AWSコンソール → Amazon Bedrock → モデルアクセス で確認してください。"
            ) from e
        if "ValidationException" in msg or "ResourceNotFoundException" in msg:
            raise RuntimeError(
                f"❌ [{stage_label}] モデルID '{model_id}' が見つかりません。\n"
                ".envの HAIKU_MODEL_ID / OPUS_MODEL_ID を確認してください。"
            ) from e
        if "ThrottlingException" in msg:
            raise RuntimeError(
                f"⏳ [{stage_label}] リクエストが多すぎます。少し待ってから再試行してください。"
            ) from e
        raise RuntimeError(f"[{stage_label}] Bedrock API エラー: {e}") from e


# ──────────────────────────────────────────
# ダミーモード（AWS認証なしでの動作確認用）
# ──────────────────────────────────────────

def generate_base_idea_dummy() -> str:
    """AWS認証未設定時のデモ用ダミー出力（①Haiku用）"""
    return textwrap.dedent("""
        **アプリ名**: TrendSpec AI
        **一言コンセプト**: トレンドを貼るだけで開発設計書が出てくる
        **解決する不満**: トレンド分析から「何を作るか」を考える時間をゼロにし、
        アイデア出しから設計書までの工程を1ステップに圧縮する。
        **主要機能**:
        - トレンドテキストの自動クリーニング
        - ベースアイデアの自動抽出（Haiku）
        - 技術設計書・実装指示の自動生成（Opus）

        （※ダミーデータです。AWS認証情報を設定して実際に生成してください）
    """).strip()


def generate_opus_spec_dummy() -> str:
    """AWS認証未設定時のデモ用ダミー出力（②Opus用・結合フォーマット）"""
    return textwrap.dedent("""
        ## 🛠️ 技術設計書
        **選定理由**: 個人開発で素早く動くプロトタイプを作れる構成。
        **技術スタック**:
        - 言語: Python
        - UI: Streamlit
        - データ: SQLite
        - 主要ライブラリ: boto3, python-dotenv
        **データ構造（主要テーブル/State）**:
        - session_state: base_idea_result, opus_result, history
        **主要ロジックのアルゴリズム**:
        - 入力テキストをclean_trend_textで整形
        - Haikuでベースアイデアを生成
        - 確定後、Opusへベースアイデアをそのまま送信して結合出力を生成
        **バグらせないための実装方針**:
        - try/exceptでAPIエラーを個別ハンドリング
        - ①が更新されたら②を必ずリセットする

        ## 🤖 AI実装指示プロンプト
        以下の仕様に沿って、Streamlit + SQLiteのアプリを実装してください。

        【コスト最適化方針（最優先）】
        - ホスティング: Streamlit Community Cloud（無料枠）
        - DB: SQLite（ファイルベース、追加コストなし）
        - LLM呼び出しは1操作1回まで。同一入力はキャッシュして再呼び出しを避ける
        - maxTokensは1000〜4000の範囲で必要最小限に設定

        【ファイル構成】
        - app.py: Streamlit UI本体
        - llm_client.py: Bedrock呼び出し・プロンプト管理

        【実装優先順位】
        1. コア機能（入力→生成→表示）を最初に実装
        2. 履歴・ダウンロード機能は後回し
        3. UI装飾は最後

        【エラーハンドリング】
        - AWS認証エラー・APIエラーをtry/exceptで個別捕捉し分かりやすく表示

        （※ダミーデータです。AWS認証情報を設定して実際に生成してください）
    """).strip()