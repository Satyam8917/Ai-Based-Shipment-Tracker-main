import csv
import io
import math
import random
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import requests
from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint("main", __name__)
CITY_OPTIONS = [
    "Mumbai",
    "Delhi",
    "Kolkata",
    "Bengaluru",
    "Hyderabad",
    "Chennai",
    "Pune",
    "Ahmedabad",
    "Jaipur",
    "Lucknow",
    "Surat",
    "Nagpur",
    "Bhopal",
    "Patna",
    "Bhubaneswar",
    "Guwahati",
    "Chandigarh",
    "Indore",
    "Kochi",
    "Visakhapatnam",
]
TRAFFIC_LABELS = {1: "Low", 2: "Medium", 3: "High"}
WEATHER_LABELS = {1: "Clear", 2: "Rain", 3: "Storm"}
ROUTE_LABELS = {1: "Good", 2: "Moderate", 3: "Poor"}
CITY_COORDS = {
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Kolkata": (22.5726, 88.3639),
    "Bengaluru": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Pune": (18.5204, 73.8567),
    "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873),
    "Lucknow": (26.8467, 80.9462),
    "Surat": (21.1702, 72.8311),
    "Nagpur": (21.1458, 79.0882),
    "Bhopal": (23.2599, 77.4126),
    "Patna": (25.5941, 85.1376),
    "Bhubaneswar": (20.2961, 85.8245),
    "Guwahati": (26.1445, 91.7362),
    "Chandigarh": (30.7333, 76.7794),
    "Indore": (22.7196, 75.8577),
    "Kochi": (9.9312, 76.2673),
    "Visakhapatnam": (17.6868, 83.2185),
}


# -------------------------------
# Util helpers
# -------------------------------

def _get_db_connection():
    return sqlite3.connect(current_app.config["DATABASE_PATH"])


def get_shipments():
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT shipment_id,status,location FROM shipments")
    data = cursor.fetchall()
    conn.close()
    return data


