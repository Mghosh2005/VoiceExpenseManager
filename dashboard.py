# dashboard.py
import sqlite3, pandas as pd, streamlit as st, time
from datetime import datetime

DB_PATH = "voice_expense.db"

def get_transactions():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM transactions ORDER BY event_ts DESC", conn)
    conn.close()
    return df

def get_rollups():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM monthly_rollups ORDER BY year_month DESC", conn)
    conn.close()
    return df

st.set_page_config(page_title="Voice Expense Tracker", page_icon="💰", layout="wide")
st.title("🎙️ Voice Expense Tracker Dashboard")

st.sidebar.header("Filters")
user_filter = st.sidebar.text_input("User ID", value="demo_user")
refresh_sec = st.sidebar.slider("Auto-refresh interval (seconds)", 5, 60, 10)
placeholder = st.empty()
countdown = st.sidebar.empty()

while True:
    with placeholder.container():
        df = get_transactions()
        if df.empty:
            st.warning("No transactions found yet.")
        else:
            df['amount'] = df['amount_minor'] / 100.0
            df = df[df['user_id'] == user_filter]
            st.dataframe(df[['event_ts', 'description', 'category', 'amount']], use_container_width=True)

            st.subheader("📊 Spending by Category")
            cat = df.groupby('category')['amount'].sum()
            st.bar_chart(cat)

            st.subheader("🥧 Expense Distribution")
            st.plotly_chart({
                "data": [{"labels": cat.index, "values": cat.values, "type": "pie", "hole": 0.4}],
                "layout": {"title": "Spending Breakdown"}
            })

            st.subheader("📈 Monthly Spending Trend")
            df['month'] = pd.to_datetime(df['event_ts']).dt.to_period('M').astype(str)
            monthly = df.groupby('month')['amount'].sum()
            st.line_chart(monthly)

        roll = get_rollups()
        if not roll.empty:
            roll['total_amount'] = roll['total_amount_minor'] / 100.0
            st.dataframe(roll[['user_id','year_month','total_amount']], use_container_width=True)
    for i in range(refresh_sec, 0, -1):
        countdown.markdown(f"🔄 Refreshing in {i}s...")
        time.sleep(1)
    st.rerun()

