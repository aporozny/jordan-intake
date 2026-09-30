import re

filepath = '/home/andre/jordan-intake/intake_service.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r"extra_body\s*=\s*\{\s*[\"']plugins[\"']:\s*\[\s*\{\s*[\"']id[\"']:\s*[\"']web[\"'],\s*[\"']max_results[\"']:\s*5\s*\}\s*\]\s*\}"

new_block = """# Fast Heuristic Intent Router
    search_triggers = ["news", "latest", "today", "weather", "search", "who is", "price", "market", "current", "update"]
    needs_search = any(trigger in user_prompt.lower() for trigger in search_triggers)
    
    extra_body = {}
    if needs_search:
        extra_body = {
            "plugins": [{"id": "web", "max_results": 5}]
        }"""

if re.search(pattern, content):
    content = re.sub(pattern, new_block, content, count=1)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Fast heuristic router added.")
else:
    print("ERROR: Could not find extra_body block.")
