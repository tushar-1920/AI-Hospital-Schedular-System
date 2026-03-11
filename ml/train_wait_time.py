import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import joblib

# ✅ Fake training data (for starting)
data = {
    "doctor_avg_time": [10,12,15,8,20,12,10,18,14,9],
    "queue_count": [1,3,5,2,10,4,6,8,7,2],
    "time_of_day": [9,10,11,9,12,10,11,12,9,10],
    "priority_level": [3,2,1,3,1,2,3,1,2,3],
    "wait_time": [10,35,75,20,200,55,60,150,95,18]
}

df = pd.DataFrame(data)

X = df.drop("wait_time", axis=1)
y = df["wait_time"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestRegressor()
model.fit(X_train, y_train)

joblib.dump(model, "ml/wait_time_model.pkl")

print("✅ Wait Time Model Trained and Saved!")
