import re

filepath = '/home/andre/jordan-intake/intake_service.py'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Remove the broken router block
text = re.sub(r"^[ \t]*# Fast Heuristic Intent Router.*?(?=[ \t]*target_model = model)", "", text, flags=re.MULTILINE | re.DOTALL)

# 2. Remove the old extra_body hardcoded block
text = re.sub(r"^[ \t]*extra_body\s*=\s*\{.*?(?=[ \t]*target_model = model)", "", text, flags=re.MULTILINE | re.DOTALL)

# 3. Clean up the specific stray comment
text = re.sub(r"^[ \t]*# If using OpenRouter.*?\n", "", text, flags=re.MULTILINE)

# 4. Inject the new, perfectly indented block
def inject_router(match):
    indent = match.group(1)
    return f'''{indent}# Fast Heuristic Intent Router
{indent}search_triggers = ["news", "latest", "today", "weather", "search", "who is", "price", "market", "current", "update"]
{indent}needs_search = any(trigger in user_prompt.lower() for trigger in search_triggers)
{indent}extra_body = {{}}
{indent}if needs_search:
{indent}    extra_body = {{"plugins": [{{"id": "web", "max_results": 5}}]}}
{indent}target_model = model'''

text = re.sub(r"^([ \t]*)target_model = model", inject_router, text, flags=re.MULTILINE)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)
print("SUCCESS: Router fixed and indented perfectly.")
