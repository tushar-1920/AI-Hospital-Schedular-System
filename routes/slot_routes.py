from flask import Blueprint, request, jsonify
from extensions import db
from models import HospitalSlot
from datetime import datetime, timedelta

slot_bp = Blueprint("slot_bp", __name__, url_prefix="/hospital")


@slot_bp.route("/generate-slots", methods=["POST"])
def generate_slots():
    data = request.json

    doctor_id = data["doctor_id"]
    slot_date = data["slot_date"]        # "2026-01-20"
    start_time = data.get("start_time", "09:00")
    end_time = data.get("end_time", "13:00")
    duration = data.get("slot_duration", 15)

    start_dt = datetime.strptime(f"{slot_date} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{slot_date} {end_time}", "%Y-%m-%d %H:%M")

    created = 0
    while start_dt < end_dt:
        slot_start = start_dt.strftime("%H:%M")
        slot_end = (start_dt + timedelta(minutes=duration)).strftime("%H:%M")

        slot = HospitalSlot(
            doctor_id=doctor_id,
            slot_date=slot_date,
            start_time=slot_start,
            end_time=slot_end,
            status="Free"
        )

        db.session.add(slot)
        created += 1
        start_dt += timedelta(minutes=duration)

    db.session.commit()

    return jsonify({"message": "Slots Generated ✅", "total_slots": created})


@slot_bp.route("/slots/<int:doctor_id>", methods=["GET"])
def get_slots(doctor_id):
    slots = HospitalSlot.query.filter_by(doctor_id=doctor_id).all()
    result = []

    for s in slots:
        result.append({
            "slot_id": s.slot_id,
            "slot_date": s.slot_date,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "status": s.status
        })

    return jsonify(result)

from flask import session

@slot_bp.route("/doctor-generate-slots", methods=["POST"])
def doctor_generate_slots():
    # ✅ Only doctor can generate their own slots
    if session.get("role") != "Doctor":
        return jsonify({"error": "Only Doctor can generate slots ❌"}), 403

    data = request.json

    doctor_id = session.get("doctor_id")
    slot_date = data["slot_date"]
    start_time = data.get("start_time", "09:00")
    end_time = data.get("end_time", "13:00")
    slot_duration = int(data.get("slot_duration", 15))

    # ✅ Generate slots for logged-in doctor only
    start_dt = datetime.strptime(start_time, "%H:%M")
    end_dt = datetime.strptime(end_time, "%H:%M")

    created_slots = 0

    while start_dt < end_dt:
        slot_start = start_dt.strftime("%H:%M")
        start_dt = start_dt + timedelta(minutes=slot_duration)
        slot_end = start_dt.strftime("%H:%M")

        slot = HospitalSlot(
            doctor_id=doctor_id,
            slot_date=slot_date,
            start_time=slot_start,
            end_time=slot_end,
            status="Free"
        )

        db.session.add(slot)
        created_slots += 1

    db.session.commit()

    return jsonify({
        "message": "✅ Doctor Slots Generated Successfully!",
        "doctor_id": doctor_id,
        "slot_date": slot_date,
        "total_slots_created": created_slots
    })


@slot_bp.route("/free-slots/<int:doctor_id>", methods=["GET"])
def get_free_slots(doctor_id):
    slots = HospitalSlot.query.filter_by(doctor_id=doctor_id, status="Free").all()

    result = []
    for s in slots:
        result.append({
            "slot_id": s.slot_id,
            "slot_date": str(s.slot_date),
            "start_time": str(s.start_time),
            "end_time": str(s.end_time),
            "status": s.status
        })

    return jsonify(result)
