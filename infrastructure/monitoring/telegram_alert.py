import os
import requests
import logging

logger = logging.getLogger(__name__)

class TelegramAlertNotifier:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
    def send_alert(self, message: str):
        if not self.bot_token or not self.chat_id or self.bot_token == "your_telegram_bot_token_here":
            logger.warning(f"Telegram credentials not configured. Would have sent: {message}")
            return False
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram alert sent successfully.")
                return True
            else:
                logger.error(f"Failed to send Telegram alert: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Exception sending Telegram alert: {e}")
            return False

# Global instance for easy import
notifier = TelegramAlertNotifier()

def send_telegram_alert(message: str):
    """Utility function to send alerts easily"""
    return notifier.send_alert(message)
