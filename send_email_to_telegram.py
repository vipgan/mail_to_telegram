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

# 加载已发送的邮件记录（使用 email_id）
def load_sent_emails():
    if os.path.exists(sent_emails_file):
        with open(sent_emails_file, 'r') as f:
            return json.load(f)
    return []

# 保存已发送的邮件记录（使用 email_id）
def save_sent_emails(sent_emails):
    with open(sent_emails_file, 'w') as f:
        json.dump(sent_emails, f)

# 发送消息到 Telegram，增加1秒延迟并清除多余换行符
def send_message(text):
    try:
        # 清理 Markdown 中的连续换行符（最多允许1个换行）
        text = re.sub(r'\n{2,}', '\n', text)  # 替换多个连续的换行符为一个
        
        time.sleep(1)  # 增加1秒延迟
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

    # 移除图片标签 <img> 和包含图片链接的 <a> 标签
    for img in soup.find_all('img'):
        img.decompose()  # 移除图片标签
    for a in soup.find_all('a'):
        if any(ext in a['href'] for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):  # 检查链接是否是图片
            a.decompose()  # 移除图片链接
        else:
            a.unwrap()  # 保留其他普通链接

    text = soup.get_text()

    # 清理多余的空行和空白字符
    text = re.sub(r'\s+', ' ', text)  # 将连续的空白字符（包括换行符）替换为单个空格
    text = re.sub(r'\n+', '\n', text)  # 清理多余的换行符
    text = re.sub(r'^\s+$', '', text, flags=re.MULTILINE)  # 删除每行的空白行

    # 按行处理，移除只包含空白或特殊字符的行
    lines = text.split('\n')
    cleaned_lines = [line.strip() for line in lines if line.strip()]  # 去掉空白行
    return '\n'.join(cleaned_lines).strip()  # 去除首尾空白并合并为字符串

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
    
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        # 搜索未读邮件
        status, messages = mail.search(None, '(UNSEEN)')
        email_ids = messages[0].split()

        for email_id in email_ids:
            if email_id.decode() in sent_emails:
                continue  # 如果已经发送，跳过此邮件

            _, msg_data = mail.fetch(email_id, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            
            subject = decode_header(msg['subject'])
            sender = decode_header(msg['from'])
            date_str = msg['date']
            body = get_email_body(msg)

            # 发送消息，使用 Markdown 格式，发件人放在主题后面
            message = f'''
*主题*: {subject}  
*发件人*: {sender}  
*时间*: {date_str}  
*内容*:  
{body}
'''
            send_message(message)
            
            # 记录发送的邮件
            sent_emails.append(email_id.decode())  # 使用 email_id 作为唯一标识

            # 将邮件标记为已读
            mail.store(email_id, '+FLAGS', '\\Seen')

    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

if __name__ == '__main__':
    fetch_emails()
