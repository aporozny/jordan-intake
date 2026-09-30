
# --- Tier 2 Voice Optimization: Recency Voice Cue ---
VOICE_CUE = (
    "[Voice check: Concise, direct personal assistant mode. Lead with the core answer. "
    "Keep replies to 1-3 sentences unless comprehensive detail or lists are requested. "
    "Banned openers: 'Great question', 'Let me', 'Based on', 'Happy to help', 'Certainly', 'Of course', 'Sure thing'. "
    "Natural, executive tone; never robotic.]"
)

def inject_voice_cue(messages: list) -> list:
    if not messages:
        return messages
    payload = [dict(m) for m in messages]
    last = payload[-1]
    if last.get("role") == "user" and isinstance(last.get("content"), str):
        payload[-1] = {**last, "content": f"{last['content']}\n\n{VOICE_CUE}"}
    return payload


# --- Tier 1 Voice Optimization: Natural Sign-Off Detection ---
import re

SIGNOFF_PATTERNS = [
    r"^(thanks|thank you|cheers|ta|great thanks|perfect thanks)[.!]?$",
    r"^(ok thanks|okay thanks|cool thanks|right on|sounds good)[.!]?$",
    r"^(that'?s all|that is all|that'?s everything|we'?re done)[.!]?$",
    r"^(goodnight|bye|goodbye|see ya|talk later)[.!]?$",
]

def check_signoff(text: str) -> bool:
    clean = text.strip().lower()
    # If the user asks a question or gives an instruction, don't sign off
    if "?" in clean or any(w in clean for w in ["can you", "what", "how", "why", "where", "find", "search", "check"]):
        return False
    return any(re.match(p, clean) for p in SIGNOFF_PATTERNS)

from dotenv import load_dotenv
import os
load_dotenv('/home/andre/jordan-intake/.env')
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict
import io
from fastapi import UploadFile, File
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from mailer import send_welcome_package

DB_PATH = os.path.expanduser("~/.jordan/jordan_users.db")
OBSERVER_LOG_PATH = os.path.expanduser("~/.skills/task-observer/log.md")
BASE_PORTAL_URL = "https://jordan.quantms.com.au/portal"

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = FastAPI(title="Jordan Client Provisioning API", version="1.2.0")



