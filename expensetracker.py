# expensetracker.py
"""
Voice Expense Tracker — Unified Version
Includes: Flask backend + Voice assistant + SMS/Gmail import + Auto shutdown
"""

import os, re, json, time, threading, signal, sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import psutil

load_dotenv()

# ========== CONFIG ==========
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voice_expense.db")
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Kolkata")
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")

# ========== DEPENDENCIES ==========
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import dateparser

try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    GMAIL_AVAILABLE = True
except Exception:
    GMAIL_AVAILABLE = False

try:
    import speech_recognition as sr
    from gtts import gTTS
    import playsound
    AUDIO_AVAILABLE = True
except Exception:
    AUDIO_AVAILABLE = False

# ========== DATABASE ==========
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    event_ts = Column(DateTime, default=datetime.utcnow)
    amount_minor = Column(Integer)
    currency = Column(String(10), default="INR")
    description = Column(String(255))
    category = Column(String(50), default="Other")
    convo_id = Column(String(128), index=True, default="")
    source = Column(String(50), default="voice")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class MonthlyRollup(Base):
    __tablename__ = "monthly_rollups"
    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    year_month = Column(String(6))
    totals_by_category = Column(JSON, default={})
    total_amount_minor = Column(Integer, default=0)
    top_items = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'year_month', name='u_user_month'),)

Base.metadata.create_all(bind=engine)

# ========== HELPERS ==========
def log(*args):
    print(datetime.now().strftime("[%H:%M:%S]"), *args)

def kill_all_processes():
    """Kill Flask, Streamlit, and this process."""
    print("🛑 Shutting down all components...")
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'])
            if any(word in cmdline for word in ['streamlit', 'flask', 'run']):
                proc.terminate()
        except Exception:
            pass
    psutil.Process(os.getpid()).terminate()
    os._exit(0)

# ========== NLP PARSER ==========
CATEGORIES = {
    "Food": ["coffee","dinner","lunch","breakfast","restaurant","snack","meal","cafe","canteen"],
    "Subscription": ["netflix","spotify","prime","membership","youtube"],
    "Travel": ["cab","taxi","uber","ola","bus","train","flight","airport"],
    "Groceries": ["grocery","market","vegetables","milk","bread","supermarket"],
    "Health": ["medicine","doctor","hospital","clinic","pharmacy","gym"],
    "Utilities": ["electricity","water","internet","wifi","bill","mobile","phone"],
    "Shopping": ["clothes","shoes","mall","shopping"],
    "Entertainment": ["movie","game","party","concert"],
    "Education": ["book","course","class","tuition","stationery"]
}

def extract_amount(text):
    t = text.lower()
    m = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', t)
    return int(float(m.group(1).replace(',', ''))*100) if m else 0

def extract_description(text):
    text = re.sub(r'₹|\d+|rs|rupees|inr', '', text, flags=re.I)
    text = re.sub(r'[^\w\s]', '', text).strip()
    return text or "Unknown"

def classify_category(text):
    for c, kws in CATEGORIES.items():
        if any(k in text.lower() for k in kws):
            return c
    return "Other"

def parse_expense(text):
    amt = extract_amount(text)
    desc = extract_description(text)
    cat = classify_category(desc)
    return {"amount_minor": amt, "description": desc, "category": cat, "event_ts": datetime.utcnow()}

# ========== DATABASE OPS ==========
def save_transaction(payload, user_id, source="voice"):
    session = SessionLocal()
    try:
        t = Transaction(
            id=f"txn_{int(time.time()*1000)}",
            user_id=user_id,
            amount_minor=payload['amount_minor'],
            currency="INR",
            description=payload['description'],
            category=payload['category'],
            event_ts=payload['event_ts'],
            source=source,
        )
        session.add(t)
        session.commit()
        log("✅ Saved:", payload)
        return {"status": "saved"}
    except Exception as e:
        session.rollback()
        log("Error saving:", e)
        return {"status": "error", "error": str(e)}
    finally:
        session.close()