def get_shipment_by_id(shipment_id):
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT shipment_id, status, location
        FROM shipments
        WHERE UPPER(shipment_id) = UPPER(?)
        """,
        (shipment_id,),
    )
    shipment = cursor.fetchone()
    conn.close()
    return shipment


def get_user(username):
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username,password FROM users WHERE username=?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_users():
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users


def get_dashboard_stats():
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM shipments")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM shipments WHERE status='Delayed'")
    delayed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM shipments WHERE status='In Transit'")
    active = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM shipments WHERE status='Delivered'")
    delivered = cursor.fetchone()[0]

    conn.close()

    success = 0
    if total > 0:
        success = round((delivered / total) * 100, 2)

    return total, delayed, active, success


def calculate_eta(distance, traffic):
    speed = 60
    if traffic == 1:
        speed = 60
    elif traffic == 2:
        speed = 40
    else:
        speed = 25

    eta = distance / speed
    return round(eta, 2)


def city_to_id(city_name):
    try:
        return CITY_OPTIONS.index(city_name)
    except ValueError:
        return 0


def build_feature_array(
    distance,
    traffic,
    weather_input,
    route,
    hour,
    source_city,
    destination_city,
):
    feature_cols = current_app.config.get(
        "FEATURE_COLS",
        ["distance", "traffic", "weather", "route_condition", "departure_hour"],
    )
    feature_map = {
        "source_city_id": city_to_id(source_city),
        "destination_city_id": city_to_id(destination_city),
        "distance": distance,
        "traffic": traffic,
        "weather": weather_input,
        "route_condition": route,
        "departure_hour": hour,
    }
    row = [feature_map.get(col, 0) for col in feature_cols]
    return pd.DataFrame([row], columns=feature_cols)


def estimate_distance_km(source_city, destination_city):
    source_lat, source_lng = CITY_COORDS.get(source_city, CITY_COORDS[CITY_OPTIONS[0]])
    dest_lat, dest_lng = CITY_COORDS.get(destination_city, CITY_COORDS[CITY_OPTIONS[1]])

    radius_km = 6371.0
    lat1 = math.radians(source_lat)
    lat2 = math.radians(dest_lat)
    delta_lat = math.radians(dest_lat - source_lat)
    delta_lng = math.radians(dest_lng - source_lng)

    hav = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    arc = 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))
    return round(radius_km * arc * 1.18, 2)


def weather_code_to_level(condition_id, wind_speed):
    if 200 <= condition_id < 300 or wind_speed >= 14:
        return 3
    if 300 <= condition_id < 800:
        return 2
    return 1


def fetch_live_weather(lat, lng):
    api_key = current_app.config.get("OPENWEATHER_API_KEY")
    if not api_key:
        return None

    try:
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "lat": lat,
                "lon": lng,
                "appid": api_key,
                "units": "metric",
            },
            timeout=6,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        return None

    weather_data = payload.get("weather", [{}])[0]
    condition_id = int(weather_data.get("id", 800))
    wind_speed = float(payload.get("wind", {}).get("speed", 0))
    level = weather_code_to_level(condition_id, wind_speed)

    return {
        "level": level,
        "label": WEATHER_LABELS[level],
        "description": weather_data.get("description", WEATHER_LABELS[level]),
        "temperature": payload.get("main", {}).get("temp"),
    }


def fetch_live_route(source_city, destination_city):
    token = current_app.config.get("TOMTOM_API_KEY")
    if not token:
        return None

    source_lat, source_lng = CITY_COORDS.get(source_city, CITY_COORDS[CITY_OPTIONS[0]])
    dest_lat, dest_lng = CITY_COORDS.get(destination_city, CITY_COORDS[CITY_OPTIONS[1]])
    route_pair = f"{source_lat},{source_lng}:{dest_lat},{dest_lng}"

    try:
        response = requests.get(
            f"https://api.tomtom.com/routing/1/calculateRoute/{route_pair}/json",
            params={
                "key": token,
                "travelMode": "truck",
                "traffic": "true",
                "routeType": "fastest",
                "computeTravelTimeFor": "all",
                "routeRepresentation": "summaryOnly",
            },
            timeout=6,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        return None

    routes = payload.get("routes", [])
    if not routes:
        return None

    summary = routes[0].get("summary", {})
    distance_km = round(float(summary.get("lengthInMeters", 0)) / 1000, 2)
    traffic_duration_hours = round(float(summary.get("travelTimeInSeconds", 0)) / 3600, 2)
    base_duration_hours = round(
        float(summary.get("noTrafficTravelTimeInSeconds", summary.get("travelTimeInSeconds", 0)))
        / 3600,
        2,
    )

    if base_duration_hours <= 0:
        traffic_level = 2
        route_condition = 2
    else:
        delay_ratio = traffic_duration_hours / base_duration_hours
        if delay_ratio < 1.12:
            traffic_level = 1
        elif delay_ratio < 1.32:
            traffic_level = 2
        else:
            traffic_level = 3

        if delay_ratio < 1.08:
            route_condition = 1
        elif delay_ratio < 1.25:
            route_condition = 2
        else:
            route_condition = 3

    return {
        "distance_km": distance_km,
        "base_duration_hours": base_duration_hours,
        "traffic_duration_hours": traffic_duration_hours,
        "traffic_level": traffic_level,
        "route_condition": route_condition,
    }


def build_live_context(source_city, destination_city):
    source_lat, source_lng = CITY_COORDS.get(source_city, CITY_COORDS[CITY_OPTIONS[0]])
    dest_lat, dest_lng = CITY_COORDS.get(destination_city, CITY_COORDS[CITY_OPTIONS[1]])
    midpoint_lat = round((source_lat + dest_lat) / 2, 4)
    midpoint_lng = round((source_lng + dest_lng) / 2, 4)

    route_data = fetch_live_route(source_city, destination_city)
    weather_data = fetch_live_weather(midpoint_lat, midpoint_lng)

    distance_km = estimate_distance_km(source_city, destination_city)
    traffic_level = 2
    route_condition = 2
    eta_hours = calculate_eta(distance_km, traffic_level)
    baseline_route_hours = eta_hours

    if route_data is not None:
        distance_km = route_data["distance_km"]
        traffic_level = route_data["traffic_level"]
        route_condition = route_data["route_condition"]
        eta_hours = route_data["traffic_duration_hours"]
        baseline_route_hours = route_data["base_duration_hours"]

    weather_level = 1
    weather_detail = "live weather unavailable"
    if weather_data is not None:
        weather_level = weather_data["level"]
        weather_detail = weather_data["description"]

    if weather_level == 3:
        route_condition = max(route_condition, 3)
    elif weather_level == 2:
        route_condition = max(route_condition, 2)

    if route_data and weather_data:
        data_mode = "Live APIs"
        data_note = "Traffic-aware routing and weather were fetched automatically."
    elif route_data or weather_data:
        data_mode = "Partial Live"
        data_note = "Some live signals were available, and missing inputs were estimated safely."
    else:
        data_mode = "Estimated Fallback"
        data_note = "API keys are missing or the live lookup failed, so internal estimates were used."

    return {
        "distance_km": round(distance_km, 2),
        "traffic_level": traffic_level,
        "traffic_label": TRAFFIC_LABELS[traffic_level],
        "weather_level": weather_level,
        "weather_label": WEATHER_LABELS[weather_level],
        "weather_detail": weather_detail.title(),
        "route_condition": route_condition,
        "route_label": ROUTE_LABELS[route_condition],
        "eta_hours": round(eta_hours, 2),
        "baseline_route_hours": round(baseline_route_hours, 2),
        "data_mode": data_mode,
        "data_note": data_note,
    }


def build_prediction_explanation(
    distance,
    traffic,
    weather_input,
    route,
    hour,
    probability,
    eta,
    predicted_delivery_time,
):
    factors = []

    if traffic == 3:
        factors.append(
            {
                "title": "Heavy traffic corridor",
                "weight": 5,
                "detail": "High congestion is the strongest operational drag on this route.",
            }
        )
    elif traffic == 2:
        factors.append(
            {
                "title": "Moderate traffic build-up",
                "weight": 3,
                "detail": "Road density is likely to slow truck rotation and checkpoint movement.",
            }
        )

    if weather_input == 3:
        factors.append(
            {
                "title": "Storm exposure",
                "weight": 4,
                "detail": "Storm conditions typically reduce speed, visibility, and stop flexibility.",
            }
        )
    elif weather_input == 2:
        factors.append(
            {
                "title": "Rain-sensitive route",
                "weight": 2,
                "detail": "Wet weather can add slower handling, braking, and loading delays.",
            }
        )

    if route == 3:
        factors.append(
            {
                "title": "Poor route condition",
                "weight": 4,
                "detail": "Rough road quality increases travel instability and vehicle strain.",
            }
        )
    elif route == 2:
        factors.append(
            {
                "title": "Mixed route quality",
                "weight": 2,
                "detail": "Moderate road condition can create uneven pace across the trip.",
            }
        )

    if hour >= 18 or hour <= 5:
        factors.append(
            {
                "title": "Off-peak dispatch window",
                "weight": 3,
                "detail": "Night and late-evening departures usually face staffing and visibility constraints.",
            }
        )

    if distance >= 1200:
        factors.append(
            {
                "title": "Long-haul exposure",
                "weight": 3,
                "detail": "This shipment spans a long corridor, increasing compounding delay risk.",
            }
        )
    elif distance >= 700:
        factors.append(
            {
                "title": "Extended route length",
                "weight": 2,
                "detail": "A mid-to-long route leaves less recovery room if the trip slows early.",
            }
        )

    model_gap = max(0, predicted_delivery_time - eta)
    if model_gap >= 2.5:
        factors.append(
            {
                "title": "Predicted schedule overrun",
                "weight": 4,
                "detail": "The learned model expects materially more time than the baseline ETA.",
            }
        )
    elif model_gap >= 1.0:
        factors.append(
            {
                "title": "Tight recovery buffer",
                "weight": 2,
                "detail": "The trip has limited slack between baseline ETA and predicted arrival.",
            }
        )

    if not factors:
        factors.append(
            {
                "title": "Stable route profile",
                "weight": 1,
                "detail": "Inputs show relatively balanced operating conditions for this shipment.",
            }
        )

    factors.sort(key=lambda item: item["weight"], reverse=True)
    total_weight = sum(item["weight"] for item in factors) or 1

    explanation = []
    for item in factors[:3]:
        share = round((item["weight"] / total_weight) * 100)
        explanation.append(
            {
                "title": item["title"],
                "detail": item["detail"],
                "share": max(8, share),
            }
        )

    if probability >= 70:
        headline = "Critical intervention recommended"
    elif probability >= 45:
        headline = "Shipment needs active monitoring"
    else:
        headline = "Route is serviceable with light oversight"

    summary = (
        f"{headline}. Traffic is {TRAFFIC_LABELS.get(traffic, 'Unknown').lower()}, "
        f"weather is {WEATHER_LABELS.get(weather_input, 'Unknown').lower()}, and route quality is "
        f"{ROUTE_LABELS.get(route, 'Unknown').lower()}."
    )

    return summary, explanation


def build_recommendations(
    distance,
    traffic,
    weather_input,
    route,
    hour,
    probability,
    eta,
    predicted_delivery_time,
):
    actions = []

    if traffic >= 2:
        actions.append(
            "Reroute or shift departure by 1-2 hours to avoid the current congestion band."
        )

    if weather_input >= 2:
        actions.append(
            "Raise driver safety buffer and dispatch a weather-ready vehicle for this leg."
        )

    if route >= 2:
        actions.append(
            "Pre-approve an alternate corridor or maintenance stop before the truck enters the rough segment."
        )

    if hour >= 18 or hour <= 5:
        actions.append(
            "Alert the destination team early because off-hour arrivals often create unloading delays."
        )

    if distance >= 900:
        actions.append(
            "Lock a refuel checkpoint in advance so the long-haul leg does not lose time at ad hoc stops."
        )

    if probability >= 60:
        actions.append(
            "Move this shipment into the exception watchlist and notify the customer with a guarded ETA."
        )

    if predicted_delivery_time - eta >= 1.5:
        actions.append(
            f"Reset the promised arrival window closer to {predicted_delivery_time:.1f} hours to protect SLA trust."
        )

    if not actions:
        actions.append(
            "Keep the route as planned and monitor for live traffic or weather changes only."
        )

    return actions[:4]


def build_cost_impact(probability, distance, eta, predicted_delivery_time, predicted_fuel_cost):
    baseline_fuel_cost = (distance / 4.8) * 92 if distance > 0 else 0
    extra_fuel_cost = max(0, predicted_fuel_cost - baseline_fuel_cost)
    delay_hours = max(0, predicted_delivery_time - eta)
    delay_cost = (delay_hours * 650) + (probability * 11)
    total_exposure = extra_fuel_cost + delay_cost

    if probability >= 70 or delay_hours >= 3:
        sla_risk = "High"
    elif probability >= 45 or delay_hours >= 1.5:
        sla_risk = "Medium"
    else:
        sla_risk = "Low"

    return {
        "baseline_fuel_cost": round(baseline_fuel_cost, 2),
        "extra_fuel_cost": round(extra_fuel_cost, 2),
        "delay_hours": round(delay_hours, 2),
        "delay_cost": round(delay_cost, 2),
        "total_exposure": round(total_exposure, 2),
        "sla_risk": sla_risk,
    }


def build_arrival_projection(hour, predicted_delivery_time):
    now = datetime.now()
    departure_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if departure_time < now:
        departure_time += timedelta(days=1)

    arrival_time = departure_time + timedelta(hours=predicted_delivery_time)

    return {
        "departure_label": departure_time.strftime("%d %b %Y, %I:%M %p"),
        "arrival_label": arrival_time.strftime("%d %b %Y, %I:%M %p"),
        "travel_window": round(predicted_delivery_time, 2),
        "day_rollover": (arrival_time.date() - departure_time.date()).days,
    }


def build_drone_telemetry(tick):
    hubs = [
        {"id": "HUB-EAST", "name": "Kolkata Hub", "lat": 22.5726, "lng": 88.3639},
        {"id": "HUB-NORTH", "name": "Delhi Hub", "lat": 28.6139, "lng": 77.2090},
        {"id": "HUB-WEST", "name": "Mumbai Hub", "lat": 19.0760, "lng": 72.8777},
    ]

    drone_specs = [
        ("DR-101", "HUB-EAST", "HUB-NORTH", 74, 3.6),
        ("DR-202", "HUB-NORTH", "HUB-WEST", 69, 4.2),
        ("DR-303", "HUB-WEST", "HUB-EAST", 83, 3.2),
        ("DR-404", "HUB-EAST", "HUB-WEST", 77, 4.8),
    ]

    hub_map = {h["id"]: h for h in hubs}
    drones = []

    for i, (drone_id, start_hub, end_hub, battery_base, speed) in enumerate(drone_specs):
        source = hub_map[start_hub]
        target = hub_map[end_hub]

        progress = ((tick * (0.018 + (i * 0.006))) + (0.14 * i)) % 1.0
        arc = math.sin(progress * math.pi) * (0.9 + (0.18 * i))

        lat = source["lat"] + (target["lat"] - source["lat"]) * progress + (arc * 0.06)
        lng = source["lng"] + (target["lng"] - source["lng"]) * progress + (arc * 0.06)
        battery = max(22, int(battery_base - (progress * 52)))
        eta_minutes = max(5, int((1.0 - progress) * (55 - i * 6)))

        drones.append(
            {
                "id": drone_id,
                "lat": round(lat, 4),
                "lng": round(lng, 4),
                "battery": battery,
                "speed": speed,
                "from": start_hub,
                "to": end_hub,
                "eta_minutes": eta_minutes,
                "payload_kg": round(1.3 + (i * 0.6), 1),
            }
        )

    lanes = [
        {"from": "HUB-EAST", "to": "HUB-NORTH"},
        {"from": "HUB-NORTH", "to": "HUB-WEST"},
        {"from": "HUB-WEST", "to": "HUB-EAST"},
    ]

    return {"hubs": hubs, "drones": drones, "lanes": lanes}


def get_weather():
    temp = random.randint(20, 35)
    weather = random.choice(["Clear", "Rain", "Storm"])
    return temp, weather


def init_db(app):
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shipments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id TEXT,
            status TEXT,
            location TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY,
            password TEXT
        )
        """
    )

    # Ensure built-in admin is not stored as a user row (authentication is handled via config)
    cursor.execute("DELETE FROM users WHERE username=?", (app.config["ADMIN_USERNAME"],))

    # Seed default shipments if empty
    cursor.execute("SELECT COUNT(*) FROM shipments")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO shipments (shipment_id,status,location) VALUES (?,?,?)",
            [
                ("SHP102", "In Transit", "Kolkata"),
                ("SHP103", "Delayed", "Delhi"),
                ("SHP104", "Delivered", "Mumbai"),
            ],
        )

    # Seed a default user (for testing) if no users exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (username,password) VALUES (?,?)",
            ("user1", generate_password_hash("userpass")),
        )

    conn.commit()
    conn.close()


