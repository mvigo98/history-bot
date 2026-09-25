# -*- coding: utf-8 -*-
"""
وحدة إدارة قاعدة البيانات لحفظ سكريبتات ومواضيع البوت
تضمن عدم تكرار أي فكرة تم إنشاؤها مسبقاً لكل مستخدم
"""

import sqlite3
import os
from typing import List, Dict, Optional

import tempfile

if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    DB_PATH = os.path.join(tempfile.gettempdir(), "history_bot.db")
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "history_bot.db")


def get_connection():
    """الحصول على اتصال بقاعدة البيانات مع تفعيل Row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """تهيئة جداول قاعدة البيانات إذا لم تكن موجودة"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic_title TEXT NOT NULL,
                era_category TEXT,
                script_text TEXT NOT NULL,
                format_type TEXT DEFAULT 'standard',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_scripts 
            ON scripts (user_id, created_at DESC)
            """
        )
        conn.commit()


def save_script(
    user_id: int,
    topic_title: str,
    era_category: Optional[str],
    script_text: str,
    format_type: str = "standard",
) -> int:
    """حفظ سكريبت جديد في قاعدة البيانات وإرجاع الـ id الخاص به"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO scripts (user_id, topic_title, era_category, script_text, format_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, topic_title, era_category or "عام", script_text, format_type),
        )
        conn.commit()
        return cursor.lastrowid


def get_user_recent_topics(user_id: int, limit: int = 50) -> List[str]:
    """جلب قائمة بأسماء المواضيع التي تم توليدها للمستخدم لمنع تكرارها"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT topic_title FROM scripts 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = cursor.fetchall()
        return [row["topic_title"] for row in rows]


def get_user_history(user_id: int, limit: int = 10) -> List[Dict]:
    """جلب ملخص بآخر السكريبتات التي تم توليدها للمستخدم"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, topic_title, era_category, format_type, created_at
            FROM scripts 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_last_base_script(user_id: int) -> Optional[Dict]:
    """جلب آخر سكريبت أساسي غير منسق مسبقاً كتلقين لمنع الاقتطاع التراكمي"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, topic_title, era_category, script_text, format_type, created_at
            FROM scripts 
            WHERE user_id = ? AND format_type != 'teleprompter'
            ORDER BY id DESC 
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        # إذا لم يوجد سكريبت غير التلقين، نأخذ آخر سكريبت أياً كان نوعه
        cursor.execute(
            """
            SELECT id, user_id, topic_title, era_category, script_text, format_type, created_at
            FROM scripts 
            WHERE user_id = ?
            ORDER BY id DESC 
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_script_by_id(script_id: int) -> Optional[Dict]:
    """جلب تفاصيل سكريبت محدد بواسطة المعرف ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, topic_title, era_category, script_text, format_type, created_at
            FROM scripts 
            WHERE id = ?
            """,
            (script_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def find_script_by_title_or_snippet(
    user_id: int, title: Optional[str] = None, snippet: Optional[str] = None
) -> Optional[Dict]:
    """البحث عن سكريبت للمستخدم بالعنوان أو بجزء من النص (للاستخدام مع ميزة الـ Reply)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if title:
            clean_title = title.strip().replace("*", "").replace("#", "").strip()
            cursor.execute(
                """
                SELECT id, user_id, topic_title, era_category, script_text, format_type, created_at
                FROM scripts 
                WHERE user_id = ? AND (topic_title LIKE ? OR ? LIKE '%' || topic_title || '%')
                ORDER BY id DESC LIMIT 1
                """,
                (user_id, f"%{clean_title}%", clean_title),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

        if snippet and len(snippet.strip()) >= 15:
            clean_snippet = snippet.strip()[:60]
            cursor.execute(
                """
                SELECT id, user_id, topic_title, era_category, script_text, format_type, created_at
                FROM scripts 
                WHERE user_id = ? AND instr(script_text, ?) > 0
                ORDER BY id DESC LIMIT 1
                """,
                (user_id, clean_snippet),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

        return None


def get_base_script_for(script_data: Optional[Dict]) -> Optional[Dict]:
    """إرجاع السكريبت الأساسي الكامل في حال كان السكريبت الممرر نسخة تلقين مسبقة لمنع التكرار"""
    if not script_data:
        return None
    if script_data.get("format_type") != "teleprompter":
        return script_data

    import re
    clean_title = re.sub(r"\s*\((?:تلقين|ريلز|يوتيوب|مخصص)\)", "", script_data["topic_title"]).strip()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM scripts 
            WHERE user_id = ? AND format_type != 'teleprompter' AND topic_title LIKE ?
            ORDER BY id DESC LIMIT 1
            """,
            (script_data["user_id"], f"%{clean_title}%"),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
    return script_data


def count_user_scripts(user_id: int) -> int:
    """حساب إجمالي السكريبتات التي قام المستخدم بإنشائها"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM scripts WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        return row["cnt"] if row else 0


def clear_user_history(user_id: int) -> int:
    """مسح سجل مواضيع المستخدم والبدء من جديد"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scripts WHERE user_id = ?", (user_id,))
        deleted = cursor.rowcount
        conn.commit()
        return deleted


# تهيئة الجداول تلقائياً عند استيراد الملف
init_db()
