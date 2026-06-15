"""
app.py — AI Trend Architect: トレンド分析から紐解くアプリ仕様ジェネレーター
        （Haiku × Opus 4.6 ハイブリッド2段階構成）

起動方法:
  streamlit run app.py

必要な環境変数（.env ファイルに設定）:
  AWS_ACCESS_KEY_ID      : AWSアクセスキー
  AWS_SECRET_ACCESS_KEY  : AWSシークレットキー
  AWS_DEFAULT_REGION     : ap-southeast-2（Sydney）推奨。Haiku/Opus共通のデフォルト
  HAIKU_MODEL_ID / HAIKU_REGION : 第1段階（任意・通常は未設定でOK）
  OPUS_MODEL_ID  / OPUS_REGION  : 第2段階（任意・通常は未設定でOK）

フロー（バトンリレー形式）:
  1. トレンドデータを貼り付けて「🚀 ① Haikuでベースアイデアを生成する」
     → clean_trend_textでノイズ除去 → Claude Haiku 4.5 が箇条書きでブレスト
  2. 気に入らなければ指摘を入力して「この指摘を反映して再生成する」を繰り返す
     （①の再生成はHaikuなので低コスト）
  3. アイデアが確定したら「✅ このアイデアで確定し、Opus 4.6で設計書を生成する」
     → Claude Opus 4.6（シドニー推論プロファイル）が
       「技術設計書」＋「AI実装指示プロンプト」を1回で凝縮生成（maxTokens=4000）

  ①②は画面上部の切り替えタブ（ボタン式）で表示され、縦に積み重なりません。
"""

from __future__ import annotations

import os
import re

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

/* 出力エリア（①Haikuベースアイデア） */
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

/* 技術設計書パネル（②Opus・前半） */
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

