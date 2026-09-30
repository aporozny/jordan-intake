import re

filepath = '/home/andre/jordan-intake/intake_service.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Locate the existing system_prompt definition block
pattern = r'system_prompt\s*=\s*\([\s\S]*?\)\n\s*save_chat_message'

new_prompt_block = '''system_prompt = (
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

    save_chat_message'''

if re.search(pattern, content):
    content = re.sub(pattern, new_prompt_block, content, count=1)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Fridge Card protocols injected into System Prompt.")
else:
    print("ERROR: Could not find the system_prompt block.")
