"""
app.py — AI Trend Architect: トレンド分析から紐解くアプリ仕様ジェネレーター

起動方法:
  streamlit run app.py

必要な環境変数（.env ファイルに設定）:
  AWS_ACCESS_KEY_ID      : AWSアクセスキー
  AWS_SECRET_ACCESS_KEY  : AWSシークレットキー
  AWS_DEFAULT_REGION     : ap-southeast-2（Sydney）推奨
  BEDROCK_MODEL_ID       : anthropic.claude-haiku-4-5-20251001-v1:0

フロー:
  1. トレンドデータを貼り付けて「① 核心アイデアを生成する」
  2. 気に入らなければ指摘を入力して「この指摘を反映して再生成する」を繰り返す
  3. アイデアが確定したら「✅ このアイデアで確定し、技術設計書を生成する」で②を生成
  4. ②が確定したら「🤖 AI実装指示プロンプトを生成する」で③を生成
     （③はコスト最適化を盛り込んだ、AIコーディングエージェント向けの指示文）

  ①②③は画面上部の切り替えタブ（ラジオ風）で表示され、縦に積み重なりません。
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# .env を最初に読み込む（import順序に依存しないよう先頭で実行）
load_dotenv(override=True)

import streamlit as st

import llm_client as llm

# ──────────────────────────────────────────
# ページ設定
# ──────────────────────────────────────────

st.set_page_config(
    page_title="AI Trend Architect",
    page_icon="🏗️",
    layout="wide",
)

# ──────────────────────────────────────────
# カスタム CSS
# ──────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; }

.stApp {
    background: linear-gradient(160deg, #0a0a14 0%, #111128 60%, #0a0a14 100%);
    color: #e2e2f0;
}

/* ヘッダー */
.app-header {
    padding: 2.4rem 0 1.6rem;
    border-bottom: 1px solid rgba(99,102,241,0.3);
    margin-bottom: 2rem;
}
.app-header h1 {
    font-family: 'Space Mono', monospace;
    font-size: 1.55rem;
    letter-spacing: 0.03em;
    background: linear-gradient(90deg, #818cf8, #38bdf8, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 0.5rem;
    line-height: 1.4;
}
.app-header p {
    color: #7070a0;
    font-size: 0.875rem;
    margin: 0;
}

/* インプットパネル */
.input-panel {
    background: rgba(99,102,241,0.07);
    border: 1px solid rgba(99,102,241,0.25);
    border-radius: 16px;
    padding: 1.6rem 1.8rem 1.8rem;
    margin-bottom: 1.6rem;
}
.input-panel h3 {
    font-family: 'Space Mono', monospace;
    font-size: 0.9rem;
    color: #a5b4fc;
    letter-spacing: 0.05em;
    margin: 0 0 1rem;
}

/* 生成ボタン（デフォルト：インディゴ系） */
.stButton > button {
    background: linear-gradient(135deg, #4f46e5, #0ea5e9) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.75rem 2rem !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em !important;
    width: 100% !important;
    box-shadow: 0 4px 20px rgba(79,70,229,0.45) !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* 出力エリア（①核心アイデア） */
.output-panel {
    background: rgba(15,15,30,0.7);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 16px;
    padding: 1.8rem 2rem;
}
.output-panel h2, .output-panel h3 {
    font-family: 'Space Mono', monospace;
    color: #6366f1;
    letter-spacing: 0.06em;
    margin: 0 0 1.2rem;
}

/* 技術設計書パネル（②） */
.tech-panel {
    background: rgba(14,165,233,0.06);
    border: 1px solid rgba(14,165,233,0.25);
    border-radius: 16px;
    padding: 1.8rem 2rem;
}
.tech-panel-title {
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    color: #7dd3fc;
    letter-spacing: 0.06em;
    margin: 0 0 1.2rem;
}

/* AI実装指示プロンプトパネル（③） */
.build-panel {
    background: rgba(34,211,238,0.05);
    border: 1px solid rgba(34,211,238,0.25);
    border-radius: 16px;
    padding: 1.8rem 2rem;
}
.build-panel-title {
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    color: #67e8f9;
    letter-spacing: 0.06em;
    margin: 0 0 1.2rem;
}
.build-panel pre, .build-panel code {
    white-space: pre-wrap !important;
}

/* Markdownの見出し調整 */
.stMarkdown h2 {
    color: #a5b4fc !important;
    font-size: 1.05rem !important;
    border-bottom: 1px solid rgba(99,102,241,0.2) !important;
    padding-bottom: 0.4rem !important;
    margin-top: 1.6rem !important;
}
.stMarkdown h3 { color: #7dd3fc !important; font-size: 0.95rem !important; }
.stMarkdown table {
    width: 100% !important;
    border-collapse: collapse !important;
    font-size: 0.875rem !important;
}
.stMarkdown th {
    background: rgba(99,102,241,0.15) !important;
    color: #a5b4fc !important;
    padding: 0.5rem 0.8rem !important;
    border: 1px solid rgba(99,102,241,0.2) !important;
}
.stMarkdown td {
    padding: 0.45rem 0.8rem !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    color: #d0d0e8 !important;
}

/* ステータスバッジ */
.badge {
    display: inline-block;
    padding: 0.18rem 0.65rem;
    border-radius: 20px;
    font-size: 0.7rem;
    font-family: 'Space Mono', monospace;
    margin-right: 0.4rem;
}
.badge-indigo { background: rgba(99,102,241,0.2); color: #a5b4fc; border: 1px solid rgba(99,102,241,0.35); }
.badge-sky    { background: rgba(14,165,233,0.2);  color: #7dd3fc; border: 1px solid rgba(14,165,233,0.35); }
.badge-green  { background: rgba(52,211,153,0.2);  color: #6ee7b7; border: 1px solid rgba(52,211,153,0.35); }

/* テキストエリア */
.stTextArea textarea {
    background: #1e1e2e !important;
    border: 1px solid rgba(99,102,241,0.25) !important;
    color: #f0f0ff !important;
    border-radius: 10px !important;
    font-size: 0.9rem !important;
    line-height: 1.7 !important;
}
.stTextArea textarea::placeholder {
    color: #7070a0 !important;
    opacity: 1 !important;
}
.stTextArea textarea:focus {
    border-color: rgba(99,102,241,0.6) !important;
    box-shadow: 0 0 0 2px rgba(99,102,241,0.15) !important;
}

hr { border-color: rgba(255,255,255,0.07) !important; }

/* フィードバックパネル */
.feedback-panel {
    background: rgba(52,211,153,0.06);
    border: 1px solid rgba(52,211,153,0.25);
    border-radius: 16px;
    padding: 1.4rem 1.8rem 1.6rem;
    margin-top: 1.6rem;
}
.feedback-panel h3 {
    font-family: 'Space Mono', monospace;
    font-size: 0.88rem;
    color: #6ee7b7;
    letter-spacing: 0.05em;
    margin: 0 0 0.8rem;
}
.feedback-panel p.desc {
    font-size: 0.8rem;
    color: #8aa;
    margin: 0 0 1rem;
}

/* 確定ボタンパネル */
.confirm-panel {
    background: rgba(244,114,182,0.06);
    border: 1px solid rgba(244,114,182,0.25);
    border-radius: 16px;
    padding: 1.4rem 1.8rem 1.6rem;
    margin-top: 1.6rem;
}
.confirm-panel h3 {
    font-family: 'Space Mono', monospace;
    font-size: 0.88rem;
    color: #f9a8d4;
    letter-spacing: 0.05em;
    margin: 0 0 0.8rem;
}
.confirm-panel p.desc {
    font-size: 0.8rem;
    color: #8aa;
    margin: 0 0 1rem;
}

/* ── ページ内タブ（ラジオ風） ── */
div[data-testid="stRadio"] > label { display: none; } /* ラジオ自体のラベルは非表示 */
div[data-testid="stRadio"] > div {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    border-bottom: 1px solid rgba(99,102,241,0.2);
    padding-bottom: 0;
    margin-bottom: 1.4rem;
}
div[data-testid="stRadio"] label {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(99,102,241,0.18);
    border-bottom: none;
    border-radius: 10px 10px 0 0;
    padding: 0.55rem 1.3rem !important;
    cursor: pointer;
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    color: #8888aa;
    transition: all 0.15s;
    margin-bottom: -1px;
}
div[data-testid="stRadio"] label:hover {
    background: rgba(99,102,241,0.1);
    color: #c7d2fe;
}
div[data-testid="stRadio"] label:has(input:checked) {
    background: rgba(99,102,241,0.18);
    border-color: rgba(99,102,241,0.5);
    color: #a5b4fc;
    font-weight: 700;
}
div[data-testid="stRadio"] label > div:first-child {
    display: none; /* ラジオの丸を隠す */
}

.footer {
    text-align: center;
    color: #333355;
    font-size: 0.7rem;
    font-family: 'Space Mono', monospace;
    margin-top: 3rem;
    padding-bottom: 1.5rem;
}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────
# セッション状態の初期化
# ──────────────────────────────────────────

if "idea_result" not in st.session_state:
    st.session_state.idea_result = None        # ①核心アイデア（最新）
if "tech_result" not in st.session_state:
    st.session_state.tech_result = None         # ②技術設計書
if "build_prompt_result" not in st.session_state:
    st.session_state.build_prompt_result = None # ③AI実装指示プロンプト
if "generating" not in st.session_state:
    st.session_state.generating = False         # ①初回生成中
if "refining" not in st.session_state:
    st.session_state.refining = False           # ①再生成中
if "tech_generating" not in st.session_state:
    st.session_state.tech_generating = False    # ②生成中
if "build_generating" not in st.session_state:
    st.session_state.build_generating = False   # ③生成中
if "error" not in st.session_state:
    st.session_state.error = None
if "last_input" not in st.session_state:
    st.session_state.last_input = ""
if "cleaned_chars" not in st.session_state:
    st.session_state.cleaned_chars = None       # クリーニング前後の文字数
if "idea_history" not in st.session_state:
    st.session_state.idea_history = []          # ①の過去バージョン履歴
if "view_tab" not in st.session_state:
    st.session_state.view_tab = "💡 ① アイデア"  # 現在表示中のタブ

# ──────────────────────────────────────────
# ヘッダー
# ──────────────────────────────────────────

model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")
region   = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")
is_live  = bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))

badge_html = (
    f'<span class="badge badge-indigo">🏗️ AI Trend Architect</span>'
    f'<span class="badge badge-sky">{model_id.split(".")[-1]}</span>'
    f'<span class="badge badge-sky">Region: {region}</span>'
    f'<span class="badge badge-green">{"🟢 LIVE" if is_live else "🔴 DEMO"}</span>'
)

st.markdown(f"""
<div class="app-header">
    <h1>🏗️ AI Trend Architect</h1>
    <p>トレンド分析から紐解くアプリ仕様ジェネレーター — 他のAIの出力を、即・開発仕様書に変換する</p>
    <div style="margin-top:0.8rem">{badge_html}</div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────
