from flask import Flask, render_template
from flask_cors import CORS
from config import Config
from extensions import db

# import models so tables are registered
import models

# Import Routes
from routes.doctor_routes import doctor_bp
from routes.patient_routes import patient_bp
from routes.slot_routes import slot_bp
from routes.appointment_routes import appointment_bp
from routes.dashboard_routes import dashboard_bp
from routes.ui_routes import ui_bp
from routes.auth_routes import auth_bp
from routes.chatbot_routes import chatbot_bp


def create_app():
    

    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = "super_secret_hospital_key"


    CORS(app)

    db.init_app(app)
    


    # ✅ Create tables automatically
    with app.app_context():
        db.create_all()
        print("✅ Hospital AI Tables Created Successfully!")

    # ✅ Register Blueprints
    app.register_blueprint(doctor_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(slot_bp)
    app.register_blueprint(appointment_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(ui_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chatbot_bp)




    # ✅ Home Page
    @app.route("/")
    def home():
        return render_template("index.html")

    return app


app = create_app()

# if __name__ == "__main__":
#     app.run(debug=True)
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure the DB and tables are created
    app.run(host='0.0.0.0', port=5000, debug=True)  # Enables access from phone
