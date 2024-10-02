import os
import imaplib
import datetime
import asyncio
import re
from telegram import Bot

async def scan_emails_and_notify():
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    SENT_EMAILS_FILE = 'sent_emails.txt'
    MAX_MESSAGE_LENGTH = 4096  # Telegram 消息最大长度

    # 加载已发送邮件的ID
    sent_email_ids = load_sent_email_ids(SENT_EMAILS_FILE)

    # 登录到QQ邮箱
    mail = imaplib.IMAP4_SSL('imap.qq.com')
    mail.login(EMAIL_USER, EMAIL_PASSWORD)
    mail.select('inbox')

    # 获取最近2天的日期
    date_since = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%d-%b-%Y")
    result, data = mail.search(None, f'SINCE {date_since}')

    email_ids = data[0].split()
    new_messages = []
    new_email_ids = []

    for email_id in email_ids:
        if email_id.decode() not in sent_email_ids:
            result, msg_data = mail.fetch(email_id, '(RFC822)')
            message_body = msg_data[0][1].decode('utf-8')
            cleaned_message = clean_message(message_body)
            new_messages.append(cleaned_message)
            new_email_ids.append(email_id.decode())

    mail.logout()

    # 将新邮件内容发送到Telegram
    bot = Bot(token=TELEGRAM_API_KEY)
    if new_messages:
        # 创建消息文本
        message_text = f"最近2天的新邮件：\n\n" + "\n\n".join(new_messages)
        
        # 拆分消息
        for i in range(0, len(message_text), MAX_MESSAGE_LENGTH):
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_text[i:i + MAX_MESSAGE_LENGTH])

        # 保存已发送的邮件ID
        save_sent_email_ids(SENT_EMAILS_FILE, new_email_ids)
    else:
        print("最近2天没有新邮件。")

def clean_message(message):
    # 删除图片和视频的链接
    message = re.sub(r'<img.*?src="(.*?)".*?>', '', message)  # 删除图片
    message = re.sub(r'<video.*?src="(.*?)".*?>', '', message)  # 删除视频
    # 进一步处理：可以添加 HTML、CSS、JS 语法高亮或格式化等
    return message

def load_sent_email_ids(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return set(f.read().splitlines())
    return set()

def save_sent_email_ids(file_path, email_ids):
    with open(file_path, 'w') as f:
        for email_id in email_ids:
            f.write(f"{email_id}\n")

if __name__ == "__main__":
    asyncio.run(scan_emails_and_notify())
