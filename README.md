# 🧠 HealthWise – AI Health Assistant Web App

HealthWise is a full-stack Flask-based web application that acts as a dual-mode AI health assistant for both **physical** and **mental health**. It leverages Google Gemini API, personalized insights, push notifications, and interactive modules to help users monitor their health holistically.

---

## 🔧 Features

### ✅ General Features
- 🔐 User Authentication and Role-based Admin Access
- 🌍 Timezone-aware Sessions
- 🧾 User History and Settings Panel
- 🛡️ Secure session handling and CSRF protection

### 🧠 Mental Health Mode
- 🧘 Guided Meditations, Relaxation Tools, Zen Garden, and Games
- 📝 Daily Journaling with Mood Tracking and Sentiment Analysis
- 💬 "MindWell" Chatbot – a reflective, CBT-based support bot powered by Gemini
- 🔔 Smart Notifications for appointments and medication reminders

### 🏥 Physical Health Mode
- 🩺 Symptom Checker using AI analysis
- 📋 Health Metrics Analyzer (BMI, Blood Pressure, Sugar, Cholesterol)
- 🥗 AI-Generated Diet Plans
- 🏃 Exercise Logger with MET-based calorie estimation
- 💬 Health Assistant Chatbot for general health queries
- 📆 Appointment & Medication Manager
- 📊 Health Dashboard with weight/exercise/mood charts

---

## 🧠 Powered By

- **Backend:** Flask, SQLite
- **AI:** Google Gemini API (`gemini-1.5-flash-latest`)
- **Push Notifications:** WebPush with VAPID keys
- **Front-end:** HTML, CSS (custom), Bootstrap
- **Env Management:** python-dotenv

---

## 🗂️ Project Structure

```
.
├── app.py
├── templates/
├── static/
├── database.py
├── service-worker.js
├── .env
├── requirements.txt
└── README.md

```
---

## 🚀 Getting Started

### 1. Clone the Repo

```bash
git clone https://github.com/yourusername/healthwise-ai-assistant.git
cd healthwise-ai-assistant
````

### 2. Setup Python Environment

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 3. Configure `.env`

Create a `.env` file with the following:

```env
GEMINI_API_KEY=your_gemini_api_key
VAPID_PUBLIC_KEY=your_vapid_public_key
VAPID_PRIVATE_KEY=your_vapid_private_key
```

### 4. Run the App

```bash
python app.py
```

Visit `http://127.0.0.1:5000` in your browser.

---

## 🧪 Test Push Notifications

After logging in, visit `/send-push-test` (must be logged in and have a push subscription saved).

---


## 📜 License

MIT License

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change or improve.

---

## 📩 Contact

Made with ❤️ by \[Your Name]
Email: [adarshai5770@gmail.com](mailto:adarshai5770@gmail.com)

```
