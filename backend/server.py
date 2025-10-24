# =========================================================
# Imports & Setup
# =========================================================
from fastapi import FastAPI, Depends, HTTPException, Header, Request, File, UploadFile, Form
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import os
import requests
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
from uuid import UUID
from supabase import create_client, Client
import io
import base64
from PIL import Image
import tempfile
from groq import Groq

# For text-to-speech
from gtts import gTTS

# =========================================================
# Environment & Config
# =========================================================
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials missing (SUPABASE_URL / SUPABASE_KEY)")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")

JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GENAI_MODEL = "gemini-flash-latest"
GENAI_VISION_MODEL = "gemini-1.5-flash"

GOOGLE_ANDROID_CLIENT_ID = os.getenv("GOOGLE_ANDROID_CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI_ANDROID", "http://127.0.0.1:8000/auth/callback")

client = Groq(api_key=os.getenv("GROQ_API"))

# Google Generative AI init
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(GENAI_MODEL)
    vision_model = genai.GenerativeModel(GENAI_MODEL)
else:
    model = None
    vision_model = None

# =========================================================
# FastAPI App Init
# =========================================================
app = FastAPI()
MAX_RECENT_MESSAGES = int(os.getenv("MAX_RECENT_MESSAGES", "10"))

# =========================================================
# Helpers (Supabase, JWT, Common Functions)
# =========================================================
def check_resp(resp, raise_on_missing: bool = True):
    """Validate a supabase-py execute() response object and return data."""
    if resp is None:
        if raise_on_missing:
            raise HTTPException(status_code=500, detail="No response from Supabase (None).")
        return None
    if not hasattr(resp, "data"):
        if raise_on_missing:
            raise HTTPException(status_code=500, detail="Invalid response from Supabase.")
        return None
    return resp.data

def encode_jwt(payload: dict) -> str:
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def create_jwt_token(user_id: int, email: str, role: str):
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRY_MINUTES),
        "iat": datetime.utcnow()
    }
    return encode_jwt(payload)

def decode_jwt_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# =========================================================
# Dependencies (Auth Middleware)
# =========================================================
def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = parts[1]
    payload = decode_jwt_token(token)

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    resp = supabase.table("users").select("*").eq("id", int(user_id_str)).maybe_single().execute()
    data = check_resp(resp, raise_on_missing=False)
    if not data:
        raise HTTPException(status_code=401, detail="User not found")
    return data

# =========================================================
# Pydantic Models
# =========================================================
class NewMessage(BaseModel):
    session_id: Optional[UUID] = None
    message: str

class GoogleSignInPayload(BaseModel):
    id_token: str

# =========================================================
# Audio Transcription Helper (Whisper)
# =========================================================
def transcribe_audio_whisper(audio_bytes: bytes) -> str:
    """
    Transcribe audio using Groq Whisper model.
    """
    try:
        # Save audio to a temporary WAV file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio.write(audio_bytes)
            temp_audio_path = temp_audio.name

        # Call Groq Whisper model
        with open(temp_audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3"
            )

        # Clean up
        os.unlink(temp_audio_path)

        # Return transcription text
        return transcription.text

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq Whisper transcription failed: {str(e)}")

# =========================================================
# Text-to-Speech Helper
# =========================================================
def text_to_speech(text: str) -> bytes:
    """
    Convert text to speech using gTTS
    """
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        return audio_fp.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text-to-speech failed: {str(e)}")

# =========================================================
# Image Analysis Helper
# =========================================================
def analyze_image_with_gemini(image_bytes: bytes, prompt: str = None) -> str:
    """
    Analyze image using Gemini Vision API
    Returns short diagnosis/classification
    """
    if not vision_model:
        raise HTTPException(status_code=500, detail="Vision model not configured")
    
    try:
        # Convert bytes to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Default prompt for plant disease detection
        if not prompt:
            prompt = """Analyze this plant image and provide ONLY a brief diagnosis in 3-5 words.
            If it's a disease, name the disease. If it's healthy, say 'Healthy Plant'.
            Do not provide explanations, just the diagnosis."""
        
        response = vision_model.generate_content([prompt, image])
        diagnosis = response.text.strip()
        
        return diagnosis
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")

def get_detailed_explanation(diagnosis: str) -> str:
    """
    Get detailed explanation for the diagnosis using regular Gemini
    """
    if not model:
        return diagnosis
    
    try:
        prompt = f"""Given this plant diagnosis: "{diagnosis}"
        
        Provide a helpful explanation that includes:
        1. What this condition means
        2. Common causes
        3. Recommended treatments or actions
        
        Keep it concise and farmer-friendly (2-3 paragraphs)."""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception:
        return diagnosis

