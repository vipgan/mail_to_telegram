import imaplib
import email
import requests
import os
import json

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
        requests.post(f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage',
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': text})
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
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
def fetch_emails():
    keywords = ['账单', '信用卡', '移动']
    sent_emails = load_sent_emails()  # 加载已发送邮件记录
    
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
        mail.select('inbox')

        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()

        for email_id in email_ids:
            _, msg_data = mail.fetch(email_id, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            
            subject = decode_header(msg['subject'])
            sender = decode_header(msg['from'])
            
            # 检查邮件ID是否已经发送过
            if subject in sent_emails:
                continue  # 如果邮件已经发送，跳过

            # 获取邮件内容
            body = get_email_body(msg)

            # 检查主题是否包含关键词
            if any(keyword in subject for keyword in keywords):
                send_message(f'New Email:\nFrom: {sender}\nSubject: {subject}\nContent: {body}')
                
                # 记录发送的邮件
                sent_emails.append(subject)

    except Exception as e:
        print(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)  # 保存已发送邮件记录

if __name__ == '__main__':
    fetch_emails()
