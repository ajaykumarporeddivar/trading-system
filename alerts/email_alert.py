import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.config import Config
from core.logger import logger

class EmailAlert:
    def __init__(self):
        self.smtp_server = Config.SMTP_SERVER
        self.smtp_port = Config.SMTP_PORT
        self.email_user = Config.EMAIL_USER
        self.email_password = Config.EMAIL_PASSWORD
        self.alert_email = Config.ALERT_EMAIL

    async def send_email(self, subject: str, body: str) -> bool:
        if not self.email_user or not self.email_password:
            logger.warning('Email credentials not configured')
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.alert_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)

            logger.info(f'Email sent: {subject}')
            return True
        except Exception as e:
            logger.error(f'Failed to send email: {e}')
            return False
