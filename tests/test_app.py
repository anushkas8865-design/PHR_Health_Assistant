"""
Integration Tests for Flask Controller Layer (tests/test_app.py).
Tests all REST endpoints and error handlers using Flask's test client and an isolated temporary SQLite database.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app


class TestAppRoutes(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary directory and test database
        self.test_dir = tempfile.mkdtemp()
        self.test_db = os.path.join(self.test_dir, "test_route_phr.db")

        # Configure application for testing with isolated database path
        self.app = create_app({
            "TESTING": True,
            "DB_PATH": self.test_db,
            "RETRIEVAL_THRESHOLD": 0.40,
            "RETRIEVAL_DATA_PATH": "data/medquad_clean.json"
        })
        self.client = self.app.test_client()

    def tearDown(self):
        # Clean up temporary test database directory completely
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # --- 1. Index Route Test ---

    def test_index_route(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

    # --- 2. Medical Q&A Chatbot Tests ---

    def test_chat_valid_medical_query(self):
        payload = {"question": "What are the symptoms of adult acute lymphoblastic leukemia?"}
        res = self.client.post("/api/chat", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["is_matched"])
        self.assertGreaterEqual(data["score"], 0.40)
        self.assertEqual(data["source"], "CancerGov")
        self.assertIn("Disclaimer", data["disclaimer"])

    def test_chat_out_of_domain_query_safe_rejection(self):
        payload = {"question": "What is the capital city of France?"}
        res = self.client.post("/api/chat", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["is_matched"])
        self.assertIn("could not find a sufficiently confident answer", data["answer"])

    def test_chat_invalid_requests(self):
        # Missing question
        res = self.client.post("/api/chat", json={})
        self.assertEqual(res.status_code, 400)

        # Empty question string
        res = self.client.post("/api/chat", json={"question": "   "})
        self.assertEqual(res.status_code, 400)

        # Non-JSON content
        res = self.client.post("/api/chat", data="not json")
        self.assertEqual(res.status_code, 400)

    # --- 3. Health Records Tests ---

    def test_record_create_and_history_retrieval(self):
        # Create record 1
        payload1 = {
            "record_type": "symptom",
            "title": "Mild Headache",
            "description": "After screen time",
            "recorded_date": "2026-10-01"
        }
        res1 = self.client.post("/api/records", json=payload1)
        self.assertEqual(res1.status_code, 201)
        data1 = res1.get_json()
        self.assertEqual(data1["status"], "created")
        self.assertEqual(data1["record"]["title"], "Mild Headache")

        # Create record 2 (later date)
        payload2 = {
            "record_type": "measurement",
            "title": "Blood Pressure",
            "metric_name": "Systolic BP",
            "metric_value": 122.0,
            "metric_unit": "mmHg",
            "recorded_date": "2026-10-09"
        }
        res2 = self.client.post("/api/records", json=payload2)
        self.assertEqual(res2.status_code, 201)

        # Query history (must be sorted recorded_date DESC)
        history_res = self.client.get("/api/records")
        self.assertEqual(history_res.status_code, 200)
        history_data = history_res.get_json()
        self.assertEqual(history_data["count"], 2)
        self.assertEqual(history_data["records"][0]["title"], "Blood Pressure")
        self.assertEqual(history_data["records"][1]["title"], "Mild Headache")

    def test_record_validation_errors(self):
        # Impossible calendar date
        bad_date_payload = {
            "record_type": "symptom",
            "title": "Fever",
            "recorded_date": "2026-02-30"
        }
        res = self.client.post("/api/records", json=bad_date_payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid calendar date", res.get_json()["error"])

        # Missing title
        bad_title_payload = {
            "record_type": "symptom",
            "title": "",
            "recorded_date": "2026-10-09"
        }
        res = self.client.post("/api/records", json=bad_title_payload)
        self.assertEqual(res.status_code, 400)

        # Non-finite number
        bad_num_payload = {
            "record_type": "measurement",
            "title": "Weight",
            "metric_value": "nan",
            "recorded_date": "2026-10-09"
        }
        res = self.client.post("/api/records", json=bad_num_payload)
        self.assertEqual(res.status_code, 400)

    # --- 4. Health Summary Tests ---

    def test_summary_empty_state_and_with_records(self):
        # Empty state
        res_empty = self.client.get("/api/summary")
        self.assertEqual(res_empty.status_code, 200)
        data_empty = res_empty.get_json()
        self.assertEqual(data_empty["status"], "empty")
        self.assertEqual(data_empty["total_records"], 0)

        # Add records
        self.client.post("/api/records", json={
            "record_type": "symptom", "title": "Cough", "recorded_date": "2026-10-05"
        })
        self.client.post("/api/records", json={
            "record_type": "measurement", "title": "Pulse", "metric_name": "Heart Rate",
            "metric_value": 72.0, "metric_unit": "bpm", "recorded_date": "2026-10-06"
        })

        # Populated summary
        res_pop = self.client.get("/api/summary")
        self.assertEqual(res_pop.status_code, 200)
        data_pop = res_pop.get_json()
        self.assertEqual(data_pop["status"], "available")
        self.assertEqual(data_pop["total_records"], 2)
        self.assertIn("records span", data_pop["date_span"]["span_description"].lower())

    # --- 5. Medication Schedules & Deactivation Tests ---

    def test_medication_creation_and_deactivation(self):
        med_payload = {
            "medication_name": "Lisinopril",
            "dosage": "10 mg",
            "frequency": "Once daily",
            "reminder_time": "08:30",
            "start_date": "2026-10-01"
        }
        res = self.client.post("/api/medications", json=med_payload)
        self.assertEqual(res.status_code, 201)
        med_id = res.get_json()["medication"]["id"]

        # Verify active
        active_res = self.client.get("/api/medications")
        self.assertEqual(active_res.status_code, 200)
        self.assertEqual(active_res.get_json()["count"], 1)

        # Deactivate
        deact_res = self.client.post(f"/api/medications/{med_id}/deactivate")
        self.assertEqual(deact_res.status_code, 200)
        self.assertEqual(deact_res.get_json()["status"], "deactivated")

        # Verify excluded from active list
        active_res_after = self.client.get("/api/medications")
        self.assertEqual(active_res_after.get_json()["count"], 0)

        # Deactivating non-existent ID returns 404
        bad_deact = self.client.post("/api/medications/99999/deactivate")
        self.assertEqual(bad_deact.status_code, 404)

    def test_medication_invalid_syntax(self):
        # Invalid time
        bad_time = {
            "medication_name": "Aspirin", "dosage": "81 mg", "frequency": "Daily",
            "reminder_time": "25:30", "start_date": "2026-10-01"
        }
        res = self.client.post("/api/medications", json=bad_time)
        self.assertEqual(res.status_code, 400)

        # Impossible start date
        bad_date = {
            "medication_name": "Aspirin", "dosage": "81 mg", "frequency": "Daily",
            "reminder_time": "09:00", "start_date": "2026-02-30"
        }
        res = self.client.post("/api/medications", json=bad_date)
        self.assertEqual(res.status_code, 400)

    # --- 6. Reminder Logging and Acknowledgment Tests ---

    def test_reminder_log_and_duplicate_safe(self):
        # Create medication
        med_res = self.client.post("/api/medications", json={
            "medication_name": "Metformin", "dosage": "500 mg", "frequency": "Daily",
            "reminder_time": "08:00", "start_date": "2026-10-01"
        })
        med_id = med_res.get_json()["medication"]["id"]

        # First trigger log -> 201 Created
        log_payload = {
            "medication_id": med_id,
            "scheduled_date": "2026-10-09",
            "scheduled_time": "08:00"
        }
        res1 = self.client.post("/api/reminders/log", json=log_payload)
        self.assertEqual(res1.status_code, 201)
        event_id = res1.get_json()["event"]["id"]

        # Duplicate trigger log on same date/time -> 200 already_logged (duplicate-safe)
        res2 = self.client.post("/api/reminders/log", json=log_payload)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.get_json()["status"], "already_logged")
        self.assertEqual(res2.get_json()["event"]["id"], event_id)

        # Acknowledge reminder -> 200 OK
        ack_res = self.client.post("/api/reminders/acknowledge", json={"event_id": event_id})
        self.assertEqual(ack_res.status_code, 200)
        ack_data = ack_res.get_json()
        self.assertEqual(ack_data["status"], "acknowledged")
        self.assertIn("does not verify, confirm, or record whether the medication was actually taken", ack_data["event"]["disclaimer"])

        # Acknowledging non-existent event -> 404
        ack_bad = self.client.post("/api/reminders/acknowledge", json={"event_id": 99999})
        self.assertEqual(ack_bad.status_code, 404)


if __name__ == "__main__":
    unittest.main()

