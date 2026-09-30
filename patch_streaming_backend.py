filepath = "/home/andre/jordan-intake/intake_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

streaming_code = '''
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

    extra_body = {
        "plugins": [
            {
                "id": "web",
                "max_results": 5
            }
        ]
    }

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
            match = re.search(r'([.!?])\s+', buffer)
            if match:
                idx = match.end()
                sentence = buffer[:idx].strip()
                buffer = buffer[idx:]
                if sentence:
                    yield f"data: {json.dumps({'type': 'sentence', 'text': sentence})}\\\\n\\\\n"

    # Flush remainder
    if buffer.strip():
        yield f"data: {json.dumps({'type': 'sentence', 'text': buffer.strip()})}\\\\n\\\\n"
    yield f"data: {json.dumps({'type': 'done'})}\\\\n\\\\n"


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
'''

if "/api/chat/stream" not in code:
    code += "\n" + streaming_code
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    print("SUCCESS: Streaming endpoint /api/chat/stream added.")
else:
    print("Streaming endpoint already exists.")
