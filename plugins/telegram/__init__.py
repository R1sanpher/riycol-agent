import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from core.plugin_loader import PluginInfo
from core.logger import log
from core.config import CFG

_bot = None

def register():
    return PluginInfo(name='telegram', version='2.0', description='Telegram bot')

def start():
    global _bot
    if not CFG.TELEGRAM_TOKEN:
        log.warn('telegram: no token, disabled')
        return
    from plugins.telegram.bot import TelegramBot
    _bot = TelegramBot()
    _bot.start()
    log.info('telegram plugin started')

def stop():
    global _bot
    if _bot: _bot.stop()
