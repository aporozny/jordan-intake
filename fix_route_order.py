import re

filepath = "/home/andre/jordan-intake/intake_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

main_match = re.search(r"^if\s+__name__\s*==\s*['\"]__main__['\"]:", content, re.MULTILINE)
stream_idx = content.find("from fastapi.responses import StreamingResponse")

if main_match and stream_idx != -1 and stream_idx > main_match.start():
    main_idx = main_match.start()
    
    # Split the file into three parts
    top_part = content[:main_idx]
    main_block = content[main_idx:stream_idx]
    stream_block = content[stream_idx:]
    
    # Reassemble: Top -> Stream Route -> Uvicorn Main Block
    new_content = top_part + "\n" + stream_block + "\n\n" + main_block
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("SUCCESS: Moved the streaming endpoint above the uvicorn.run() blocking call.")
else:
    print("WARNING: Could not find the expected structure or it's already in the correct order.")
