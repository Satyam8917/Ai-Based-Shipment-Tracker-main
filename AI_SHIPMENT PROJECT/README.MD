# AI Shipment Delay Predictor

A Flask-based shipment delay prediction dashboard with admin/user roles.

## Features
- Admin dashboard (add/remove users, manage shipments, run delay prediction)
- User dashboard (view shipments + live truck tracking)
- Simple ML model for delay prediction (loaded from `model.pkl`)
- Live route context using TomTom + OpenWeather to auto-fill traffic, weather, route condition, and distance
- SQLite storage (`shipments.db`)

## Quick Start

### 1) Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r Requirements.txt
```

### 2) Configure environment variables

Copy the example file and adjust values:

```bash
cp .env.example .env
```

For live prediction context, set:

- `TOMTOM_API_KEY` for traffic-aware routing and distance
- `OPENWEATHER_API_KEY` for live weather

If these are missing, the app still works, but prediction context falls back to internal estimates.

### 3) Run the app locally

```bash
python app.py
```

Open in browser:

```
http://localhost:5001
```

### 4) Run using Docker (optional)

```bash
docker build -t ai-shipment .
docker run -p 5001:5001 --env-file .env ai-shipment
```

or using docker-compose:

```bash
docker-compose up --build
```

### Default Admin Login

- **Username:** `admin`
- **Password:** `admin123`

### Creating Users

Log in as admin, then use the **User Management** section of the dashboard.

## Notes

- Passwords are stored hashed using Werkzeug.
- For production, replace the `SECRET_KEY` and never check it into source control.