def compute_monthly_rollup(user_id, year_month=None):
    session = SessionLocal()
    try:
        if not year_month:
            year_month = datetime.utcnow().strftime("%Y%m")
        txs = session.query(Transaction).filter(Transaction.user_id==user_id).all()
        totals = {}
        for tx in txs:
            totals[tx.category] = totals.get(tx.category, 0) + tx.amount_minor
        total = sum(totals.values())
        top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:3]
        r = MonthlyRollup(
            id=f"roll_{user_id}_{year_month}", user_id=user_id, year_month=year_month,
            totals_by_category=totals, total_amount_minor=total, top_items=top
        )
        session.merge(r)
        session.commit()
        return {"total_minor": total, "top_items": top}
    finally:
        session.close()

# ========== SPEECH ==========
def speech_to_text_console(prompt="Speak: "):
    if AUDIO_AVAILABLE:
        try:
            r = sr.Recognizer()
            with sr.Microphone() as source:
                print(prompt)
                audio = r.listen(source, timeout=5)
            return r.recognize_google(audio)
        except Exception as e:
            log("STT error:", e)
    return input(prompt)

def text_to_speech_console(text):
    print("Assistant:", text)
    if AUDIO_AVAILABLE:
        try:
            tts = gTTS(text=text, lang='en')
            tmp = f"tts_{int(time.time())}.mp3"
            tts.save(tmp)
            playsound.playsound(tmp)
            os.remove(tmp)
        except Exception as e:
            log("TTS error:", e)

# ========== VOICE ASSISTANT ==========
def run_voice_to_voice(user_id="demo_user"):
    text_to_speech_console("Hello Mohona! I'm ready. Say your expense or ask for a summary.")
    while True:
        spoken = speech_to_text_console("🎤 Speak now (say 'exit' to stop): ")
        if not spoken:
            text_to_speech_console("Didn't catch that, please repeat.")
            continue
        lower = spoken.lower()

        if any(x in lower for x in ["exit", "stop", "quit", "bye"]):
            text_to_speech_console("All systems closed. Have a great day, Mohona!")
            time.sleep(2)
            kill_all_processes()

        if any(x in lower for x in ["summary", "spent", "total", "month"]):
            roll = compute_monthly_rollup(user_id)
            total = roll.get("total_minor", 0) / 100.0
            top = roll.get("top_items", [])
            top_cat = top[0][0] if top else "None"
            msg = f"You've spent ₹{total:.2f} so far. Top category: {top_cat}."
            text_to_speech_console(msg)
            continue

        parsed = parse_expense(spoken)
        if parsed['amount_minor'] == 0:
            text_to_speech_console("Couldn't detect amount, please repeat.")
            continue
        confirm = f"Save ₹{parsed['amount_minor']/100:.2f} to {parsed['category']} for {parsed['description']}?"
        text_to_speech_console(confirm)
        ans = input("Confirm? (y/n): ").lower().strip()
        if ans.startswith("y"):
            save_transaction(parsed, user_id)
            text_to_speech_console("Saved successfully.")
        else:
            text_to_speech_console("Okay, not saved.")

# ========== FLASK BACKEND ==========
app = Flask("voice_expense")
@app.route("/api/log", methods=["POST"])
def api_log():
    d = request.get_json(force=True)
    text = d.get("text", "")
    user = d.get("user_id", "demo_user")
    parsed = parse_expense(text)
    res = save_transaction(parsed, user)
    return jsonify(res)

@app.route("/api/summary")
def api_summary():
    user = request.args.get("user_id", "demo_user")
    roll = compute_monthly_rollup(user)
    return jsonify(roll)

# ========== MAIN ==========
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--runserver", action="store_true")
    parser.add_argument("--voice2voice", action="store_true")
    args = parser.parse_args()

    if args.runserver:
        app.run(debug=True)
    elif args.voice2voice:
        run_voice_to_voice()
    else:
        print("Use --runserver or --voice2voice")