# -------------------------------
# Routes
# -------------------------------

@bp.route("/truck_location")
def truck_location():
    truck_routes = {
        "truck1": [(20.29, 85.82), (20.50, 85.30), (20.80, 84.90), (21.10, 84.30)],
        "truck2": [(21.00, 85.90), (21.40, 85.30), (21.90, 84.50), (22.20, 84.00)],
        "truck3": [(20.50, 84.80), (20.90, 84.20), (21.40, 83.70), (21.80, 83.20)],
        "truck4": [(21.30, 86.10), (21.70, 85.50), (22.00, 84.90), (22.50, 84.30)],
        "truck5": [(20.80, 85.50), (21.20, 84.90), (21.60, 84.30), (22.00, 83.80)],
    }

    # store index in session to persist between requests
    idx = session.get("truck_index", 0)
    locations = {}

    for truck, route in truck_routes.items():
        lat, lng = route[idx % len(route)]
        locations[truck] = {"lat": lat, "lng": lng}

    session["truck_index"] = idx + 1
    return jsonify(locations)


@bp.route("/analytics")
def analytics():
    total, delayed, active, success = get_dashboard_stats()
    return jsonify({"total": total, "delayed": delayed, "active": active, "success": success})


@bp.route("/drone_telemetry")
def drone_telemetry():
    if session.get("role") != "admin":
        return jsonify({"error": "unauthorized"}), 401

    tick = session.get("drone_tick", 0) + 1
    session["drone_tick"] = tick

    telemetry = build_drone_telemetry(tick)
    telemetry["tick"] = tick
    telemetry["summary"] = {
        "active_drones": len(telemetry["drones"]),
        "avg_battery": round(
            sum(drone["battery"] for drone in telemetry["drones"]) / len(telemetry["drones"]), 1
        ),
        "deliveries_per_hour": 16 + (tick % 7),
    }
    return jsonify(telemetry)