# 入力エリア
# ──────────────────────────────────────────

st.markdown('<div class="input-panel">', unsafe_allow_html=True)
st.markdown("### 📋 トレンド分析データを貼り付ける", unsafe_allow_html=False)

trend_input = st.text_area(
    label="トレンドデータ入力",
    placeholder=(
        "他のAI（PerplexityやChatGPTなど）で出力した\n"
        "「今XやYouTubeで話題の課題・不満・トレンド」を\n"
        "ここにそのまま貼り付けてください。\n\n"
        "例：\n"
        "・最近Z世代の間で〇〇への不満が急増しており...\n"
        "・Xのトレンドに「△△できない」「□□が面倒」が頻出...\n"
        "・YouTubeのコメント欄で共通して見られる悩みとして..."
    ),
    height=220,
    label_visibility="collapsed",
    key="trend_input_area",
)

st.markdown("</div>", unsafe_allow_html=True)

# 文字数カウント
char_count = len(trend_input)
if char_count > 0:
    color = "#34d399" if char_count >= 100 else "#fbbf24"
    st.markdown(
        f'<p style="font-size:0.78rem; color:{color}; text-align:right; margin-top:-0.8rem;">'
        f'{char_count:,} 文字'
        f'{"　✅ 生成できます" if char_count >= 100 else "　（100文字以上推奨）"}'
        f'</p>',
        unsafe_allow_html=True,
    )