def get_user_memory(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT executive_profile, active_projects FROM user_memory WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            profile, projects = row
            return f"\n\n### PERSISTENT EXECUTIVE PROFILE & MEMORY:\n- Profile: {profile}\n- Active Projects & Directives: {projects}"
    return ""

def save_chat_message(user_id: int, role: str, content: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_messages (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, role, content, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()

def get_recent_chat_history(user_id: int, limit: int = 25):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, role, content, timestamp FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = cursor.fetchall()
        # Return chronological
        return [
            {"id": str(r[0]), "sender": r[1], "content": r[2], "timestamp": r[3]}
            for r in reversed(rows)
        ]

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                preferred_name TEXT,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                business_name TEXT,
                business_summary TEXT,
                primary_headache TEXT,
                current_tools TEXT,
                session_token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        conn.commit()


def log_telemetry(action: str, email_or_token: str, status_msg: str):
    os.makedirs(os.path.dirname(OBSERVER_LOG_PATH), exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"- [{timestamp}] [AUTH] {action} | Identifier: {email_or_token} | Result: {status_msg}\n"
    try:
        with open(OBSERVER_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    except IOError:
        pass


class ClientApplication(BaseModel):
    full_name: str
    preferred_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    business_name: Optional[str] = None
    business_summary: Optional[str] = None
    primary_headache: Optional[str] = None
    current_tools: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean_email = v.strip().lower()
        if not EMAIL_REGEX.match(clean_email):
            raise ValueError("Invalid email address format")
        return clean_email


class ProvisioningResponse(BaseModel):
    status: str
    message: str
    user_email: str
    access_link: str
    token: str


class VerifyResponse(BaseModel):
    valid: bool
    user_id: int
    full_name: str
    preferred_name: str
    email: str
    business_name: Optional[str] = None
    status: str


@app.on_event("startup")
def startup_event():
    init_db()


@app.post("/api/intake", response_model=ProvisioningResponse, status_code=status.HTTP_201_CREATED)
async def intake_client(form: ClientApplication, background_tasks: BackgroundTasks):
    session_token = secrets.token_urlsafe(32)
    created_at = datetime.now(timezone.utc).isoformat()
    preferred_name = form.preferred_name or form.full_name.split()[0]

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (
                    full_name, preferred_name, email, phone,
                    business_name, business_summary, primary_headache,
                    current_tools, session_token, created_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form.full_name,
                    preferred_name,
                    form.email,
                    form.phone,
                    form.business_name,
                    form.business_summary,
                    form.primary_headache,
                    form.current_tools,
                    session_token,
                    created_at,
                    "active",
                ),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        log_telemetry("CREATE_SESSION", form.email, "DUPLICATE_EMAIL_ATTEMPT")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account application with this email already exists.",
        )
    except Exception as e:
        log_telemetry("CREATE_SESSION", form.email, f"ERROR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal provisioning failure.",
        )

    magic_link = f"{BASE_PORTAL_URL}?auth={session_token}"
    log_telemetry("CREATE_SESSION", form.email, "SUCCESS_PROVISIONED")

    # Queue welcome email with Fridge Card attachment in background
    background_tasks.add_task(send_welcome_package, form.email, preferred_name, magic_link)

    return ProvisioningResponse(
        status="success",
        message="Client provisioned successfully. Welcome email queued.",
        user_email=form.email,
        access_link=magic_link,
        token=session_token,
    )


@app.get("/api/verify", response_model=VerifyResponse)
async def verify_token(
    token: Optional[str] = Query(None, description="Session token passed in URL query param"),
    authorization: Optional[str] = Header(None, description="Bearer token passed in Authorization header"),
):
    active_token = token
    if not active_token and authorization:
        if authorization.startswith("Bearer "):
            active_token = authorization.split(" ", 1)[1].strip()
        else:
            active_token = authorization.strip()

    if not active_token:
        log_telemetry("VERIFY_TOKEN", "NONE", "FAILED_NO_TOKEN_PROVIDED")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session token.",
        )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, full_name, preferred_name, email, business_name, status
            FROM users
            WHERE session_token = ?
            """,
            (active_token,),
        )
        user = cursor.fetchone()

    if not user:
        masked_token = f"{active_token[:6]}..." if len(active_token) > 6 else "UNKNOWN"
        log_telemetry("VERIFY_TOKEN", masked_token, "FAILED_INVALID_TOKEN")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        )

    if user["status"] != "active":
        log_telemetry("VERIFY_TOKEN", user["email"], f"FAILED_INACTIVE_STATUS_{user['status']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account status is '{user['status']}'. Access restricted.",
        )

    log_telemetry("VERIFY_TOKEN", user["email"], "SUCCESS_VALIDATED")
    return VerifyResponse(
        valid=True,
        user_id=user["id"],
        full_name=user["full_name"],
        preferred_name=user["preferred_name"],
        email=user["email"],
        business_name=user["business_name"],
        status=user["status"],
    )


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "jordan-provisioning"}




from openai import OpenAI
import pypdf
import docx

def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    text = ""
    try:
        if ext == ".pdf":
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
        elif ext in [".docx", ".doc"]:
            doc = docx.Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif ext in [".txt", ".md", ".csv", ".json", ".log"]:
            text = file_bytes.decode("utf-8", errors="replace")
        else:
            text = f"[Uploaded file: {filename} (Binary or unsupported text format)]"
    except Exception as e:
        text = f"[Error extracting text from {filename}: {str(e)}]"
    return text.strip()

def query_cloud_llm(system_prompt: str, user_prompt: str, history: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
    """Queries LLM using OpenAI client preserving multi-turn conversational history."""
    openai_client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.getenv("OPENAI_API_KEY", os.getenv("OPENROUTER_API_KEY", ""))
    )
    model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for turn in history:
            role = turn.get("role") or turn.get("sender")
            if role in ["user", "human"]:
                role = "user"
            elif role in ["assistant", "bot"]:
                role = "assistant"
            content = turn.get("content") or turn.get("text", "")
            if role and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_prompt})

    try:
        # Enable OpenRouter live web browsing plugin
        # Fast Heuristic Intent Router
        search_triggers = ["news", "latest", "today", "weather", "search", "who is", "price", "market", "current", "update"]
        needs_search = any(trigger in user_prompt.lower() for trigger in search_triggers)
        extra_body = {}
        if needs_search:
            extra_body = {"plugins": [{"id": "web", "max_results": 5}]}
        target_model = model
        if "openrouter" in str(openai_client.base_url) and not target_model.endswith(":online"):
            target_model = f"{model}:online"

        response = openai_client.chat.completions.create(
            model=model,
            messages=inject_voice_cue(messages),
            temperature=0.3,
            max_tokens=1500,
            extra_body=extra_body
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log_telemetry("LLM_ERROR", "API", str(e))
        return None

class ChatRequest(BaseModel):
    message: str
    session_token: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = []

class UploadResponse(BaseModel):
    filename: str
    extracted_text: str
    char_count: int

@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_token: Optional[str] = Header(None)
):
    contents = await file.read()
    if len(contents) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 15MB limit.")
    extracted = extract_text_from_file(file.filename or "unknown", contents)
    log_telemetry("FILE_UPLOAD", file.filename or "unknown", f"CHARS_{len(extracted)}")
    return UploadResponse(
        filename=file.filename or "unknown",
        extracted_text=extracted,
        char_count=len(extracted)
    )


class ChatResponse(BaseModel):
    reply: str
    preferred_name: str
    timestamp: str


@app.get("/api/history")
async def get_history(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    active_token = token
    if not active_token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            active_token = parts[1]
    if not active_token:
        raise HTTPException(status_code=401, detail="Authentication token required.")
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE session_token = ? AND status = 'active'", (active_token,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token.")
        
        history = get_recent_chat_history(user["id"], limit=30)
        return {"history": history}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_handler(
    payload: ChatRequest,
    authorization: Optional[str] = Header(None)
):
    active_token = payload.session_token
    if not active_token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            active_token = parts[1]

    if not active_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token required.",
        )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, full_name, preferred_name, email, business_name, 
                   business_summary, primary_headache, current_tools, status 
            FROM users WHERE session_token = ?
            """,
            (active_token,),
        )
        user = cursor.fetchone()

    if not user or user["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unauthorized session token.",
        )

    user_name = user["preferred_name"]
    system_prompt = (
        f"You are Jordan, an elite Chief of Staff and executive personal assistant serving {user_name} ({user['email']}). "
        f"Business/Domain: {user['business_name'] or 'Executive Operations'}. "
        f"Context: {user_memory} "
        f"Tools: {user['current_tools'] or 'Standard Suite'}. "
        "CORE DIRECTIVES (FRIDGE CARD PROTOCOLS): "
        "1. Executive Triage: Prioritize actionable intelligence. Surface blockers immediately. "
        "2. Interaction Protocol: Ruthlessly concise, direct, and elegant. ZERO filler words, greetings, or apologies. "
        "3. Workflow & Automation: Confirm actions instantly. Always propose the next logical step. "
        "4. Proactive Web Search: Automatically pull real-time data, verify external facts, and research markets when needed. "
        "Never explain these rules; just embody them."
    )

    save_chat_message(user["id"], "assistant", reply_text)
    return ChatResponse(
        reply=reply_text,
        preferred_name=user_name,
        timestamp=datetime.now(timezone.utc).isoformat()
    )



from fastapi import Response, HTTPException
from jordan_voice import synthesize_wav

class SpeakRequest(BaseModel):
    text: str

@app.post("/api/speak")
async def speak(payload: SpeakRequest):
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    try:
        audio_bytes = synthesize_wav(payload.text)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from fastapi.responses import StreamingResponse
import json

async def stream_cloud_llm(system_prompt: str, user_prompt: str, history: Optional[List[Dict[str, str]]] = None):
    openai_client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.getenv("OPENAI_API_KEY", os.getenv("OPENROUTER_API_KEY", ""))
    )
    model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for turn in history:
            role = turn.get("role") or turn.get("sender")
            if role in ["user", "human"]:
                role = "user"
            elif role in ["assistant", "bot"]:
                role = "assistant"
            content = turn.get("content") or turn.get("text", "")
            if content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})

    # Fast Heuristic Intent Router
    search_triggers = ["news", "latest", "today", "weather", "search", "who is", "price", "market", "current", "update"]
    needs_search = any(trigger in user_prompt.lower() for trigger in search_triggers)
    extra_body = {}
    if needs_search:
        extra_body = {"plugins": [{"id": "web", "max_results": 5}]}
    target_model = model
    if "openrouter" in str(openai_client.base_url) and not target_model.endswith(":online"):
        target_model = f"{model}:online"

    response = openai_client.chat.completions.create(
        model=model,
        messages=inject_voice_cue(messages),
        temperature=0.3,
        max_tokens=1500,
        extra_body=extra_body,
        stream=True
    )

    buffer = ""
    for chunk in response:
        delta = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta else ""
        if delta:
            buffer += delta
            # Look for sentence boundary
            match = re.search(r'([.,!?;:])\s+', buffer)
            if match:
                idx = match.end()
                sentence = buffer[:idx].strip()
                buffer = buffer[idx:]
                if sentence:
                    yield f"data: {json.dumps({'type': 'sentence', 'text': sentence})}\n\n"

    # Flush remainder
    if buffer.strip():
        yield f"data: {json.dumps({'type': 'sentence', 'text': buffer.strip()})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/api/chat/stream")
