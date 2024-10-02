import imaplib
import email
import requests
import os
import json
import time
import re

# 设置邮箱信息
email_user = os.environ['EMAIL_USER']
email_password = os.environ['EMAIL_PASSWORD']
imap_server = "imap.qq.com"

# 设置 Telegram 信息
TELEGRAM_API_KEY = os.environ['TELEGRAM_API_KEY']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

# 保存发送记录文件
sent_emails_file = 'sent_emails.json'
MAX_MESSAGE_LENGTH = 4096  # Telegram 单条消息的最大长度

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
        time.sleep(1)  # 增加1秒延迟
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[:MAX_MESSAGE_LENGTH]  # 截断消息
        print(f"发送的消息内容: {text}")  # 打印要发送的消息内容
        response = requests.post(f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage',
                                 data={'chat_id': TELEGRAM_CHAT_ID, 'text': text})  # 发送纯文本
        response.raise_for_status()
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")
        print(f"Failed message content: {text}")  # 打印失败的消息内容

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# 获取邮件内容并清除所有 HTML、CSS、JS 和 Markdown 代码
def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                charset = part.get_content_charset()
                body = part.get_payload(decode=True).decode(charset or 'utf-8')
                break
    else:
        charset = msg.get_content_charset()
        body = msg.get_payload(decode=True).decode(charset or 'utf-8')

    # 去除 HTML 标签、CSS、JS 和 Markdown
    body = re.sub(r'<.*?>', '', body)  # 去除 HTML 标签
    body = re.sub(r'\s+', ' ', body)  # 将多个空白字符替换为单个空格
    body = re.sub(r'^\s*|\s*$', '', body)  # 去除首尾空白
    body = re.sub(r'<script.*?</script>', '', body, flags=re.DOTALL)  # 去除 <script> 标签及内容
    body = re.sub(r'javascript:[^\'" >]*', '', body)  # 去除 JavaScript URL
    body = re.sub(r'`{1,3}.*?`{1,3}', '', body)  # 去除代码块和行内代码
    body = re.sub(r'[*_~#-]', '', body)  # 去除 Markdown 符号，如 *、_、~、#、- 等

    return body.strip()

# 获取并处理邮件
def fetch_emails():
    sent_emails = load_sent_emails()

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
            body = get_email_body(msg)

            # 检查邮件是否已经发送过
            if subject in sent_emails:
                continue

            # 发送消息到 Telegram
            message = f'''
发件人: {sender}  
主题: {subject}  
内容:  
{body}
'''
            send_message(message)

            # 记录已发送的邮件
            sent_emails.append(subject)

    except Exception as e:
        print(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

if __name__ == '__main__':
    fetch_emails()  # 获取并发送邮件
