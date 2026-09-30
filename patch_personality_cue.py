filepath = "/home/andre/jordan-intake/intake_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

cue_block = '''
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
        payload[-1] = {**last, "content": f"{last['content']}\\n\\n{VOICE_CUE}"}
    return payload
'''

if "def inject_voice_cue" not in code:
    code = cue_block + "\n" + code

old_call = "messages=messages,"
new_call = "messages=inject_voice_cue(messages),"

if old_call in code and "inject_voice_cue(messages)" not in code:
    code = code.replace(old_call, new_call, 1)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(code)

print("Personality voice cue injected successfully.")
