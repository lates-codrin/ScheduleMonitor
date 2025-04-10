# 📅 Schedule Monitor API

A FastAPI-based service that scrapes academic timetable data from HTML pages and exposes it via a simple RESTful API. This project fetches group schedules, tracks updates, and provides access to campus news and room info from [webfmi.vercel.app](https://webfmi.vercel.app/).

---

## 🚀 Features

- ✅ Scrapes and parses HTML tables into structured JSON
- 🔄 Automatically detects and reports timetable changes
- 📬 Fetches announcements/news
- 🏫 Maps room names to their locations
- 🧪 Fully interactive OpenAPI docs (Swagger UI)

---

## 📚 API Documentation

### 🧪 Swagger UI
Visit the interactive docs at:
http://localhost:8000/orar/docs || https://schedulemonitor.onrender.com/orar/docs


---

## 📦 Endpoints Overview

| Method | Path                | Description                          |
|--------|---------------------|--------------------------------------|
| `GET`  | `/`                 | Welcome message                      |
| `GET`  | `/rescan`           | Rescan all pages and update groups   |
| `GET`  | `/orar/{grupa}`     | Get timetable data for a group       |
| `GET`  | `/news`             | Get latest news/announcements        |
| `GET`  | `/rooms`            | Get room names and their locations   |

---

## 🛠️ Tech Stack

- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [Pandas](https://pandas.pydata.org/) - Tabular data handling
- [Uvicorn](https://www.uvicorn.org/) - ASGI server

---

## 📥 Installation

```bash
# Clone the repo
git clone https://github.com/lates-codrin/ScheduleMonitor.git
cd schedule-monitor-api

# Create a virtual environment and activate it
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

```

## 🧪 Run the App
```bash
uvicorn main:app --reload
```
Then open: http://localhost:8000/orar/docs

---
🤝 Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you’d like to change.
