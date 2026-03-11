from flask import Blueprint, request, jsonify, session
from datetime import datetime

from extensions import db
from models import HospitalPatient
from routes.appointment_routes import ai_book_appointment  # ❌ DON'T IMPORT ROUTES LIKE THIS

# ✅ Instead we call booking function internally by making same logic (recommended)

from models import HospitalDoctor, HospitalSlot, HospitalQueue, HospitalAppointment
from datetime import date
from ml.predict_wait_time import predict_wait_time
from ml.predict_no_show import predict_no_show

chatbot_bp = Blueprint("chatbot_bp", __name__, url_prefix="/chatbot")


# ✅ Small helper for token
def generate_token(doctor_id):
    today = date.today()

    last = HospitalAppointment.query.filter(
        HospitalAppointment.doctor_id == doctor_id,
        HospitalAppointment.created_at >= datetime(today.year, today.month, today.day)
    ).order_by(HospitalAppointment.token_number.desc()).first()

    if last and last.token_number:
        return last.token_number + 1
    return 1


def score_doctor(doc, queue_count, priority):
    # ✅ same scoring you use
    score = 0
    if priority == "Emergency":
        score += 50
    elif priority == "Urgent":
        score += 20

    score -= queue_count * 2
    score += doc.experience_years
    return score


# ✅ MAIN CHAT API
@chatbot_bp.route("/ask", methods=["POST"])
def chatbot_ask():
    data = request.json
    message = (data.get("message") or "").strip().lower()
    patient_id = data.get("patient_id")

    if not patient_id:
        return jsonify({"reply": "❌ Patient ID required"}), 400

    patient = HospitalPatient.query.get(patient_id)
    if not patient:
        return jsonify({"reply": "❌ Patient not found. Check Patient ID."}), 404

    # ✅ Create chatbot state store inside session
    if "chat_booking" not in session:
        session["chat_booking"] = {}

    booking = session["chat_booking"]

    # ✅ STEP 0: Start booking intent
    if "book" in message and "appointment" in message:
        # Example: book cardiology appointment
        dept = message.replace("book", "").replace("appointment", "").strip().title()

        booking.clear()
        booking["department"] = dept
        booking["step"] = "symptoms"

        session["chat_booking"] = booking

        return jsonify({
            "reply": f"✅ Booking started for **{dept}**.\n\nTell me your symptoms (example: fever, headache)."
        })

    # ✅ STEP 1: Symptoms
    if booking.get("step") == "symptoms":
        booking["symptoms"] = message
        booking["step"] = "priority"
        session["chat_booking"] = booking

        return jsonify({
            "reply": "✅ Got it.\n\nChoose priority: **Normal / Urgent / Emergency**"
        })

    # ✅ STEP 2: Priority
    if booking.get("step") == "priority":
        pr = message.title()

        if pr not in ["Normal", "Urgent", "Emergency"]:
            return jsonify({"reply": "❌ Invalid priority. Type: Normal / Urgent / Emergency"})

        booking["priority"] = pr
        booking["step"] = "type"
        session["chat_booking"] = booking

        return jsonify({
            "reply": "✅ Priority saved.\n\nVisit type: **First Visit / Follow-up Visit**"
        })

    # ✅ STEP 3: Appointment Type
    if booking.get("step") == "type":
        appt_type = message.title()

        if appt_type not in ["First Visit", "Follow-Up Visit", "Follow-Up", "Follow Up Visit", "Follow Up"]:
            return jsonify({"reply": "❌ Invalid visit type. Type: First Visit / Follow-up Visit"})

        if "follow" in message:
            booking["appointment_type"] = "Follow-up Visit"
        else:
            booking["appointment_type"] = "First Visit"

        booking["step"] = "confirm"
        session["chat_booking"] = booking

        # ✅ Confirmation message
        return jsonify({
            "reply": f"""
✅ Please confirm your booking:

🧾 Department: {booking.get("department")}
🩺 Symptoms: {booking.get("symptoms")}
⚡ Priority: {booking.get("priority")}
📌 Visit Type: {booking.get("appointment_type")}

Type **confirm** or press Confirm button ✅
""",
            "show_confirm_button": True
        })

    # ✅ STEP 4: Confirm booking
    if booking.get("step") == "confirm":
        if message != "confirm":
            return jsonify({"reply": "❌ Please type **confirm** to book."})

        department = booking.get("department")
        priority = booking.get("priority", "Normal")
        appointment_type = booking.get("appointment_type", "First Visit")
        patient_message = booking.get("symptoms", "")

        # ✅ Find doctors for department
        doctors = HospitalDoctor.query.filter_by(department=department, status="Available").all()
        if not doctors:
            return jsonify({"reply": f"❌ No available doctors in {department} right now."})

        best_doctor = None
        best_score = -999999

        for doc in doctors:
            queue = HospitalQueue.query.filter_by(doctor_id=doc.doctor_id).first()
            queue_count = queue.current_patient_count if queue else 0

            score = score_doctor(doc, queue_count, priority)
            if score > best_score:
                best_score = score
                best_doctor = doc

        if not best_doctor:
            return jsonify({"reply": "❌ No doctor found"}), 404

        free_slot = HospitalSlot.query.filter_by(
            doctor_id=best_doctor.doctor_id,
            status="Free"
        ).order_by(HospitalSlot.slot_date.asc(), HospitalSlot.start_time.asc()).first()

        if not free_slot:
            return jsonify({"reply": f"❌ No free slots for {best_doctor.name}"}), 404

        queue = HospitalQueue.query.filter_by(doctor_id=best_doctor.doctor_id).first()
        queue_count = queue.current_patient_count if queue else 0

        # ✅ Predict wait time
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

        # ✅ Predict no-show
        try:
            booking_gap = max((free_slot.slot_date - date.today()).days, 0)
        except:
            booking_gap = 1

        day_of_week = date.today().weekday()
        appt_type_num = 1 if "Follow" in appointment_type else 0

        no_show_chance = predict_no_show(
            history_count=getattr(patient, "history_count", 0),
            booking_gap=booking_gap,
            day_of_week=day_of_week,
            appt_type=appt_type_num
        )
        no_show_chance = no_show_chance if no_show_chance is not None else 0

        # ✅ Generate token
        new_token = generate_token(best_doctor.doctor_id)

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
            token_number=new_token
        )

        db.session.add(appointment)

        if queue:
            queue.current_patient_count += 1
        else:
            db.session.add(HospitalQueue(doctor_id=best_doctor.doctor_id, current_patient_count=1))

        db.session.commit()

        # ✅ Clear chatbot state
        session["chat_booking"] = {}

        return jsonify({
            "reply": f"""
✅ Booking Confirmed 🎉

🎫 Token: {new_token}
👨‍⚕️ Doctor: {best_doctor.name} (ID: {best_doctor.doctor_id})
🏥 Department: {best_doctor.department}
🕒 Slot: {free_slot.slot_date} {free_slot.start_time}-{free_slot.end_time}

⏳ Predicted wait: {predicted_wait_time} min
⚠️ No-show chance: {no_show_chance}%
"""
        })

    # ✅ Default message
    return jsonify({
        "reply": "Type: **book cardiology appointment** to start booking ✅"
    })
