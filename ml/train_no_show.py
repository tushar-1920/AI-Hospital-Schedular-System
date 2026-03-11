import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
import joblib

# ✅ Dummy dataset
data = {
    "history_count": [0,1,2,3,5,0,1,4,6,2],
    "booking_gap": [1,7,3,2,1,10,5,1,0,4],
    "day_of_week": [0,5,2,1,3,6,4,2,1,0],  # 0=Mon
    "appt_type": [0,1,0,1,0,1,0,0,1,0],    # 0=New, 1=Follow-up
    "no_show": [1,1,0,0,0,1,1,0,0,0]
}

df = pd.DataFrame(data)
X = df.drop("no_show", axis=1)
y = df["no_show"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = LogisticRegression()
model.fit(X_train, y_train)

joblib.dump(model, "ml/no_show_model.pkl")

print("✅ No-show Model trained and saved!")
