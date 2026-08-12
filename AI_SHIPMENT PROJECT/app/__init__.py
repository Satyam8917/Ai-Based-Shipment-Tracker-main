import os

from dotenv import load_dotenv
from flask import Flask


def create_app(test_config=None):
    """Create and configure the Flask application."""

    # Load environment variables from .env
    load_dotenv()

    app = Flask(
        __name__,
        instance_relative_config=False,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
    )

    # Configuration
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "change-me"),
        ADMIN_USERNAME=os.getenv("ADMIN_USERNAME", "admin"),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", "admin123"),
        DATABASE_PATH=os.getenv("DATABASE_PATH", "shipments.db"),
        OPENWEATHER_API_KEY=os.getenv("OPENWEATHER_API_KEY", ""),
        CITY=os.getenv("CITY", "Bhubaneswar"),
        TOMTOM_API_KEY=os.getenv("TOMTOM_API_KEY", os.getenv("MAPBOX_TOKEN", "")),
        MAPBOX_TOKEN=os.getenv("MAPBOX_TOKEN", ""),
        MAPBOX_STYLE=os.getenv("MAPBOX_STYLE", "mapbox://styles/mapbox/light-v11"),
    )

    if test_config is not None:
        app.config.update(test_config)

    # Load ML model bundle (optional)
    try:
        import pickle

        bundle = pickle.load(open("model_bundle.pkl", "rb"))
        app.config["ML_MODEL"] = bundle.get("delay_model")
        app.config["FUEL_MODEL"] = bundle.get("fuel_model")
        app.config["TIME_MODEL"] = bundle.get("time_model")
        app.config["FEATURE_COLS"] = bundle.get(
            "feature_cols",
            ["distance", "traffic", "weather", "route_condition", "departure_hour"],
        )
    except Exception:
        # Backward compatibility with single delay model only.
        try:
            import pickle

            app.config["ML_MODEL"] = pickle.load(open("model.pkl", "rb"))
        except Exception:
            app.config["ML_MODEL"] = None
        app.config["FUEL_MODEL"] = None
        app.config["TIME_MODEL"] = None
        app.config["FEATURE_COLS"] = [
            "distance",
            "traffic",
            "weather",
            "route_condition",
            "departure_hour",
        ]

    # Estimate model accuracy (if model exists and dataset is available)
    try:
        if app.config["ML_MODEL"] is not None:
            import pandas as pd
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score

            data = pd.read_csv("shipment_data.csv")
            feature_cols = app.config.get(
                "FEATURE_COLS",
                ["distance", "traffic", "weather", "route_condition", "departure_hour"],
            )
            valid_cols = [col for col in feature_cols if col in data.columns]
            X = data[valid_cols]
            y = data["delay"]

            _, X_test, _, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            pred = app.config["ML_MODEL"].predict(X_test)
            app.config["MODEL_ACCURACY"] = accuracy_score(y_test, pred)
        else:
            app.config["MODEL_ACCURACY"] = None
    except Exception:
        app.config["MODEL_ACCURACY"] = None

    # Import and register routes
    from . import routes

    app.register_blueprint(routes.bp)

    # Initialize database
    routes.init_db(app)

    return app
