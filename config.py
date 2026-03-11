class Config:
    SECRET_KEY = "hospital_ai_secret_key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///skillgap.db"   # ✅ same style as your old project
    SQLALCHEMY_TRACK_MODIFICATIONS = False
