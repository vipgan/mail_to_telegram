import imaplib
import email
import requests
import os
import json
import time
import re
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import base64

# 设置日志记录
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

# 发送消息到 Telegram，增加1秒延迟
def send_message(text):
    try:
        time.sleep(4)  # 增加1秒延迟
        requests.post(f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage',
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'})
    except Exception as e:
        logging.error(f"Error sending message to Telegram: {e}")

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# 清理邮件内容并转换为 Markdown 格式
def clean_email_body(body):
    # 使用 BeautifulSoup 清理 HTML
    soup = BeautifulSoup(body, 'html.parser')
    text = soup.get_text()

    # 清理多余的空行和空白
    text = re.sub(r'\n\s*\n+', '\n', text)  # 替换多个换行符为一个换行符
    text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)  # 清除空行
    return text.strip()  # 去除首尾空白

# 获取邮件内容并解决乱码问题
def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                charset = part.get_content_charset()
                body = part.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
                break
    else:
        charset = msg.get_content_charset()
        body = msg.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
    return clean_email_body(body)

# 获取并处理邮件
def fetch_emails():
    sent_emails = load_sent_emails()

# 清理邮件主题
def clean_subject(subject):
    return re.sub(r'[^\w\s]', '', subject)  # 清除符号

# 获取并处理邮件
def fetch_emails():
    sent_emails = load_sent_emails()
    
    # 获取当前时间
    now = datetime.now()
    two_days_ago = now - timedelta(days=2)
    
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        # 搜索未读邮件
        status, messages = mail.search(None, '(UNSEEN)')
        email_ids = messages[0].split()

        for email_id in email_ids:
            _, msg_data = mail.fetch(email_id, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            
            subject = clean_subject(decode_header(msg['subject']))  # 清理主题
            sender = decode_header(msg['from'])
            date_str = msg['date']
            body = get_email_body(msg)

            # 发送消息，使用 Markdown 格式
            message = f'''
*发件人*: {sender}  
*主题*: {subject}  
*时间*: {date_str}  
*内容*:  
{body}
'''
            send_message(message)
            
            # 记录发送的邮件
            sent_emails.append(base64.b64encode(subject.encode()).decode())  # 用 base64 保存主题

    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

if __name__ == '__main__':
    fetch_emails()
