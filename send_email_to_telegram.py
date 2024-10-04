import imaplib
import email
import os
import json
import time
import re
import base64
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from telegram import Bot

# 设置邮箱信息
email_user = os.environ['EMAIL_USER']
email_password = os.environ['EMAIL_PASSWORD']
imap_server = "imap.qq.com"

# 设置 Telegram 信息
TELEGRAM_API_KEY = os.environ['TELEGRAM_API_KEY']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

# 创建 Telegram Bot 实例
bot = Bot(token=TELEGRAM_API_KEY)

# 保存发送记录文件
sent_emails_file = 'sent_emails.json'

# Base64 编码
def encode_base64(text):
    return base64.b64encode(text.encode('utf-8')).decode('utf-8')

# Base64 解码
def decode_base64(encoded_text):
    return base64.b64decode(encoded_text.encode('utf-8')).decode('utf-8')

# 加载已发送的邮件记录（Base64 解码）
def load_sent_emails():
    if os.path.exists(sent_emails_file):
        with open(sent_emails_file, 'r') as f:
            encoded_emails = json.load(f)
            return [decode_base64(subject) for subject in encoded_emails]
    return []

# 保存已发送的邮件记录（Base64 编码）
def save_sent_emails(sent_emails):
    with open(sent_emails_file, 'w') as f:
        encoded_emails = [encode_base64(subject) for subject in sent_emails]
        json.dump(encoded_emails, f)

# 发送消息到 Telegram
def send_message(text):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode='Markdown')
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# 清理邮件体，去除图片和代码内容，保留文本
def clean_email_body(body):
    # 使用 BeautifulSoup 清理 HTML 内容
    soup = BeautifulSoup(body, "html.parser")

    # 去掉图片标签和脚本/样式标签
    for img in soup.find_all('img'):
        img.decompose()
    for script in soup.find_all(['script', 'style']):
        script.decompose()

    # 获取文本内容
    text = soup.get_text()
    # 将多个空行替换为一个空行
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

# 获取邮件内容并转换为文本格式
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

    # 清理邮件体并返回
    return clean_email_body(body)

# 获取邮件原始时间
def get_email_date(msg):
    date_tuple = parsedate_to_datetime(msg['date'])
    return date_tuple.strftime('%Y-%m-%d %H:%M:%S') if date_tuple else '未知时间'

# 获取并处理邮件
def fetch_emails():
    sent_emails = load_sent_emails()
    
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        # 获取最近三天的日期
        since_date = (datetime.now() - timedelta(days=3)).strftime("%d-%b-%Y")

        # 仅搜索最近三天内的未读邮件
        status, messages = mail.search(None, f'(UNSEEN SINCE {since_date})')
        if status != 'OK':
            print("Error searching inbox.")
            return

        email_ids = messages[0].split()

        for email_id in email_ids:
            try:
                _, msg_data = mail.fetch(email_id, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])
                
                subject = decode_header(msg['subject'])
                sender = decode_header(msg['from'])
                body = get_email_body(msg)
                email_date = get_email_date(msg)

                # 检查邮件ID是否已经发送过
                if subject in sent_emails:
                    continue

                # 发送消息，使用 Markdown 格式
                message = f'''
*主题*: {subject}
*发件人*: {sender}  
*时间*: {email_date}  
*内容*:  
{body}
'''
                send_message(message)
                
                # 记录发送的邮件（Base64 编码保存）
                sent_emails.append(subject)

            except Exception as e:
                print(f"Error fetching email ID {email_id}: {e}")

    except Exception as e:
        print(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

if __name__ == '__main__':
    fetch_emails()
