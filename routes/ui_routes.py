from flask import Blueprint, render_template, session, redirect

ui_bp = Blueprint("ui_bp", __name__)

# ✅ Role Protected Decorator
def role_required(allowed_roles):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # ✅ Not logged in
            if "role" not in session:
                return redirect("/ui/login")

            # ✅ Logged in but wrong role
            if session.get("role") not in allowed_roles:
                return redirect("/ui/unauthorized")

            return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


# ✅ ----------------------------------------
# ✅ PUBLIC ROUTES (No Login Needed)
# ✅ ----------------------------------------

@ui_bp.route("/")
def home():
    role = session.get("role")

    if role == "Admin":
        return redirect("/ui/admin-dashboard")
    elif role == "Doctor":
        return redirect("/ui/doctor-dashboard")
    elif role == "Patient":
        return redirect("/ui/patient-dashboard")

    return render_template("index.html")



@ui_bp.route("/ui/login")
def login_ui():
    return render_template("login.html")


@ui_bp.route("/ui/register")
def register_ui():
    return render_template("register.html")


@ui_bp.route("/ui/unauthorized")
def unauthorized():
    return render_template("unauthorized.html")


# ✅ ----------------------------------------
# ✅ ADMIN ROUTES (Only Admin)
# ✅ ----------------------------------------

@ui_bp.route("/ui/admin-dashboard")
@role_required(["Admin"])
def admin_dash():
    return render_template("admin_dashboard.html")


@ui_bp.route("/ui/admin-report")
@role_required(["Admin"])
def admin_report_ui():
    return render_template("admin_feedback_report.html")


@ui_bp.route("/ui/doctors")
@role_required(["Admin"])
def doctors_ui():
    return render_template("doctors.html")


@ui_bp.route("/ui/patients")
@role_required(["Admin"])
def patients_ui():
    return render_template("patients.html")


@ui_bp.route("/ui/slots")
@role_required(["Admin"])
def slots_ui():
    return render_template("generate_slots.html")


@ui_bp.route("/ui/dashboard")
@role_required(["Admin"])
def dashboard_ui():
    return render_template("dashboard.html")


@ui_bp.route("/ui/appointments")
@role_required(["Admin"])
def appointments_ui():
    return render_template("appointments.html")


@ui_bp.route("/ui/doctor-slots")
@role_required(["Admin"])
def doctor_slots_ui():
    return render_template("doctor_slots.html")


@ui_bp.route("/ui/patient-history")
@role_required(["Admin"])
def patient_history_ui():
    return render_template("patient_history.html")


# ✅ ----------------------------------------
# ✅ DOCTOR ROUTES (Only Doctor)
# ✅ ----------------------------------------

@ui_bp.route("/ui/doctor-dashboard")
@role_required(["Doctor"])
def doctor_dash():
    return render_template("doctor_dashboard.html")


@ui_bp.route("/ui/emergency")
@role_required(["Doctor", "Admin"])
def emergency_ui():
    return render_template("emergency.html")

@ui_bp.route("/ui/prescription/<int:appointment_id>")
@role_required(["Doctor"])
def prescription_ui(appointment_id):
    return render_template("doctor_prescription.html", appointment_id=appointment_id)



# ✅ ----------------------------------------
# ✅ PATIENT ROUTES (Only Patient)
# ✅ ----------------------------------------

@ui_bp.route("/ui/book")
@role_required(["Patient"])
def book_ui():
    return render_template("book_ai.html")


@ui_bp.route("/ui/patient-dashboard")
@role_required(["Patient"])
def patient_dash():
    return render_template("patient_dashboard.html")

@ui_bp.route("/ui/messages")
@role_required(["Patient"])
def patient_messages_ui():
    return render_template("patient_messages.html")

@ui_bp.route("/ui/feedback/<int:appointment_id>")
@role_required(["Patient"])
def feedback_ui(appointment_id):
    return render_template("feedback.html", appointment_id=appointment_id)


# ✅ ----------------------------------------
# ✅ OPTIONAL CHATBOT ROUTE (ONLY PATIENT)
# ✅ ----------------------------------------

@ui_bp.route("/ui/chatbot")
@role_required(["Patient"])
def chatbot_ui():
    return render_template("chatbot.html")


@ui_bp.route("/ui/my-history")
@role_required(["Patient"])
def my_history_ui():
    return render_template("patient_history.html")

