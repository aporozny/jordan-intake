filepath = '/home/andre/jordan-intake/intake_service.py'
with open(filepath, 'r') as f:
    lines = f.read().split('\n')

for i, line in enumerate(lines):
    if 'yield f"data: ' in line:
        # Find the last closing brace of the JSON payload
        idx = line.rfind('}')
        if idx != -1:
            # Reconstruct the line with the correct Python string escape sequence
            lines[i] = line[:idx+1] + r'\n\n"'

with open(filepath, 'w') as f:
    f.write('\n'.join(lines))
print("SUCCESS: Fixed SSE newlines in Python.")
