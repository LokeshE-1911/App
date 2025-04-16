# ✅ Unified FastAPI Backend: Roleplay API with Three Endpoints

import os
import csv
import json
import time
from typing import Literal
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai

# Load API key and configure Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

# FastAPI App Init
app = FastAPI()
chat_history = []
product_data = []
role_scripts = {"seller": [], "buyer": []}
session_scores = {}  # Dictionary to store scores per session

# ========================
# Auto Load Data from Local Files
# ========================
def load_local_product_data():
    global product_data
    try:
        if os.path.exists("products.json"):
            with open("products.json", "r") as f:
                product_data = json.load(f)
        elif os.path.exists("products.csv"):
            with open("products.csv", "r") as f:
                reader = csv.DictReader(f)
                product_data = [row for row in reader]
    except Exception as e:
        print(f"Error loading product data: {e}")


def load_local_scripts():
    global role_scripts
    for role in ["seller", "buyer"]:
        path = f"{role}_script.txt"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    role_scripts[role] = f.read().strip().split("\n")
            except Exception as e:
                print(f"Error loading {role} script: {e}")

# Call once during startup
load_local_product_data()
load_local_scripts()

# ========================
# Detect Stage from Prompt
# ========================
def detect_conversation_stage(prompt, role):
    stage_prompt = (
        f"You are a role-play assistant in a {role} scenario. Based on the following input, identify the stage:\n"
        f"Options: opening, discovery, presentation, objection_handling, closing, follow_up, general\n"
        f"Input: \"{prompt}\"\n"
        f"Return only the stage name."
    )
    try:
        response = model.generate_content(stage_prompt)
        detected = response.text.strip().lower()
        return detected if detected in ["opening", "discovery", "presentation", "objection_handling", "closing", "follow_up", "general"] else "general"
    except:
        return "general"

# ========================
# Update Score for Stage
# ========================
def update_stage_score(stage, session_id):
    if session_id in session_scores and stage in session_scores[session_id]:
        session_scores[session_id][stage] += 1

# ========================
# Generate Chat Response
# ========================
def generate_response(prompt, stage, role, session_id):
    if not product_data:
        load_local_product_data()

    if stage == "auto":
        stage = detect_conversation_stage(prompt, role)

    update_stage_score(stage, session_id)

    context = f"You are a {role}. You are in the {stage} stage of the role-play."
    products_text = "\n\n".join([
        f"- {p.get('name', 'Unknown')} (${p.get('price', 'N/A')})\n  {p.get('description', '')}" for p in product_data[:5]
    ]) or "No product data."

    script_section = "\n\nScript:\n" + "\n".join(role_scripts[role]) if role_scripts[role] else ""

    full_prompt = (
        f"{context}\n\nProducts:\n{products_text}{script_section}\n\nUser: {prompt}\nRespond naturally."
    )

    try:
        chat_history.append({"role": "user", "parts": [full_prompt]})
        response = model.generate_content(chat_history)
        chat_history.append({"role": "model", "parts": [response.text]})
        return response.text
    except Exception as e:
        return f"❌ Response error: {str(e)}"

# ========================
# /start - Create New Session
# ========================
@app.get("/start")
def start_session():
    session_id = str(uuid4())
    session_scores[session_id] = {
        "opening": 0,
        "discovery": 0,
        "presentation": 0,
        "objection_handling": 0,
        "closing": 0,
        "follow_up": 0,
        "general": 0
    }
    return {"session_id": session_id}

# ========================
# /chat - Handle User Prompt
# ========================
class ChatInput(BaseModel):
    prompt: str
    role: Literal["seller", "buyer"]
    session_id: str
    stage: str = "auto"

@app.post("/chat")
def chat_handler(data: ChatInput):
    if data.session_id not in session_scores:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    response = generate_response(data.prompt, data.stage, data.role, data.session_id)
    return {
        "session_id": data.session_id,
        "response": response,
        "scores": session_scores[data.session_id]
    }

# ========================
# /scores - Get Score Breakdown
# ========================
@app.get("/scores")
def get_scores(session_id: str):
    if session_id not in session_scores:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    return {
        "session_id": session_id,
        "scores": session_scores[session_id]
    }

# ========================
# Root Route
# ========================
@app.get("/")
def root():
    return {"message": "✅ Roleplay API is live. Use /start, /chat, /scores."}