#!/usr/bin/env python3
"""CLI test harness and runner for Jordan Intake FastAPI service."""

import argparse
import sys
import json
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv("/home/andre/jordan-intake/.env")

from fastapi.testclient import TestClient
from intake_service import app, init_db, DB_PATH

def get_default_token() -> str:
    """Retrieve the first active session token from the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_token FROM users WHERE status = 'active' AND session_token IS NOT NULL LIMIT 1;"
            )
            row = cursor.fetchone()
            if row:
                return row[0]
    except Exception as e:
        print(f"[!] Warning: Failed to query default token: {e}", file=sys.stderr)
    return ""

def main():
    parser = argparse.ArgumentParser(description="Jordan Intake Runner & Test Harness")
    parser.add_argument("--health", action="store_true", help="Run health check on /health")
    parser.add_argument("--test-chat", type=str, help="Send a test message through query_cloud_llm via /api/chat")
    parser.add_argument("--token", type=str, help="Specify session token (defaults to first active in DB)")
    parser.add_argument("--serve", action="store_true", help="Launch the uvicorn service on 127.0.0.1:8082")
    parser.add_argument("--port", type=int, default=8082, help="Port to serve on (default: 8082)")
    args = parser.parse_args()

    init_db()

    if args.serve:
        import uvicorn
        print(f"[*] Launching Jordan Intake FastAPI service on http://127.0.0.1:{args.port}...")
        uvicorn.run(app, host="127.0.0.1", port=args.port)
        return

    client = TestClient(app)

    # Health Check
    if args.health or not any([args.test_chat, args.serve]):
        print("[*] Running /health probe...")
        response = client.get("/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

    # Chat / LLM Connectivity Probe
    if args.test_chat:
        token = args.token or get_default_token()
        if not token:
            print("[-] Error: No active session token found in DB. Provide one via --token.", file=sys.stderr)
            sys.exit(1)

        print(f"[*] Testing LLM query via /api/chat (token: {token[:8]}...) with message: {args.test_chat!r}")
        payload = {
            "session_token": token,
            "message": args.test_chat
        }
        response = client.post("/api/chat", json=payload)
        print(f"Status: {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except Exception:
            print(response.text)

if __name__ == "__main__":
    main()
