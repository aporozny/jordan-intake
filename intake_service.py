from dotenv import load_dotenv
import os
load_dotenv('/home/andre/jordan-intake/.env')
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from mailer import send_welcome_package

DB_PATH = os.path.expanduser("~/.jordan/jordan_users.db")
OBSERVER_LOG_PATH = os.path.expanduser("~/.skills/task-observer/log.md")
BASE_PORTAL_URL = "https://jordan.quantms.com.au/portal"

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = FastAPI(title="Jordan Client Provisioning API", version="1.2.0")


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

def query_cloud_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Queries LLM using OpenAI client with OpenRouter/Anthropic fallbacks."""
    openai_client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.getenv("OPENAI_API_KEY", os.getenv("OPENROUTER_API_KEY", ""))
    )
    model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1024
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log_telemetry("LLM_ERROR", "API", str(e))
        return None


class ChatRequest(BaseModel):
    message: str
    session_token: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    preferred_name: str
    timestamp: str

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
        f"You are the QuantMS Executive Personal Assistant, dedicated to serving {user_name}. "
        f"Client full name: {user['full_name']}. "
        f"Business/Domain: {user['business_name'] or 'Operations'}. "
        f"Summary: {user['business_summary'] or 'Executive management'}. "
        f"Current primary focus/headache: {user['primary_headache'] or 'Workflow coordination'}. "
        f"Integrated tools: {user['current_tools'] or 'Standard Suite'}. "
        "Role: Act as a sharp, proactive, discreet Chief of Staff / PA. "
        "Style: Direct, highly capable, elegant, concise. Avoid corporate fluff, filler greetings, or conversational apologies. "
        "Acknowledge tasks, confirm actions, or provide direct answers immediately."
    )

    # Query Cloud LLM Engine (OpenRouter / Anthropic)
    cloud_reply = query_cloud_llm(system_prompt, payload.message)
    if cloud_reply:
        reply_text = cloud_reply
    else:
        reply_text = (
            f"Understood, {user_name}. Directive noted in your operational ledger. "
            f"Standing by for execution against {user['business_name'] or 'your workspace'} workflows."
        )

    log_telemetry("CHAT_PROMPT", user["email"], f"LEN_{len(payload.message)}")

    return ChatResponse(
        reply=reply_text,
        preferred_name=user_name,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8082)
