import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone

OBSERVER_LOG_PATH = os.path.expanduser("~/.skills/task-observer/log.md")

def log_telemetry(action: str, target: str, status_msg: str):
    os.makedirs(os.path.dirname(OBSERVER_LOG_PATH), exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"- [{timestamp}] [MAILER] {action} | Target: {target} | Result: {status_msg}\n"
    try:
        with open(OBSERVER_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    except IOError:
        pass

def send_welcome_package(recipient_email: str, preferred_name: str, magic_link: str):
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_name = os.getenv("SMTP_FROM_NAME", "Jordan PA")
    from_email = os.getenv("SMTP_FROM_EMAIL", user)
    fridge_card_path = os.getenv("FRIDGE_CARD_PATH", "/home/andre/jordan-intake/assets/jordan_fridge_card.pdf")

    if not user or not password:
        log_telemetry("SEND_WELCOME", recipient_email, "SKIPPED_NO_SMTP_CREDENTIALS")
        return

    msg = EmailMessage()
    msg["Subject"] = f"Welcome to Jordan, {preferred_name} — Quick-Start Access & Fridge Card"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = recipient_email

    plain_text = f"""Hi {preferred_name},

Your Jordan workspace is provisioned and ready.

Direct Access Link:
{magic_link}

Attached to this email is your Jordan Fridge Card quick-start guide. Keep it handy for reference commands and daily routine outlines.

If you have any questions, reply directly to this email.

Best regards,
The Jordan Team
"""
    msg.set_content(plain_text)

    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #111; max-width: 580px; margin: 0 auto; padding: 24px;">
    <h2 style="font-size: 20px; font-weight: 600; margin-bottom: 16px;">Welcome aboard, {preferred_name}.</h2>
    <p>Your dedicated workspace is provisioned and ready to handle your daily operations and workflows.</p>
    
    <div style="margin: 28px 0;">
        <a href="{magic_link}" style="background-color: #111; color: #fff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 500; display: inline-block;">
            Launch Jordan Workspace &rarr;
        </a>
    </div>

    <p style="font-size: 14px; color: #555;">Attached is your <strong>Jordan Fridge Card</strong> quick-start guide covering default actions, standard prompts, and system conventions.</p>
    
    <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 32px 0 16px;" />
    <p style="font-size: 12px; color: #888;">Direct Magic Link (valid for this browser session):<br/><a href="{magic_link}" style="color: #666; word-break: break-all;">{magic_link}</a></p>
</body>
</html>
"""
    msg.add_alternative(html_content, subtype="html")

    if os.path.isfile(fridge_card_path):
        filename = os.path.basename(fridge_card_path)
        with open(fridge_card_path, "rb") as f:
            file_data = f.read()
        msg.add_attachment(
            file_data,
            maintype="application",
            subtype="pdf" if filename.endswith(".pdf") else "octet-stream",
            filename=filename
        )
    else:
        log_telemetry("ATTACHMENT", recipient_email, f"MISSING_FILE_{fridge_card_path}")

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        log_telemetry("SEND_WELCOME", recipient_email, "SUCCESS_DELIVERED")
    except Exception as e:
        log_telemetry("SEND_WELCOME", recipient_email, f"ERROR_{str(e)}")
