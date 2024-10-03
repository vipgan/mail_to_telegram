import imaplib
import email
import os
import json
import time
import re
from telegram import Bot
import asyncio
from html import escape

# 设置邮箱信息
email_user = os.environ['EMAIL_USER']
email_password = os.environ['EMAIL_PASSWORD']
imap_server = "imap.qq.com"

# 设置 Telegram 信息
TELEGRAM_API_KEY = os.environ['TELEGRAM_API_KEY']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

# Telegram Bot 实例化
bot = Bot(token=TELEGRAM_API_KEY)

# 保存发送记录文件
sent_emails_file = 'sent_emails.json'

# 加载已发送的邮件记录
def load_sent_emails():
    if os.path.exists(sent_emails_file):
        with open(sent_emails_file, 'r') as f:
            return json.load(f)
    return []

# 保存已发送的邮件记录
def save_sent_emails(sent_emails):
    with open(sent_emails_file, 'w') as f:
        json.dump(sent_emails, f)

# 发送消息到 Telegram
async def send_message(text):
    try:
        await asyncio.sleep(1)
        response = await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode='HTML')
        print(f"Message sent: {response}")
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# 清理邮件内容
def clean_email_body(body):
    body = ' '.join(body.split())
    return escape(body)

# 过滤特殊字符
def sanitize_string(s):
    return ''.join(char for char in s if char.isprintable())

# 获取邮件内容并解决乱码问题
def get_email_body(msg):
    body = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                charset = part.get_content_charset()
                if content_type in ['text/plain', 'text/html']:
                    body = part.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
                    break
        else:
            charset = msg.get_content_charset()
            body = msg.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
        
        cleaned_body = clean_email_body(body)
        return cleaned_body if isinstance(cleaned_body, str) else str(cleaned_body)

    except Exception as e:
        print(f"Error getting email body: {e}")
        return ""

# 获取并处理邮件
async def fetch_emails():
    sent_emails = load_sent_emails()

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()

        for email_id in email_ids:
            _, msg_data = mail.fetch(email_id, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            
            subject = sanitize_string(decode_header(msg['subject']))
            sender = sanitize_string(decode_header(msg['from']))
            body = get_email_body(msg)

            date = sanitize_string(decode_header(msg['date']))

            print(f"Processing email: ID={email_id}, Subject={subject}, Sender={sender}, Body Length={len(body)}")

            if subject in sent_emails:
                continue

            message = f'''
<b>New mail</b>
<b>发件人</b>: {escape(sender)}<br>
<b>时间</b>: {escape(date)}<br>
<b>主题</b>: {escape(subject)}<br>
<b>内容</b>: <pre>{escape(body[:1000])}</pre>  # 限制发送内容长度
'''
            print(f"Message to send: {message}")  # 打印即将发送的消息

            await send_message(message)
            sent_emails.append(subject)

    except Exception as e:
        print(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

if __name__ == '__main__':
    asyncio.run(fetch_emails())
