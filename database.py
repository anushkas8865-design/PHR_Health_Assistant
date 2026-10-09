"""
Database Foundation for Intelligent Personal Health Record (PHR) Assistant.
Provides safe SQLite initialization, thread-safe connections, and schema creation.
"""

import os
import sqlite3
from typing import Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "phr_database.db")


def get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Returns a configured SQLite connection.
    Enforces foreign keys and row access by column name.
    """
    target_path = db_path if db_path is not None else DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Safely creates tables if they do not exist.
    Guarantees that existing user data is never overwritten or deleted.
    """
    conn = get_db(db_path)
    cursor = conn.cursor()

    # 1. Health Records Table (Chronological personal health log)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS health_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_type TEXT NOT NULL CHECK(record_type IN ('symptom', 'measurement', 'general_note')),
        title TEXT NOT NULL,
        description TEXT,
        metric_name TEXT,
        metric_value REAL,
        metric_unit TEXT,
        recorded_date TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # 2. Medication Schedules Table (Active and historical schedules)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medication_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medication_name TEXT NOT NULL,
        dosage TEXT NOT NULL,
        frequency TEXT NOT NULL,
        reminder_time TEXT NOT NULL,
        start_date TEXT NOT NULL,
        instructions TEXT,
        is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
        created_at TEXT NOT NULL
    );
    """)

    # 3. Reminder Events Table (Tracks specific occurrences to prevent duplicate alerts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminder_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medication_id INTEGER NOT NULL REFERENCES medication_schedules(id) ON DELETE CASCADE,
        scheduled_date TEXT NOT NULL,
        scheduled_time TEXT NOT NULL,
        triggered_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'triggered' CHECK(status IN ('triggered', 'acknowledged', 'dismissed')),
        acknowledged_at TEXT,
        notes TEXT,
        UNIQUE(medication_id, scheduled_date, scheduled_time)
    );
    """)

    # Create indexes for fast chronological and foreign key queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_date ON health_records (recorded_date DESC, created_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_meds_active ON medication_schedules (is_active);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reminder_occurrence ON reminder_events (medication_id, scheduled_date, scheduled_time);")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database schema successfully initialized.")