# ヒント
with st.expander("💡 精度を上げるコツ", expanded=False):
    st.markdown("""
入力に含めると精度UP：
- ターゲット属性（「20代女性」「エンジニア」等）
- 不満の具体的なセリフ（「〇〇が面倒」）
- プラットフォーム（X・YouTube・Reddit等）
- 競合への言及（「既存の□□では〜が足りない」）
""")

st.markdown("<br>", unsafe_allow_html=True)

# 生成ボタン（①核心アイデア）
btn_label = "⏳ 生成中..." if st.session_state.generating else "🚀 ① 核心アイデアを生成する"
generate_clicked = st.button(
    btn_label,
    disabled=st.session_state.generating or not trend_input.strip(),
    use_container_width=True,
)

st.divider()

# ── 生成処理（①初回） ──────────────────────────────
if generate_clicked and trend_input.strip():
    st.session_state.generating = True
    st.session_state.error = None

    with st.spinner("Claude Haiku 4.5 がアイデアを構築中... 🏗️"):
        try:
            if is_live:
                cleaned = llm.clean_trend_text(trend_input.strip())
                st.session_state.cleaned_chars = (len(trend_input.strip()), len(cleaned))
                idea = llm.generate_idea_spec(trend_input.strip())
            else:
                st.session_state.cleaned_chars = None
                idea = llm.generate_idea_spec_dummy()

            st.session_state.idea_result = idea
            st.session_state.last_input = trend_input.strip()
            st.session_state.idea_history = [idea]       # 新規生成のたびに履歴をリセット
            st.session_state.tech_result = None          # ②も必ずリセット
            st.session_state.build_prompt_result = None  # ③も必ずリセット
            st.session_state.view_tab = "💡 ① アイデア"

        except (EnvironmentError, ImportError) as e:
            st.session_state.error = str(e)
        except Exception as e:
            st.session_state.error = f"予期しないエラー: {e}"
        finally:
            st.session_state.generating = False

    st.rerun()

