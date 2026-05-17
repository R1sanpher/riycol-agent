import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from core.plugin_loader import PluginInfo
from core.logger import log
from core.config import CFG

_bot = None


def register():
    return PluginInfo(name='discord', version='1.0',
                       description='Discord bot with slash commands and notifications')


def start():
    global _bot
    if not CFG.DISCORD_BOT_TOKEN:
        log.warn('discord: no token, disabled')
        return
    from plugins.discord.bot import DiscordBot
    _bot = DiscordBot()
    _bot.start()
    log.info('discord plugin started')


def stop():
    global _bot
    if _bot:
        _bot.stop()
        _bot = None


def send_notification(user_id: str, message: str) -> bool:
    """Send a DM notification to a Discord user.

    Thread-safe. Returns True if queued, False if bot not running.
    Callable from any module::

        from plugins.discord import send_notification
        send_notification("123456789", "Task complete!")
    """
    global _bot
    if _bot is None:
        return False
    return _bot.send_dm(user_id, message)
