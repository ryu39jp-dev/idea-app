"""
database.py — SQLite layer for the idea evaluation app.
Handles table creation, insertion, and retrieval.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path("idea_eval.db")


# ──────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────

@dataclass
class Idea:
    id: int
    idea_text: str
    generation_prompt: str
    generated_at: str


@dataclass
class Evaluation:
    id: int
    idea_id: int
    self_need_score: int
    emotion_sync_score: int
    negative_emotion_relief_score: int
    originality_score: int
    feedback_text: str
    evaluated_at: str

    @property
    def total_score(self) -> float:
        """4項目の平均スコアを返す"""
        return (
            self.self_need_score
            + self.emotion_sync_score
            + self.negative_emotion_relief_score
            + self.originality_score
        ) / 4.0


# ──────────────────────────────────────────
# Connection helper
# ──────────────────────────────────────────

@contextmanager
def get_connection():
    """スレッドセーフなコネクションコンテキストマネージャ"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 並行アクセス耐性向上
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ──────────────────────────────────────────
# Initialization
# ──────────────────────────────────────────

def init_db() -> None:
    """テーブルが存在しない場合は自動生成する"""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ideas (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_text        TEXT    NOT NULL,
                generation_prompt TEXT   NOT NULL,
                generated_at     TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evaluations (
                id                            INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id                       INTEGER NOT NULL,
                self_need_score               INTEGER NOT NULL CHECK (self_need_score BETWEEN 1 AND 5),
                emotion_sync_score            INTEGER NOT NULL CHECK (emotion_sync_score BETWEEN 1 AND 5),
                negative_emotion_relief_score INTEGER NOT NULL CHECK (negative_emotion_relief_score BETWEEN 1 AND 5),
                originality_score             INTEGER NOT NULL CHECK (originality_score BETWEEN 1 AND 5),
                feedback_text                 TEXT    NOT NULL DEFAULT '',
                evaluated_at                  TEXT    NOT NULL,
                FOREIGN KEY (idea_id) REFERENCES ideas(id)
            );
        """)


# ──────────────────────────────────────────
# Ideas
# ──────────────────────────────────────────

def insert_idea(idea_text: str, generation_prompt: str) -> int:
    """新しいアイデアをDBに保存し、そのIDを返す"""
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO ideas (idea_text, generation_prompt, generated_at) VALUES (?, ?, ?)",
            (idea_text, generation_prompt, now),
        )
        return cur.lastrowid


def get_latest_idea() -> Optional[Idea]:
    """最新のアイデアを1件取得する"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ideas ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return Idea(**dict(row))


def get_idea_by_id(idea_id: int) -> Optional[Idea]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ideas WHERE id = ?", (idea_id,)
        ).fetchone()
    if row is None:
        return None
    return Idea(**dict(row))


# ──────────────────────────────────────────
# Evaluations
# ──────────────────────────────────────────

def insert_evaluation(
    idea_id: int,
    self_need_score: int,
    emotion_sync_score: int,
    negative_emotion_relief_score: int,
    originality_score: int,
    feedback_text: str,
) -> int:
    """評価をDBに保存し、そのIDを返す"""
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO evaluations (
                idea_id, self_need_score, emotion_sync_score,
                negative_emotion_relief_score, originality_score,
                feedback_text, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                idea_id,
                self_need_score,
                emotion_sync_score,
                negative_emotion_relief_score,
                originality_score,
                feedback_text,
                now,
            ),
        )
        return cur.lastrowid


def get_all_evaluations_with_ideas() -> list[dict]:
    """
    評価履歴とアイデアを結合して全件取得する。
    デバッグ用テーブル表示に使用。
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                e.id              AS eval_id,
                e.idea_id,
                i.idea_text,
                e.self_need_score,
                e.emotion_sync_score,
                e.negative_emotion_relief_score,
                e.originality_score,
                e.feedback_text,
                e.evaluated_at,
                ROUND(
                    (e.self_need_score + e.emotion_sync_score
                     + e.negative_emotion_relief_score + e.originality_score) / 4.0,
                    2
                ) AS avg_score
            FROM evaluations e
            JOIN ideas i ON i.id = e.idea_id
            ORDER BY e.id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_evaluations_for_prompt() -> tuple[list[dict], list[dict]]:
    """
    プロンプト組み立て用に高評価・低評価アイデアを返す。
    Returns:
        (high_eval_list, low_eval_list) — それぞれ avg_score 降順/昇順 top-3
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                i.idea_text,
                e.feedback_text,
                ROUND(
                    (e.self_need_score + e.emotion_sync_score
                     + e.negative_emotion_relief_score + e.originality_score) / 4.0,
                    2
                ) AS avg_score
            FROM evaluations e
            JOIN ideas i ON i.id = e.idea_id
            ORDER BY avg_score DESC
            """
        ).fetchall()

    all_evals = [dict(r) for r in rows]
    if not all_evals:
        return [], []

    high = all_evals[:3]           # 上位3件
    low  = all_evals[-3:][::-1]    # 下位3件（平均が低い順）
    return high, low


def get_latest_feedback(n: int = 3) -> list[str]:
    """直近 n 件のフィードバックテキストを返す（プロンプト用）"""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT feedback_text FROM evaluations
            WHERE feedback_text != ''
            ORDER BY id DESC
            LIMIT ?
            """,
            (n,),
        ).fetchall()
    return [r["feedback_text"] for r in rows]


def count_evaluations() -> int:
    """評価の総件数を返す"""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM evaluations").fetchone()
    return row["cnt"]