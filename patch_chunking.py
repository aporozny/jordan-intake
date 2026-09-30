filepath = '/home/andre/jordan-intake/intake_service.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Change the regex to split on commas, colons, and semicolons too
old_regex = r"r'([.!?])\s+'"
new_regex = r"r'([.,!?;:])\s+'"

if old_regex in content:
    content = content.replace(old_regex, new_regex)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Phrase-level chunking enabled.")
else:
    print("WARNING: Could not find the exact regex. Check the file manually.")
