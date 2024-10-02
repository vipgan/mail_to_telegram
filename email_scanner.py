import os
import imaplib
import datetime
import asyncio
from telegram import Bot

async def scan_emails_and_notify():
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    SENT_EMAILS_FILE = 'sent_emails.txt'

    # 加载已发送邮件的ID
    sent_email_ids = load_sent_email_ids(SENT_EMAILS_FILE)

    # 登录到QQ邮箱
    mail = imaplib.IMAP4_SSL('imap.qq.com')
    mail.login(EMAIL_USER, EMAIL_PASSWORD)
    mail.select('inbox')

    # 获取最近3天的日期
    date_since = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime("%d-%b-%Y")
    result, data = mail.search(None, f'SINCE {date_since}')

    email_ids = data[0].split()
    new_messages = []
    new_email_ids = []

    for email_id in email_ids:
        if email_id.decode() not in sent_email_ids:
            result, msg_data = mail.fetch(email_id, '(RFC822)')
            new_messages.append(msg_data[0][1])
            new_email_ids.append(email_id.decode())

    mail.logout()

    # 将新邮件内容发送到Telegram
    bot = Bot(token=TELEGRAM_API_KEY)
    if new_messages:
        message_text = f"最近3天的新邮件：\n\n" + "\n\n".join([msg.decode('utf-8') for msg in new_messages])
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_text)

        # 保存已发送的邮件ID
        save_sent_email_ids(SENT_EMAILS_FILE, new_email_ids)
    else:
        print("最近3天没有新邮件。")

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
