"""
llm_client.py — LLM API クライアント（OpenAI / Gemini 切り替え対応）

環境変数:
  OPENAI_API_KEY   : OpenAI を使う場合に設定
  GEMINI_API_KEY   : Gemini を使う場合に設定
  LLM_PROVIDER     : "openai" または "gemini"（デフォルト: openai）
"""

from __future__ import annotations

import os
import textwrap
from typing import Optional

# ──────────────────────────────────────────
# 設定
# ──────────────────────────────────────────

PROVIDER        = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_MODEL    = os.getenv("OPENAI_MODEL",  "gpt-4o-mini")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL",  "gemini-1.5-flash")


# ──────────────────────────────────────────
# メイン生成関数
# ──────────────────────────────────────────

def generate_idea(system_prompt: str, user_prompt: str) -> str:
    """
    プロンプトをLLMに投げてアイデアテキストを返す。
    PROVIDER に応じて OpenAI / Gemini を切り替える。

    Raises:
        EnvironmentError: APIキーが未設定の場合
        RuntimeError:     API呼び出しに失敗した場合
    """
    if PROVIDER == "gemini":
        return _call_gemini(system_prompt, user_prompt)
    else:
        return _call_openai(system_prompt, user_prompt)


# ──────────────────────────────────────────
# OpenAI
# ──────────────────────────────────────────

def _call_openai(system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY が設定されていません。"
            ".env ファイルまたは環境変数に設定してください。"
        )

    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise ImportError(
            "openai パッケージがインストールされていません。"
            "  pip install openai"
        ) from e

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.9,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI API エラー: {e}") from e


# ──────────────────────────────────────────
# Gemini
# ──────────────────────────────────────────

def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY が設定されていません。"
            ".env ファイルまたは環境変数に設定してください。"
        )

    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as e:
        raise ImportError(
            "google-generativeai パッケージがインストールされていません。"
            "  pip install google-generativeai"
        ) from e

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt,
    )

    try:
        response = model.generate_content(
            user_prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.9,
                max_output_tokens=600,
            ),
        )
        return response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Gemini API エラー: {e}") from e


# ──────────────────────────────────────────
# ダミーモード（APIキーなしでの動作確認用）
# ──────────────────────────────────────────

def generate_idea_dummy(user_prompt: str) -> str:
    """
    APIキー未設定時に使えるダミー生成関数。
    開発・デモ用途のみ。
    """
    return textwrap.dedent("""
        【アイデア名】だるさログ
        【一言説明】今日のだるさを記録して、パターンを可視化するアプリ
        【解決する葛藤】「なんか今日だるい」の原因がわからず、無力感だけが積み重なる問題
        【コア機能】1タップでだるさレベルを記録。週次レポートで「だるさの法則」を自動分析
        【なぜ刺さるか】原因不明のだるさに名前をつけることで、自分を客観視できる安心感
    """).strip()