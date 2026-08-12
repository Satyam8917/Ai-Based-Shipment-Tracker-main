import pandas as pd
import random

TOTAL_RECORDS = 15000
RANDOM_SEED = 42

random.seed(RANDOM_SEED)
data = []

CITIES = [
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

# Approximate baseline inter-city distances (km)
ROUTE_BASE_DISTANCE = {
    ("Mumbai", "Delhi"): 1420,
    ("Mumbai", "Kolkata"): 1960,
    ("Mumbai", "Bengaluru"): 980,
    ("Mumbai", "Hyderabad"): 710,
    ("Mumbai", "Chennai"): 1330,
    ("Mumbai", "Pune"): 150,
    ("Delhi", "Kolkata"): 1530,
    ("Delhi", "Bengaluru"): 2150,
    ("Delhi", "Hyderabad"): 1580,
    ("Delhi", "Chennai"): 2180,
    ("Delhi", "Pune"): 1470,
    ("Kolkata", "Bengaluru"): 1870,
    ("Kolkata", "Hyderabad"): 1500,
    ("Kolkata", "Chennai"): 1670,
    ("Kolkata", "Pune"): 2050,
    ("Bengaluru", "Hyderabad"): 575,
    ("Bengaluru", "Chennai"): 350,
    ("Bengaluru", "Pune"): 840,
    ("Hyderabad", "Chennai"): 630,
    ("Hyderabad", "Pune"): 560,
    ("Chennai", "Pune"): 1160,
}


def route_distance_km(source, destination):
    key = (source, destination)
    rev_key = (destination, source)
    baseline = ROUTE_BASE_DISTANCE.get(key) or ROUTE_BASE_DISTANCE.get(rev_key)
    if baseline is None:
        baseline = random.randint(250, 2200)
    # Add mild trip-to-trip variation
    return max(80, int(random.gauss(baseline, baseline * 0.07)))


city_to_id = {city: idx for idx, city in enumerate(CITIES)}

for _ in range(TOTAL_RECORDS):
    source_city = random.choice(CITIES)
    destination_city = random.choice([c for c in CITIES if c != source_city])

    distance = route_distance_km(source_city, destination_city)
    traffic = random.choices([1, 2, 3], weights=[0.25, 0.45, 0.30], k=1)[0]
    weather = random.choices([1, 2, 3], weights=[0.55, 0.30, 0.15], k=1)[0]
    route_condition = random.choices([1, 2, 3], weights=[0.40, 0.40, 0.20], k=1)[0]
    hour = random.randint(0, 23)

    score = 0

    if distance > 250:
        score += 1

    if traffic == 3:
        score += 1

    if weather == 3:
        score += 1

    if route_condition == 3:
        score += 1

    # Evening/night departures tend to be more delay-prone.
    if hour >= 18 or hour <= 5:
        score += 1

    # Higher scores are more likely to be delayed.
    delay_probability = min(0.92, 0.08 + (score * 0.18))
    delay = 1 if random.random() < delay_probability else 0

    # Fuel cost (synthetic): distance + traffic + weather + road condition impact.
    fuel_efficiency = random.uniform(3.8, 5.8)  # km/l for loaded truck
    diesel_price = random.uniform(89, 97)  # INR/l
    fuel_multiplier = 1.0 + (traffic - 1) * 0.06 + (weather - 1) * 0.04 + (route_condition - 1) * 0.05
    fuel_cost = (distance / fuel_efficiency) * diesel_price * fuel_multiplier
    fuel_cost += random.uniform(-350, 350)
    fuel_cost = round(max(1200, fuel_cost), 2)

    # Delivery time (hours): base speed adjusted by conditions + handling overhead.
    avg_speed = random.uniform(48, 62)
    if traffic == 2:
        avg_speed *= 0.82
    elif traffic == 3:
        avg_speed *= 0.64
    if weather == 2:
        avg_speed *= 0.9
    elif weather == 3:
        avg_speed *= 0.76
    if route_condition == 2:
        avg_speed *= 0.9
    elif route_condition == 3:
        avg_speed *= 0.78

    handling_hours = random.uniform(1.2, 5.5)
    if hour >= 18 or hour <= 5:
        handling_hours += random.uniform(0.4, 1.5)

    delivery_time_hours = round((distance / max(18, avg_speed)) + handling_hours, 2)

    data.append(
        [
            source_city,
            destination_city,
            city_to_id[source_city],
            city_to_id[destination_city],
            distance,
            traffic,
            weather,
            route_condition,
            hour,
            fuel_cost,
            delivery_time_hours,
            delay,
        ]
    )

df = pd.DataFrame(
    data,
    columns=[
        "source_city",
        "destination_city",
        "source_city_id",
        "destination_city_id",
        "distance",
        "traffic",
        "weather",
        "route_condition",
        "departure_hour",
        "fuel_cost",
        "delivery_time_hours",
        "delay",
    ],
)

# Write both names to avoid case-sensitivity mismatch across environments/files.
df.to_csv("shipment_data.csv", index=False)
df.to_csv("Shipment_data.csv", index=False)

print(f"Dataset generated: {len(df)} rows")
