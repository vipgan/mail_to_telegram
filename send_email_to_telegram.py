import imaplib
import email
import requests
import os
import json
import time
import re
import logging
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# 常量配置
IMAP_SERVER = "imap.qq.com"
MAX_MESSAGE_LENGTH = 4096
MAX_WORKERS = 5

# 设置日志记录
logging.basicConfig(level=logging.INFO)

# 设置邮箱信息
email_user = os.environ['EMAIL_USER']
email_password = os.environ['EMAIL_PASSWORD']

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
        # 清理 Markdown 中的连续换行符（最多允许1个换行）
        text = re.sub(r'\n{2,}', '\n', text)

        # 检查消息长度并截断超过限制的部分
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[:MAX_MESSAGE_LENGTH-3] + "..."

        # 增加延迟避免 API 限制
        time.sleep(1)  # 增加1秒延迟

        # 发送到 Telegram
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
    # 使用 BeautifulSoup 解析 HTML 内容
    soup = BeautifulSoup(body, 'html.parser')

    # 移除所有 <img> 标签
    for img in soup.find_all('img'):
        img.decompose()

    # 清理多余的空行
    text = soup.get_text()
    text = re.sub(r'\n{2,}', '\n', text)  # 将连续两个或多个换行符替换为一个

    # 返回清理后的文本
    return text.strip()

# 获取邮件内容并解决乱码问题
def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                charset = part.get_content_charset()
                try:
                    body = part.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
                except Exception as e:
                    logging.error(f"Error decoding email body: {e}")
                    continue
                break
    else:
        charset = msg.get_content_charset()
        try:
            body = msg.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
        except Exception as e:
            logging.error(f"Error decoding email body: {e}")
    return clean_email_body(body)

# 单独处理每封邮件
def process_email(email_id, mail, sent_emails):
    try:
        _, msg_data = mail.fetch(email_id, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        
        subject = decode_header(msg['subject'])
        sender = decode_header(msg['from'])
        date_str = msg['date']
        body = get_email_body(msg)

        # 发送消息，使用 Markdown 格式，将发件人放在主题后面
        message = f'''
*主题*: {subject}  
*发件人*: {sender}  
*时间*: {date_str}  
*内容*:  
{body}
'''
        send_message(message)

        # 记录发送的邮件
        sent_emails.append(subject)
    except Exception as e:
        logging.error(f"Error processing email: {e}")

# 获取并处理邮件
def fetch_emails():
    sent_emails = load_sent_emails()

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(email_user, email_password)
        mail.select('inbox')

        # 搜索所有邮件
        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()

        # 使用多线程处理每封邮件
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for email_id in email_ids:
                executor.submit(process_email, email_id, mail, sent_emails)

    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP login failed: {e}")
    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

if __name__ == '__main__':
    start_time = time.time()
    fetch_emails()
    logging.info(f"Total processing time: {time.time() - start_time} seconds")
