filepath = "/home/andre/jordan-intake/intake_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the create call to include extra_body and online model suffix
old_block = """        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,"""

new_block = """        # If using OpenRouter and not already :online, enable web capability
        target_model = model
        if "openrouter" in str(openai_client.base_url) and not target_model.endswith(":online"):
            target_model = f"{model}:online"

        response = openai_client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=0.3,
            extra_body=extra_body,"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully patched extra_body and online model routing in intake_service.py.")
else:
    print("Could not find exact block, checking lines...")