# =========================================================
# Auth Routes
# =========================================================
@app.post("/auth/google")
def auth_google(payload: GoogleSignInPayload):
    # 1. Verify the token with Google
    verify_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={payload.id_token}"
    google_resp = requests.get(verify_url)
    if google_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Invalid Google ID token")

    google_data = google_resp.json()
    email = google_data.get("email")
    name = google_data.get("name") or email
    if not email:
        raise HTTPException(status_code=400, detail="Google account missing email")

    # 2. Check if user exists in Supabase, else create
    check_user_resp = supabase.table("users").select("*").eq("email", email).maybe_single().execute()
    existing = check_resp(check_user_resp, raise_on_missing=False)
    if not existing:
        insert_resp = supabase.table("users").insert({
            "name": name, "email": email, "role": "user"
        }).execute()
        inserted = check_resp(insert_resp)
        if not inserted:
            raise HTTPException(status_code=500, detail="Failed to create user")
        user_data = inserted[0]
    else:
        user_data = existing

    # 3. Create JWT for the app
    jwt_token = create_jwt_token(
        user_data["id"], 
        user_data["email"], 
        user_data.get("role", "user")
    )

    return JSONResponse({
        "message": f"Welcome, {user_data.get('name')}",
        "jwt_token": jwt_token,
        "user": user_data
    })

# =========================================================
# Session Routes
# =========================================================

@app.get("/")
def get_env_vars():
    return "App is Running Fine"

@app.get("/sessions")
def list_sessions(user=Depends(get_current_user)):
    resp = supabase.table("sessions").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    data = check_resp(resp, raise_on_missing=False)
    return data or []

@app.get("/messages/{session_id}")
def get_messages(session_id: UUID, user=Depends(get_current_user)):
    session_resp = supabase.table("sessions").select("*").eq("id", str(session_id)).maybe_single().execute()
    session = check_resp(session_resp, raise_on_missing=False)
    if not session or session.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not your session")
    messages_resp = supabase.table("messages").select("*").eq("session_id", str(session_id)).order("timestamp").execute()
    messages = check_resp(messages_resp, raise_on_missing=False)
    return messages or []

# =========================================================
# Voice Transcription Route
# =========================================================
@app.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """
    Transcribe audio file to text using Whisper
    """
    audio_bytes = await audio.read()
    transcription = transcribe_audio_whisper(audio_bytes)
    return {"transcription": transcription}

# =========================================================
# Text-to-Speech Route
# =========================================================
@app.post("/tts")
def generate_speech(
    text: str = Form(...),
    user=Depends(get_current_user)
):
    """
    Convert text to speech
    """
    audio_bytes = text_to_speech(text)
    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "attachment; filename=speech.mp3"}
    )

# =========================================================
# Image Analysis Route
# =========================================================
@app.post("/analyze_image")
async def analyze_image(
    image: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    additional_question: Optional[str] = Form(None),
    user=Depends(get_current_user)
):
    """
    Analyze image and return diagnosis + detailed explanation
    """
    image_bytes = await image.read()
    
    # Get short diagnosis
    try:
        diagnosis = analyze_image_with_gemini(image_bytes)
    except Exception as e:
        print("Image analysis failed:", e)
        raise HTTPException(status_code=500, detail="Image analysis failed")

    
    # If there's an additional question, incorporate it
    if additional_question:
        prompt = f"""Based on this image analysis: "{diagnosis}"
        
        User's question: {additional_question}
        
        Provide a helpful response."""
        
        if model:
            try:
                response = model.generate_content(prompt)
                detailed_response = response.text.strip()
            except:
                detailed_response = get_detailed_explanation(diagnosis)
        else:
            detailed_response = get_detailed_explanation(diagnosis)
    else:
        # Get detailed explanation
        detailed_response = get_detailed_explanation(diagnosis)
    
    return {
        "diagnosis": diagnosis,
        "explanation": detailed_response,
        "session_id": session_id
    }

