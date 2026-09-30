import re

filepath = "/home/andre/jordan-intake/intake_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Add helper functions for DB memory retrieval and message persistence
helpers = '''
def get_user_memory(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT executive_profile, active_projects FROM user_memory WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            profile, projects = row
            return f"\\n\\n### PERSISTENT EXECUTIVE PROFILE & MEMORY:\\n- Profile: {profile}\\n- Active Projects & Directives: {projects}"
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
'''

if "def get_user_memory" not in content:
    content = content.replace("def init_db():", helpers + "\ndef init_db():")

# Add GET /api/history endpoint
history_endpoint = '''
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
'''

if "@app.get(\"/api/history\")" not in content:
    content = content.replace("@app.post(\"/api/chat\"", history_endpoint + "\n@app.post(\"/api/chat\"")

# Update chat_handler to inject user memory and save messages
# 1. Inject persistent profile into system prompt
old_sys_prompt_end = 'f"Operational Headache: {user[\'primary_headache\'] or \'None specified\'}\\n\\n"'
new_sys_prompt_end = 'f"Operational Headache: {user[\'primary_headache\'] or \'None specified\'}\\n" + get_user_memory(user[\'id\']) + "\\n\\n"'
content = content.replace(old_sys_prompt_end, new_sys_prompt_end)

# 2. Save user message before querying
old_query_call = "cloud_reply = query_cloud_llm(system_prompt, payload.message, payload.history)"
new_query_call = """# Save incoming user turn
    save_chat_message(user["id"], "user", payload.message)
    cloud_reply = query_cloud_llm(system_prompt, payload.message, payload.history)"""
content = content.replace(old_query_call, new_query_call)

# 3. Save assistant reply before returning
old_return = "return ChatResponse("
new_return = """save_chat_message(user["id"], "assistant", reply_text)
    return ChatResponse("""
content = content.replace(old_return, new_return)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Memory and history patch applied to intake_service.py.")
