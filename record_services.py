"""
Service layer for Personal Health Records (Feature 2, Feature 3, Feature 5).
Handles input validation, parameterized database operations, chronological history,
and strictly factual, non-diagnostic record summarization.
"""

import math
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import sqlite3

RECORD_TYPES = {"symptom", "measurement", "general_note"}
SUMMARY_DISCLAIMER = (
    "Disclaimer: This summary is generated strictly from self-reported records entered by "
    "the user for personal health tracking. It does not constitute medical advice, clinical evaluation, "
    "treatment recommendation, or a diagnosis. Consult a qualified physician for healthcare decisions."
)


def validate_health_record(data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates health record inputs.
    Enforces strict calendar date checks, non-finite number rejections, and text length limits.
    """
    if not isinstance(data, dict):
        return False, "Input data must be a JSON object.", {}

    record_type = str(data.get("record_type", "")).strip().lower()
    if record_type not in RECORD_TYPES:
        return False, f"Invalid record_type '{record_type}'. Allowed types: {', '.join(sorted(RECORD_TYPES))}.", {}

    title = str(data.get("title", "")).strip()
    if not title:
        return False, "Title is required and cannot be empty.", {}
    if len(title) > 150:
        return False, "Title must be 150 characters or fewer.", {}

    description = str(data.get("description", "")).strip()
    if len(description) > 1000:
        return False, "Description must be 1000 characters or fewer.", {}

    # Strict calendar-date validation
    recorded_date_str = str(data.get("recorded_date", "")).strip()
    if not recorded_date_str:
        return False, "Recorded date is required.", {}
    try:
        # datetime.strptime validates real calendar dates (rejects e.g. 2026-02-30)
        parsed_date = datetime.strptime(recorded_date_str, "%Y-%m-%d")
        recorded_date = parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        return False, f"Invalid calendar date '{recorded_date_str}'. Must be a valid date in YYYY-MM-DD format.", {}

    # Optional metric validation
    metric_name = str(data.get("metric_name", "")).strip()
    if len(metric_name) > 50:
        return False, "Metric name must be 50 characters or fewer.", {}

    metric_unit = str(data.get("metric_unit", "")).strip()
    if len(metric_unit) > 20:
        return False, "Metric unit must be 20 characters or fewer.", {}

    raw_value = data.get("metric_value")
    metric_value = None
    if raw_value is not None and str(raw_value).strip() != "":
        try:
            val = float(raw_value)
            if math.isnan(val) or math.isinf(val):
                return False, "Metric value must be a finite number (NaN and Infinity are not permitted).", {}
            metric_value = val
        except (ValueError, TypeError):
            return False, "Metric value must be a valid numeric measurement.", {}

    validated = {
        "record_type": record_type,
        "title": title,
        "description": description if description else None,
        "metric_name": metric_name if metric_name else None,
        "metric_value": metric_value,
        "metric_unit": metric_unit if metric_unit else None,
        "recorded_date": recorded_date,
    }
    return True, "", validated


def create_health_record(conn: sqlite3.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Saves a validated personal health record into SQLite using parameterized queries.
    """
    is_valid, err_msg, validated = validate_health_record(data)
    if not is_valid:
        raise ValueError(err_msg)

    created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO health_records (
        record_type, title, description, metric_name, metric_value, metric_unit, recorded_date, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        validated["record_type"],
        validated["title"],
        validated["description"],
        validated["metric_name"],
        validated["metric_value"],
        validated["metric_unit"],
        validated["recorded_date"],
        created_at
    ))
    conn.commit()

    record_id = cursor.lastrowid
    return {
        "id": record_id,
        "record_type": validated["record_type"],
        "title": validated["title"],
        "description": validated["description"],
        "metric_name": validated["metric_name"],
        "metric_value": validated["metric_value"],
        "metric_unit": validated["metric_unit"],
        "recorded_date": validated["recorded_date"],
        "created_at": created_at
    }


