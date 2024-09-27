import imaplib
import email
import requests
import os

# 获取环境变量
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
QQ_EMAIL = os.getenv('QQ_EMAIL')
QQ_EMAIL_API_KEY = os.getenv('QQ_EMAIL_API_KEY')  # 使用 API 密钥

# 邮箱连接设置
IMAP_SERVER = 'imap.qq.com'
KEYWORDS = ['信用卡', '账单', '移动']

def send_message_to_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    requests.post(url, json=payload)

def fetch_emails():
    print(f"QQ_EMAIL: {QQ_EMAIL}")
    print(f"QQ_EMAIL_API_KEY: {QQ_EMAIL_API_KEY}")

    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(QQ_EMAIL, QQ_EMAIL_API_KEY)  # 使用 API 密钥
    mail.select('inbox')

    result, data = mail.search(None, 'ALL')
    email_ids = data[0].split()

    for email_id in email_ids:
        result, msg_data = mail.fetch(email_id, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        subject = msg.get('subject')

        if subject and any(keyword in subject for keyword in KEYWORDS):
            send_message_to_telegram(f'新邮件: {subject}')

    mail.logout()

if __name__ == '__main__':
    fetch_emails()
