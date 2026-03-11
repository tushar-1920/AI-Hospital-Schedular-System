from flask import Blueprint, request, jsonify, session, redirect
from extensions import db
from models import User, HospitalDoctor, HospitalPatient

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")


# ✅ Register API
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json

    name = data["name"]
    email = data["email"]
    password = data["password"]
    role = data["role"]  # Admin/Doctor/Patient

    # ✅ Check email already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered ❌"}), 400

    user = User(name=name, email=email, role=role)
    user.set_password(password)

    # ✅ If doctor role, create doctor record
    if role == "Doctor":
        department = data.get("department", "General")
        specialization = data.get("specialization", "General")
        avg_consult_time = data.get("avg_consult_time", 10)
        experience_years = data.get("experience_years", 1)

        doctor = HospitalDoctor(
            name=name,
            department=department,
            specialization=specialization,
            status="Available",
            avg_consult_time=avg_consult_time,
            experience_years=experience_years
        )
        db.session.add(doctor)
        db.session.commit()

        user.doctor_id = doctor.doctor_id

    # ✅ If patient role, create patient record
    if role == "Patient":
        age = data.get("age", 20)
        gender = data.get("gender", "Male")
        phone = data.get("phone", "")

        patient = HospitalPatient(
            name=name,
            age=age,
            gender=gender,
            phone=phone
        )
        db.session.add(patient)
        db.session.commit()

        user.patient_id = patient.patient_id

    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User registered ✅", "role": role, "user_id": user.user_id})


# ✅ Login API
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json

    email = data["email"]
    password = data["password"]

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password ❌"}), 401

    # ✅ Save session
    session["user_id"] = user.user_id
    session["role"] = user.role
    session["name"] = user.name
    session["doctor_id"] = user.doctor_id
    session["patient_id"] = user.patient_id

    return jsonify({
        "message": "Login success ✅",
        "role": user.role,
        "doctor_id": user.doctor_id,
        "patient_id": user.patient_id
    })


# ✅ Session Info API
@auth_bp.route("/me", methods=["GET"])
def me():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    return jsonify({
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "name": session.get("name"),
        "doctor_id": session.get("doctor_id"),
        "patient_id": session.get("patient_id")
    })


# ✅ Logout API
@auth_bp.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect("/ui/login")
