from flask import Blueprint, request, jsonify, session
from extensions import db
from models import (
    HospitalDoctor,
    HospitalQueue,
    HospitalSlot,
    HospitalAppointment,
    HospitalPatient
)

doctor_bp = Blueprint("doctor_bp", __name__, url_prefix="/hospital")


# ✅ ------------------------------
# ✅ Add Doctor
# ✅ ------------------------------
@doctor_bp.route("/add-doctor", methods=["POST"])
def add_doctor():
    data = request.json

    doctor = HospitalDoctor(
        name=data["name"],
        department=data["department"],
        specialization=data.get("specialization", "General"),
        status=data.get("status", "Available"),
        avg_consult_time=data.get("avg_consult_time", 10),
        experience_years=data.get("experience_years", 1)
    )

    db.session.add(doctor)
    db.session.commit()

    # ✅ Ensure queue row exists
    queue = HospitalQueue.query.filter_by(doctor_id=doctor.doctor_id).first()
    if not queue:
        queue = HospitalQueue(doctor_id=doctor.doctor_id, current_patient_count=0)
        db.session.add(queue)
        db.session.commit()

    return jsonify({"message": "Doctor Added ✅", "doctor_id": doctor.doctor_id})


# ✅ ------------------------------
# ✅ Update Doctor Status
# ✅ ------------------------------
@doctor_bp.route("/update-status/<int:doctor_id>", methods=["PUT"])
def update_status(doctor_id):
    data = request.json
    doctor = HospitalDoctor.query.get(doctor_id)

    if not doctor:
        return jsonify({"error": "Doctor not found ❌"}), 404

    doctor.status = data.get("status", "Available")
    db.session.commit()

    return jsonify({"message": f"Doctor status updated to {doctor.status} ✅"})


# ✅ ------------------------------
# ✅ Get All Doctors
# ✅ ------------------------------
@doctor_bp.route("/doctors", methods=["GET"])
def get_doctors():
    doctors = HospitalDoctor.query.all()
    result = []

    for d in doctors:
        result.append({
            "doctor_id": d.doctor_id,
            "name": d.name,
            "department": d.department,
            "specialization": d.specialization,
            "status": d.status,
            "avg_consult_time": d.avg_consult_time,
            "experience_years": d.experience_years
        })

    return jsonify(result)


# ✅ ------------------------------
# ✅ Get Available Doctors
# ✅ ------------------------------
@doctor_bp.route("/available-doctors", methods=["GET"])
def available_doctors():
    doctors = HospitalDoctor.query.filter_by(status="Available").all()

    result = []
    for d in doctors:
        result.append({
            "doctor_id": d.doctor_id,
            "name": d.name,
            "department": d.department,
            "specialization": d.specialization,
            "status": d.status,
            "avg_consult_time": d.avg_consult_time
        })

    return jsonify(result)


# ✅ ------------------------------
# ✅ Departments List
# ✅ ------------------------------
@doctor_bp.route("/departments", methods=["GET"])
def get_departments():
    departments = db.session.query(HospitalDoctor.department).distinct().all()
    dept_list = [d[0] for d in departments]
    return jsonify(dept_list)


# ✅ ------------------------------
# ✅ Doctor Dashboard API
# ✅ /hospital/doctor-dashboard/<doctor_id>
# ✅ ------------------------------
@doctor_bp.route("/doctor-dashboard/<int:doctor_id>", methods=["GET"])
def doctor_dashboard(doctor_id):
    doctor = HospitalDoctor.query.get(doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found ❌"}), 404

    # ✅ queue
    queue = HospitalQueue.query.filter_by(doctor_id=doctor_id).first()
    queue_count = queue.current_patient_count if queue else 0

    # ✅ slots
    slots = HospitalSlot.query.filter_by(doctor_id=doctor_id).order_by(HospitalSlot.slot_date.asc()).all()
    slot_list = []
    for s in slots:
        slot_list.append({
            "slot_id": s.slot_id,
            "slot_date": str(s.slot_date),
            "start_time": s.start_time,
            "end_time": s.end_time,
            "status": s.status
        })

    return jsonify({
        "doctor_id": doctor.doctor_id,
        "name": doctor.name,
        "department": doctor.department,
        "status": doctor.status,
        "queue_count": queue_count,
        "slots": slot_list
    })


# ✅ ------------------------------
# ✅ Doctor Appointments API
# ✅ /hospital/doctor-appointments/<doctor_id>
# ✅ ------------------------------
@doctor_bp.route("/doctor-appointments/<int:doctor_id>", methods=["GET"])
def doctor_appointments(doctor_id):
    appointments = HospitalAppointment.query.filter_by(doctor_id=doctor_id).order_by(
        HospitalAppointment.created_at.desc()
    ).all()

    result = []
    for a in appointments:
        patient = HospitalPatient.query.get(a.patient_id)
        slot = HospitalSlot.query.get(a.slot_id)

        result.append({
            "appointment_id": a.appointment_id,
            "token_number": a.token_number,   # ✅ TOKEN
            "patient_id": patient.patient_id if patient else None,
            "patient_name": patient.name if patient else "Unknown",
            "patient_message": a.patient_message if hasattr(a, "patient_message") else "",
            "slot": f"{slot.slot_date} {slot.start_time}-{slot.end_time}" if slot else "NA",
            "status": a.status
        })

    return jsonify(result)


# ✅ ------------------------------
# ✅ Doctor Next Patient (Now Serving)
# ✅ /hospital/doctor-next-patient
# ✅ ------------------------------
@doctor_bp.route("/doctor-next-patient", methods=["PUT"])
def doctor_next_patient():
    # ✅ Doctor only
    if "role" not in session or session.get("role") != "Doctor":
        return jsonify({"error": "Doctor login required ❌"}), 401

    doctor_id = session.get("doctor_id")
    if not doctor_id:
        return jsonify({"error": "Doctor ID not found in session ❌"}), 400

    # ✅ Next appointment with smallest token
    next_appt = HospitalAppointment.query.filter_by(
        doctor_id=doctor_id,
        status="Booked"
    ).order_by(HospitalAppointment.token_number.asc()).first()

    if not next_appt:
        return jsonify({"message": "No patients waiting ✅", "token_number": None})

    return jsonify({
        "message": "Now serving next patient ✅",
        "appointment_id": next_appt.appointment_id,
        "token_number": next_appt.token_number,
        "patient_id": next_appt.patient_id
    })
