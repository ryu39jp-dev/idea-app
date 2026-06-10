"""
app.py — AI Trend Architect: トレンド分析から紐解くアプリ仕様ジェネレーター

起動方法:
  streamlit run app.py

必要な環境変数（.env ファイルに設定）:
  AWS_ACCESS_KEY_ID      : AWSアクセスキー
  AWS_SECRET_ACCESS_KEY  : AWSシークレットキー
  AWS_DEFAULT_REGION     : ap-southeast-2（Sydney）推奨
  BEDROCK_MODEL_ID       : anthropic.claude-haiku-4-5-20251001-v1:0
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

/* 生成ボタン */
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

/* 出力エリア */
.output-panel {
    background: rgba(15,15,30,0.7);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 16px;
    padding: 1.8rem 2rem;
}
.output-panel h2 {
    font-family: 'Space Mono', monospace;
    font-size: 0.9rem;
    color: #6366f1;
    letter-spacing: 0.06em;
    margin: 0 0 1.2rem;
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

if "result" not in st.session_state:
    st.session_state.result = None
if "generating" not in st.session_state:
    st.session_state.generating = False
if "error" not in st.session_state:
    st.session_state.error = None
if "last_input" not in st.session_state:
    st.session_state.last_input = ""
if "cleaned_chars" not in st.session_state:
    st.session_state.cleaned_chars = None   # クリーニング後の文字数

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
# レイアウト：入力エリア（上）→ タブ出力（下）
# ──────────────────────────────────────────

# ── 入力エリア ────────────────────────────
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

# ヒント・デバッグ（横並び）
hint_col, debug_col = st.columns(2)
with hint_col:
    with st.expander("💡 精度を上げるコツ", expanded=False):
        st.markdown("""
入力に含めると精度UP：
- ターゲット属性（「20代女性」「エンジニア」等）
- 不満の具体的なセリフ（「〇〇が面倒」）
- プラットフォーム（X・YouTube・Reddit等）
- 競合への言及（「既存の□□では〜が足りない」）
""")
with debug_col:
    with st.expander("🔧 接続設定の確認", expanded=False):
        access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        st.code(
            f"KEY    = {'✅ ' + access_key[:8] + '...' if access_key else '❌ 未設定'}\n"
            f"SECRET = {'✅ 設定済み' if os.getenv('AWS_SECRET_ACCESS_KEY') else '❌ 未設定'}\n"
            f"REGION = {region}\n"
            f"MODEL  = {model_id.split('.')[-1]}\n"
            f".env   = {'✅ 存在' if os.path.exists('.env') else '❌ なし'}"
        )

st.markdown("<br>", unsafe_allow_html=True)

# 生成ボタン
btn_label = "⏳ 生成中..." if st.session_state.generating else "🚀 アプリ仕様書を生成する"
generate_clicked = st.button(
    btn_label,
    disabled=st.session_state.generating or not trend_input.strip(),
    use_container_width=True,
)

st.divider()

# ── 生成処理 ──────────────────────────────
if generate_clicked and trend_input.strip():
    st.session_state.generating = True
    st.session_state.error = None

    with st.spinner("Claude Haiku 4.5 が仕様書を構築中... 🏗️"):
        try:
            if is_live:
                cleaned = llm.clean_trend_text(trend_input.strip())
                st.session_state.cleaned_chars = (len(trend_input.strip()), len(cleaned))
                result = llm.generate_spec(trend_input.strip())
            else:
                st.session_state.cleaned_chars = None
                result = llm.generate_spec_dummy()

            st.session_state.result = result
            st.session_state.last_input = trend_input.strip()

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

# ── 結果表示（タブ） ──────────────────────
if st.session_state.result:

    # ダウンロードボタン + クリーニング結果
    dl_col, info_col = st.columns([1, 3])
    with dl_col:
        st.download_button(
            label="📥 .md で保存",
            data=st.session_state.result,
            file_name="app_spec.md",
            mime="text/markdown",
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

    # セクションをパースしてタブに分割
    raw = st.session_state.result

    def extract_section(text: str, marker: str, next_marker: str | None) -> str:
        """## ① 〜 ## ② の間を抽出する"""
        start = text.find(marker)
        if start == -1:
            return ""
        if next_marker:
            end = text.find(next_marker, start)
            return text[start:end].strip() if end != -1 else text[start:].strip()
        return text[start:].strip()

    sec1 = extract_section(raw, "## ①", "## ②")
    sec2 = extract_section(raw, "## ②", "## ③")
    sec3 = extract_section(raw, "## ③", "## ④")
    sec4 = extract_section(raw, "## ④", None)

    # セクションが取れない場合は全文をそのまま表示
    has_sections = any([sec1, sec2, sec3, sec4])

    if has_sections:
        tab1, tab2, tab3, tab4 = st.tabs([
            "👤 ① ターゲット選定",
            "💡 ② プロダクト構想",
            "🛠️ ③ MVP設計",
            "🎤 ④ ガクチカ",
        ])
        for tab, sec, label in [
            (tab1, sec1, "ターゲット選定"),
            (tab2, sec2, "プロダクト構想"),
            (tab3, sec3, "MVP設計"),
            (tab4, sec4, "ガクチカ"),
        ]:
            with tab:
                if sec:
                    st.markdown(sec)
                else:
                    st.info(f"{label} のセクションが見つかりませんでした。")
    else:
        # パースできない場合のフォールバック
        st.markdown(raw)

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
            仕様書がここにタブ表示されます
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