# =========================================================
# Message & Bot Reply Route (Enhanced)
# =========================================================
@app.post("/message/add")
async def add_message(
    session_id: Optional[str] = Form(None),
    message: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    user=Depends(get_current_user)
):
    """
    Add a message with support for text, audio, or image input
    Returns text response and optional audio response
    """
    
    # Handle audio input
    if audio:
        audio_bytes = await audio.read()
        message = transcribe_audio_whisper(audio_bytes)
    
    # Handle image input
    if image:
        image_bytes = await image.read()
        diagnosis = analyze_image_with_gemini(image_bytes)
        
        # If there's also a text message, treat it as a follow-up question
        if message:
            detailed_response = f"Image Analysis: {diagnosis}\n\n"
            prompt = f"""Based on this image diagnosis: "{diagnosis}"
            
            User's question: {message}
            
            Provide a helpful, concise response."""
            
            if model:
                try:
                    response = model.generate_content(prompt)
                    detailed_response += response.text.strip()
                except:
                    detailed_response += get_detailed_explanation(diagnosis)
            else:
                detailed_response += get_detailed_explanation(diagnosis)
            
            message = f"[Image uploaded] {message}"
            bot_reply = detailed_response
        else:
            message = "[Image uploaded]"
            bot_reply = get_detailed_explanation(diagnosis)
    
    if not message:
        raise HTTPException(status_code=400, detail="No message, audio, or image provided")
    
    # --- Session Handling ---
    session_id_uuid = UUID(session_id) if session_id else None
    new_session_created = False
    session_data = None

    if not session_id_uuid:
        new_session_created = True
        title = message[:40] if message else "New Chat"

        if model and not image:  # Don't generate title for image messages
            try:
                title_prompt = f"Give a short and clear 3–5 word title for this new conversation:\n\nUser: {message}"
                title_resp = model.generate_content(title_prompt)
                title = title_resp.text.strip()
            except Exception:
                pass

        session_insert_resp = supabase.table("sessions").insert({
            "user_id": user["id"],
            "user_email": user["email"],
            "title": title,
            "summary": ""
        }).execute()

        inserted = check_resp(session_insert_resp)
        if not inserted:
            raise HTTPException(status_code=500, detail="Failed to create session")
        session_id_uuid = inserted[0]["id"]
        session_data = inserted[0]

    else:
        session_resp = (
            supabase.table("sessions")
            .select("user_id, summary")
            .eq("id", str(session_id_uuid))
            .maybe_single()
            .execute()
        )
        session_data = check_resp(session_resp, raise_on_missing=False)
        if not session_data or session_data.get("user_id") != user["id"]:
            raise HTTPException(status_code=403, detail="Not your session")

    # --- Save User Message ---
    supabase.table("messages").insert({
        "session_id": str(session_id_uuid),
        "sender": "user",
        "message": message
    }).execute()

    # --- Generate Bot Reply (if not already generated from image) ---
    if not image:
        # Prepare conversation history
        messages_resp = (
            supabase.table("messages")
            .select("*")
            .eq("session_id", str(session_id_uuid))
            .order("timestamp", desc=True)
            .limit(MAX_RECENT_MESSAGES)
            .execute()
        )
        recent_messages = check_resp(messages_resp, raise_on_missing=False) or []
        recent_messages = list(reversed(recent_messages))

        SYSTEM_PROMPT = """You are a friendly and helpful agriculture AI assistant.
- Be concise but clear.
- Do not prefix your answers with "Bot:" or "AI:".
- Respond naturally, like a chat conversation.
- Focus on agricultural advice, farming tips, and crop management.
- If asked something unclear, politely ask for clarification.
"""

        history_text = "\n".join(
            [("User" if m["sender"] == "user" else "Assistant") + ": " + m["message"]
             for m in recent_messages]
        )

        prompt = SYSTEM_PROMPT + "\n\nConversation so far:\n" + history_text + \
                 f"\nAssistant:"

        bot_reply = f"[local fallback reply] You said: {message}"
        if model:
            try:
                bot_reply = model.generate_content(prompt).text.strip()

                if bot_reply.lower().startswith("assistant:"):
                    bot_reply = bot_reply.split(":", 1)[1].strip()

            except Exception as e:
                print(f"Gemini API call failed: {e}")

    # --- Save Bot Reply ---
    supabase.table("messages").insert({
        "session_id": str(session_id_uuid),
        "sender": "bot",
        "message": bot_reply
    }).execute()

    # --- Generate audio response if audio input was provided ---
    audio_response = None
    if audio:
        try:
            audio_bytes = text_to_speech(bot_reply)
            audio_response = base64.b64encode(audio_bytes).decode('utf-8')
        except:
            pass  # If TTS fails, just return text

    return {
        "session_id": str(session_id_uuid),
        "reply": bot_reply,
        "audio_reply": audio_response,  # Base64 encoded audio
        "new_session": new_session_created
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860)