def get_health_history(conn: sqlite3.Connection, record_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves health records ordered chronologically (recorded_date DESC, created_at DESC).
    """
    cursor = conn.cursor()
    if record_type and record_type in RECORD_TYPES:
        cursor.execute("""
        SELECT id, record_type, title, description, metric_name, metric_value, metric_unit, recorded_date, created_at
        FROM health_records
        WHERE record_type = ?
        ORDER BY recorded_date DESC, created_at DESC;
        """, (record_type,))
    else:
        cursor.execute("""
        SELECT id, record_type, title, description, metric_name, metric_value, metric_unit, recorded_date, created_at
        FROM health_records
        ORDER BY recorded_date DESC, created_at DESC;
        """)

    rows = cursor.fetchall()
    return [
        {
            "id": row["id"],
            "record_type": row["record_type"],
            "title": row["title"],
            "description": row["description"],
            "metric_name": row["metric_name"],
            "metric_value": row["metric_value"],
            "metric_unit": row["metric_unit"],
            "recorded_date": row["recorded_date"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]


def generate_health_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Generates a strictly factual summary derived exclusively from existing SQLite records.
    Never infers clinical diagnoses, treatments, or speculative trends.
    """
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, record_type, title, description, metric_name, metric_value, metric_unit, recorded_date, created_at
    FROM health_records
    ORDER BY recorded_date ASC, created_at ASC;
    """)
    records = cursor.fetchall()

    total_records = len(records)
    if total_records == 0:
        return {
            "status": "empty",
            "message": "No health records have been entered yet. History is currently empty.",
            "total_records": 0,
            "disclaimer": SUMMARY_DISCLAIMER
        }

    # Aggregate counts by category
    type_counts = {"symptom": 0, "measurement": 0, "general_note": 0}
    dates = []
    symptoms_recorded = {}
    metrics_by_name = {}

    for row in records:
        rtype = row["record_type"]
        if rtype in type_counts:
            type_counts[rtype] += 1
        dates.append(row["recorded_date"])

        if rtype == "symptom":
            sym_title = row["title"].strip()
            symptoms_recorded[sym_title] = symptoms_recorded.get(sym_title, 0) + 1

        if row["metric_name"] and row["metric_value"] is not None:
            mname = row["metric_name"].strip()
            if mname not in metrics_by_name:
                metrics_by_name[mname] = []
            metrics_by_name[mname].append({
                "value": row["metric_value"],
                "unit": row["metric_unit"] or "",
                "date": row["recorded_date"]
            })

    earliest_date = min(dates)
    latest_date = max(dates)

    # Compile factual summaries for metrics
    metric_summaries = []
    for mname, entries in sorted(metrics_by_name.items()):
        latest_entry = entries[-1]
        values = [e["value"] for e in entries]
        entry_count = len(entries)
        
        unit = latest_entry["unit"]
        unit_str = f" {unit}" if unit else ""

        metric_data = {
            "metric_name": mname,
            "total_measurements": entry_count,
            "latest_value": latest_entry["value"],
            "unit": unit,
            "latest_recorded_date": latest_entry["date"],
            "min_value": min(values),
            "max_value": max(values),
            "trend_note": (
                f"Range: {min(values)}{unit_str} to {max(values)}{unit_str} across {entry_count} readings."
                if entry_count >= 2
                else "Insufficient historical data for trend evaluation (only 1 recorded reading)."
            )
        }
        metric_summaries.append(metric_data)

    symptom_summary = [
        {"symptom": k, "frequency": v}
        for k, v in sorted(symptoms_recorded.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "status": "available",
        "total_records": total_records,
        "date_span": {
            "earliest_date": earliest_date,
            "latest_date": latest_date,
            "span_description": (
                f"Records span from {earliest_date} to {latest_date}."
                if earliest_date != latest_date
                else f"All records logged on {earliest_date}."
            )
        },
        "records_by_type": type_counts,
        "symptoms": symptom_summary,
        "measurements": metric_summaries,
        "disclaimer": SUMMARY_DISCLAIMER
    }

