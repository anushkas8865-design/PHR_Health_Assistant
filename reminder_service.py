"""
Service layer for Medication Reminders (Feature 4).
Handles schedule validation, deactivation (no deletion), duplicate-safe occurrence tracking,
and acknowledgment logging with honest adherence disclaimers.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import sqlite3

ACKNOWLEDGMENT_DISCLAIMER = (
    "Notice: Acknowledging a reminder confirms only that the alert was viewed or dismissed by the user. "
    "It does not verify, confirm, or record whether the medication was actually taken."
)


def validate_medication_schedule(data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates medication schedule inputs.
    Strictly verifies real calendar dates and 24-hour HH:MM time syntax.
    """
    if not isinstance(data, dict):
        return False, "Input data must be a JSON object.", {}

    name = str(data.get("medication_name", "")).strip()
    if not name:
        return False, "Medication name is required and cannot be empty.", {}
    if len(name) > 100:
        return False, "Medication name must be 100 characters or fewer.", {}

    dosage = str(data.get("dosage", "")).strip()
    if not dosage:
        return False, "Dosage description is required (e.g., '500 mg', '1 tablet').", {}
    if len(dosage) > 50:
        return False, "Dosage must be 50 characters or fewer.", {}

    frequency = str(data.get("frequency", "")).strip()
    if not frequency:
        return False, "Frequency is required (e.g., 'Once daily', 'Twice daily').", {}
    if len(frequency) > 50:
        return False, "Frequency must be 50 characters or fewer.", {}

    # Strict 24-hour HH:MM time validation
    reminder_time_str = str(data.get("reminder_time", "")).strip()
    if not reminder_time_str:
        return False, "Reminder time is required.", {}
    try:
        parsed_time = datetime.strptime(reminder_time_str, "%H:%M")
        reminder_time = parsed_time.strftime("%H:%M")
    except ValueError:
        return False, f"Invalid time '{reminder_time_str}'. Must be a valid 24-hour time in HH:MM format (00:00 to 23:59).", {}

    # Strict calendar-date validation for start_date
    start_date_str = str(data.get("start_date", "")).strip()
    if not start_date_str:
        return False, "Start date is required.", {}
    try:
        parsed_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        start_date = parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        return False, f"Invalid calendar date '{start_date_str}'. Must be a valid date in YYYY-MM-DD format.", {}

    instructions = str(data.get("instructions", "")).strip()
    if len(instructions) > 500:
        return False, "Instructions must be 500 characters or fewer.", {}

    validated = {
        "medication_name": name,
        "dosage": dosage,
        "frequency": frequency,
        "reminder_time": reminder_time,
        "start_date": start_date,
        "instructions": instructions if instructions else None
    }
    return True, "", validated


def create_medication_schedule(conn: sqlite3.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a new medication schedule using parameterized SQL.
    """
    is_valid, err_msg, validated = validate_medication_schedule(data)
    if not is_valid:
        raise ValueError(err_msg)

    created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO medication_schedules (
        medication_name, dosage, frequency, reminder_time, start_date, instructions, is_active, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?);
    """, (
        validated["medication_name"],
        validated["dosage"],
        validated["frequency"],
        validated["reminder_time"],
        validated["start_date"],
        validated["instructions"],
        created_at
    ))
    conn.commit()

    schedule_id = cursor.lastrowid
    return {
        "id": schedule_id,
        "medication_name": validated["medication_name"],
        "dosage": validated["dosage"],
        "frequency": validated["frequency"],
        "reminder_time": validated["reminder_time"],
        "start_date": validated["start_date"],
        "instructions": validated["instructions"],
        "is_active": 1,
        "created_at": created_at
    }