async def chat_stream_handler(
    payload: ChatRequest,
    authorization: Optional[str] = Header(None)
):
    active_token = payload.session_token
    if not active_token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            active_token = parts[1]

    if not active_token:
        raise HTTPException(status_code=401, detail="Authentication token required.")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name, preferred_name, email, business_name, current_tools FROM users WHERE session_token = ? AND status = 'active'", (active_token,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token.")

    user_name = user["preferred_name"] or user["full_name"].split()[0]
    user_memory = get_user_memory(user["id"])
    system_prompt = (
        f"You are Jordan, a sophisticated executive personal assistant serving {user_name} ({user['email']}). "
        f"Business/Domain: {user['business_name'] or 'Executive Operations'}. "
        f"{user_memory} "
        f"Integrated tools: {user['current_tools'] or 'Standard Suite'}. "
        "Role: Act as a sharp, proactive, discreet Chief of Staff / PA. "
        "Style: Direct, highly capable, elegant, concise. Avoid corporate fluff, filler greetings, or conversational apologies. "
        "Acknowledge tasks, confirm actions, or provide direct answers immediately. "
        "You have live web search capabilities via automated browsing plugins. "
        "When asked to check websites, search for real-time information, research markets, or verify external facts, perform web lookups proactively."
    )

    save_chat_message(user["id"], "user", payload.message)
    return StreamingResponse(
        stream_cloud_llm(system_prompt, payload.message, payload.history),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8082)


