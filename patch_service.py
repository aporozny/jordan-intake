import sys
import os

filepath = "/home/andre/jordan-intake/intake_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update imports
if "from typing import Optional" in content:
    content = content.replace(
        "from typing import Optional",
        "from typing import Optional, List, Dict\nimport io\nfrom fastapi import UploadFile, File"
    )

# 2. Add document extraction helper and replace query_cloud_llm + ChatRequest + chat_handler
target_anchor = "from openai import OpenAI"
if target_anchor in content:
    replacement = '''from openai import OpenAI
import pypdf
import docx

def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    text = ""
    try:
        if ext == ".pdf":
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                text += (page.extract_text() or "") + "\\n"
        elif ext in [".docx", ".doc"]:
            doc = docx.Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                text += para.text + "\\n"
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
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=1500
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
'''
    # We replace from 'from openai import OpenAI' down to the original 'class ChatRequest' definition
    idx_start = content.find("from openai import OpenAI")
    idx_end = content.find("class ChatResponse(BaseModel):")
    if idx_start != -1 and idx_end != -1:
        content = content[:idx_start] + replacement + "\n\n" + content[idx_end:]

# Update the call inside chat_handler:
content = content.replace(
    "cloud_reply = query_cloud_llm(system_prompt, payload.message)",
    "cloud_reply = query_cloud_llm(system_prompt, payload.message, payload.history)"
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied successfully.")
