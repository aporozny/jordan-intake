import os
import sys
import sqlite3
from dotenv import load_dotenv
from web_tools import fetch_page_sync
from openai import OpenAI

load_dotenv("/home/andre/jordan-intake/.env")
DB_PATH = os.path.expanduser("~/.jordan/jordan_users.db")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", os.getenv("OPENROUTER_API_KEY", ""))
MODEL = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")

client = OpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)

def summarize(markdown, biz_name):
    prompt = f"Analyze scraped site for {biz_name}. Provide a 2-3 sentence executive operational summary (core offering, target client, service model). No fluff:\n\n{markdown}"
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )
    return response.choices[0].message.content.strip()

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
