"""
Unit Tests for Database Foundation (tests/test_database.py).
Tests schema creation, integrity constraints, and idempotence using an in-memory SQLite database.
"""

import os
import sys
import unittest
import sqlite3

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import init_db, get_db


class TestDatabaseFoundation(unittest.TestCase):
    def setUp(self):
        # Use an isolated test database in memory
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")

        # Apply schema to in-memory connection
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE health_records (
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
        cursor.execute("""
        CREATE TABLE medication_schedules (
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
        cursor.execute("""
        CREATE TABLE reminder_events (
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
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_health_record_insert_and_constraint(self):
        cursor = self.conn.cursor()
        # Valid insert
        cursor.execute("""
        INSERT INTO health_records (record_type, title, description, metric_name, metric_value, metric_unit, recorded_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("measurement", "Blood Pressure", "Routine morning check", "Systolic BP", 120.0, "mmHg", "2026-10-09", "2026-10-09T08:00:00Z"))
        self.conn.commit()

        row = cursor.execute("SELECT * FROM health_records WHERE title = ?", ("Blood Pressure",)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["metric_value"], 120.0)
        self.assertEqual(row["record_type"], "measurement")

        # Invalid record_type constraint check
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("""
            INSERT INTO health_records (record_type, title, recorded_date, created_at)
            VALUES (?, ?, ?, ?)
            """, ("invalid_type", "Test", "2026-10-09", "2026-10-09T08:00:00Z"))

    def test_medication_schedule_and_deactivation(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO medication_schedules (medication_name, dosage, frequency, reminder_time, start_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("Metformin", "500 mg", "Once daily", "08:00", "2026-10-09", "2026-10-09T08:00:00Z"))
        self.conn.commit()
        med_id = cursor.lastrowid

        # Verify active
        row = cursor.execute("SELECT is_active FROM medication_schedules WHERE id = ?", (med_id,)).fetchone()
        self.assertEqual(row["is_active"], 1)

        # Deactivate schedule
        cursor.execute("UPDATE medication_schedules SET is_active = 0 WHERE id = ?", (med_id,))
        self.conn.commit()

        row_deactivated = cursor.execute("SELECT is_active FROM medication_schedules WHERE id = ?", (med_id,)).fetchone()
        self.assertEqual(row_deactivated["is_active"], 0)

    def test_reminder_occurrence_unique_constraint(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO medication_schedules (medication_name, dosage, frequency, reminder_time, start_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("Lisinopril", "10 mg", "Once daily", "09:00", "2026-10-09", "2026-10-09T08:00:00Z"))
        self.conn.commit()
        med_id = cursor.lastrowid

        # Insert first occurrence
        cursor.execute("""
        INSERT INTO reminder_events (medication_id, scheduled_date, scheduled_time, triggered_at, status)
        VALUES (?, ?, ?, ?, ?)
        """, (med_id, "2026-10-09", "09:00", "2026-10-09T09:00:02Z", "triggered"))
        self.conn.commit()

        # Duplicate occurrence on same date and time MUST fail
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("""
            INSERT INTO reminder_events (medication_id, scheduled_date, scheduled_time, triggered_at, status)
            VALUES (?, ?, ?, ?, ?)
            """, (med_id, "2026-10-09", "09:00", "2026-10-09T09:00:05Z", "triggered"))

        # Occurrence on different date succeeds
        cursor.execute("""
        INSERT INTO reminder_events (medication_id, scheduled_date, scheduled_time, triggered_at, status)
        VALUES (?, ?, ?, ?, ?)
        """, (med_id, "2026-10-10", "09:00", "2026-10-10T09:00:01Z", "triggered"))
        self.conn.commit()

        events = cursor.execute("SELECT * FROM reminder_events WHERE medication_id = ?", (med_id,)).fetchall()
        self.assertEqual(len(events), 2)

    def test_init_db_file_idempotence(self):
        import tempfile
        temp_dir = tempfile.mkdtemp()
        temp_db = os.path.join(temp_dir, "test_phr.db")
        try:
            # 1. First init_db call
            init_db(temp_db)
            conn = get_db(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            self.assertIn("health_records", tables)
            self.assertIn("medication_schedules", tables)
            self.assertIn("reminder_events", tables)

            # Insert sample data
            cursor.execute("""
            INSERT INTO health_records (record_type, title, recorded_date, created_at)
            VALUES (?, ?, ?, ?)
            """, ("symptom", "Headache", "2026-10-09", "2026-10-09T10:00:00Z"))
            conn.commit()
            conn.close()

            # 2. Second init_db call must not erase existing data
            init_db(temp_db)
            conn2 = get_db(temp_db)
            row = conn2.execute("SELECT title FROM health_records WHERE title = ?", ("Headache",)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "Headache")
            conn2.close()
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)


if __name__ == "__main__":
    unittest.main()
