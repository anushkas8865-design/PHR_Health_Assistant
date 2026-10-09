"""
Unit Tests for Service Layer (tests/test_services.py).
Tests record_services.py and reminder_service.py against an isolated in-memory SQLite database.
"""

import math
import os
import sys
import unittest
import sqlite3

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from record_services import (
    validate_health_record,
    create_health_record,
    get_health_history,
    generate_health_summary
)
from reminder_service import (
    validate_medication_schedule,
    create_medication_schedule,
    get_active_schedules,
    deactivate_schedule,
    log_reminder_occurrence,
    acknowledge_reminder
)


class TestServiceLayer(unittest.TestCase):
    def setUp(self):
        # Create fresh in-memory database with schema for each test
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")

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

    # --- 1. Health Record Validation Tests ---

    def test_record_validation_success(self):
        valid_data = {
            "record_type": "measurement",
            "title": "Morning Blood Pressure",
            "description": "Resting seated",
            "metric_name": "Systolic BP",
            "metric_value": 120.5,
            "metric_unit": "mmHg",
            "recorded_date": "2026-10-09"
        }
        ok, err, val = validate_health_record(valid_data)
        self.assertTrue(ok)
        self.assertEqual(val["metric_value"], 120.5)

    def test_record_validation_invalid_type_and_missing_title(self):
        ok, err, _ = validate_health_record({"record_type": "invalid_type", "title": "Check", "recorded_date": "2026-10-09"})
        self.assertFalse(ok)
        self.assertIn("Invalid record_type", err)

        ok, err, _ = validate_health_record({"record_type": "symptom", "title": "   ", "recorded_date": "2026-10-09"})
        self.assertFalse(ok)
        self.assertIn("Title is required", err)

    def test_record_validation_impossible_calendar_dates(self):
        # 2026-02-30 does not exist
        ok, err, _ = validate_health_record({"record_type": "symptom", "title": "Fever", "recorded_date": "2026-02-30"})
        self.assertFalse(ok)
        self.assertIn("Invalid calendar date", err)

        # 2026-04-31 does not exist (April has 30 days)
        ok, err, _ = validate_health_record({"record_type": "symptom", "title": "Fever", "recorded_date": "2026-04-31"})
        self.assertFalse(ok)
        self.assertIn("Invalid calendar date", err)

    def test_record_validation_non_finite_numbers(self):
        # NaN rejection
        ok, err, _ = validate_health_record({
            "record_type": "measurement", "title": "BP", "recorded_date": "2026-10-09",
            "metric_value": float("nan")
        })
        self.assertFalse(ok)
        self.assertIn("finite number", err)

        # Infinity rejection
        ok, err, _ = validate_health_record({
            "record_type": "measurement", "title": "BP", "recorded_date": "2026-10-09",
            "metric_value": float("inf")
        })
        self.assertFalse(ok)
        self.assertIn("finite number", err)

    # --- 2. Chronological History Tests ---

    def test_chronological_history_ordering(self):
        # Create records across different dates out of order
        create_health_record(self.conn, {"record_type": "symptom", "title": "Older Headache", "recorded_date": "2026-10-01"})
        create_health_record(self.conn, {"record_type": "measurement", "title": "Latest BP", "recorded_date": "2026-10-09"})
        create_health_record(self.conn, {"record_type": "general_note", "title": "Middle Check", "recorded_date": "2026-10-05"})

        history = get_health_history(self.conn)
        self.assertEqual(len(history), 3)
        # Must be ordered by recorded_date DESC
        self.assertEqual(history[0]["title"], "Latest BP")
        self.assertEqual(history[1]["title"], "Middle Check")
        self.assertEqual(history[2]["title"], "Older Headache")

    # --- 3. Factual Health Summary Tests ---

    def test_summary_empty_state(self):
        summary = generate_health_summary(self.conn)
        self.assertEqual(summary["status"], "empty")
        self.assertEqual(summary["total_records"], 0)
        self.assertIn("Disclaimer", summary["disclaimer"])

    def test_summary_single_record_insufficient_trend(self):
        create_health_record(self.conn, {
            "record_type": "measurement",
            "title": "Blood Glucose",
            "metric_name": "Fasting Glucose",
            "metric_value": 95.0,
            "metric_unit": "mg/dL",
            "recorded_date": "2026-10-09"
        })
        summary = generate_health_summary(self.conn)
        self.assertEqual(summary["status"], "available")
        self.assertEqual(summary["total_records"], 1)
        self.assertEqual(len(summary["measurements"]), 1)
        # Must report insufficient data for trends
        self.assertIn("Insufficient historical data", summary["measurements"][0]["trend_note"])

    def test_summary_multiple_records_factual_aggregation(self):
        create_health_record(self.conn, {"record_type": "symptom", "title": "Headache", "recorded_date": "2026-10-01"})
        create_health_record(self.conn, {"record_type": "symptom", "title": "Headache", "recorded_date": "2026-10-03"})
        create_health_record(self.conn, {
            "record_type": "measurement", "title": "BP 1", "metric_name": "Systolic BP",
            "metric_value": 118.0, "metric_unit": "mmHg", "recorded_date": "2026-10-01"
        })
        create_health_record(self.conn, {
            "record_type": "measurement", "title": "BP 2", "metric_name": "Systolic BP",
            "metric_value": 124.0, "metric_unit": "mmHg", "recorded_date": "2026-10-05"
        })

        summary = generate_health_summary(self.conn)
        self.assertEqual(summary["total_records"], 4)
        self.assertEqual(summary["date_span"]["earliest_date"], "2026-10-01")
        self.assertEqual(summary["date_span"]["latest_date"], "2026-10-05")

        # Symptom frequency check
        self.assertEqual(summary["symptoms"][0]["symptom"], "Headache")
        self.assertEqual(summary["symptoms"][0]["frequency"], 2)

        # Metric range check
        m = summary["measurements"][0]
        self.assertEqual(m["metric_name"], "Systolic BP")
        self.assertEqual(m["latest_value"], 124.0)
        self.assertEqual(m["min_value"], 118.0)
        self.assertEqual(m["max_value"], 124.0)
        self.assertIn("Range: 118.0 mmHg to 124.0 mmHg", m["trend_note"])

    # --- 4. Medication Reminders & Schedules Tests ---

    def test_medication_validation_invalid_times_and_dates(self):
        # 25:00 is not a valid 24-hr time
        ok, err, _ = validate_medication_schedule({
            "medication_name": "Aspirin", "dosage": "81 mg", "frequency": "Daily",
            "reminder_time": "25:00", "start_date": "2026-10-09"
        })
        self.assertFalse(ok)
        self.assertIn("Invalid time", err)

        # 12:60 is not a valid time
        ok, err, _ = validate_medication_schedule({
            "medication_name": "Aspirin", "dosage": "81 mg", "frequency": "Daily",
            "reminder_time": "12:60", "start_date": "2026-10-09"
        })
        self.assertFalse(ok)
        self.assertIn("Invalid time", err)

        # 2026-02-30 is not a valid date
        ok, err, _ = validate_medication_schedule({
            "medication_name": "Aspirin", "dosage": "81 mg", "frequency": "Daily",
            "reminder_time": "08:00", "start_date": "2026-02-30"
        })
        self.assertFalse(ok)
        self.assertIn("Invalid calendar date", err)

    def test_medication_creation_and_deactivation(self):
        sched = create_medication_schedule(self.conn, {
            "medication_name": "Metformin",
            "dosage": "500 mg",
            "frequency": "Twice daily",
            "reminder_time": "08:00",
            "start_date": "2026-10-01"
        })
        sched_id = sched["id"]

        # Check active schedules
        active_list = get_active_schedules(self.conn)
        self.assertEqual(len(active_list), 1)
        self.assertEqual(active_list[0]["medication_name"], "Metformin")

        # Deactivate schedule (is_active = 0)
        success = deactivate_schedule(self.conn, sched_id)
        self.assertTrue(success)

        # Deactivated schedule MUST NOT be returned in active schedules
        active_after = get_active_schedules(self.conn)
        self.assertEqual(len(active_after), 0)

    def test_medication_future_start_date_filtered(self):
        create_medication_schedule(self.conn, {
            "medication_name": "Future Med",
            "dosage": "10 mg",
            "frequency": "Daily",
            "reminder_time": "10:00",
            "start_date": "2026-11-01"
        })
        # If checked on 2026-10-09, future schedule should not be active
        active_on_current_date = get_active_schedules(self.conn, reference_date="2026-10-09")
        self.assertEqual(len(active_on_current_date), 0)

        # On or after 2026-11-01, it is active
        active_in_future = get_active_schedules(self.conn, reference_date="2026-11-01")
        self.assertEqual(len(active_in_future), 1)

    def test_reminder_occurrence_duplicate_safe(self):
        sched = create_medication_schedule(self.conn, {
            "medication_name": "Lisinopril",
            "dosage": "10 mg",
            "frequency": "Daily",
            "reminder_time": "09:00",
            "start_date": "2026-10-01"
        })
        med_id = sched["id"]

        # First trigger log succeeds
        ok1, msg1, event1 = log_reminder_occurrence(self.conn, med_id, "2026-10-09", "09:00")
        self.assertTrue(ok1)
        self.assertEqual(event1["status"], "triggered")

        # Duplicate trigger log on same date & time is safely rejected without crash
        ok2, msg2, event2 = log_reminder_occurrence(self.conn, med_id, "2026-10-09", "09:00")
        self.assertFalse(ok2)
        self.assertIn("already logged", msg2)
        self.assertEqual(event2["id"], event1["id"])

    def test_reminder_acknowledgment_disclaimer(self):
        sched = create_medication_schedule(self.conn, {
            "medication_name": "Atorvastatin",
            "dosage": "20 mg",
            "frequency": "Nightly",
            "reminder_time": "21:00",
            "start_date": "2026-10-01"
        })
        _, _, event = log_reminder_occurrence(self.conn, sched["id"], "2026-10-09", "21:00")

        # Acknowledge reminder
        ok, msg, ack_data = acknowledge_reminder(self.conn, event["id"])
        self.assertTrue(ok)
        self.assertEqual(ack_data["status"], "acknowledged")
        # Verify honesty disclaimer is present
        self.assertIn("does not verify, confirm, or record whether the medication was actually taken", ack_data["disclaimer"])


if __name__ == "__main__":
    unittest.main()