# ── エラー表示 ────────────────────────────
if st.session_state.error:
    st.error(st.session_state.error)

# ── ①②③ 切り替えタブ ──────────────────────────────────────
if st.session_state.idea_result:

    # 利用可能なタブを動的に構築
    tab_options = ["💡 ① アイデア"]
    if st.session_state.tech_result:
        tab_options.append("🛠️ ② 技術設計書")
    if st.session_state.build_prompt_result:
        tab_options.append("🤖 ③ AI実装指示")

    # 現在のview_tabが選択肢に存在しない場合（②③がまだ無い等）は①に戻す
    if st.session_state.view_tab not in tab_options:
        st.session_state.view_tab = "💡 ① アイデア"

    selected_tab = st.radio(
        label="表示切り替え",
        options=tab_options,
        horizontal=True,
        label_visibility="collapsed",
        key="view_tab",
    )

    # ════════════════════════════════════════
    # タブ① — 核心アイデア
    # ════════════════════════════════════════
    if selected_tab == "💡 ① アイデア":

        # ダウンロードボタン + クリーニング結果
        dl_col, info_col = st.columns([1, 3])
        with dl_col:
            st.download_button(
                label="📥 ①を.mdで保存",
                data=st.session_state.idea_result,
                file_name="idea_spec.md",
                mime="text/markdown",
                key="dl_idea",
            )
        with info_col:
            if st.session_state.cleaned_chars:
                before, after = st.session_state.cleaned_chars
                saved = before - after
                pct = int(saved / before * 100) if before > 0 else 0
                st.markdown(
                    f'<p style="font-size:0.78rem; color:#6ee7b7; margin-top:0.6rem;">'
                    f'🧹 クリーニング済み: {before:,} 文字 → {after:,} 文字'
                    f'（<strong>{saved:,} 文字 / {pct}% 削減</strong>）'
                    f'</p>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="output-panel">', unsafe_allow_html=True)
        st.markdown("### 💡 ① プロダクトの核心アイデア", unsafe_allow_html=False)
        st.markdown(st.session_state.idea_result)
        st.markdown("</div>", unsafe_allow_html=True)

        # ── フィードバック & 再生成パネル ──────────────────────
        st.markdown('<div class="feedback-panel">', unsafe_allow_html=True)
        st.markdown("### 🔧 このアイデアに指摘・修正要望を出す", unsafe_allow_html=False)
        st.markdown(
            '<p class="desc">'
            '気になる点・変えたい部分を具体的に書いてください（例：「アプリ名がありきたりなので'
            'もっと個性的な案にして」「主要機能をもっとシンプルにして」など）。'
            'この指摘を反映して、①のアイデアを再生成します。'
            '</p>',
            unsafe_allow_html=True,
        )

        feedback_text = st.text_area(
            label="指摘・修正要望",
            placeholder=(
                "例：\n"
                "・アプリ名がありきたりなので、もっと個性的な案にしてほしい\n"
                "・主要機能の3つ目をもっとユニークなものに変えてほしい\n"
                "・解決する不満をもっと具体的に書いてほしい"
            ),
            height=120,
            label_visibility="collapsed",
            key="feedback_input_area",
        )

        refine_clicked = st.button(
            "⏳ 再生成中..." if st.session_state.refining else "🔄 この指摘を反映して再生成する",
            disabled=st.session_state.refining or not feedback_text.strip(),
            use_container_width=True,
            key="refine_button",
        )

        # 過去バージョンへのアクセス
        if len(st.session_state.idea_history) > 1:
            with st.expander(f"🕑 過去バージョンを見る（{len(st.session_state.idea_history)}件）", expanded=False):
                for i, past in enumerate(st.session_state.idea_history[:-1], start=1):
                    st.markdown(f"**バージョン {i}**")
                    st.markdown(past)
                    st.divider()

        st.markdown("</div>", unsafe_allow_html=True)

        # ── 再生成処理（①フィードバック反映） ──────────────────
        if refine_clicked and feedback_text.strip():
            st.session_state.refining = True
            st.session_state.error = None

            with st.spinner("指摘を反映してアイデアを再構築中... 🔧"):
                try:
                    if is_live:
                        refined = llm.refine_idea_spec(
                            trend_text=st.session_state.last_input,
                            previous_idea=st.session_state.idea_result,
                            feedback=feedback_text.strip(),
                        )
                    else:
                        refined = llm.generate_idea_spec_dummy()

                    st.session_state.idea_history.append(refined)
                    st.session_state.idea_result = refined
                    st.session_state.tech_result = None          # ①が変わったら②をリセット
                    st.session_state.build_prompt_result = None  # ③もリセット
                    st.session_state.view_tab = "💡 ① アイデア"

                except (EnvironmentError, ImportError) as e:
                    st.session_state.error = str(e)
                except Exception as e:
                    st.session_state.error = f"予期しないエラー: {e}"
                finally:
                    st.session_state.refining = False

            st.rerun()

        # ── 確定 → ②生成パネル ──────────────────────────────
        st.markdown('<div class="confirm-panel">', unsafe_allow_html=True)
        st.markdown("### ✅ このアイデアで確定する", unsafe_allow_html=False)
        st.markdown(
            '<p class="desc">'
            'もう指摘するところがなければ、このアイデアを確定し、'
            '技術スタック・自動生成用構造設計書（②）を生成します。'
            '</p>',
            unsafe_allow_html=True,
        )

        confirm_clicked = st.button(
            "⏳ 設計書を生成中..." if st.session_state.tech_generating
            else "✅ このアイデアで確定し、技術設計書を生成する",
            disabled=st.session_state.tech_generating,
            use_container_width=True,
            key="confirm_button",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        # ── 生成処理（②技術設計書） ────────────────────────────
        if confirm_clicked:
            st.session_state.tech_generating = True
            st.session_state.error = None

            with st.spinner("技術スタック・構造設計書を構築中... 🛠️"):
                try:
                    if is_live:
                        tech = llm.generate_tech_spec(st.session_state.idea_result)
                    else:
                        tech = llm.generate_tech_spec_dummy()

                    st.session_state.tech_result = tech
                    st.session_state.build_prompt_result = None  # ③もリセット
                    st.session_state.view_tab = "🛠️ ② 技術設計書"

                except (EnvironmentError, ImportError) as e:
                    st.session_state.error = str(e)
                except Exception as e:
                    st.session_state.error = f"予期しないエラー: {e}"
                finally:
                    st.session_state.tech_generating = False

            st.rerun()

    # ════════════════════════════════════════
    # タブ② — 技術スタック ＆ 構造設計書
    # ════════════════════════════════════════
    elif selected_tab == "🛠️ ② 技術設計書":

        st.markdown('<div class="tech-panel">', unsafe_allow_html=True)
        st.markdown(
            '<p class="tech-panel-title">🛠️ ② 最適技術スタック ＆ 自動生成用構造設計書</p>',
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state.tech_result)
        st.markdown("</div>", unsafe_allow_html=True)

        dl_col2, regen_col2 = st.columns([1, 1])
        with dl_col2:
            st.download_button(
                label="📥 ②を.mdで保存",
                data=st.session_state.tech_result,
                file_name="tech_spec.md",
                mime="text/markdown",
                key="dl_tech",
                use_container_width=True,
            )
        with regen_col2:
            regen_tech_clicked = st.button(
                "⏳ 再生成中..." if st.session_state.tech_generating else "🔄 ②を再生成する",
                disabled=st.session_state.tech_generating,
                use_container_width=True,
                key="regen_tech_button",
            )

        if regen_tech_clicked:
            st.session_state.tech_generating = True
            st.session_state.error = None

            with st.spinner("技術スタック・構造設計書を再構築中... 🛠️"):
                try:
                    if is_live:
                        tech = llm.generate_tech_spec(st.session_state.idea_result)
                    else:
                        tech = llm.generate_tech_spec_dummy()

                    st.session_state.tech_result = tech
                    st.session_state.build_prompt_result = None
                    st.session_state.view_tab = "🛠️ ② 技術設計書"

                except (EnvironmentError, ImportError) as e:
                    st.session_state.error = str(e)
                except Exception as e:
                    st.session_state.error = f"予期しないエラー: {e}"
                finally:
                    st.session_state.tech_generating = False

            st.rerun()

        # ── 確定 → ③生成パネル ──────────────────────────────
        st.markdown('<div class="confirm-panel">', unsafe_allow_html=True)
        st.markdown("### 🤖 この設計書でAI実装指示プロンプトを作る", unsafe_allow_html=False)
        st.markdown(
            '<p class="desc">'
            'Claude CodeやCursorなどのAIコーディングエージェントに、そのまま貼り付けて'
            '実装を依頼できる指示プロンプトを生成します。'
            '<strong>運用コストを抑える実装方針</strong>（無料枠ホスティング・API呼び出し最適化・'
            'キャッシュ等）も指示文に含まれます。'
            '</p>',
            unsafe_allow_html=True,
        )

        build_clicked = st.button(
            "⏳ 生成中..." if st.session_state.build_generating
            else "🤖 AI実装指示プロンプトを生成する",
            disabled=st.session_state.build_generating,
            use_container_width=True,
            key="build_button",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        # ── 生成処理（③AI実装指示プロンプト） ──────────────────
        if build_clicked:
            st.session_state.build_generating = True
            st.session_state.error = None

            with st.spinner("AIエージェント向けの実装指示プロンプトを構築中... 🤖"):
                try:
                    if is_live:
                        build_prompt = llm.generate_build_prompt(
                            idea_spec=st.session_state.idea_result,
                            tech_spec=st.session_state.tech_result,
                        )
                    else:
                        build_prompt = llm.generate_build_prompt_dummy()

                    st.session_state.build_prompt_result = build_prompt
                    st.session_state.view_tab = "🤖 ③ AI実装指示"

                except (EnvironmentError, ImportError) as e:
                    st.session_state.error = str(e)
                except Exception as e:
                    st.session_state.error = f"予期しないエラー: {e}"
                finally:
                    st.session_state.build_generating = False

            st.rerun()

    # ════════════════════════════════════════
    # タブ③ — AI実装指示プロンプト
    # ════════════════════════════════════════
    elif selected_tab == "🤖 ③ AI実装指示":

        st.markdown('<div class="build-panel">', unsafe_allow_html=True)
        st.markdown(
            '<p class="build-panel-title">🤖 ③ AI実装指示プロンプト（コスト最適化込み）</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p style="font-size:0.8rem; color:#8aa; margin-bottom:1rem;">'
            'このプロンプトをそのままコピーして、Claude CodeやCursorなどの'
            'AIコーディングエージェントに貼り付けると実装が始められます。'
            '</p>',
            unsafe_allow_html=True,
        )
        st.code(st.session_state.build_prompt_result, language="markdown")
        st.markdown("</div>", unsafe_allow_html=True)

        dl_col3, regen_col3 = st.columns([1, 1])
        with dl_col3:
            st.download_button(
                label="📥 ③を.mdで保存",
                data=st.session_state.build_prompt_result,
                file_name="build_prompt.md",
                mime="text/markdown",
                key="dl_build",
                use_container_width=True,
            )
        with regen_col3:
            regen_build_clicked = st.button(
                "⏳ 再生成中..." if st.session_state.build_generating else "🔄 ③を再生成する",
                disabled=st.session_state.build_generating,
                use_container_width=True,
                key="regen_build_button",
            )

        if regen_build_clicked:
            st.session_state.build_generating = True
            st.session_state.error = None

            with st.spinner("AIエージェント向けの実装指示プロンプトを再構築中... 🤖"):
                try:
                    if is_live:
                        build_prompt = llm.generate_build_prompt(
                            idea_spec=st.session_state.idea_result,
                            tech_spec=st.session_state.tech_result,
                        )
                    else:
                        build_prompt = llm.generate_build_prompt_dummy()

                    st.session_state.build_prompt_result = build_prompt
                    st.session_state.view_tab = "🤖 ③ AI実装指示"

                except (EnvironmentError, ImportError) as e:
                    st.session_state.error = str(e)
                except Exception as e:
                    st.session_state.error = f"予期しないエラー: {e}"
                finally:
                    st.session_state.build_generating = False

            st.rerun()

elif not st.session_state.error:
    st.markdown("""
<div style="
    height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px dashed rgba(99,102,241,0.2);
    border-radius: 16px;
    color: #444466;
    text-align: center;
">
    <div>
        <div style="font-size:2.5rem; opacity:0.35">🏗️</div>
        <p style="font-family:'Space Mono',monospace; font-size:0.82rem; color:#555577; margin:0.5rem 0 0;">
            ①核心アイデアがここに表示されます
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────
# フッター
# ──────────────────────────────────────────

st.markdown(
    '<div class="footer">AI Trend Architect — Powered by Amazon Bedrock × Claude Haiku 4.5 × Streamlit</div>',
    unsafe_allow_html=True,
)