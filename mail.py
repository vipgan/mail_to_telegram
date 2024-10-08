import imaplib
import email
import requests
import os
import re
import logging
import mysql.connector
from datetime import datetime
from mysql.connector import pooling
from bs4 import BeautifulSoup
from telegram.helpers import escape_markdown

# 设置日志记录并分级
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# 设置邮箱信息
email_user = os.environ['EMAIL_USER']
email_password = os.environ['EMAIL_PASSWORD']
imap_server = "imap.qq.com"

# 设置 Telegram 信息
TELEGRAM_API_KEY = os.environ['TELEGRAM_API_KEY']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

# 设置 MySQL 连接池
dbconfig = {
    "host": os.environ['DB_HOST'],              # 数据库主机
    "database": os.environ['DB_NAME'],          # 数据库名称
    "user": os.environ['DB_USER'],              # 数据库用户名
    "password": os.environ['DB_PASSWORD'],      # 数据库密码
    "pool_name": "mypool",
    "pool_size": 5
}

connection_pool = mysql.connector.pooling.MySQLConnectionPool(**dbconfig)

# 加载已发送的邮件记录
def load_sent_emails():
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT message_id FROM sent_emails")
        rows = cursor.fetchall()
        return {row[0] for row in rows}  # 返回一个包含所有已发送邮件的集合
    except mysql.connector.Error as e:
        logger.error(f"Error fetching sent emails: {e}")
        return set()
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# 批量保存已发送的邮件记录
def save_sent_emails_to_db(message_ids):
    if not message_ids:
        return
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        sql = "INSERT IGNORE INTO sent_emails (message_id) VALUES (%s)"
        cursor.executemany(sql, [(msg_id,) for msg_id in message_ids])
        connection.commit()  # 批量提交事务
        logger.info(f"Saved {len(message_ids)} sent email IDs")
    except mysql.connector.Error as e:
        logger.error(f"Error saving sent emails: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def send_message(text):
    try:
        MAX_MESSAGE_LENGTH = 4000
        messages = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
        
        for message_part in messages:
            message_part = escape_markdown(message_part)
            response = requests.post(f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage',
                                     data={'chat_id': TELEGRAM_CHAT_ID, 'text': message_part, 'parse_mode': 'Markdown'})
            response.raise_for_status()
            logger.info(f"Message part sent: {message_part}")
    except Exception as e:
        logger.error(f"Error sending message to Telegram: {e}")

def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        fragment.decode(encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

def clean_email_body(body):
    soup = BeautifulSoup(body, 'html.parser')
    text = soup.get_text()
    text = re.sub(r'\n\s*\n+', '\n', text)  
    return text.strip() 

def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            charset = part.get_content_charset() or 'utf-8'
            
            if content_type in ['text/html', 'text/plain']:
                body = part.get_payload(decode=True).decode(charset, errors='ignore')
                break
    else:
        charset = msg.get_content_charset() or 'utf-8'
        body = msg.get_payload(decode=True).decode(charset, errors='ignore')
        
    return clean_email_body(body)

def clean_subject(subject):
    return re.sub(r'[^\w\s]', '', subject)

# 获取并处理邮件
def fetch_emails():
    connection = None
    sent_emails = load_sent_emails()  
    new_sent_emails = []

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        status, messages = mail.search(None, '(UNSEEN)')
        if status != 'OK':
            logger.error("Error searching for emails")
            return
        
        email_ids = messages[0].split()
        
        for email_id in email_ids:
            try:
                _, msg_data = mail.fetch(email_id, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])

                message_id = msg['Message-ID']
                if message_id in sent_emails:
                    logger.info(f"Email already sent: {message_id}")
                    continue

                subject = clean_subject(decode_header(msg['subject']))
                sender = decode_header(msg['from'])
                date_str = msg['date']
                body = get_email_body(msg)

                message = f'''
主题: {subject}
发件人: {sender}
时间: {date_str}
内容:------------------------------
{body}
'''
                send_message(message)

                new_sent_emails.append(message_id)

            except Exception as e:
                logger.error(f"Error processing email ID {email_id}: {e}")

    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        if new_sent_emails:
            save_sent_emails_to_db(new_sent_emails)

if __name__ == '__main__':
    fetch_emails()
