import os, sys, sqlite3, json, urllib.request
from dotenv import load_dotenv
from web_tools import fetch_page_sync

load_dotenv("/home/andre/jordan-intake/.env")
DB_PATH = os.path.expanduser("~/.jordan/jordan_users.db")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-5").strip()

def summarize(markdown, biz_name):
    prompt = f"Analyze scraped site for {biz_name}. Provide a 2-3 sentence executive operational summary (core offering, target client, service model). No fluff:\n\n{markdown}"
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 200}).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENROUTER_KEY}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()

def enrich(user_id, url):
    print(f"Scraping {url}...")
    md = fetch_page_sync(url)
    if not md:
        print("Failed to scrape.")
        return
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT business_name FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        name = row[0] if row and row[0] else "Client"
        print(f"Summarizing {name} via {MODEL}...")
        summary = summarize(md, name)
        cursor.execute("UPDATE users SET business_summary = ? WHERE id = ?", (summary, user_id))
        conn.commit()
    print(f"Enriched user {user_id}:\n{summary}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        enrich(int(sys.argv[1]), sys.argv[2])
