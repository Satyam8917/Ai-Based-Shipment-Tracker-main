import pandas as pd
import pickle

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error

data = pd.read_csv("shipment_data.csv")

feature_cols = [
    "source_city_id",
    "destination_city_id",
    "distance",
    "traffic",
    "weather",
    "route_condition",
    "departure_hour",
]

if not all(col in data.columns for col in feature_cols):
    # Backward compatibility with older datasets.
    feature_cols = ["distance", "traffic", "weather", "route_condition", "departure_hour"]

X = data[feature_cols]

y_delay = data["delay"]
y_fuel = data["fuel_cost"] if "fuel_cost" in data.columns else None
y_time = data["delivery_time_hours"] if "delivery_time_hours" in data.columns else None

X_train, X_test, y_train, y_test = train_test_split(
    X, y_delay, test_size=0.2, random_state=42
)

delay_model = RandomForestClassifier(
    n_estimators=220,
    max_depth=12,
    random_state=42
)
delay_model.fit(X_train, y_train)

pred = delay_model.predict(X_test)
accuracy = accuracy_score(y_test, pred)

bundle = {
    "feature_cols": feature_cols,
    "delay_model": delay_model,
    "fuel_model": None,
    "time_model": None,
}

if y_fuel is not None:
    Xf_train, Xf_test, yf_train, yf_test = train_test_split(
        X, y_fuel, test_size=0.2, random_state=42
    )
    fuel_model = RandomForestRegressor(
        n_estimators=260,
        max_depth=14,
        random_state=42
    )
    fuel_model.fit(Xf_train, yf_train)
    fuel_mae = mean_absolute_error(yf_test, fuel_model.predict(Xf_test))
    bundle["fuel_model"] = fuel_model
    print("Fuel Cost MAE:", round(float(fuel_mae), 2))

if y_time is not None:
    Xt_train, Xt_test, yt_train, yt_test = train_test_split(
        X, y_time, test_size=0.2, random_state=42
    )
    time_model = RandomForestRegressor(
        n_estimators=260,
        max_depth=14,
        random_state=42
    )
    time_model.fit(Xt_train, yt_train)
    time_mae = mean_absolute_error(yt_test, time_model.predict(Xt_test))
    bundle["time_model"] = time_model
    print("Delivery Time MAE (hours):", round(float(time_mae), 2))

print("Delay Model Accuracy:", accuracy)

pickle.dump(bundle, open("model_bundle.pkl", "wb"))
pickle.dump(delay_model, open("model.pkl", "wb"))

print("Model bundle saved successfully")
