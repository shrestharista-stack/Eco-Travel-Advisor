import streamlit as st
import requests
import pandas as pd
import os
from datetime import datetime

RASA_URL = "http://localhost:5005/webhooks/rest/webhook"
LOG_FILE = "chat_logs.csv"


def log_interaction(user_msg, bot_msg):
    # save the conversation to a csv file for the analytics panel
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = pd.DataFrame([[timestamp, user_msg, bot_msg]], columns=["Timestamp", "User", "Bot"])
    if not os.path.isfile(LOG_FILE):
        row.to_csv(LOG_FILE, index=False)
    else:
        row.to_csv(LOG_FILE, mode="a", header=False, index=False)


def send_to_rasa(message):
    # sender ID links every message to the same rasa conversation tracker
    # without this rasa treats every message as a brand new conversation
    body = {"sender": st.session_state.session_id, "message": message}
    resp = requests.post(RASA_URL, json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()


def process_response(rasa_data, user_message):
    text = ""
    buttons = []
    for item in rasa_data:
        if "text" in item:
            text = text + item["text"] + "\n\n"
        if "buttons" in item:
            buttons.extend(item["buttons"])

    if text == "" and len(buttons) == 0:
        text = "I am listening but didn't quite catch that."

    # store text AND buttons together in the message
    # buttons need to live in session_state so they are re-rendered on every page load
    st.session_state.messages.append({
        "role": "assistant",
        "content": text.strip(),
        "buttons": buttons,
    })
    log_interaction(user_message, text.strip())


#page setup
st.set_page_config(page_title="EcoTravel Advisor", layout="wide")

st.title("🌏 Welcome to Eco Travel Advisor")

# give this browser session a stable ID so rasa tracks the conversation correctly
if "session_id" not in st.session_state:
    st.session_state.session_id = "user_" + str(abs(id(st.session_state)))

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---- render chat history ----
# everything is rendered from session_state so buttons persist across rerenders
# quick-reply buttons are only shown under the last assistant message
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

    is_last = (i == len(st.session_state.messages) - 1)
    if msg["role"] == "assistant" and msg.get("buttons") and is_last:
        cols = st.columns(len(msg["buttons"]))
        for col, btn in zip(cols, msg["buttons"]):
            with col:
                if st.button(btn["title"], key="qr_" + str(i) + "_" + btn["payload"]):
                    # add the button label as a user message in the chat
                    st.session_state.messages.append({
                        "role": "user", "content": btn["title"], "buttons": []
                    })
                    try:
                        # send the intent payload to rasa e.g. /ask_city_break
                        rasa_data = send_to_rasa(btn["payload"])
                        process_response(rasa_data, btn["title"])
                    except Exception as e:
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "Connection error: " + str(e),
                            "buttons": [],
                        })
                    st.rerun()

# ---- text input ----
if prompt := st.chat_input("How can I help you today?"):
    st.session_state.messages.append({"role": "user", "content": prompt, "buttons": []})
    try:
        rasa_data = send_to_rasa(prompt)
        process_response(rasa_data, prompt)
    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Connection error: " + str(e),
            "buttons": [],
        })
    st.rerun()
