import imaplib
import email
from email.header import decode_header
import requests
import json
import os
import time

# 从环境变量获取邮箱和Telegram配置信息
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TELEGRAM_API_KEY = os.getenv("TELEGRAM_API_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 定义保存已发送邮件的文件
SENT_EMAILS_FILE = "sent_emails.json"

# 初始化 IMAP 客户端并连接到邮箱
def connect_to_email():
    mail = imaplib.IMAP4_SSL("imap.qq.com")
    mail.login(EMAIL_USER, EMAIL_PASSWORD)
    return mail

# 从邮箱中获取未读邮件
def fetch_unread_emails(mail):
    mail.select("inbox")
    status, messages = mail.search(None, 'UNSEEN')
    email_ids = messages[0].split()
    return email_ids

# 解析邮件并提取内容
def parse_email(mail, email_id):
    res, msg = mail.fetch(email_id, "(RFC822)")
    for response_part in msg:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else "utf-8")
            from_ = msg.get("From")
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            return subject, from_, body
    return None, None, None

# 发送消息到 Telegram
def send_message_to_telegram(subject, from_, body):
    text = f"Subject: {subject}\nFrom: {from_}\n\n{body}"
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,  # 发送纯文本消息
        "parse_mode": "MarkdownV2"  # 使用MarkdownV2确保特殊字符被正确转义
    }

    # 避免解析错误，发送前对特殊字符进行转义
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')

    response = requests.post(url, data=payload)
    if response.status_code != 200:
        print(f"Error sending message to Telegram: {response.text}")
    else:
        print("Message sent successfully")

# 加载已发送的邮件ID
def load_sent_emails():
    if os.path.exists(SENT_EMAILS_FILE):
        with open(SENT_EMAILS_FILE, "r") as f:
            return json.load(f)
    return []

# 保存已发送的邮件ID
def save_sent_email(sent_emails):
    with open(SENT_EMAILS_FILE, "w") as f:
        json.dump(sent_emails, f)

def main():
    sent_emails = load_sent_emails()
    mail = connect_to_email()
    email_ids = fetch_unread_emails(mail)

    print(f"Found {len(email_ids)} unread emails.")
    
    for email_id in email_ids:
        if email_id in sent_emails:
            print(f"Email with ID {email_id} already sent.")
            continue
        
        subject, from_, body = parse_email(mail, email_id)
        if subject and from_ and body:
            send_message_to_telegram(subject, from_, body)
            sent_emails.append(email_id)
            time.sleep(1)  # 增加延迟，避免Telegram API限制

    save_sent_email(sent_emails)
    mail.logout()

if __name__ == "__main__":
    main()
