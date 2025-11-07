# VoiceExpenseManager\
# 🎙️ Voice-to-Voice Expense Tracker

A smart expense tracker you can **talk to** — it listens to your voice, saves expenses automatically, and shows analytics in a live dashboard.

---

## 🚀 Features
✅ Voice-to-voice interaction (speak → parses → confirms → responds)  
✅ Smart NLP for category & amount detection  
✅ Real-time Streamlit dashboard  
✅ Flask API backend  
✅ Auto-refreshing charts  
✅ Voice-triggered shutdown (“exit” / “stop”)  
✅ SQLite persistence  
✅ One-click launcher (`run_expense_tracker.bat`)

---

## 🧩 Tech Stack
- Python 3.10+
- Flask + SQLAlchemy (backend)
- SpeechRecognition + gTTS (voice)
- Streamlit + Plotly (visuals)
- SQLite (local storage)
- psutil (process control)

---

## ⚙️ Installation

cd VoiceExpenseTracker
pip install -r requirements.txt
Just double-click:

run_expense_tracker.bat


Or manually:

python expensetracker.py --runserver
streamlit run dashboard.py
python expensetracker.py --voice2voice

Access in your browser:
👉 http://localhost:8501

You’ll see:
Recent transactions
Bar chart by category
Pie chart of distribution
Monthly spending trends
