import imaplib
import email
import requests
import os
import json
import time
import re
from email.utils import parsedate_to_datetime

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
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'MarkdownV2'})
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# 获取邮件原始时间
def get_email_date(msg):
    date_tuple = parsedate_to_datetime(msg['date'])
    return date_tuple.strftime('%Y-%m-%d %H:%M:%S') if date_tuple else '未知时间'

# 清理邮件主体，去除图片、CSS和JS代码，并将多个空行合并为一个空行
def clean_email_body(body):
    # 去除 HTML 标签
    body = re.sub(r'<[^>]+>', '', body)  # 去除所有 HTML 标签
    
    # 去除 CSS 和 JS 代码块
    body = re.sub(r'(<style.*?>.*?</style>)|(<script.*?>.*?</script>)', '', body, flags=re.DOTALL)
    
    # 将多个空行替换为一个空行
    body = re.sub(r'\n\s*\n+', '\n\n', body)
    
    return body.strip()  # 去除首尾空白

# 获取邮件主体
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

        # 仅搜索未读邮件
        status, messages = mail.search(None, 'UNSEEN')
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
                email_date = get_email_date(msg)
                body = get_email_body(msg)

                # 检查邮件ID是否已经发送过
                if subject in sent_emails:
                    continue

                # 发送消息
                message = f'''
主题: {subject}
发件人: {sender}  
时间: {email_date}  
内容:  
{body}
'''
                send_message(message)
                
                # 记录发送的邮件
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
