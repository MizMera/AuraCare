# AuraCare

AuraCare is an advanced, AI-powered telemetry and monitoring platform designed specifically for nursing homes and assisted living facilities. Its primary purpose is to enhance the safety, health tracking, and overall well-being of residents while providing actionable insights to caregivers and peace of mind to their families.

## 🎯 Project Purpose

The core objective of AuraCare is to bridge the gap between continuous resident care and unobtrusive monitoring. By leveraging environmental sensors (such as cameras and microphones) strategically placed in facility zones, the platform intelligently gathers health metrics and detects critical incidents in real-time. This proactive approach allows staff to respond immediately to emergencies and helps track long-term health trends without requiring wearable devices.

## ✨ Key Features

- **Role-Based Portals**: Tailored interfaces and access levels for **Administrators**, **Caregivers**, and **Family** members.
- **Intelligent Health Tracking**: Continuous, background measurement of key health and behavioral indicators:
  - **Mobility tracking:** Gait Speed & Stride Length.
  - **Well-being tracking:** Social Score & Vocal Activity.
- **Automated Incident Detection**: Real-time alerts categorized by severity (Critical, High, Medium) for high-risk situations:
  - Falls & Cardiac events
  - Distress Cries & Aggression
  - Wandering & Unexpected Absences
- **Zone & Schedule Management**: Monitors expected resident locations based on daily schedules to detect anomalies (e.g., a resident missing from the dining hall during mealtime).
- **AI Gait Analysis**: Automatic detection of abnormal walking patterns using computer vision, with alerts triggered after consecutive abnormal sessions.

## 🤖 Gait Analysis Module

The gait analysis module uses **MediaPipe** and a trained **GradientBoosting** classifier to analyze walking patterns from corridor camera recordings.

### How it works
1. Caregiver uploads daily corridor recording via the dashboard
2. System automatically detects all residents in the video
3. Each resident's gait is analyzed (normal / abnormal)
4. Results and snapshots are saved to the database
5. Alerts are triggered if abnormal gait persists for multiple days

### Features
- **Multi-person detection** — up to 5 persons simultaneously
- **Automatic patient identification** — matches residents by body signature
- **Snapshot capture** — saves image at moment of abnormal detection
- **Automatic alerts** — notifies caregiver after consecutive abnormal sessions
- **Gait History page** — full history with charts, filters, and snapshots

### Setup (gait_model/)
```bash
cd gait_model
python -m venv gait_env
gait_env\Scripts\activate        # Windows
source gait_env/bin/activate     # Linux/Mac
pip install -r requirements.txt
```

### Required files in gait_model/data/
- `gait_model_local.pkl` — trained gait classifier
- `pose_landmarker.task` — MediaPipe pose model
  - Download: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task

### Patient Registration
Before analysis, register residents by running:
```bash
cd gait_model
gait_env\Scripts\activate
py realtime_gait_v4.py --mode video --path "path/to/video.mp4"
# Press R to register a person with their exact Django Resident name
```

## 🛠️ Technology Stack

### Backend
- **Django** (Python) — REST API, data modeling, secure authentication
- **Django REST Framework** — API endpoints
- **SimpleJWT** — JWT authentication
- **SQLite** — database (development)

### Frontend
- **React + Vite** — modern web application
- **Recharts** — health data visualization
- **Lucide Icons** — UI icons
- **Axios** — API communication

### AI / Gait Model
- **MediaPipe** — pose detection and body landmark extraction
- **OpenCV** — video processing
- **scikit-learn** — GradientBoosting classifier
- **NumPy / SciPy** — feature extraction

## 🚀 Getting Started

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 3. Seed database with test data
```bash
cd backend
py seed_db.py
```

### 4. Default test accounts
| Role | Email | Password |
|------|-------|----------|
| Caregiver | caregiver@auracare.com | caregiver2026 |
| Family | family1@auracare.com | familypassword! |
| Admin | admin@auracare.com | admin |

## 📁 Project Structure

```
AuraCare/
├── backend/                  # Django REST API
│   ├── core/
│   │   ├── models.py         # Data models (Resident, GaitObservation, Incident...)
│   │   ├── views.py          # API endpoints
│   │   └── urls.py           # URL routing
│   └── requirements.txt
│
├── frontend/                 # React application
│   └── src/
│       └── pages/
│           ├── Dashboard.jsx      # Caregiver & Family dashboards
│           ├── GaitHistory.jsx    # Gait analysis history
│           └── UploadVideo.jsx    # Upload corridor recordings
│
└── gait_model/               # AI Gait Analysis module
    ├── realtime_gait_v4.py   # Main pipeline
    ├── requirements.txt
    └── data/
        ├── gait_model_local.pkl
        └── pose_landmarker.task
```

## 🔗 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login/` | POST | User authentication |
| `/api/mobile/dashboard/` | GET | Caregiver dashboard data |
| `/api/gait/ingest/` | POST | Receive gait analysis results |
| `/api/gait/history/<id>/` | GET | Gait history for a resident |
| `/api/gait/all/` | GET | All residents gait history |
| `/api/gait/analyze/` | POST | Upload video for analysis |

---
*AuraCare - Empowering caregivers and connecting families through intelligent, compassionate care.*
