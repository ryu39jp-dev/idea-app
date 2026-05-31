"""
app.py — アイデア出し＆評価ループアプリ（MVP）

起動方法:
  streamlit run app.py

必要な環境変数（.env ファイルまたはシェルで設定）:
  OPENAI_API_KEY=sk-...        # OpenAI を使う場合
  GEMINI_API_KEY=AIza...       # Gemini を使う場合
  LLM_PROVIDER=openai          # "openai" または "gemini"（デフォルト: openai）
"""

from __future__ import annotations

import os
from typing import Optional

import streamlit as st
from dotenv import load_dotenv  # python-dotenv

import database as db
import llm_client as llm
import prompt_builder as pb

# ──────────────────────────────────────────
# 初期設定
# ──────────────────────────────────────────

load_dotenv()  # .env ファイルから環境変数を読み込む

st.set_page_config(
    page_title="アイデア評価ループ",
    page_icon="💡",
    layout="centered",
)


# ──────────────────────────────────────────
# カスタム CSS
# ──────────────────────────────────────────

st.markdown(
    """
    <style>
    /* ── Google Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Noto Sans JP', sans-serif;
    }

    /* ── 全体背景 ── */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #0f0f1a 100%);
        color: #e8e8f0;
    }

    /* ── ヘッダー ── */
    .app-header {
        text-align: center;
        padding: 2rem 0 1rem;
        border-bottom: 1px solid rgba(120, 80, 255, 0.3);
        margin-bottom: 1.5rem;
    }
    .app-header h1 {
        font-family: 'Space Mono', monospace;
        font-size: 1.6rem;
        letter-spacing: 0.05em;
        background: linear-gradient(90deg, #a78bfa, #60a5fa, #34d399);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .app-header p {
        color: #8888aa;
        font-size: 0.85rem;
        margin: 0.4rem 0 0;
    }

    /* ── アイデアカード ── */
    .idea-card {
        background: linear-gradient(145deg, rgba(120,80,255,0.12), rgba(60,120,255,0.08));
        border: 1px solid rgba(120, 80, 255, 0.35);
        border-radius: 16px;
        padding: 1.6rem 2rem;
        margin-bottom: 1.8rem;
        box-shadow: 0 4px 32px rgba(120, 80, 255, 0.15);
        position: relative;
        overflow: hidden;
    }
    .idea-card::before {
        content: "💡";
        position: absolute;
        top: -0.2rem;
        right: 1rem;
        font-size: 3rem;
        opacity: 0.12;
    }
    .idea-card h2 {
        font-size: 1.1rem;
        color: #c4b5fd;
        margin: 0 0 0.6rem;
        font-family: 'Space Mono', monospace;
        letter-spacing: 0.04em;
    }
    .idea-text {
        font-size: 0.95rem;
        line-height: 1.85;
        color: #d4d4e8;
        white-space: pre-wrap;
    }
    .idea-meta {
        font-size: 0.75rem;
        color: #666688;
        margin-top: 1rem;
        font-family: 'Space Mono', monospace;
    }

    /* ── 評価フォームエリア ── */
    .eval-section {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 1.4rem 1.8rem 1.6rem;
        margin-bottom: 2rem;
    }
    .eval-section h3 {
        font-size: 1rem;
        color: #a0a0c8;
        margin: 0 0 1.2rem;
        font-family: 'Space Mono', monospace;
        letter-spacing: 0.04em;
    }

    /* ── スコアラベル ── */
    .score-label {
        font-size: 0.82rem;
        color: #9090b8;
        margin-bottom: 0.2rem;
    }

    /* ── ボタン上書き ── */
    .stButton > button {
        background: linear-gradient(135deg, #7c3aed, #2563eb) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.65rem 2rem !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.03em !important;
        width: 100% !important;
        transition: opacity 0.2s ease !important;
        box-shadow: 0 4px 16px rgba(124, 58, 237, 0.4) !important;
    }
    .stButton > button:hover {
        opacity: 0.88 !important;
    }

    /* ── デバッグエリア ── */
    .debug-header {
        font-family: 'Space Mono', monospace;
        font-size: 0.85rem;
        color: #555577;
        letter-spacing: 0.06em;
        margin-bottom: 0.4rem;
    }

    /* ── ステータスバッジ ── */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-family: 'Space Mono', monospace;
        margin-right: 0.5rem;
    }
    .badge-purple { background: rgba(124,58,237,0.25); color: #c4b5fd; border: 1px solid rgba(124,58,237,0.4); }
    .badge-blue   { background: rgba(37,99,235,0.25);  color: #93c5fd; border: 1px solid rgba(37,99,235,0.4); }
    .badge-green  { background: rgba(16,185,129,0.25); color: #6ee7b7; border: 1px solid rgba(16,185,129,0.4); }

    /* ── Streamlit デフォルト要素の調整 ── */
    div[data-testid="stSlider"] > div { margin-top: -0.4rem; }
    .stTextArea textarea {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        color: #d4d4e8 !important;
        border-radius: 10px !important;
    }
    .stDataFrame { border-radius: 10px; overflow: hidden; }

    /* ── Divider ── */
    hr { border-color: rgba(255,255,255,0.08) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────
# DB 初期化（アプリ起動時に1度だけ）
# ──────────────────────────────────────────

db.init_db()


# ──────────────────────────────────────────
# セッション状態の初期化
# ──────────────────────────────────────────

def _init_session_state() -> None:
    """セッション変数のデフォルト値をセットする"""
    if "current_idea" not in st.session_state:
        st.session_state.current_idea = None     # 現在表示中のアイデア (db.Idea)
    if "generating" not in st.session_state:
        st.session_state.generating = False      # LLM 呼び出し中フラグ
    if "error_message" not in st.session_state:
        st.session_state.error_message = None    # エラーメッセージ
    if "initialized" not in st.session_state:
        st.session_state.initialized = False     # 初回アイデア生成済みフラグ


_init_session_state()


# ──────────────────────────────────────────
# ヘルパー：アイデア生成（DB 保存込み）
# ──────────────────────────────────────────

def _generate_and_save_idea(user_prompt: str) -> db.Idea:
    """
    LLM にアイデアを生成させて DB に保存し、Idea オブジェクトを返す。
    APIキー未設定の場合はダミーデータを使用する。
    """
    api_key_set = bool(
        os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
    )

    if api_key_set:
        idea_text = llm.generate_idea(pb.SYSTEM_PROMPT, user_prompt)
    else:
        # デモ用ダミー（APIキー未設定時）
        idea_text = llm.generate_idea_dummy(user_prompt)

    idea_id = db.insert_idea(idea_text, user_prompt)
    return db.get_idea_by_id(idea_id)


# ──────────────────────────────────────────
# 初回アイデア生成（DB 空のとき）
# ──────────────────────────────────────────

if not st.session_state.initialized:
    if db.count_evaluations() == 0 and st.session_state.current_idea is None:
        # DBが空 → デフォルトプロンプトで最初のアイデアを生成
        latest = db.get_latest_idea()
        if latest:
            st.session_state.current_idea = latest
        else:
            try:
                st.session_state.current_idea = _generate_and_save_idea(
                    pb.DEFAULT_FIRST_PROMPT
                )
            except Exception as e:
                st.session_state.error_message = str(e)
    else:
        # 既存データあり → 最新のアイデアを表示
        if st.session_state.current_idea is None:
            st.session_state.current_idea = db.get_latest_idea()

    st.session_state.initialized = True


# ──────────────────────────────────────────
# ヘッダー
# ──────────────────────────────────────────

st.markdown(
    """
    <div class="app-header">
        <h1>💡 IDEA EVAL LOOP</h1>
        <p>AIが生成したアプリ企画を評価して、次のアイデアを磨いていく</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# API キー未設定時の警告
if not (os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")):
    st.warning(
        "⚠️ **APIキーが設定されていません。** "
        "`.env` ファイルに `OPENAI_API_KEY` または `GEMINI_API_KEY` を設定してください。"
        "現在はダミーデータで動作しています。",
        icon="⚠️",
    )

# エラーメッセージ表示
if st.session_state.error_message:
    st.error(f"❌ エラーが発生しました: {st.session_state.error_message}")
    st.session_state.error_message = None


# ──────────────────────────────────────────
# アイデア表示エリア
# ──────────────────────────────────────────

current_idea: Optional[db.Idea] = st.session_state.current_idea

if current_idea is None:
    st.info("アイデアを読み込み中です...")
else:
    # バッジ情報
    eval_count = db.count_evaluations()
    badge_html = (
        f'<span class="badge badge-purple">IDEA #{current_idea.id}</span>'
        f'<span class="badge badge-blue">評価済み {eval_count} 件</span>'
        f'<span class="badge badge-green">{"🔴 DEMO" if not (os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")) else "🟢 LIVE"}</span>'
    )

    st.markdown(
        f"""
        <div class="idea-card">
            <h2>✦ 今回のアイデア</h2>
            <div class="idea-text">{current_idea.idea_text}</div>
            <div class="idea-meta">
                {badge_html}<br>
                生成日時: {current_idea.generated_at}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────
# 評価フォーム
# ──────────────────────────────────────────

st.markdown('<div class="eval-section">', unsafe_allow_html=True)
st.markdown("### 📊 このアイデアを評価する", unsafe_allow_html=False)

col1, col2 = st.columns(2)

with col1:
    st.markdown('<p class="score-label">① 自分ニーズ度（自分が欲しいか）</p>', unsafe_allow_html=True)
    self_need = st.slider(
        "自分ニーズ度",
        min_value=1, max_value=5, value=3,
        key="self_need_score",
        label_visibility="collapsed",
    )

    st.markdown('<p class="score-label">② 感情のシンクロ度（共感できるか）</p>', unsafe_allow_html=True)
    emotion_sync = st.slider(
        "感情のシンクロ度",
        min_value=1, max_value=5, value=3,
        key="emotion_sync_score",
        label_visibility="collapsed",
    )

with col2:
    st.markdown('<p class="score-label">③ 負の感情解消度（モヤモヤが消えるか）</p>', unsafe_allow_html=True)
    neg_relief = st.slider(
        "負の感情解消度",
        min_value=1, max_value=5, value=3,
        key="neg_relief_score",
        label_visibility="collapsed",
    )

    st.markdown('<p class="score-label">④ 意外性（驚きや新鮮さがあるか）</p>', unsafe_allow_html=True)
    originality = st.slider(
        "意外性",
        min_value=1, max_value=5, value=3,
        key="originality_score",
        label_visibility="collapsed",
    )

# スコアサマリー
avg = (self_need + emotion_sync + neg_relief + originality) / 4.0
st.markdown(
    f"**現在の平均スコア: `{avg:.2f} / 5.0`** "
    f"（①{self_need} ②{emotion_sync} ③{neg_relief} ④{originality}）"
)

st.markdown("")
feedback = st.text_area(
    "💬 本音フィードバック（任意）",
    placeholder="このアイデアについて正直に。「惜しい」「こういうのより〇〇が欲しい」など何でも",
    height=90,
    key="feedback_text",
)

st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────
# 「次のアイデアを出す」ボタン
# ──────────────────────────────────────────

button_disabled = (current_idea is None) or st.session_state.generating

if st.button(
    "🚀 この評価で次のアイデアを出す",
    disabled=button_disabled,
    use_container_width=True,
):
    if current_idea is None:
        st.error("アイデアが読み込まれていません。ページを再読み込みしてください。")
    else:
        st.session_state.generating = True

        with st.spinner("評価を保存して次のアイデアを生成中... ✨"):
            try:
                # ① 評価を DB に保存
                db.insert_evaluation(
                    idea_id=current_idea.id,
                    self_need_score=self_need,
                    emotion_sync_score=emotion_sync,
                    negative_emotion_relief_score=neg_relief,
                    originality_score=originality,
                    feedback_text=feedback.strip(),
                )

                # ② 過去の評価データを取得してプロンプトを組み立てる
                high_evals, low_evals = db.get_evaluations_for_prompt()
                recent_feedbacks = db.get_latest_feedback(n=3)

                user_prompt = pb.build_dynamic_prompt(
                    high_evals=high_evals,
                    low_evals=low_evals,
                    recent_feedbacks=recent_feedbacks,
                )

                # ③ LLM でアイデア生成 → DB 保存
                new_idea = _generate_and_save_idea(user_prompt)
                st.session_state.current_idea = new_idea

                st.success("✅ 新しいアイデアを生成しました！")

            except (EnvironmentError, ImportError) as e:
                st.session_state.error_message = str(e)
            except Exception as e:
                st.session_state.error_message = f"予期しないエラー: {e}"
            finally:
                st.session_state.generating = False

        st.rerun()


# ──────────────────────────────────────────
# デバッグ用：評価履歴テーブル
# ──────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)
st.divider()

with st.expander("🗂️ デバッグ：評価履歴データベース", expanded=False):
    history = db.get_all_evaluations_with_ideas()

    if not history:
        st.info("まだ評価データがありません。最初のアイデアを評価してみましょう！")
    else:
        import pandas as pd

        df = pd.DataFrame(history)

        # 列名を日本語に
        df = df.rename(columns={
            "eval_id":                          "評価ID",
            "idea_id":                          "アイデアID",
            "idea_text":                        "アイデア（冒頭60文字）",
            "self_need_score":                  "①自分ニーズ",
            "emotion_sync_score":               "②感情シンクロ",
            "negative_emotion_relief_score":    "③負感情解消",
            "originality_score":                "④意外性",
            "avg_score":                        "平均スコア",
            "feedback_text":                    "フィードバック",
            "evaluated_at":                     "評価日時",
        })

        # アイデアテキストを短縮表示
        df["アイデア（冒頭60文字）"] = df["アイデア（冒頭60文字）"].str[:60] + "…"

        st.markdown(
            f'<p class="debug-header">EVALUATIONS TABLE — {len(df)} records</p>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "平均スコア": st.column_config.NumberColumn(format="%.2f ⭐"),
                "①自分ニーズ":  st.column_config.NumberColumn(format="%d / 5"),
                "②感情シンクロ": st.column_config.NumberColumn(format="%d / 5"),
                "③負感情解消":  st.column_config.NumberColumn(format="%d / 5"),
                "④意外性":     st.column_config.NumberColumn(format="%d / 5"),
            },
        )

        # 平均スコア推移グラフ
        if len(df) >= 2:
            st.markdown("**📈 平均スコアの推移**")
            chart_df = df[["評価ID", "平均スコア"]].set_index("評価ID").sort_index()
            st.line_chart(chart_df, height=180)


# ──────────────────────────────────────────
# フッター
# ──────────────────────────────────────────

st.markdown(
    """
    <div style="text-align:center; color:#444466; font-size:0.72rem;
                font-family:'Space Mono',monospace; margin-top:2rem; padding-bottom:1rem;">
        IDEA EVAL LOOP — MVP v0.1 | Powered by Streamlit + SQLite + LLM
    </div>
    """,
    unsafe_allow_html=True,
)