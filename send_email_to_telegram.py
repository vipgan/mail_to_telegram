import imaplib
import email
import requests
import os
import json
import logging
from email.header import decode_header
from concurrent.futures import ThreadPoolExecutor

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        response = requests.post(f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage',
                                 data={'chat_id': TELEGRAM_CHAT_ID, 'text': text})
        if response.status_code == 200:
            logging.info("Message sent to Telegram successfully.")
        else:
            logging.error(f"Failed to send message. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Error sending message to Telegram: {e}")

# 发送错误通知到 Telegram
def send_error_notification(error_message):
    send_message(f"Error Occurred: {error_message}")

# 解码邮件头
def decode_header_value(header):
    decoded_fragments = decode_header(header)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# 获取邮件内容并解决乱码问题
def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                charset = part.get_content_charset()
                if charset:
                    body = part.get_payload(decode=True).decode(charset, errors='ignore')
                else:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                break
    else:
        charset = msg.get_content_charset()
        if charset:
            body = msg.get_payload(decode=True).decode(charset, errors='ignore')
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
    return body

# 获取并处理邮件
def process_email(mail, email_id, sent_emails, keywords, sender_filter):
    try:
        _, msg_data = mail.fetch(email_id, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        
        subject = decode_header_value(msg['subject'])
        sender = decode_header_value(msg['from'])
        message_id = msg.get('Message-ID')  # 使用 Message-ID 作为邮件唯一标识
        
        # 检查邮件ID是否已经发送过
        if message_id in sent_emails:
            logging.info(f"Email '{subject}' already sent. Skipping...")
            return

        # 检查发件人过滤器
        if sender_filter and sender_filter not in sender:
            logging.info(f"Email from '{sender}' does not match the filter. Skipping...")
            return

        # 获取邮件内容
        body = get_email_body(msg)

        # 检查主题是否包含关键词
        if any(keyword in subject for keyword in keywords):
            send_message(f'New Email:\nFrom: {sender}\nSubject: {subject}\nContent: {body}')
            
            # 记录发送的邮件
            sent_emails.append(message_id)
            logging.info(f"Email '{subject}' sent and recorded.")

    except Exception as e:
        logging.error(f"Error processing email {email_id}: {e}")
        send_error_notification(f"Error processing email {email_id}: {e}")

# 获取所有邮件并处理
def fetch_emails():
    keywords = ['账单', '信用卡', '移动']  # 关键词
    sender_filter = 'specific_sender@example.com'  # 发件人过滤器
    sent_emails = load_sent_emails()  # 加载已发送邮件记录
    
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()

        # 并发处理邮件
        with ThreadPoolExecutor(max_workers=10) as executor:  # 增加线程池数量以提升性能
            for email_id in email_ids:
                executor.submit(process_email, mail, email_id, sent_emails, keywords, sender_filter)

    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
        send_error_notification(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)  # 保存已发送邮件记录
        logging.info("Emails fetched and sent_emails.json updated.")

if __name__ == '__main__':
    fetch_emails()