/* AI実装指示プロンプトパネル（②Opus・後半） */
.build-panel {
    background: rgba(34,211,238,0.05);
    border: 1px solid rgba(34,211,238,0.25);
    border-radius: 16px;
    padding: 1.8rem 2rem;
    margin-top: 1.6rem;
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
.badge-amber  { background: rgba(251,191,36,0.18); color: #fcd34d; border: 1px solid rgba(251,191,36,0.35); }

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

/* フィードバックパネル（①Haiku再生成） */
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

/* 確定ボタンパネル（①→②Opus） */
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

/* ── ページ内タブ切り替えボタン ── */
.stButton > button[kind="secondary"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(99,102,241,0.18) !important;
    color: #8888aa !important;
    box-shadow: none !important;
    font-weight: 500 !important;
}
.stButton > button[kind="secondary"]:hover {
    background: rgba(99,102,241,0.12) !important;
    border-color: rgba(99,102,241,0.4) !important;
    color: #c7d2fe !important;
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

if "base_idea_result" not in st.session_state:
    st.session_state.base_idea_result = None   # ①Haikuベースアイデア（最新）
if "opus_result" not in st.session_state:
    st.session_state.opus_result = None        # ②Opus結合出力（技術設計書＋実装指示）
if "generating" not in st.session_state:
    st.session_state.generating = False         # ①初回生成中（Haiku）
if "refining" not in st.session_state:
    st.session_state.refining = False           # ①再生成中（Haiku）
if "opus_generating" not in st.session_state:
    st.session_state.opus_generating = False    # ②生成中（Opus）
if "error" not in st.session_state:
    st.session_state.error = None
if "last_input" not in st.session_state:
    st.session_state.last_input = ""
if "cleaned_chars" not in st.session_state:
    st.session_state.cleaned_chars = None       # クリーニング前後の文字数
if "idea_history" not in st.session_state:
    st.session_state.idea_history = []          # ①の過去バージョン履歴（Haiku）
if "view_tab" not in st.session_state:
    st.session_state.view_tab = "💡 ① Haikuベースアイデア"  # 現在表示中のタブ


# ──────────────────────────────────────────
# Opus結合出力のセクション分割
# ──────────────────────────────────────────

def split_opus_output(raw: str) -> tuple[str, str]:
    """
    Opusの結合出力を「技術設計書」と「AI実装指示プロンプト」に分割する。
    "## 🤖 AI実装指示プロンプト" のような見出し行で分割する。
    見つからない場合は全体を技術設計書側に入れ、プロンプト側は空文字を返す。
    """
    pattern = re.compile(r'(?m)^[ \t]*#{0,3}[ \t]*🤖?[ \t]*AI実装指示プロンプト.*$')
    m = pattern.search(raw)
    if not m:
        return raw.strip(), ""
    tech_part = raw[:m.start()].strip()
    prompt_part = raw[m.end():].strip()
    return tech_part, prompt_part


# ──────────────────────────────────────────
# ヘッダー
# ──────────────────────────────────────────

is_live = bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))

badge_html = (
    f'<span class="badge badge-indigo">🏗️ AI Trend Architect</span>'
    f'<span class="badge badge-amber">⚡ Stage1: Haiku 4.5</span>'
    f'<span class="badge badge-sky">🧠 Stage2: Opus 4.6</span>'
    f'<span class="badge badge-sky">Region: {llm.OPUS_REGION}</span>'
    f'<span class="badge badge-green">{"🟢 LIVE" if is_live else "🔴 DEMO"}</span>'
)

st.markdown(f"""
<div class="app-header">
    <h1>🏗️ AI Trend Architect</h1>
    <p>トレンド分析から紐解くアプリ仕様ジェネレーター — Haiku×Opusのハイブリッド2段階生成</p>
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

# 生成ボタン（①Haikuベースアイデア）
btn_label = "⏳ 生成中..." if st.session_state.generating else "🚀 ① Haikuでベースアイデアを生成する"
generate_clicked = st.button(
    btn_label,
    disabled=st.session_state.generating or not trend_input.strip(),
    use_container_width=True,
)

st.divider()

# ── 生成処理（①初回・Haiku） ──────────────────────────────
if generate_clicked and trend_input.strip():
    st.session_state.generating = True
    st.session_state.error = None

    with st.spinner("Claude Haiku 4.5 がベースアイデアをブレスト中... ⚡"):
        try:
            if is_live:
                cleaned = llm.clean_trend_text(trend_input.strip())
                st.session_state.cleaned_chars = (len(trend_input.strip()), len(cleaned))
                idea = llm.generate_base_idea(trend_input.strip())
            else:
                st.session_state.cleaned_chars = None
                idea = llm.generate_base_idea_dummy()

            st.session_state.base_idea_result = idea
            st.session_state.last_input = trend_input.strip()
            st.session_state.idea_history = [idea]   # 新規生成のたびに履歴をリセット
            st.session_state.opus_result = None      # ②も必ずリセット
            st.session_state.view_tab = "💡 ① Haikuベースアイデア"

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

# ── ①② 切り替えタブ ──────────────────────────────────────
if st.session_state.base_idea_result:

    # 利用可能なタブを動的に構築
    tab_options = ["💡 ① Haikuベースアイデア"]
    if st.session_state.opus_result:
        tab_options.append("🛠️ ② Opus設計書＋実装指示")

    # 現在のview_tabが選択肢に存在しない場合（②がまだ無い等）は①に戻す
    if st.session_state.view_tab not in tab_options:
        st.session_state.view_tab = "💡 ① Haikuベースアイデア"

    # ── タブ切り替え（ボタン式）────────────────────────────
    # 注意: view_tabはどのウィジェットのkeyにも使わない。
    #       (st.radioのkeyにすると、生成系ボタンが処理後にview_tabを
    #        書き換える際 "cannot be modified after the widget...is
    #        instantiated" エラーになるため)
    tab_cols = st.columns(len(tab_options))
    for col, option in zip(tab_cols, tab_options):
        with col:
            is_active = (st.session_state.view_tab == option)
            if st.button(
                option,
                key=f"tabbtn_{option}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.view_tab = option
                st.rerun()

    selected_tab = st.session_state.view_tab

    # ════════════════════════════════════════
    # タブ① — Haikuベースアイデア
    # ════════════════════════════════════════
    if selected_tab == "💡 ① Haikuベースアイデア":

        # ダウンロードボタン + クリーニング結果
        dl_col, info_col = st.columns([1, 3])
        with dl_col:
            st.download_button(
                label="📥 ①を.mdで保存",
                data=st.session_state.base_idea_result,
                file_name="base_idea.md",
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
        st.markdown("### ⚡ ① Haikuが考えたベースアイデア（ブレスト）", unsafe_allow_html=False)
        st.markdown(st.session_state.base_idea_result)
        st.markdown("</div>", unsafe_allow_html=True)

        # ── フィードバック & 再生成パネル（Haiku） ──────────────
        st.markdown('<div class="feedback-panel">', unsafe_allow_html=True)
        st.markdown("### 🔧 このアイデアに指摘・修正要望を出す", unsafe_allow_html=False)
        st.markdown(
            '<p class="desc">'
            '気になる点・変えたい部分を具体的に書いてください（例：「アプリ名がありきたりなので'
            'もっと個性的な案にして」「主要機能をもっとシンプルにして」など）。'
            'この指摘を反映して、Haikuが①のアイデアを再生成します（低コスト）。'
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
            "⏳ 再生成中..." if st.session_state.refining else "🔄 この指摘を反映して再生成する（Haiku）",
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

        # ── 再生成処理（①フィードバック反映・Haiku） ──────────────
        if refine_clicked and feedback_text.strip():
            st.session_state.refining = True
            st.session_state.error = None

            with st.spinner("Haikuが指摘を反映してベースアイデアを再構築中... ⚡"):
                try:
                    if is_live:
                        refined = llm.refine_base_idea(
                            trend_text=st.session_state.last_input,
                            previous_idea=st.session_state.base_idea_result,
                            feedback=feedback_text.strip(),
                        )
                    else:
                        refined = llm.generate_base_idea_dummy()

                    st.session_state.idea_history.append(refined)
                    st.session_state.base_idea_result = refined
                    st.session_state.opus_result = None  # ①が変わったら②をリセット
                    st.session_state.view_tab = "💡 ① Haikuベースアイデア"

                except (EnvironmentError, ImportError) as e:
                    st.session_state.error = str(e)
                except Exception as e:
                    st.session_state.error = f"予期しないエラー: {e}"
                finally:
                    st.session_state.refining = False

            st.rerun()

        # ── 確定 → ②Opus生成パネル ──────────────────────────────
        st.markdown('<div class="confirm-panel">', unsafe_allow_html=True)
        st.markdown("### ✅ このアイデアで確定する", unsafe_allow_html=False)
        st.markdown(
            '<p class="desc">'
            'もう指摘するところがなければ、このベースアイデアを確定し、'
            '<strong>Claude Opus 4.6</strong>に引き継いで'
            '「技術設計書」と「AI実装指示プロンプト」を1回で凝縮生成します'
            '（出力は無駄な解説を省いた簡潔な形式・maxTokens=4000の物理ブレーキ付き）。'
            '</p>',
            unsafe_allow_html=True,
        )

        confirm_clicked = st.button(
            "⏳ Opusが設計書を生成中..." if st.session_state.opus_generating
            else "✅ このアイデアで確定し、Opus 4.6で設計書を生成する",
            disabled=st.session_state.opus_generating,
            use_container_width=True,
            key="confirm_button",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        # ── 生成処理（②Opus結合出力） ────────────────────────────
        if confirm_clicked:
            st.session_state.opus_generating = True
            st.session_state.error = None

            with st.spinner("Claude Opus 4.6 が技術設計書＋実装指示を構築中... 🧠"):
                try:
                    if is_live:
                        opus = llm.generate_opus_spec(st.session_state.base_idea_result)
                    else:
                        opus = llm.generate_opus_spec_dummy()

                    st.session_state.opus_result = opus
                    st.session_state.view_tab = "🛠️ ② Opus設計書＋実装指示"

                except (EnvironmentError, ImportError) as e:
                    st.session_state.error = str(e)
                except Exception as e:
                    st.session_state.error = f"予期しないエラー: {e}"
                finally:
                    st.session_state.opus_generating = False

            st.rerun()

    # ════════════════════════════════════════
    # タブ② — Opus設計書 ＋ AI実装指示プロンプト
    # ════════════════════════════════════════
    elif selected_tab == "🛠️ ② Opus設計書＋実装指示":

        tech_part, prompt_part = split_opus_output(st.session_state.opus_result)

        # --- 技術設計書（前半） ---
        st.markdown('<div class="tech-panel">', unsafe_allow_html=True)
        st.markdown(
            '<p class="tech-panel-title">🛠️ Opusが仕上げた極小・高精度な技術設計書</p>',
            unsafe_allow_html=True,
        )
        st.markdown(tech_part if tech_part else st.session_state.opus_result)
        st.markdown("</div>", unsafe_allow_html=True)

        # --- AI実装指示プロンプト（後半・コピー用） ---
        if prompt_part:
            st.markdown('<div class="build-panel">', unsafe_allow_html=True)
            st.markdown(
                '<p class="build-panel-title">🤖 AI実装指示プロンプト（コピー用・コスト最適化込み）</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p style="font-size:0.8rem; color:#8aa; margin-bottom:1rem;">'
                'このプロンプトをそのままコピーして、Claude CodeやCursorなどの'
                'AIコーディングエージェントに貼り付けると実装が始められます。'
                '</p>',
                unsafe_allow_html=True,
            )
            st.code(prompt_part, language="markdown")
            st.markdown("</div>", unsafe_allow_html=True)

        # --- ダウンロード & 再生成 ---
        dl_col2, dl_col3, regen_col2 = st.columns([1, 1, 1])
        with dl_col2:
            st.download_button(
                label="📥 設計書を.mdで保存",
                data=tech_part if tech_part else st.session_state.opus_result,
                file_name="tech_spec.md",
                mime="text/markdown",
                key="dl_tech",
                use_container_width=True,
            )
        with dl_col3:
            st.download_button(
                label="📥 実装指示を.mdで保存",
                data=prompt_part if prompt_part else "",
                file_name="build_prompt.md",
                mime="text/markdown",
                key="dl_build",
                use_container_width=True,
                disabled=not prompt_part,
            )
        with regen_col2:
            regen_opus_clicked = st.button(
                "⏳ 再生成中..." if st.session_state.opus_generating else "🔄 ②を再生成する（Opus）",
                disabled=st.session_state.opus_generating,
                use_container_width=True,
                key="regen_opus_button",
            )

        if regen_opus_clicked:
            st.session_state.opus_generating = True
            st.session_state.error = None

            with st.spinner("Claude Opus 4.6 が技術設計書＋実装指示を再構築中... 🧠"):
                try:
                    if is_live:
                        opus = llm.generate_opus_spec(st.session_state.base_idea_result)
                    else:
                        opus = llm.generate_opus_spec_dummy()

                    st.session_state.opus_result = opus
                    st.session_state.view_tab = "🛠️ ② Opus設計書＋実装指示"

                except (EnvironmentError, ImportError) as e:
                    st.session_state.error = str(e)
                except Exception as e:
                    st.session_state.error = f"予期しないエラー: {e}"
                finally:
                    st.session_state.opus_generating = False

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
            ①Haikuのベースアイデアがここに表示されます
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────
# フッター
# ──────────────────────────────────────────

st.markdown(
    '<div class="footer">AI Trend Architect — Powered by Amazon Bedrock × Claude Haiku 4.5 + Opus 4.6 × Streamlit</div>',
    unsafe_allow_html=True,
)