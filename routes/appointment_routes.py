from flask import Blueprint, request, jsonify, session
from extensions import db
from models import (
    HospitalAppointment,
    HospitalSlot,
    HospitalQueue,
    HospitalDoctor,
    HospitalPatient,
    DoctorFeedback
)

from datetime import datetime, date
from ml.predict_no_show import predict_no_show
from ml.predict_wait_time import predict_wait_time
from utils.doctor_scoring import calculate_doctor_score

appointment_bp = Blueprint("appointment_bp", __name__, url_prefix="/hospital")


# ✅ Helper: Doctor Score (AI Logic)
def calculate_doctor_score(doctor, queue_count, priority):
    """
    Higher score = better doctor choice
    """
    availability_score = 50 if doctor.status == "Available" else -100
    queue_penalty = queue_count * 3
    experience_score = doctor.experience_years * 2

    if priority == "P1":
        priority_score = 20
    elif priority == "P2":
        priority_score = 10
    else:
        priority_score = 0

    total_score = availability_score - queue_penalty + experience_score + priority_score
    return total_score



@appointment_bp.route("/ai-book-appointment", methods=["POST"])
def ai_book_appointment():
    data = request.json

    patient_id = data.get("patient_id")
    department = data.get("department")
    priority = data.get("priority", "Normal")
    appointment_type = data.get("appointment_type", "First Visit")
    patient_message = data.get("patient_message", "")

    if not patient_id or not department:
        return jsonify({"error": "patient_id and department are required ❌"}), 400

    # ✅ Check patient
    patient = HospitalPatient.query.get(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found ❌"}), 404

    # ✅ Doctors in department
    doctors = HospitalDoctor.query.filter_by(department=department).all()
    if not doctors:
        return jsonify({"error": "No doctors available ❌"}), 404

    best_doctor = None
    best_score = -999999

    for doc in doctors:
        queue = HospitalQueue.query.filter_by(doctor_id=doc.doctor_id).first()
        queue_count = queue.current_patient_count if queue else 0

        score = calculate_doctor_score(doc, queue_count, priority)

        if score > best_score:
            best_score = score
            best_doctor = doc

    if not best_doctor:
        return jsonify({"error": "No suitable doctor found ❌"}), 404

    # ✅ Free slot
    free_slot = HospitalSlot.query.filter_by(
        doctor_id=best_doctor.doctor_id,
        status="Free"
    ).first()

    if not free_slot:
        return jsonify({"error": f"No free slot available for {best_doctor.name} ❌"}), 404

    # ✅ Queue
    queue = HospitalQueue.query.filter_by(doctor_id=best_doctor.doctor_id).first()
    queue_count = queue.current_patient_count if queue else 0

    # ✅ ML Wait Time
    current_hour = datetime.now().hour
    priority_map = {"Emergency": 1, "Urgent": 2, "Normal": 3}
    priority_level = priority_map.get(priority, 3)

    ml_wait = predict_wait_time(
        doctor_avg_time=best_doctor.avg_consult_time,
        queue_count=queue_count,
        time_of_day=current_hour,
        priority_level=priority_level
    )

    predicted_wait_time = ml_wait if ml_wait is not None else queue_count * best_doctor.avg_consult_time

    # ✅ No Show prediction
    try:
        slot_date_obj = free_slot.slot_date
        booking_gap = max((slot_date_obj - date.today()).days, 0)
    except:
        booking_gap = 1

    day_of_week = date.today().weekday()
    appt_type_num = 1 if "Follow" in appointment_type else 0

    no_show_chance = predict_no_show(
        history_count=patient.history_count,
        booking_gap=booking_gap,
        day_of_week=day_of_week,
        appt_type=appt_type_num
    )
    no_show_chance = no_show_chance if no_show_chance is not None else 0

    # ✅ TOKEN GENERATION (Doctor wise)
    last_token = db.session.query(db.func.max(HospitalAppointment.token_number)).filter_by(
        doctor_id=best_doctor.doctor_id
    ).scalar()

    new_token = (last_token or 0) + 1

    # ✅ Book slot
    free_slot.status = "Booked"

    appointment = HospitalAppointment(
        patient_id=patient_id,
        doctor_id=best_doctor.doctor_id,
        slot_id=free_slot.slot_id,
        priority=priority,
        appointment_type=appointment_type,
        status="Booked",
        predicted_wait_time=predicted_wait_time,
        no_show_chance=no_show_chance,
        patient_message=patient_message,
        token_number=new_token   # ✅ SAVE TOKEN
    )

    db.session.add(appointment)

    # ✅ Update queue count
    if queue:
        queue.current_patient_count += 1
    else:
        db.session.add(HospitalQueue(doctor_id=best_doctor.doctor_id, current_patient_count=1))

    db.session.commit()

    return jsonify({
        "message": "AI Appointment Booked ✅",
        "appointment_id": appointment.appointment_id,
        "assigned_doctor": best_doctor.name,
        "doctor_id": best_doctor.doctor_id,
        "department": best_doctor.department,
        "slot": f"{free_slot.slot_date} {free_slot.start_time}-{free_slot.end_time}",
        "predicted_wait_time_min": predicted_wait_time,
        "no_show_chance_percent": no_show_chance,
        "doctor_score": best_score,
        "token_number": new_token   # ✅ RETURN TOKEN TO PATIENT
    })

# ✅ 2) Emergency Booking + Shifting
@appointment_bp.route("/emergency-book", methods=["POST"])
def emergency_book():
    data = request.json

    patient_id = data["patient_id"]
    department = data["department"]
    priority = "P1"  # ✅ always emergency

    # ✅ Check patient exists
    patient = HospitalPatient.query.get(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found ❌"}), 404

    # ✅ Get doctors from department
    doctors = HospitalDoctor.query.filter_by(department=department).all()
    if not doctors:
        return jsonify({"error": "No doctors available in this department ❌"}), 404

    best_doctor = None
    best_score = -999999

    for doc in doctors:
        queue = HospitalQueue.query.filter_by(doctor_id=doc.doctor_id).first()
        queue_count = queue.current_patient_count if queue else 0

        score = calculate_doctor_score(doc, queue_count, priority)
        if score > best_score:
            best_score = score
            best_doctor = doc

    if not best_doctor:
        return jsonify({"error": "No suitable doctor found ❌"}), 404

    # ✅ Try free slot first
    free_slot = HospitalSlot.query.filter_by(
        doctor_id=best_doctor.doctor_id,
        status="Free"
    ).first()

    if free_slot:
        free_slot.status = "Booked"

        queue = HospitalQueue.query.filter_by(doctor_id=best_doctor.doctor_id).first()
        queue_count = queue.current_patient_count if queue else 0

        # ✅ ML wait time for emergency too (optional)
        current_hour = datetime.now().hour
        ml_wait = predict_wait_time(
            doctor_avg_time=best_doctor.avg_consult_time,
            queue_count=queue_count,
            time_of_day=current_hour,
            priority_level=1
        )
        predicted_wait_time = ml_wait if ml_wait is not None else queue_count * best_doctor.avg_consult_time

        appointment = HospitalAppointment(
            patient_id=patient_id,
            doctor_id=best_doctor.doctor_id,
            slot_id=free_slot.slot_id,
            priority="P1",
            appointment_type="New",
            status="Booked",
            predicted_wait_time=predicted_wait_time
        )

        db.session.add(appointment)

        # ✅ Update queue
        if queue:
            queue.current_patient_count += 1
        else:
            new_queue = HospitalQueue(doctor_id=best_doctor.doctor_id, current_patient_count=1)
            db.session.add(new_queue)

        db.session.commit()

        return jsonify({
            "message": "🚑 Emergency Booked ✅ (Free Slot Found)",
            "appointment_id": appointment.appointment_id,
            "assigned_doctor": best_doctor.name,
            "slot": f"{free_slot.slot_date} {free_slot.start_time}-{free_slot.end_time}",
            "predicted_wait_time_min": predicted_wait_time
        })

    # ✅ If no free slot -> shift earliest booked slot
    booked_slot = HospitalSlot.query.filter_by(
        doctor_id=best_doctor.doctor_id,
        status="Booked"
    ).first()

    if not booked_slot:
        return jsonify({"error": "No booked slot found to shift ❌"}), 404

    old_appointment = HospitalAppointment.query.filter_by(slot_id=booked_slot.slot_id).first()
    if not old_appointment:
        return jsonify({"error": "Old appointment not found ❌"}), 404

    next_free_slot = HospitalSlot.query.filter_by(
        doctor_id=best_doctor.doctor_id,
        status="Free"
    ).first()

    if not next_free_slot:
        return jsonify({"error": "No free slot available to shift patient ❌"}), 400

    # ✅ Shift old appointment to next free slot
    next_free_slot.status = "Booked"
    old_appointment.slot_id = next_free_slot.slot_id

    # ✅ Emergency takes booked_slot
    emergency_appointment = HospitalAppointment(
        patient_id=patient_id,
        doctor_id=best_doctor.doctor_id,
        slot_id=booked_slot.slot_id,
        priority="P1",
        appointment_type="New",
        status="Booked",
        predicted_wait_time=0
    )

    db.session.add(emergency_appointment)
    db.session.commit()

    return jsonify({
        "message": "🚑 Emergency Booked ✅ (Appointment Shifted)",
        "assigned_doctor": best_doctor.name,
        "emergency_slot": f"{booked_slot.slot_date} {booked_slot.start_time}-{booked_slot.end_time}",
        "shifted_patient_id": old_appointment.patient_id,
        "new_slot_for_shifted_patient": f"{next_free_slot.slot_date} {next_free_slot.start_time}-{next_free_slot.end_time}",
        "emergency_appointment_id": emergency_appointment.appointment_id
    })


@appointment_bp.route("/appointments", methods=["GET"])
def get_all_appointments():
    appointments = HospitalAppointment.query.all()
    result = []

    for appt in appointments:
        doctor = HospitalDoctor.query.get(appt.doctor_id)
        patient = HospitalPatient.query.get(appt.patient_id)
        slot = HospitalSlot.query.get(appt.slot_id)

        result.append({
            "appointment_id": appt.appointment_id,
            "patient_name": patient.name if patient else "Unknown",
            "doctor_name": doctor.name if doctor else "Unknown",
            "department": doctor.department if doctor else "Unknown",
            "priority": appt.priority,
            "type": appt.appointment_type,
            "status": appt.status,
            "slot_date": slot.slot_date if slot else "",
            "slot_time": f"{slot.start_time}-{slot.end_time}" if slot else "",
            "predicted_wait_time": appt.predicted_wait_time
        })

    return jsonify(result)


@appointment_bp.route("/cancel-appointment/<int:appointment_id>", methods=["PUT"])
def cancel_appointment(appointment_id):
    appt = HospitalAppointment.query.get(appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found ❌"}), 404

    # ✅ Free the slot
    slot = HospitalSlot.query.get(appt.slot_id)
    if slot:
        slot.status = "Free"

    # ✅ Reduce queue count
    queue = HospitalQueue.query.filter_by(doctor_id=appt.doctor_id).first()
    if queue and queue.current_patient_count > 0:
        queue.current_patient_count -= 1

    appt.status = "Cancelled"
    db.session.commit()

    return jsonify({"message": "Appointment Cancelled ✅", "appointment_id": appointment_id})


@appointment_bp.route("/reschedule-appointment/<int:appointment_id>", methods=["PUT"])
def reschedule_appointment(appointment_id):
    appt = HospitalAppointment.query.get(appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found ❌"}), 404

    if appt.status != "Booked":
        return jsonify({"error": "Only booked appointments can be rescheduled ❌"}), 400

    doctor_id = appt.doctor_id

    # ✅ Find next free slot for that doctor
    next_free_slot = HospitalSlot.query.filter_by(
        doctor_id=doctor_id,
        status="Free"
    ).first()

    if not next_free_slot:
        return jsonify({"error": "No free slots available for reschedule ❌"}), 400

    # ✅ Free old slot
    old_slot = HospitalSlot.query.get(appt.slot_id)
    if old_slot:
        old_slot.status = "Free"

    # ✅ Assign new slot
    next_free_slot.status = "Booked"
    appt.slot_id = next_free_slot.slot_id

    db.session.commit()

    return jsonify({
        "message": "Appointment Rescheduled ✅",
        "appointment_id": appointment_id,
        "new_slot": f"{next_free_slot.slot_date} {next_free_slot.start_time}-{next_free_slot.end_time}"
    })

@appointment_bp.route("/patient-history/<int:patient_id>", methods=["GET"])
def patient_history(patient_id):
    appointments = HospitalAppointment.query.filter_by(patient_id=patient_id).all()

    if not appointments:
        return jsonify([])

    result = []
    for appt in appointments:
        doctor = HospitalDoctor.query.get(appt.doctor_id)
        slot = HospitalSlot.query.get(appt.slot_id)

        result.append({
            "appointment_id": appt.appointment_id,
            "doctor_name": doctor.name if doctor else "Unknown",
            "department": doctor.department if doctor else "Unknown",
            "priority": appt.priority,
            "status": appt.status,
            "slot_date": slot.slot_date if slot else "",
            "slot_time": f"{slot.start_time}-{slot.end_time}" if slot else "",
            "predicted_wait_time": appt.predicted_wait_time
        })

    return jsonify(result)

@appointment_bp.route("/doctor-appointments/<int:doctor_id>", methods=["GET"])
def doctor_appointments(doctor_id):
    appointments = HospitalAppointment.query.filter_by(doctor_id=doctor_id).all()
    result = []

    for appt in appointments:
        patient = HospitalPatient.query.get(appt.patient_id)
        slot = HospitalSlot.query.get(appt.slot_id)

        result.append({
            "appointment_id": appt.appointment_id,
            "patient_id": appt.patient_id,
            "patient_name": patient.name if patient else "Unknown",
            "priority": appt.priority,
            "visit_type": appt.appointment_type,
            "patient_message": getattr(appt, "patient_message", ""),
            "status": appt.status,
            "predicted_wait_time": appt.predicted_wait_time,
            "slot": f"{slot.slot_date} {slot.start_time}-{slot.end_time}" if slot else "N/A"
        })

    return jsonify(result)


@appointment_bp.route("/mark-done/<int:appointment_id>", methods=["PUT"])
def mark_done(appointment_id):
    appt = HospitalAppointment.query.get(appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found ❌"}), 404

    appt.status = "Done"

    # ✅ Reduce queue count
    queue = HospitalQueue.query.filter_by(doctor_id=appt.doctor_id).first()
    if queue and queue.current_patient_count > 0:
        queue.current_patient_count -= 1

    db.session.commit()
    return jsonify({"message": "Appointment marked Done ✅", "appointment_id": appointment_id})


@appointment_bp.route("/patient-cancel/<int:appointment_id>", methods=["PUT"])
def patient_cancel_appointment(appointment_id):
    appt = HospitalAppointment.query.get(appointment_id)

    if not appt:
        return jsonify({"error": "Appointment not found ❌"}), 404

    if appt.status != "Booked":
        return jsonify({"error": "Only booked appointments can be cancelled ❌"}), 400

    # ✅ Free slot
    slot = HospitalSlot.query.get(appt.slot_id)
    if slot:
        slot.status = "Free"

    # ✅ Update queue
    queue = HospitalQueue.query.filter_by(doctor_id=appt.doctor_id).first()
    if queue and queue.current_patient_count > 0:
        queue.current_patient_count -= 1

    appt.status = "Cancelled"
    db.session.commit()

    return jsonify({"message": "Appointment cancelled ✅", "appointment_id": appointment_id})

@appointment_bp.route("/patient-reschedule/<int:appointment_id>", methods=["PUT"])
def patient_reschedule(appointment_id):
    appt = HospitalAppointment.query.get(appointment_id)

    if not appt:
        return jsonify({"error": "Appointment not found ❌"}), 404

    if appt.status != "Booked":
        return jsonify({"error": "Only Booked appointments can be rescheduled ❌"}), 400

    doctor_id = appt.doctor_id

    # ✅ Find next free slot
    next_free_slot = HospitalSlot.query.filter_by(
        doctor_id=doctor_id,
        status="Free"
    ).first()

    if not next_free_slot:
        return jsonify({"error": "No free slot available for reschedule ❌"}), 400

    # ✅ Free old slot
    old_slot = HospitalSlot.query.get(appt.slot_id)
    if old_slot:
        old_slot.status = "Free"

    # ✅ Assign new slot
    next_free_slot.status = "Booked"
    appt.slot_id = next_free_slot.slot_id

    db.session.commit()

    return jsonify({
        "message": "Appointment Rescheduled ✅",
        "appointment_id": appointment_id,
        "new_slot": f"{next_free_slot.slot_date} {next_free_slot.start_time}-{next_free_slot.end_time}"
    })

@appointment_bp.route("/book-slot", methods=["POST"])
def book_selected_slot():
    data = request.json

    patient_id = data.get("patient_id")
    doctor_id = data.get("doctor_id")
    slot_id = data.get("slot_id")
    priority = data.get("priority", "Normal")
    appointment_type = data.get("appointment_type", "First Visit")
    patient_message = data.get("patient_message", "")

    # ✅ Validate
    patient = HospitalPatient.query.get(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found ❌"}), 404

    doctor = HospitalDoctor.query.get(doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found ❌"}), 404

    slot = HospitalSlot.query.get(slot_id)
    if not slot or slot.status != "Free":
        return jsonify({"error": "Slot not available ❌"}), 400

    # ✅ Predict wait time based on queue
    queue = HospitalQueue.query.filter_by(doctor_id=doctor_id).first()
    queue_count = queue.current_patient_count if queue else 0

    predicted_wait_time = queue_count * doctor.avg_consult_time

    # ✅ Book slot
    slot.status = "Booked"

    appt = HospitalAppointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        slot_id=slot_id,
        priority=priority,
        appointment_type=appointment_type,
        status="Booked",
        predicted_wait_time=predicted_wait_time,
        patient_message=patient_message
    )

    db.session.add(appt)

    # ✅ Update queue
    if queue:
        queue.current_patient_count += 1
    else:
        db.session.add(HospitalQueue(doctor_id=doctor_id, current_patient_count=1))

    db.session.commit()

    return jsonify({
        "message": "Appointment booked successfully ✅",
        "appointment_id": appt.appointment_id,
        "doctor": doctor.name,
        "doctor_id": doctor.doctor_id,
        "slot": f"{slot.slot_date} {slot.start_time}-{slot.end_time}",
        "predicted_wait_time_min": predicted_wait_time
    })

from datetime import datetime

@appointment_bp.route("/add-prescription/<int:appointment_id>", methods=["POST"])
def add_prescription(appointment_id):
    if "role" not in session or session.get("role") != "Doctor":
        return jsonify({"error": "Unauthorized ❌"}), 403

    data = request.json
    prescription = data.get("prescription", "")
    doctor_message = data.get("doctor_message", "")

    appt = HospitalAppointment.query.get(appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found ❌"}), 404

    # ✅ Only that doctor can update their appointment
    if appt.doctor_id != session.get("doctor_id"):
        return jsonify({"error": "Not allowed ❌"}), 403

    appt.prescription = prescription
    appt.doctor_message = doctor_message
    appt.prescription_created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    db.session.commit()

    return jsonify({"message": "Prescription sent ✅"})


@appointment_bp.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    if "role" not in session or session.get("role") != "Patient":
        return jsonify({"error": "Unauthorized ❌"}), 403

    data = request.json
    appointment_id = data["appointment_id"]
    rating = int(data["rating"])
    feedback_text = data.get("feedback_text", "")

    appt = HospitalAppointment.query.get(appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found ❌"}), 404

    if appt.patient_id != session.get("patient_id"):
        return jsonify({"error": "Not allowed ❌"}), 403

    if appt.status != "Done":
        return jsonify({"error": "Feedback allowed only after Done ✅"}), 400

    fb = DoctorFeedback(
        appointment_id=appointment_id,
        doctor_id=appt.doctor_id,
        patient_id=appt.patient_id,
        rating=rating,
        feedback_text=feedback_text
    )

    db.session.add(fb)
    db.session.commit()

    return jsonify({"message": "Feedback submitted ✅"})

@appointment_bp.route("/doctor-next-patient", methods=["PUT"])
def doctor_next_patient():
    # ✅ Only Doctor
    if "role" not in session or session.get("role") != "Doctor":
        return jsonify({"error": "Unauthorized ❌"}), 401

    doctor_id = session.get("doctor_id")
    if not doctor_id:
        return jsonify({"error": "Doctor session missing ❌"}), 400

    # ✅ Get queue row
    queue = HospitalQueue.query.filter_by(doctor_id=doctor_id).first()
    if not queue:
        return jsonify({"error": "Queue not found ❌"}), 404

    # ✅ Find next booked appointment by token order
    next_appt = HospitalAppointment.query.filter_by(
        doctor_id=doctor_id,
        status="Booked"
    ).order_by(HospitalAppointment.token_number.asc()).first()

    if not next_appt:
        queue.now_serving_token = 0
        db.session.commit()
        return jsonify({
            "message": "No patients in queue ✅",
            "now_serving_token": 0
        })

    # ✅ Update now serving token
    queue.now_serving_token = next_appt.token_number
    db.session.commit()

    return jsonify({
        "message": "Now serving updated ✅",
        "now_serving_token": queue.now_serving_token,
        "appointment_id": next_appt.appointment_id
    })


@appointment_bp.route("/now-serving/<int:doctor_id>", methods=["PUT"])
def now_serving(doctor_id):
    # ✅ Only Doctor/Admin can update now serving
    if "role" not in session or session.get("role") not in ["Doctor", "Admin"]:
        return jsonify({"error": "Unauthorized ❌"}), 403

    # ✅ decrease queue count (now serving next patient)
    queue = HospitalQueue.query.filter_by(doctor_id=doctor_id).first()
    if not queue or queue.current_patient_count == 0:
        return jsonify({"message": "No patients in queue ✅"}), 200

    queue.current_patient_count -= 1
    db.session.commit()

    return jsonify({
        "message": "Now serving next patient ✅",
        "doctor_id": doctor_id,
        "remaining_queue": queue.current_patient_count
    })

@appointment_bp.route("/doctor-preview-next", methods=["GET"])
def doctor_preview_next():
    if "role" not in session or session.get("role") != "Doctor":
        return jsonify({"error": "Unauthorized ❌"}), 403

    doctor_id = session.get("doctor_id")

    queue = HospitalQueue.query.filter_by(doctor_id=doctor_id).first()
    if not queue:
        queue = HospitalQueue(doctor_id=doctor_id, current_patient_count=0, now_serving_token=0)
        db.session.add(queue)
        db.session.commit()

    next_token = queue.now_serving_token + 1

    return jsonify({
        "doctor_id": doctor_id,
        "current_now_serving": queue.now_serving_token,
        "next_token": next_token
    })

@appointment_bp.route("/doctor-confirm-now-serving", methods=["PUT"])
def doctor_confirm_now_serving():
    if "role" not in session or session.get("role") != "Doctor":
        return jsonify({"error": "Unauthorized ❌"}), 403

    doctor_id = session.get("doctor_id")

    queue = HospitalQueue.query.filter_by(doctor_id=doctor_id).first()
    if not queue:
        queue = HospitalQueue(doctor_id=doctor_id, current_patient_count=0, now_serving_token=0)
        db.session.add(queue)
        db.session.commit()

    # ✅ Update now serving token
    queue.now_serving_token += 1
    db.session.commit()

    return jsonify({
        "message": "✅ Now Serving Confirmed",
        "doctor_id": doctor_id,
        "now_serving_token": queue.now_serving_token
    })
