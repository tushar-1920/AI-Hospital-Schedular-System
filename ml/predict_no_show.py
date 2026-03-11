import joblib
import os

MODEL_PATH = "ml/no_show_model.pkl"

def predict_no_show(history_count, booking_gap, day_of_week, appt_type):
    if not os.path.exists(MODEL_PATH):
        return None

    model = joblib.load(MODEL_PATH)

    features = [[history_count, booking_gap, day_of_week, appt_type]]
    prob = model.predict_proba(features)[0][1]  # probability of no-show
    return int(prob * 100)
