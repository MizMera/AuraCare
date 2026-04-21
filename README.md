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

## Model Integration

- The `models/modelayoub` pipeline is integrated as a separate, launchable workflow.
- It stays isolated from the existing detection modules and runs through its own backend adapter.
- Backend endpoints:
  - `POST /api/models/modelayoub/launch/`
  - `GET /api/models/modelayoub/status/`
  - `GET /api/models/modelayoub/artifacts/`
- Its outputs remain in `models/modelayoub/tracking_results/` and are surfaced to the dashboard through JSON summaries and artifact listings.

## 🛠️ Technology Stack

- **Backend Architecture**: Built with Django (Python) for robust data modeling and secure API management.
- **Frontend Interface**: A modern, responsive web application built with React, Vite, Recharts (for dynamic health data visualization), and Lucide Icons.

---
*AuraCare - Empowering caregivers and connecting families through intelligent, compassionate care.*