def get_active_schedules(conn: sqlite3.Connection, reference_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves all currently active schedules (is_active = 1).
    If reference_date is provided, filters out schedules whose start_date is in the future.
    """
    cursor = conn.cursor()
    if reference_date:
        try:
            datetime.strptime(reference_date, "%Y-%m-%d")
            cursor.execute("""
            SELECT id, medication_name, dosage, frequency, reminder_time, start_date, instructions, is_active, created_at
            FROM medication_schedules
            WHERE is_active = 1 AND start_date <= ?
            ORDER BY reminder_time ASC, medication_name ASC;
            """, (reference_date,))
        except ValueError:
            # Fallback if invalid date string passed
            cursor.execute("""
            SELECT id, medication_name, dosage, frequency, reminder_time, start_date, instructions, is_active, created_at
            FROM medication_schedules
            WHERE is_active = 1
            ORDER BY reminder_time ASC, medication_name ASC;
            """)
    else:
        cursor.execute("""
        SELECT id, medication_name, dosage, frequency, reminder_time, start_date, instructions, is_active, created_at
        FROM medication_schedules
        WHERE is_active = 1
        ORDER BY reminder_time ASC, medication_name ASC;
        """)

    rows = cursor.fetchall()
    return [
        {
            "id": row["id"],
            "medication_name": row["medication_name"],
            "dosage": row["dosage"],
            "frequency": row["frequency"],
            "reminder_time": row["reminder_time"],
            "start_date": row["start_date"],
            "instructions": row["instructions"],
            "is_active": row["is_active"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]


def deactivate_schedule(conn: sqlite3.Connection, schedule_id: int) -> bool:
    """
    Deactivates a medication schedule by setting is_active = 0.
    Does NOT delete records, preserving audit trail.
    """
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE medication_schedules
    SET is_active = 0
    WHERE id = ?;
    """, (schedule_id,))
    conn.commit()
    return cursor.rowcount > 0


def log_reminder_occurrence(
    conn: sqlite3.Connection,
    medication_id: int,
    scheduled_date: str,
    scheduled_time: str,
    notes: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Records that a scheduled reminder was triggered at a specific date and time.
    Duplicate-safe: Uses the UNIQUE(medication_id, scheduled_date, scheduled_time) constraint
    to prevent logging duplicate alerts for the exact same occurrence.
    """
    cursor = conn.cursor()

    # 1. Verify schedule exists and is active
    cursor.execute("SELECT id, medication_name, is_active, start_date FROM medication_schedules WHERE id = ?;", (medication_id,))
    med = cursor.fetchone()
    if not med:
        return False, f"Medication schedule ID {medication_id} does not exist.", {}
    if med["is_active"] == 0:
        return False, f"Medication schedule ID {medication_id} is deactivated and cannot trigger alerts.", {}

    # Validate date and time syntax
    try:
        datetime.strptime(scheduled_date, "%Y-%m-%d")
        datetime.strptime(scheduled_time, "%H:%M")
    except ValueError:
        return False, "Invalid scheduled_date or scheduled_time format.", {}

    # Verify scheduled_date is not prior to schedule start_date
    if scheduled_date < med["start_date"]:
        return False, f"Scheduled date {scheduled_date} is prior to medication start date {med['start_date']}.", {}

    triggered_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        cursor.execute("""
        INSERT INTO reminder_events (
            medication_id, scheduled_date, scheduled_time, triggered_at, status, notes
        ) VALUES (?, ?, ?, ?, 'triggered', ?);
        """, (medication_id, scheduled_date, scheduled_time, triggered_at, notes))
        conn.commit()

        event_id = cursor.lastrowid
        return True, "Reminder occurrence logged successfully.", {
            "id": event_id,
            "medication_id": medication_id,
            "medication_name": med["medication_name"],
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
            "triggered_at": triggered_at,
            "status": "triggered",
            "disclaimer": ACKNOWLEDGMENT_DISCLAIMER
        }

    except sqlite3.IntegrityError:
        # Occurrence already logged; retrieve existing event safely
        cursor.execute("""
        SELECT id, medication_id, scheduled_date, scheduled_time, triggered_at, status, acknowledged_at, notes
        FROM reminder_events
        WHERE medication_id = ? AND scheduled_date = ? AND scheduled_time = ?;
        """, (medication_id, scheduled_date, scheduled_time))
        existing = cursor.fetchone()
        return False, "Reminder occurrence was already logged for this schedule, date, and time.", dict(existing) if existing else {}


def acknowledge_reminder(conn: sqlite3.Connection, event_id: int, notes: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Marks a triggered reminder occurrence as acknowledged.
    Explicitly clarifies that acknowledgment does not confirm medical intake.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, medication_id, status FROM reminder_events WHERE id = ?;", (event_id,))
    row = cursor.fetchone()
    if not row:
        return False, f"Reminder event ID {event_id} does not exist.", {}

    ack_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor.execute("""
    UPDATE reminder_events
    SET status = 'acknowledged', acknowledged_at = ?, notes = COALESCE(?, notes)
    WHERE id = ?;
    """, (ack_time, notes, event_id))
    conn.commit()

    return True, "Reminder event acknowledged.", {
        "id": event_id,
        "medication_id": row["medication_id"],
        "status": "acknowledged",
        "acknowledged_at": ack_time,
        "disclaimer": ACKNOWLEDGMENT_DISCLAIMER
    }

