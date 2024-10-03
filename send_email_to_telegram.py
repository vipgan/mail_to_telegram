import os
import json
import re
import email
import imaplib
import asyncio
from email.header import decode_header
from telegram import Bot

# 配置 Telegram Bot
TELEGRAM_TOKEN = 'YOUR_TELEGRAM_TOKEN'
CHAT_ID = 'YOUR_CHAT_ID'
bot = Bot(token=TELEGRAM_TOKEN)

# 邮箱配置
IMAP_SERVER = 'imap.qq.com'
EMAIL_USER = 'YOUR_EMAIL'
EMAIL_PASSWORD = 'YOUR_EMAIL_PASSWORD'

# 发送邮件记录文件
SENT_EMAILS_FILE = 'sent_emails.json'

# 载入已发送邮件记录
def load_sent_emails():
    if os.path.exists(SENT_EMAILS_FILE):
        with open(SENT_EMAILS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# 保存已发送邮件记录
def save_sent_emails(sent_emails):
    with open(SENT_EMAILS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sent_emails, f)

# HTML 字符转义
def escape(text):
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))

# 解码邮件头
def sanitize_string(header):
    decoded_parts = decode_header(header)
    return ''.join(
        str(part, encoding) if isinstance(part, bytes) else part
        for part, encoding in decoded_parts
    )

# 获取邮件内容
def get_email_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                return part.get_payload(decode=True).decode()
            elif part.get_content_type() == 'text/html':
                return part.get_payload(decode=True).decode()
    else:
        return msg.get_payload(decode=True).decode()
    return ''

# 发送消息到 Telegram
async def send_message(message):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='HTML')
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

# 获取并处理邮件
async def fetch_emails():
    sent_emails = load_sent_emails()

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        mail.select('inbox')

        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()

        for email_id in email_ids:
            try:
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
                print(f"Error processing email ID={email_id}: {e}")

    except Exception as e:
        print(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

# 主函数
if __name__ == '__main__':
    asyncio.run(fetch_emails())
