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
from telegram.helpers import escape_markdown

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
            return set(json.load(f))  # 使用集合以便快速查找
    return set()

# 保存已发送的邮件记录
def save_sent_emails(sent_emails):
    with open(sent_emails_file, 'w') as f:
        json.dump(list(sent_emails), f)

def send_message(text):
    try:
        if not isinstance(text, str):
            logging.error(f"Expected string but got: {type(text)}")
            return
        
        time.sleep(4)  # 增加1秒延迟
        text = escape_markdown(text, version=2)  # 清理文本以适应 Markdown
        response = requests.post(f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage',
                                 data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'})
        response.raise_for_status()
        logging.info(f"Message sent: {text}")
    except Exception as e:
        logging.error(f"Error sending message to Telegram: {e}")

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        fragment.decode(encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

def clean_email_body(body):
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
            content_type = part.get_content_type()
            charset = part.get_content_charset() or 'utf-8'
            
            if content_type in ['text/html', 'text/plain']:
                body = part.get_payload(decode=True).decode(charset, errors='ignore')
                break  # 找到第一个有效内容后退出
    else:
        charset = msg.get_content_charset() or 'utf-8'
        body = msg.get_payload(decode=True).decode(charset, errors='ignore')
        
    return clean_email_body(body)

# 清理邮件主题
def clean_subject(subject):
    return re.sub(r'[^\w\s]', '', subject)  # 清除符号

# 获取并处理邮件
def fetch_emails():
    sent_emails = load_sent_emails()
    
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        # 搜索未读邮件
        status, messages = mail.search(None, '(UNSEEN)')
        if status != 'OK':
            logging.error("Error searching for emails")
            return
        
        email_ids = messages[0].split()
        
        for email_id in email_ids:
            try:
                _, msg_data = mail.fetch(email_id, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])
                
                subject = clean_subject(decode_header(msg['subject']))
                sender = decode_header(msg['from'])
                date_str = msg['date']
                body = get_email_body(msg)

                # 检查是否已发送
                if email_id in sent_emails:  # 使用 email_id 来判断
                    logging.info(f"Email already sent: {subject}")
                    continue
                
                # 发送消息，使用指定的格式
                message = f'''
主题: {subject}  
发件人: {sender}  
时间: {date_str}  
内容:----------------------------
{body}
'''
                send_message(message)

                # 记录发送的邮件
                sent_emails.add(email_id)  # 使用邮件 ID 记录

            except Exception as e:
                logging.error(f"Error processing email ID {email_id}: {e}")

    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

if __name__ == '__main__':
    fetch_emails()