@bp.route("/ai_decisions")
def ai_decisions():
    if session.get("role") != "admin":
        return jsonify({"error": "unauthorized"}), 401

    tick = session.get("drone_tick", 0)
    telemetry = build_drone_telemetry(tick)
    shipments = get_shipments()

    delayed = sum(1 for s in shipments if s[1] == "Delayed")
    in_transit = sum(1 for s in shipments if s[1] == "In Transit")
    delivered = sum(1 for s in shipments if s[1] == "Delivered")
    low_battery_count = sum(1 for d in telemetry["drones"] if d["battery"] < 35)

    risk_score = min(
        100,
        int((delayed * 16) + (in_transit * 6) + (low_battery_count * 12) + ((tick % 5) * 4)),
    )

    strategy = "Speed Priority" if risk_score >= 55 else "Cost Optimized"
    if delayed >= in_transit and delayed > 0:
        strategy = "Delay Recovery"

    decisions = [
        {
            "title": "Dispatch Strategy",
            "action": strategy,
            "impact": "Balances SLA and battery risk across active routes.",
        },
        {
            "title": "Reroute Recommendation",
            "action": f"{max(1, delayed)} drone(s) shifted to delayed corridors",
            "impact": "Cuts expected late arrivals in the next 30 minutes.",
        },
        {
            "title": "Hub Load Balancing",
            "action": "Shift 2 pending pickups to HUB-WEST",
            "impact": "Prevents queue growth at HUB-EAST during demand spikes.",
        },
    ]

    return jsonify(
        {
            "risk_score": risk_score,
            "on_time_projection": max(55, min(99, 94 - delayed * 3 + delivered)),
            "decisions": decisions,
            "signals": {
                "delayed_shipments": delayed,
                "in_transit_shipments": in_transit,
                "low_battery_drones": low_battery_count,
            },
        }
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Admin login
        if (
            username == current_app.config["ADMIN_USERNAME"]
            and password == current_app.config["ADMIN_PASSWORD"]
        ):
            session["role"] = "admin"
            return redirect("/admin")

        # User login
        user = get_user(username)
        if user and check_password_hash(user[1], password):
            session["role"] = "user"
            session["username"] = username
            return redirect("/user")

        return render_template("login.html", error="Invalid credentials")

    # Support showing a creation message after successful signup
    created = request.args.get("created")
    return render_template("login.html", created=created)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("signup.html", error="Username and password are required.")

        if username == current_app.config["ADMIN_USERNAME"]:
            return render_template(
                "signup.html",
                error="That username is reserved. Please choose a different username.",
            )

        if get_user(username):
            return render_template(
                "signup.html", error="Username already exists. Please choose a different one."
            )

        conn = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username,password) VALUES (?,?)",
            (username, generate_password_hash(password)),
        )
        conn.commit()
        conn.close()

        # Redirect to login with a flag to show success
        return redirect("/login?created=1")

    return render_template("signup.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@bp.route("/")
def home():
    if "role" not in session:
        return redirect("/login")

    if session["role"] == "admin":
        return redirect("/admin")

    return redirect("/user")


@bp.route("/admin", defaults={"section": "dashboard"})
@bp.route("/admin/<section>")
def admin_dashboard(section="dashboard"):
    if session.get("role") != "admin":
        return redirect("/login")

    allowed_sections = {"dashboard", "prediction", "shipments", "analytics", "control", "admin"}
    if section not in allowed_sections:
        return redirect("/admin")

    shipments = get_shipments()
    users = get_users()

    temp, weather = get_weather()
    total, delayed, active, success = get_dashboard_stats()

    retrain_message = None
    if request.args.get("retrained"):
        retrain_message = "Model retrained successfully. Accuracy updated."

    return render_template(
        "index.html",
        shipments=shipments,
        users=users,
        username=session.get("username"),
        temperature=temp,
        weather=weather,
        total_shipments=total,
        delayed_shipments=delayed,
        active_trucks=active,
        success_rate=success,
        model_accuracy=current_app.config.get("MODEL_ACCURACY"),
        retrain_message=retrain_message,
        city_options=CITY_OPTIONS,
        selected_source_city=CITY_OPTIONS[0],
        selected_destination_city=CITY_OPTIONS[1],
        selected_distance=None,
        selected_traffic=None,
        selected_weather=None,
        selected_route=None,
        selected_hour=None,
        prediction_text=None,
        probability=None,
        eta=None,
        predicted_fuel_cost=None,
        predicted_delivery_time=None,
        arrival_projection=None,
        live_context=None,
        prediction_summary=None,
        prediction_explanation=[],
        recommended_actions=[],
        cost_impact=None,
        active_section=section,
        mapbox_token=current_app.config.get("MAPBOX_TOKEN"),
        mapbox_style=current_app.config.get("MAPBOX_STYLE"),
    )


@bp.route("/user")
def user_panel():
    if session.get("role") != "user":
        return redirect("/login")

    shipments = get_shipments()
    search_value = (request.args.get("shipment_id") or "").strip()
    searched_shipment = None
    search_message = None

    if search_value:
        searched_shipment = get_shipment_by_id(search_value)
        if searched_shipment is None:
            search_message = f"No shipment found for ID '{search_value}'."

    return render_template(
        "user.html",
        shipments=shipments,
        searched_shipment=searched_shipment,
        search_value=search_value,
        search_message=search_message,
    )


@bp.route("/predict", methods=["POST"])
def predict():
    if session.get("role") != "admin":
        return redirect("/login")

    hour = int(request.form.get("hour") or 0)
    source_city = request.form.get("source_city") or CITY_OPTIONS[0]
    destination_city = request.form.get("destination_city") or CITY_OPTIONS[1]
    if source_city == destination_city:
        destination_city = CITY_OPTIONS[1] if source_city != CITY_OPTIONS[1] else CITY_OPTIONS[0]

    live_context = build_live_context(source_city, destination_city)
    distance = live_context["distance_km"]
    traffic = live_context["traffic_level"]
    weather_input = live_context["weather_level"]
    route = live_context["route_condition"]
    eta = live_context["eta_hours"]
    features = build_feature_array(
        distance,
        traffic,
        weather_input,
        route,
        hour,
        source_city,
        destination_city,
    )

    # model is loaded by create_app and attached to current_app
    model = current_app.config.get("ML_MODEL")
    if model is None:
        return redirect("/admin")

    prediction = model.predict(features)
    probability = model.predict_proba(features)[0][1] * 100

    if prediction[0] == 1:
        result = f"⚠ High Risk of Delay ({probability:.2f}%)"
    else:
        result = f"✅ On Time Delivery ({100-probability:.2f}%)"

    fuel_model = current_app.config.get("FUEL_MODEL")
    if fuel_model is not None:
        predicted_fuel_cost = max(0, float(fuel_model.predict(features)[0]))
    else:
        predicted_fuel_cost = (distance / 4.8) * 92 * (1 + (traffic - 1) * 0.08)

    time_model = current_app.config.get("TIME_MODEL")
    if time_model is not None:
        predicted_delivery_time = max(0.5, float(time_model.predict(features)[0]))
    else:
        predicted_delivery_time = eta

    prediction_summary, prediction_explanation = build_prediction_explanation(
        distance,
        traffic,
        weather_input,
        route,
        hour,
        probability,
        eta,
        predicted_delivery_time,
    )
    recommended_actions = build_recommendations(
        distance,
        traffic,
        weather_input,
        route,
        hour,
        probability,
        eta,
        predicted_delivery_time,
    )
    cost_impact = build_cost_impact(
        probability,
        distance,
        eta,
        predicted_delivery_time,
        predicted_fuel_cost,
    )
    arrival_projection = build_arrival_projection(hour, predicted_delivery_time)

    shipments = get_shipments()
    users = get_users()
    temp, weather = get_weather()
    total, delayed, active, success = get_dashboard_stats()

    session["latest_prediction_report"] = {
        "generated_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "source_city": source_city,
        "destination_city": destination_city,
        "departure_hour": hour,
        "distance_km": round(distance, 2),
        "traffic_label": TRAFFIC_LABELS.get(traffic, "Unknown"),
        "weather_label": WEATHER_LABELS.get(weather_input, "Unknown"),
        "route_label": ROUTE_LABELS.get(route, "Unknown"),
        "delay_probability": round(probability, 2),
        "prediction_text": result,
        "predicted_fuel_cost": round(predicted_fuel_cost, 2),
        "predicted_delivery_time": round(predicted_delivery_time, 2),
        "arrival_time": arrival_projection["arrival_label"],
        "recommendations": recommended_actions,
        "summary": prediction_summary,
    }

    return render_template(
        "index.html",
        prediction_text=result,
        probability=round(probability, 2),
        eta=eta,
        city_options=CITY_OPTIONS,
        selected_source_city=source_city,
        selected_destination_city=destination_city,
        selected_distance=distance,
        selected_traffic=traffic,
        selected_weather=weather_input,
        selected_route=route,
        selected_hour=hour,
        predicted_fuel_cost=round(predicted_fuel_cost, 2),
        predicted_delivery_time=round(predicted_delivery_time, 2),
        arrival_projection=arrival_projection,
        live_context=live_context,
        prediction_summary=prediction_summary,
        prediction_explanation=prediction_explanation,
        recommended_actions=recommended_actions,
        cost_impact=cost_impact,
        shipments=shipments,
        users=users,
        temperature=temp,
        weather=weather,
        total_shipments=total,
        delayed_shipments=delayed,
        active_trucks=active,
        success_rate=success,
        model_accuracy=current_app.config.get("MODEL_ACCURACY"),
        retrain_message=None,
        username=session.get("username"),
        active_section="prediction",
        mapbox_token=current_app.config.get("MAPBOX_TOKEN"),
        mapbox_style=current_app.config.get("MAPBOX_STYLE"),
    )


@bp.route("/add_shipment", methods=["POST"])
def add_shipment():
    if session.get("role") != "admin":
        return redirect("/login")

    shipment_id = request.form.get("shipment_id")
    status = request.form.get("status")
    location = request.form.get("location")

    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO shipments (shipment_id,status,location) VALUES (?,?,?)",
        (shipment_id, status, location),
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


@bp.route("/add_user", methods=["POST"])
def add_user():
    if session.get("role") != "admin":
        return redirect("/login")

    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password or username == current_app.config["ADMIN_USERNAME"]:
        return redirect("/admin")

    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (username,password) VALUES (?,?)",
        (username, generate_password_hash(password)),
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


@bp.route("/retrain_model", methods=["POST"])
def retrain_model():
    if session.get("role") != "admin":
        return redirect("/login")

    # Retrain using the existing dataset
    try:
        import pandas as pd
        import pickle
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.metrics import mean_absolute_error
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score

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
            feature_cols = [
                "distance",
                "traffic",
                "weather",
                "route_condition",
                "departure_hour",
            ]

        X = data[feature_cols]
        y = data["delay"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        model = RandomForestClassifier(n_estimators=220, max_depth=12, random_state=42)
        model.fit(X_train, y_train)

        fuel_model = None
        if "fuel_cost" in data.columns:
            Xf_train, Xf_test, yf_train, yf_test = train_test_split(
                X, data["fuel_cost"], test_size=0.2, random_state=42
            )
            fuel_model = RandomForestRegressor(
                n_estimators=260, max_depth=14, random_state=42
            )
            fuel_model.fit(Xf_train, yf_train)
            _ = mean_absolute_error(yf_test, fuel_model.predict(Xf_test))

        time_model = None
        if "delivery_time_hours" in data.columns:
            Xt_train, Xt_test, yt_train, yt_test = train_test_split(
                X, data["delivery_time_hours"], test_size=0.2, random_state=42
            )
            time_model = RandomForestRegressor(
                n_estimators=260, max_depth=14, random_state=42
            )
            time_model.fit(Xt_train, yt_train)
            _ = mean_absolute_error(yt_test, time_model.predict(Xt_test))

        bundle = {
            "feature_cols": feature_cols,
            "delay_model": model,
            "fuel_model": fuel_model,
            "time_model": time_model,
        }
        pickle.dump(bundle, open("model_bundle.pkl", "wb"))
        pickle.dump(model, open("model.pkl", "wb"))

        # Update in-app model + accuracy
        current_app.config["ML_MODEL"] = model
        current_app.config["FUEL_MODEL"] = fuel_model
        current_app.config["TIME_MODEL"] = time_model
        current_app.config["FEATURE_COLS"] = feature_cols
        acc = accuracy_score(y_test, model.predict(X_test))
        current_app.config["MODEL_ACCURACY"] = acc
    except Exception:
        pass

    return redirect("/admin?retrained=1")


@bp.route("/delete_user/<username>")
def delete_user(username):
    if session.get("role") != "admin":
        return redirect("/login")

    if username == current_app.config["ADMIN_USERNAME"]:
        return redirect("/admin")

    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()

    return redirect("/admin")


@bp.route("/delete/<shipment_id>")
def delete_shipment(shipment_id):
    if session.get("role") != "admin":
        return redirect("/login")

    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM shipments WHERE shipment_id=?", (shipment_id,))
    conn.commit()
    conn.close()

    return redirect("/admin")


@bp.route("/export_shipments")
def export_shipments():
    if session.get("role") != "admin":
        return redirect("/login")

    shipments = get_shipments()

    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(["shipment_id", "status", "location"])
    writer.writerows(shipments)

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=shipments.csv"
    output.headers["Content-Type"] = "text/csv"

    return output


@bp.route("/export_summary_report")
def export_summary_report():
    if session.get("role") != "admin":
        return redirect("/login")

    total, delayed, active, success = get_dashboard_stats()
    temp, weather = get_weather()

    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(["metric", "value"])
    writer.writerow(["generated_at", datetime.now().strftime("%d %b %Y, %I:%M %p")])
    writer.writerow(["total_shipments", total])
    writer.writerow(["delayed_shipments", delayed])
    writer.writerow(["active_trucks", active])
    writer.writerow(["delivery_success_rate", success])
    writer.writerow(["current_temperature_c", temp])
    writer.writerow(["current_weather", weather])
    writer.writerow(["model_accuracy", current_app.config.get("MODEL_ACCURACY")])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=operations_summary.csv"
    output.headers["Content-Type"] = "text/csv"
    return output


@bp.route("/export_prediction_report")
def export_prediction_report():
    if session.get("role") != "admin":
        return redirect("/login")

    report = session.get("latest_prediction_report")
    if not report:
        return redirect("/admin/prediction")

    lines = [
        "AI Shipment Prediction Report",
        f"Generated: {report['generated_at']}",
        f"Route: {report['source_city']} -> {report['destination_city']}",
        f"Departure Hour: {report['departure_hour']}:00",
        f"Distance (km): {report['distance_km']}",
        f"Traffic: {report['traffic_label']}",
        f"Weather: {report['weather_label']}",
        f"Route Condition: {report['route_label']}",
        f"Prediction: {report['prediction_text']}",
        f"Delay Probability: {report['delay_probability']}%",
        f"Predicted Fuel Cost: Rs {report['predicted_fuel_cost']}",
        f"Predicted Delivery Time: {report['predicted_delivery_time']} hrs",
        f"Expected Arrival: {report['arrival_time']}",
        "",
        "AI Summary",
        report["summary"],
        "",
        "Recommended Actions",
    ]

    for index, action in enumerate(report["recommendations"], start=1):
        lines.append(f"{index}. {action}")

    output = make_response("\n".join(lines))
    output.headers["Content-Disposition"] = "attachment; filename=latest_prediction_report.txt"
    output.headers["Content-Type"] = "text/plain; charset=utf-8"
    return output


@bp.route("/upload_shipments", methods=["POST"])
def upload_shipments():
    if session.get("role") != "admin":
        return redirect("/login")

    if "file" not in request.files:
        return redirect("/admin")

    file = request.files["file"]
    if file.filename == "":
        return redirect("/admin")

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8"))
        reader = csv.DictReader(stream)
        rows = [(r.get("shipment_id"), r.get("status"), r.get("location")) for r in reader]

        conn = _get_db_connection()
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO shipments (shipment_id, status, location) VALUES (?, ?, ?)",
            [row for row in rows if row[0] and row[1] and row[2]],
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return redirect("/admin")
