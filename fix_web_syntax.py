filepath = "/home/andre/jordan-intake/intake_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False

for line in lines:
    if "openai_client.chat.completions.create(" in line:
        new_lines.append("        response = openai_client.chat.completions.create(\n")
        new_lines.append("            model=model,\n")
        new_lines.append("            messages=messages,\n")
        new_lines.append("            temperature=0.3,\n")
        new_lines.append("            max_tokens=1500,\n")
        new_lines.append("            extra_body=extra_body\n")
        new_lines.append("        )\n")
        skip = True
        continue
    
    if skip:
        if line.strip() == ")":
            skip = False
        continue

    new_lines.append(line)

with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Cleaned up chat.completions.create call.")
