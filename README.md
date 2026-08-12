# 🚚 AI Shipment Delay Predictor

A powerful Flask-based web application that predicts shipment delays using machine learning and real-time contextual data from TomTom and OpenWeather APIs.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-2.0%2B-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 📋 Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Docker Deployment](#-docker-deployment)
- [Project Structure](#-project-structure)
- [API Integration](#-api-integration)
- [Database](#-database)
- [Machine Learning Model](#-machine-learning-model)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

### Admin Dashboard
- 👤 User management (add/remove users)
- 📦 Shipment management interface
- 🤖 Run delay predictions on shipments
- 📊 View prediction history and analytics

### User Dashboard
- 📋 View assigned shipments
- 📍 Live truck tracking
- ⚠️ View predicted delays
- 🗺️ Interactive route visualization

### Intelligence Features
- 🚗 **Traffic-Aware Routing** - Real-time traffic data via TomTom API
- 🌤️ **Weather Integration** - Current weather conditions via OpenWeather API
- 📐 **Distance Calculation** - Accurate route distance computation
- 🔄 **Automatic Context Population** - Auto-fills prediction features from APIs
- 🎯 **ML-Powered Predictions** - Random Forest classifier for delay prediction

### Technical Features
- 🔐 Role-based access control (Admin/User)
- 💾 SQLite database storage
- 📱 Responsive web interface
- 🐳 Docker & Docker Compose support
- 🔧 Environment-based configuration

## 🛠️ Tech Stack

- **Backend:** Flask, Python 3.8+
- **Database:** SQLite
- **ML:** Scikit-learn (Random Forest)
- **Data Processing:** Pandas, NumPy
- **Frontend:** HTML5, CSS3, JavaScript
- **APIs:** TomTom (routing), OpenWeather (weather)
- **Deployment:** Docker, Docker Compose

## 📦 Prerequisites

- Python 3.8 or higher
- pip or conda package manager
- Git
- Docker & Docker Compose (optional, for containerized deployment)
- TomTom API key (optional, for live traffic data)
- OpenWeather API key (optional, for live weather data)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/AI-Shipment-Delay-Predictor.git
cd AI_SHIPMENT\ PROJECT
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r Requirements.txt
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# TomTom API
TOMTOM_API_KEY=your_tomtom_api_key_here

# OpenWeather API
OPENWEATHER_API_KEY=your_openweather_api_key_here

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your_secret_key_here
```

**Note:** If API keys are not configured, the app will still function with estimated fallback values.

## 🎯 Usage

### Running Locally

```bash
python app.py
```

Open your browser and navigate to:

```
http://localhost:5001
```

### Default Credentials (Update in Production)

- **Admin Account:** admin / admin123
- **Test User:** user / user123

### Workflow

1. **Login** with admin or user credentials
2. **Admin:** Manage users, add shipments, and run predictions
3. **User:** View assigned shipments and tracking information
4. **View Results:** Check predicted delays and context data

## 🐳 Docker Deployment

### Using Docker Compose

```bash
docker-compose up --build
```

### Build Docker Image

```bash
docker build -t shipment-predictor:latest .
```

### Run Container

```bash
docker run -p 5001:5001 --env-file .env shipment-predictor:latest
```

## 📁 Project Structure

```
AI_SHIPMENT PROJECT/
├── app.py                    # Flask application entry point
├── database.py              # Database initialization and models
├── model.py                 # ML model training script
├── train_model.py           # Model training pipeline
├── generate_dataset.py      # Synthetic data generation
├── Shipment_data.csv        # Training dataset
├── Requirements.txt         # Python dependencies
├── Dockerfile              # Docker configuration
├── docker-compose.yml      # Docker Compose configuration
├── README.MD               # Original project documentation
├── .env.example            # Environment variables template
│
├── app/
│   ├── __init__.py         # Flask app factory
│   └── routes.py           # Application routes and logic
│
├── templates/              # HTML templates
│   ├── index.html         # Home page
│   ├── login.html         # Login page
│   ├── signup.html        # Registration page
│   └── user.html          # User dashboard
│
└── static/                # Static assets
    ├── style.css          # CSS styling
    └── test.py            # Testing utilities
```

## 🔌 API Integration

### TomTom API

Used for:
- Real-time traffic data
- Route distance calculation
- Traffic flow information

Request example:
```python
# Automatic via the application
# No manual API calls needed
```

### OpenWeather API

Used for:
- Current weather conditions
- Temperature and precipitation
- Weather-based delay factors

## 💾 Database

### SQLite Database (`shipments.db`)

**Tables:**
- `users` - User accounts and roles
- `shipments` - Shipment records
- `predictions` - Delay predictions and results

### Schema

```sql
-- Simplified schema
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT  -- 'admin' or 'user'
);

CREATE TABLE shipments (
    id INTEGER PRIMARY KEY,
    origin TEXT,
    destination TEXT,
    distance FLOAT,
    departure_time TIMESTAMP,
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE predictions (
    id INTEGER PRIMARY KEY,
    shipment_id INTEGER,
    predicted_delay BOOLEAN,
    confidence FLOAT,
    created_at TIMESTAMP,
    FOREIGN KEY (shipment_id) REFERENCES shipments(id)
);
```

## 🤖 Machine Learning Model

### Model Details

- **Algorithm:** Random Forest Classifier
- **Training Data:** Historical shipment data
- **Features:** 5 input variables
  - `distance` - Route distance in km
  - `traffic` - Traffic level (0-100)
  - `weather` - Weather condition code
  - `route_condition` - Road condition (0-100)
  - `departure_hour` - Hour of departure (0-23)

### Output

- **Binary Classification:** 
  - `0` - On-time delivery
  - `1` - Delayed delivery

### Training

To retrain the model with new data:

```bash
# Generate new dataset (optional)
python generate_dataset.py

# Train model
python train_model.py

# Model will be saved as model.pkl
```

### Model Performance

The model is loaded from `model.pkl` and provides real-time predictions based on current contextual data.

## 🔐 Security Considerations

- **Production:** Change default credentials immediately
- **Environment Variables:** Never commit `.env` files
- **HTTPS:** Use HTTPS in production
- **API Keys:** Rotate API keys regularly
- **Input Validation:** All inputs are validated on backend

## 📊 Future Enhancements

- [ ] Real-time notification system
- [ ] Advanced analytics dashboard
- [ ] Model performance metrics
- [ ] Integration with more APIs (weather forecast, traffic prediction)
- [ ] Batch prediction support
- [ ] API endpoint for external integrations
- [ ] Unit and integration tests
- [ ] CI/CD pipeline

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For issues and questions, please open an issue on the GitHub repository.

## 🙏 Acknowledgments

- Scikit-learn for the ML framework
- Flask for the web framework
- TomTom and OpenWeather for API services

---

**Last Updated:** March 2026

Made with ❤️ for smart shipment management
