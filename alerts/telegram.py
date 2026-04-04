import requests
from core.config import Config
from core.logger import logger

class TelegramAlert:
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f'https://api.telegram.org/bot{self.bot_token}'

    async def send_message(self, message: str) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.warning('Telegram credentials not configured')
            return False

        url = f'{self.base_url}/sendMessage'
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info('Telegram message sent')
                return True
            else:
                logger.error(f'Telegram API error: {response.text}')
                return False
        except Exception as e:
            logger.error(f'Failed to send Telegram message: {e}')
            return False

    async def send_photo(self, photo_url: str, caption: str = '') -> bool:
        if not self.bot_token or not self.chat_id:
            return False

        url = f'{self.base_url}/sendPhoto'
        payload = {
            'chat_id': self.chat_id,
            'photo': photo_url,
            'caption': caption
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f'Failed to send Telegram photo: {e}')
            return False
