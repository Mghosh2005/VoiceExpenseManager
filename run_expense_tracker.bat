@echo off
title Voice Expense Tracker Launcher
echo ============================================
echo     🎙️ Voice Expense Tracker Launcher
echo ============================================

echo [1/3] Starting Flask backend...
start cmd /k "python expensetracker.py --runserver"

timeout /t 3 >nul
echo [2/3] Starting Streamlit dashboard...
start cmd /k "streamlit run dashboard.py"

timeout /t 3 >nul
echo [3/3] Starting Voice Assistant...
start cmd /k "python expensetracker.py --voice2voice"

echo ============================================
echo Flask: http://127.0.0.1:5000
echo Dashboard: http://localhost:8501
echo Voice assistant active (say 'exit' to close all)
echo ============================================
pause

