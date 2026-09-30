import re

filepath = "/home/andre/jordan-intake/intake_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update query_cloud_llm to include OpenRouter web plugin in extra_body
old_call = '''        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=1500
        )'''

new_call = '''        # Enable OpenRouter live web browsing plugin
        extra_body = {
            "plugins": [
                {
                    "id": "web",
                    "max_results": 5
                }
            ]
        }
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
            extra_body=extra_body
        )'''

if old_call in content:
    content = content.replace(old_call, new_call)
    print("Replaced chat completion call with web plugin extra_body.")
else:
    print("WARNING: Exact match for completion call not found. Checking regex...")
    pattern = r"response\s*=\s*openai_client\.chat\.completions\.create\s*\(\s*model=model,\s*messages=messages,\s*temperature=0\.3,\s*max_tokens=\d+\s*\)"
    content = re.sub(pattern, new_call.strip(), content)

# 2. Update System Prompt in chat_handler to explicitly grant web research capability
old_style = '"Acknowledge tasks, confirm actions, or provide direct answers immediately."'
new_style = '''"Acknowledge tasks, confirm actions, or provide direct answers immediately. "
        "You have live web search capabilities via automated browsing plugins. "
        "When asked to check websites, search for real-time information, research markets, or verify external facts, perform web lookups proactively."'''

if old_style in content:
    content = content.replace(old_style, new_style)
    print("Updated system prompt instructions to include web browsing authority.")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Web search patch completed.")
