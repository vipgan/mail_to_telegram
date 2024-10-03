import imaplib
import email
import requests
import os
import json
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# 设置日志
logging.basicConfig(level=logging.INFO)

# 设置邮箱信息
email_user = os.environ['EMAIL_USER']
email_password = os.environ['EMAIL_PASSWORD']
imap_server = "imap.qq.com"

# 设置 Telegram 信息
TELEGRAM_API_KEY = os.environ['TELEGRAM_API_KEY']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

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
def send_message(text):
    try:
        # 检查文本长度
        if len(text) > 4096:
            logging.warning("Message too long, trimming...")
            text = text[:4096]

        # 打印发送的消息
        logging.info(f"Sending message: {text}")

        # 发送到 Telegram
        response = requests.post(f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage',
                                 data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'})
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Error sending message to Telegram: {e}")

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# 清理邮件内容
def clean_email_body(body):
    soup = BeautifulSoup(body, 'html.parser')
    
    # 清除特定标签
    for img in soup.find_all('img'):
        img.decompose()
    for a in soup.find_all('a'):
        a.decompose()
    for video in soup.find_all('video'):
        video.decompose()
    for script in soup.find_all('script'):
        script.decompose()
    for style in soup.find_all('style'):
        style.decompose()

    text = soup.get_text()
    # 去除空行
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return '\n'.join(lines)

# 获取邮件内容并解决乱码问题
def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                charset = part.get_content_charset()
                body = part.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
                break
    else:
        charset = msg.get_content_charset()
        body = msg.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
    return clean_email_body(body)

# 处理单封邮件
def process_email(email_id, sent_emails):
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')
        
        _, msg_data = mail.fetch(email_id, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        
        subject = decode_header(msg['subject'])
        sender = decode_header(msg['from'])
        body = get_email_body(msg)

        # 获取原始邮件日期
        original_time = email.utils.parsedate_to_datetime(msg['Date']).strftime('%Y-%m-%d %H:%M:%S')

        # 检查邮件ID是否已经发送过
        if subject in sent_emails:
            return

        # 发送消息，使用 Markdown 格式
        message = f'''
*发件人*: {sender}  
*主题*: {subject}  
*时间*: {original_time}  
*内容*:  
{body}
'''
        send_message(message)
        sent_emails.append(subject)
        logging.info(f"Message sent for subject: {subject}")

    except Exception as e:
        logging.error(f"Error processing email ID {email_id}: {e}")
    finally:
        mail.logout()

# 获取并处理邮件
def fetch_emails():
    sent_emails = load_sent_emails()

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        # 只获取未读邮件
        status, messages = mail.search(None, 'UNSEEN')
        email_ids = messages[0].split()

        with ThreadPoolExecutor(max_workers=5) as executor:
            # 使用多线程处理邮件
            for email_id in email_ids:
                executor.submit(process_email, email_id, sent_emails)

    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

if __name__ == '__main__':
    fetch_emails()
