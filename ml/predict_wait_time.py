import joblib
import os

MODEL_PATH = "ml/wait_time_model.pkl"

def predict_wait_time(doctor_avg_time, queue_count, time_of_day, priority_level):
    if not os.path.exists(MODEL_PATH):
        return None

    model = joblib.load(MODEL_PATH)

    features = [[doctor_avg_time, queue_count, time_of_day, priority_level]]
    prediction = model.predict(features)[0]

    return int(prediction)
