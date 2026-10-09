"""
Flask Controller Layer for Intelligent Personal Health Record (PHR) Assistant.
Exposes REST API endpoints for Medical Q&A, Health Records, History, Reminders, and Summaries.
"""

import os
from typing import Optional
from flask import Flask, request, jsonify, render_template, g
from database import get_db, init_db
from record_services import (
    create_health_record,
    get_health_history,
    generate_health_summary
)
from reminder_service import (
    create_medication_schedule,
    get_active_schedules,
    deactivate_schedule,
    log_reminder_occurrence,
    acknowledge_reminder
)
from retrieval.engine import MedicalRetrievalEngine

DEFAULT_CONFIDENCE_THRESHOLD = 0.40


def create_app(config: Optional[dict] = None) -> Flask:
    app = Flask(__name__)

    # Default application configurations
    app.config["DB_PATH"] = None  # None defaults to data/phr_database.db in database.py
    app.config["RETRIEVAL_THRESHOLD"] = DEFAULT_CONFIDENCE_THRESHOLD
    app.config["RETRIEVAL_DATA_PATH"] = "data/medquad_clean.json"

    if config:
        app.config.update(config)

    # Initialize database tables safely and idempotently
    with app.app_context():
        init_db(app.config["DB_PATH"])

    # Initialize retrieval engine once at application startup
    try:
        retrieval_engine = MedicalRetrievalEngine(data_path=app.config["RETRIEVAL_DATA_PATH"])
    except Exception as e:
        app.logger.warning(f"Retrieval engine initialization deferred or using mock: {e}")
        retrieval_engine = None

    # Request-scoped database connection helpers
    def get_app_db():
        if "db" not in g:
            g.db = get_db(app.config["DB_PATH"])
        return g.db

    @app.teardown_appcontext
    def close_app_db(exception):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    # --- Error Handlers (Safe, non-leaking responses) ---

    @app.errorhandler(400)
    def handle_bad_request(e):
        return jsonify({"error": "Bad request. Please verify submitted data."}), 400

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"error": "Requested resource not found."}), 404

    @app.errorhandler(500)
    def handle_internal_error(e):
        return jsonify({"error": "An internal error occurred. Please try again later."}), 500

    # --- 1. Frontend Route ---

    @app.route("/", methods=["GET"])
    def index():
        try:
            return render_template("index.html")
        except Exception:
            return jsonify({
                "status": "healthy",
                "service": "Intelligent Personal Health Record (PHR) Assistant API"
            }), 200

    # --- 2. Medical Q&A Chatbot (Feature 1) ---

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        if not request.is_json:
            return jsonify({"error": "Request body must be valid JSON."}), 400

        data = request.get_json()
        question = data.get("question") if isinstance(data, dict) else None
        if not question or not isinstance(question, str) or not question.strip():
            return jsonify({"error": "A non-empty question string is required."}), 400

        if not retrieval_engine:
            return jsonify({"error": "Medical retrieval engine is not currently initialized."}), 500

        threshold = app.config.get("RETRIEVAL_THRESHOLD", DEFAULT_CONFIDENCE_THRESHOLD)
        result = retrieval_engine.search(question.strip(), threshold=threshold)
        return jsonify(result), 200

    # --- 3. Save Personal Health Records (Feature 2) ---

    @app.route("/api/records", methods=["POST"])
    def api_create_record():
        if not request.is_json:
            return jsonify({"error": "Request body must be valid JSON."}), 400

        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({"error": "JSON body must be an object."}), 400

        try:
            conn = get_app_db()
            saved_record = create_health_record(conn, data)
            return jsonify({"status": "created", "record": saved_record}), 201
        except ValueError as val_err:
            return jsonify({"error": str(val_err)}), 400
        except Exception:
            return jsonify({"error": "Unable to save health record."}), 500

    # --- 4. Chronological Health History (Feature 3) ---

    @app.route("/api/records", methods=["GET"])
    def api_get_records():
        record_type = request.args.get("type", "").strip() or None
        conn = get_app_db()
        records = get_health_history(conn, record_type=record_type)
        return jsonify({"records": records, "count": len(records)}), 200

    # --- 5. Factual Health Summary (Feature 5) ---

    @app.route("/api/summary", methods=["GET"])
    def api_get_summary():
        conn = get_app_db()
        summary = generate_health_summary(conn)
        return jsonify(summary), 200

    # --- 6. Medication Schedules & Reminders (Feature 4) ---

    @app.route("/api/medications", methods=["POST"])
    def api_create_medication():
        if not request.is_json:
            return jsonify({"error": "Request body must be valid JSON."}), 400

        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({"error": "JSON body must be an object."}), 400

        try:
            conn = get_app_db()
            saved_med = create_medication_schedule(conn, data)
            return jsonify({"status": "created", "medication": saved_med}), 201
        except ValueError as val_err:
            return jsonify({"error": str(val_err)}), 400
        except Exception:
            return jsonify({"error": "Unable to create medication schedule."}), 500

    @app.route("/api/medications", methods=["GET"])
    def api_get_medications():
        ref_date = request.args.get("date", "").strip() or None
        conn = get_app_db()
        schedules = get_active_schedules(conn, reference_date=ref_date)
        return jsonify({"schedules": schedules, "count": len(schedules)}), 200

    @app.route("/api/medications/<int:schedule_id>/deactivate", methods=["POST"])
    def api_deactivate_medication(schedule_id: int):
        conn = get_app_db()
        success = deactivate_schedule(conn, schedule_id)
        if not success:
            return jsonify({"error": f"Medication schedule ID {schedule_id} not found."}), 404
        return jsonify({"status": "deactivated", "id": schedule_id}), 200

    @app.route("/api/reminders/log", methods=["POST"])
    def api_log_reminder():
        if not request.is_json:
            return jsonify({"error": "Request body must be valid JSON."}), 400

        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({"error": "JSON body must be an object."}), 400

        med_id = data.get("medication_id")
        scheduled_date = data.get("scheduled_date")
        scheduled_time = data.get("scheduled_time")
        notes = data.get("notes")

        if not med_id or not scheduled_date or not scheduled_time:
            return jsonify({"error": "medication_id, scheduled_date, and scheduled_time are required."}), 400

        try:
            med_id_int = int(med_id)
        except (ValueError, TypeError):
            return jsonify({"error": "medication_id must be a valid integer."}), 400

        conn = get_app_db()
        ok, msg, event_data = log_reminder_occurrence(
            conn, med_id_int, str(scheduled_date).strip(), str(scheduled_time).strip(), notes
        )
        if ok:
            return jsonify({"status": "logged", "message": msg, "event": event_data}), 201
        else:
            if "already logged" in msg:
                return jsonify({"status": "already_logged", "message": msg, "event": event_data}), 200
            return jsonify({"error": msg}), 400

    @app.route("/api/reminders/acknowledge", methods=["POST"])
    def api_acknowledge_reminder():
        if not request.is_json:
            return jsonify({"error": "Request body must be valid JSON."}), 400

        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({"error": "JSON body must be an object."}), 400

        event_id = data.get("event_id")
        notes = data.get("notes")

        if not event_id:
            return jsonify({"error": "event_id is required."}), 400

        try:
            event_id_int = int(event_id)
        except (ValueError, TypeError):
            return jsonify({"error": "event_id must be a valid integer."}), 400

        conn = get_app_db()
        ok, msg, ack_data = acknowledge_reminder(conn, event_id_int, notes)
        if not ok:
            return jsonify({"error": msg}), 404
        return jsonify({"status": "acknowledged", "message": msg, "event": ack_data}), 200

    return app


if __name__ == "__main__":
    app = create_app()
    print("\n" + "=" * 60)
    print("Intelligent Personal Health Record (PHR) Assistant running.")
    print("Access the dashboard at: http://127.0.0.1:5000")
    print("=" * 60 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)

