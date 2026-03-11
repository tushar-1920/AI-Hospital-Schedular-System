from flask import Blueprint, request, jsonify, session
from extensions import db
from models import HospitalDoctor, HospitalPatient, HospitalAppointment, HospitalSlot, HospitalQueue


patient_bp = Blueprint("patient_bp", __name__, url_prefix="/hospital")

# ✅ Add Patient
@patient_bp.route("/add-patient", methods=["POST"])
def add_patient():
    data = request.json

    patient = HospitalPatient(
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        phone=data.get("phone", ""),
        history_count=data.get("history_count", 0)
    )

    db.session.add(patient)
    db.session.commit()

    return jsonify({"message": "Patient Added ✅", "patient_id": patient.patient_id})


# ✅ Get Patients
@patient_bp.route("/patients", methods=["GET"])
def get_patients():
    patients = HospitalPatient.query.all()
    result = []

    for p in patients:
        result.append({
            "patient_id": p.patient_id,
            "name": p.name,
            "age": p.age,
            "gender": p.gender,
            "phone": p.phone,
            "history_count": p.history_count
        })

    return jsonify(result)


@patient_bp.route("/patient-messages/<int:patient_id>", methods=["GET"])
def patient_messages(patient_id):
    if "role" not in session or session.get("role") != "Patient":
        return jsonify({"error": "Unauthorized"}), 403

    if session.get("patient_id") != patient_id:
        return jsonify({"error": "Not allowed"}), 403

    appts = HospitalAppointment.query.filter_by(patient_id=patient_id).all()

    result = []
    for a in appts:
        doctor = HospitalDoctor.query.get(a.doctor_id)
        slot = HospitalSlot.query.get(a.slot_id)

        # ✅ only show if doctor sent prescription/message
        if (a.prescription and a.prescription.strip()) or (a.doctor_message and a.doctor_message.strip()):
            result.append({
                "appointment_id": a.appointment_id,
                "status": a.status,
                "doctor_name": doctor.name if doctor else "Unknown",
                "department": doctor.department if doctor else "Unknown",
                "slot": f"{slot.slot_date} {slot.start_time}-{slot.end_time}" if slot else "N/A",
                "doctor_message": a.doctor_message,
                "prescription": a.prescription,
                "sent_at": a.prescription_created_at
            })

    return jsonify(result)

@patient_bp.route("/live-status/<int:appointment_id>", methods=["GET"])
def live_status(appointment_id):
    appt = HospitalAppointment.query.get(appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found ❌"}), 404

    your_token = appt.token_number
    doctor_id = appt.doctor_id

    queue = HospitalQueue.query.filter_by(doctor_id=doctor_id).first()

    now_serving = queue.now_serving_token if queue else 0
    waiting = max(your_token - now_serving, 0)

    # ✅ Status calculation
    if your_token == now_serving:
        status = "✅ Your Turn Now"
    elif your_token < now_serving:
        status = "✅ Completed"
    else:
        status = "⏳ Waiting"

    return jsonify({
        "appointment_id": appointment_id,
        "your_token": your_token,
        "now_serving_token": now_serving,
        "waiting_patients": waiting,
        "status": status
    })
