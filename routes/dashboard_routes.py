from flask import Blueprint, jsonify, session, request
from sqlalchemy import func

from extensions import db
from models import (
    HospitalDoctor,
    HospitalPatient,
    HospitalSlot,
    HospitalAppointment,
    HospitalQueue,
    DoctorFeedback
)



dashboard_bp = Blueprint("dashboard_bp", __name__, url_prefix="/hospital")


@dashboard_bp.route("/dashboard-stats", methods=["GET"])
def dashboard_stats():
    total_doctors = HospitalDoctor.query.count()
    total_patients = HospitalPatient.query.count()
    total_slots = HospitalSlot.query.count()
    total_appointments = HospitalAppointment.query.count()

    # ✅ Peak hour calculation (based on booked appointments)
    # We take slot_id -> get slot start_time -> find most common hour
    # SQLite time stored as string "09:00"
    peak_hour = None
    peak_hour_count = 0

    appointments = HospitalAppointment.query.all()

    hour_count = {}
    for appt in appointments:
        slot = HospitalSlot.query.get(appt.slot_id)
        if slot:
            hour = slot.start_time.split(":")[0]  # "09"
            hour_count[hour] = hour_count.get(hour, 0) + 1

    if hour_count:
        peak_hour = max(hour_count, key=hour_count.get)
        peak_hour_count = hour_count[peak_hour]

    # ✅ Department wise appointment count
    dept_data = (
        HospitalAppointment.query
        .join(HospitalDoctor, HospitalAppointment.doctor_id == HospitalDoctor.doctor_id)
        .with_entities(HospitalDoctor.department, func.count(HospitalAppointment.appointment_id))
        .group_by(HospitalDoctor.department)
        .all()
    )

    dept_counts = [{"department": d[0], "count": d[1]} for d in dept_data]

    return jsonify({
        "total_doctors": total_doctors,
        "total_patients": total_patients,
        "total_slots": total_slots,
        "total_appointments": total_appointments,
        "peak_hour": peak_hour,
        "peak_hour_count": peak_hour_count,
        "department_counts": dept_counts
    })

@dashboard_bp.route("/doctor-dashboard/<int:doctor_id>", methods=["GET"])
def doctor_dashboard_data(doctor_id):
    doctor = HospitalDoctor.query.get(doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found ❌"}), 404

    queue = HospitalQueue.query.filter_by(doctor_id=doctor_id).first()
    queue_count = queue.current_patient_count if queue else 0

    # ✅ Today's slots (optional)
    # We will return all slots because date selection may vary
    slots = HospitalSlot.query.filter_by(doctor_id=doctor_id).all()
    slot_list = []

    for s in slots:
        slot_list.append({
            "slot_id": s.slot_id,
            "slot_date": s.slot_date,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "status": s.status
        })

    return jsonify({
        "doctor_id": doctor.doctor_id,
        "name": doctor.name,
        "department": doctor.department,
        "specialization": doctor.specialization,
        "status": doctor.status,
        "queue_count": queue_count,
        "slots": slot_list
    })



@dashboard_bp.route("/patient-dashboard/<int:patient_id>", methods=["GET"])
def patient_dashboard_data(patient_id):
    patient = HospitalPatient.query.get(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found ❌"}), 404

    appointments = HospitalAppointment.query.filter_by(patient_id=patient_id).all()
    appt_list = []

    for appt in appointments:
        doctor = HospitalDoctor.query.get(appt.doctor_id)
        slot = HospitalSlot.query.get(appt.slot_id)

        appt_list.append({
            "appointment_id": appt.appointment_id,
            "doctor_name": doctor.name if doctor else "Unknown",
            "department": doctor.department if doctor else "Unknown",
            "priority": appt.priority,
            "status": appt.status,
            "slot": f"{slot.slot_date} {slot.start_time}-{slot.end_time}" if slot else "N/A",
            "predicted_wait_time": appt.predicted_wait_time,
            "no_show_chance": appt.no_show_chance
        })

    return jsonify({
        "patient_id": patient.patient_id,
        "name": patient.name,
        "appointments": appt_list
    })


@dashboard_bp.route("/admin/doctor-report", methods=["GET"])
def admin_doctor_report():

    if "role" not in session or session.get("role") != "Admin":
        return jsonify({"error": "Unauthorized ❌"}), 403

    # ✅ Total appointments per doctor
    visits = db.session.query(
        HospitalAppointment.doctor_id,
        func.count(HospitalAppointment.appointment_id).label("total_visits")
    ).group_by(HospitalAppointment.doctor_id).all()

    visits_map = {d: v for d, v in visits}

    # ✅ Feedback stats per doctor
    feedback_stats = db.session.query(
        DoctorFeedback.doctor_id,
        func.count(DoctorFeedback.feedback_id).label("feedback_count"),
        func.avg(DoctorFeedback.rating).label("avg_rating")
    ).group_by(DoctorFeedback.doctor_id).all()

    report = []
    for doctor_id, feedback_count, avg_rating in feedback_stats:
        doc = HospitalDoctor.query.get(doctor_id)

        report.append({
            "doctor_id": doctor_id,
            "doctor_name": doc.name if doc else "Unknown",
            "department": doc.department if doc else "Unknown",
            "total_visits": visits_map.get(doctor_id, 0),
            "feedback_count": feedback_count,
            "avg_rating": round(avg_rating, 2) if avg_rating else 0
        })

    # ✅ Sort by most visits first
    report = sorted(report, key=lambda x: x["total_visits"], reverse=True)

    return jsonify(report)
