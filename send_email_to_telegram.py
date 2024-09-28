import imaplib
import email
import requests
import os

# 设置邮箱信息
email_user = os.environ['EMAIL_USER']
email_password = os.environ['EMAIL_PASSWORD']
imap_server = "imap.qq.com"

# 设置 Telegram 信息
TELEGRAM_API_KEY = os.environ['TELEGRAM_API_KEY']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

def send_message(text):
    requests.post(f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage',
                  data={'chat_id': TELEGRAM_CHAT_ID, 'text': text})

def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

def fetch_emails():
    keywords = ['账单', '信用卡', '移动']
    
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(email_user, email_password)
    mail.select('inbox')

    status, messages = mail.search(None, 'ALL')
    email_ids = messages[0].split()

    for email_id in email_ids:
        _, msg = mail.fetch(email_id, '(RFC822)')
        msg = email.message_from_bytes(msg[0][1])
        
        subject = decode_header(msg['subject'])
        sender = msg['from']
        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

        # 检查主题是否包含关键词
        if any(keyword in subject for keyword in keywords):
            send_message(f'New Email:\nFrom: {sender}\nSubject: {subject}\nContent: {body}')

    mail.logout()

if __name__ == '__main__':
    fetch_emails()
