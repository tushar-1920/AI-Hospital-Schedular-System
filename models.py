from extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# ✅ 1) Doctors Table
class HospitalDoctor(db.Model):
    __tablename__ = "hospital_doctors"

    doctor_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)

    status = db.Column(db.String(20), default="Available")  # Available, Busy, Emergency, Leave
    avg_consult_time = db.Column(db.Integer, default=10)
    experience_years = db.Column(db.Integer, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ✅ 2) Patients Table
class HospitalPatient(db.Model):
    __tablename__ = "hospital_patients"

    patient_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)  # Male/Female/Other
    phone = db.Column(db.String(15))
    history_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ✅ 3) Slots Table
class HospitalSlot(db.Model):
    __tablename__ = "hospital_slots"

    slot_id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("hospital_doctors.doctor_id"), nullable=False)

    slot_date = db.Column(db.String(20), nullable=False)   # "2026-01-20"
    start_time = db.Column(db.String(10), nullable=False)  # "09:00"
    end_time = db.Column(db.String(10), nullable=False)    # "09:15"

    status = db.Column(db.String(20), default="Free")  # Free, Booked, Blocked


# ✅ 4) Appointments Table
class HospitalAppointment(db.Model):
    __tablename__ = "hospital_appointments"

    appointment_id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, nullable=False)
    doctor_id = db.Column(db.Integer, nullable=False)
    slot_id = db.Column(db.Integer, nullable=False)

    priority = db.Column(db.String(20), default="Normal")
    appointment_type = db.Column(db.String(50), default="First Visit")
    status = db.Column(db.String(30), default="Booked")
    token_number = db.Column(db.Integer, default=None)

    predicted_wait_time = db.Column(db.Integer, default=None)
    no_show_chance = db.Column(db.Integer, default=0)

    patient_message = db.Column(db.Text, default="")

    # ✅ NEW (Doctor → Patient)
    doctor_message = db.Column(db.Text, default="")
    prescription = db.Column(db.Text, default="")
    prescription_created_at = db.Column(db.String(50), default="")
    

    created_at = db.Column(db.DateTime, default=datetime.utcnow)




# ✅ 5) Doctor Queue Table
class HospitalQueue(db.Model):
    __tablename__ = "hospital_queue"

    queue_id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("hospital_doctors.doctor_id"), nullable=False)

    current_patient_count = db.Column(db.Integer, default=0)
    now_serving_token = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_token_generated = db.Column(db.Integer, default=0)


# ✅ Auth Users Table (Admin/Doctor/Patient)
class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    role = db.Column(db.String(20), nullable=False)  # Admin / Doctor / Patient

    # ✅ Optional link to doctor/patient record
    doctor_id = db.Column(db.Integer, nullable=True)
    patient_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class DoctorFeedback(db.Model):
    __tablename__ = "doctor_feedback"

    feedback_id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, nullable=False)
    doctor_id = db.Column(db.Integer, nullable=False)
    patient_id = db.Column(db.Integer, nullable=False)

    rating = db.Column(db.Integer, nullable=False)  # 1–5
    feedback_text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
