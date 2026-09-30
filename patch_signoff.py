filepath = "/home/andre/jordan-intake/intake_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

helper_code = '''
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
'''

if "def check_signoff" not in code:
    # Insert helper before chat endpoint
    code = helper_code + "\n" + code

# Inject check into the chat handler before LLM call
target_marker = 'async def chat(request: ChatRequest'
if target_marker in code and "check_signoff(request.message)" not in code:
    replacement = target_marker + ''':
    if check_signoff(request.message):
        return {"reply": "", "session_token": request.session_token, "signoff": True}
'''
    code = code.replace(target_marker + ':', replacement, 1)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(code)

print("Sign-off interception successfully injected.")
