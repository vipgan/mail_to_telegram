import imaplib
import email
import requests
import os
import json
import time
from bs4 import BeautifulSoup

# 设置邮箱信息
email_user = os.environ['EMAIL_USER']
email_password = os.environ['EMAIL_PASSWORD']
imap_server = "imap.qq.com"

# 设置 Telegram 信息
TELEGRAM_API_KEY = os.environ['TELEGRAM_API_KEY']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

# 保存发送记录文件
sent_emails_file = 'sent_emails.json'

# 设置延迟和过滤选项
send_delay = int(os.environ.get('SEND_DELAY', 1))  # 发送消息时的延迟，默认为1秒
enable_send_filter = os.environ.get('ENABLE_SEND_FILTER', 'false').lower() == 'true'  # 启用发送过滤，默认关闭
enable_reject_filter = os.environ.get('ENABLE_REJECT_FILTER', 'false').lower() == 'true'  # 启用拒收过滤，默认关闭

# 过滤关键词
send_keywords = ['接收', 'google', 'Azure', '账单']  # 发送过滤的关键词
reject_keywords = ['信用卡', '银行']  # 拒收过滤的关键词

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

# 发送消息到 Telegram，增加自定义延迟
def send_message(text):
    try:
        time.sleep(send_delay)  # 自定义延迟
        requests.post(f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage',
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'MarkdownV2'})  # 使用 MarkdownV2
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

# 解码邮件头
def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

# 使用 BeautifulSoup 清理并转换为 Telegram Markdown 格式的文本
def clean_email_body(body):
    soup = BeautifulSoup(body, 'html.parser')
    text = soup.get_text()

    # 转换成 Telegram 支持的 Markdown 格式
    text = text.replace('_', '\\_')  # 转义下划线
    text = text.replace('*', '\\*')  # 转义星号
    text = text.replace('[', '\\[')  # 转义方括号
    text = text.replace(']', '\\]')  # 转义方括号
    text = text.replace('(', '\\(')  # 转义圆括号
    text = text.replace(')', '\\)')  # 转义圆括号
    text = text.replace('~', '\\~')  # 转义波浪号
    text = text.replace('`', '\\`')  # 转义反引号
    text = text.replace('>', '\\>')  # 转义大于号
    text = text.replace('#', '\\#')  # 转义井号
    text = text.replace('+', '\\+')  # 转义加号
    text = text.replace('-', '\\-')  # 转义减号
    text = text.replace('=', '\\=')  # 转义等号
    text = text.replace('|', '\\|')  # 转义竖线
    text = text.replace('.', '\\.')  # 转义句号
    text = text.replace('!', '\\!')  # 转义感叹号

    return text

# 获取邮件内容并解决乱码问题
def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                charset = part.get_content_charset()
                body = part.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
                break
    else:
        charset = msg.get_content_charset()
        body = msg.get_payload(decode=True).decode(charset or 'utf-8', errors='ignore')
    return clean_email_body(body)

# 检查是否包含发送过滤关键词
def contains_send_keywords(subject):
    return any(keyword in subject for keyword in send_keywords)

# 检查是否包含拒收过滤关键词
def contains_reject_keywords(subject):
    return any(keyword in subject for keyword in reject_keywords)

# 获取并处理邮件
def fetch_emails():
    sent_emails = load_sent_emails()
    
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_password)
    except imaplib.IMAP4.error as e:
        print(f"Login failed: {e}")
        return

    try:
        mail.select('inbox')
        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()

        for email_id in email_ids:
            _, msg_data = mail.fetch(email_id, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            
            subject = decode_header(msg['subject'])
            sender = decode_header(msg['from'])
            body = get_email_body(msg)

            # 检查邮件ID是否已经发送过
            if subject in sent_emails:
                continue

            # 启用拒收过滤
            if enable_reject_filter and contains_reject_keywords(subject):
                print(f"Email rejected due to subject: {subject}")
                continue

            # 启用发送过滤
            if enable_send_filter and not contains_send_keywords(subject):
                print(f"Email skipped due to missing keywords in subject: {subject}")
                continue

            # 发送消息，使用 Telegram MarkdownV2 格式
            message = f'''
*发件人*: {sender}  
*主题*: {subject}  
*内容*:  
{body}
'''
            send_message(message)

            # 标记邮件为已读
            mail.store(email_id, '+FLAGS', '\\Seen')
            
            # 记录发送的邮件
            sent_emails.append(subject)

    except Exception as e:
        print(f"Error fetching emails: {e}")
    finally:
        mail.logout()
        save_sent_emails(sent_emails)

if __name__ == '__main__':
    fetch_emails()
