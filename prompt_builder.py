"""
prompt_builder.py — 評価履歴から動的プロンプトを組み立てるモジュール
"""

from __future__ import annotations

# ──────────────────────────────────────────
# システムプロンプト（固定）
# ──────────────────────────────────────────

SYSTEM_PROMPT = """あなたは鋭い洞察力を持つプロダクトアイデアジェネレーターです。
現代人が日常的に感じるリアルな葛藤、だるさ、もやもや感に刺さる「アプリ企画アイデア」を1つだけ生成してください。

出力フォーマット（必ずこの形式で）:
【アイデア名】〈簡潔なアプリ名〉
【一言説明】〈20〜40文字でアプリの本質を表す〉
【解決する葛藤】〈ユーザーが感じているリアルな痛みや不満〉
【コア機能】〈アプリの核となる機能を1〜2行で〉
【なぜ刺さるか】〈感情的・心理的な訴求ポイント〉

上記5項目を必ず含め、余計な前置きや後書きは一切不要です。"""

# ──────────────────────────────────────────
# 初回起動用デフォルトプロンプト
# ──────────────────────────────────────────

DEFAULT_FIRST_PROMPT = "現代人のリアルな葛藤やだるさを突いたアプリ企画を1つ出してください。"


# ──────────────────────────────────────────
# 動的プロンプト組み立て
# ──────────────────────────────────────────

def build_dynamic_prompt(
    high_evals: list[dict],
    low_evals: list[dict],
    recent_feedbacks: list[str],
) -> str:
    """
    過去の評価データから動的ユーザープロンプトを組み立てる。

    Args:
        high_evals: 高評価アイデアのリスト（avg_score, idea_text, feedback_text）
        low_evals:  低評価アイデアのリスト（同上）
        recent_feedbacks: 直近のフィードバックテキストリスト

    Returns:
        LLM に渡すユーザープロンプト文字列
    """
    lines: list[str] = []

    # ── 高評価 Few-shot ──
    if high_evals:
        lines.append("【参考：ユーザーが高評価したアイデア（こういう方向性が好まれています）】")
        for i, ev in enumerate(high_evals, 1):
            lines.append(
                f"  {i}. （平均 {ev['avg_score']} / 5.0）{ev['idea_text'][:80]}…"
            )
            if ev.get("feedback_text"):
                lines.append(f"     フィードバック: {ev['feedback_text']}")
        lines.append("")

    # ── 低評価 Negative example ──
    if low_evals:
        lines.append("【避けるべきアイデアの傾向（こういう方向性は低評価でした）】")
        for i, ev in enumerate(low_evals, 1):
            lines.append(
                f"  {i}. （平均 {ev['avg_score']} / 5.0）{ev['idea_text'][:80]}…"
            )
            if ev.get("feedback_text"):
                lines.append(f"     フィードバック: {ev['feedback_text']}")
        lines.append("")

    # ── 直近の不満・要望 ──
    if recent_feedbacks:
        lines.append("【直近のユーザーの本音・不満（これを踏まえて改善してください）】")
        for fb in recent_feedbacks:
            lines.append(f"  - {fb}")
        lines.append("")

    # ── 指示 ──
    lines.append(
        "上記のフィードバックと評価傾向を完全に学習したうえで、"
        "高評価の方向性を維持しつつ、低評価アイデアとは明確に差別化された、"
        "新鮮で刺さる次のアプリ企画アイデアを1つ生成してください。"
        "過去と同じアイデアは絶対に出さないでください。"
    )

    return "\n".join(lines) if lines else DEFAULT_FIRST_PROMPT