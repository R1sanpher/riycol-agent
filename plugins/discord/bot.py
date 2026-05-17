"""DiscordBot — wraps discord.py 2.x in a background thread.

Reuses AIChat from the Telegram plugin for LLM routing (90/10 local/cloud).
Provides slash commands /chat and /ask, plus DM notification support.
"""
import asyncio
import os
import re
import threading
import discord
from discord import app_commands
from core.config import CFG
from core.logger import log
from core.memory_store import memory_store
from plugins.telegram.ai import AIChat

DISCORD_MAX_MSG_LEN = 2000
MEMORY_AGENT_NAME = "discord"


class DiscordBot:
    def __init__(self):
        self.ai = AIChat(model=CFG.DISCORD_MODEL)  # Reuse Telegram's AIChat
        self.running = False
        self._thread = None
        self._loop = None
        self._proxy = None

        # Parse allowed users (same pattern as Telegram)
        self._allowed_users: set[int] = set()
        allowed_str = CFG.DISCORD_ALLOWED_USERS
        if allowed_str:
            for part in allowed_str.split(","):
                part = part.strip()
                if part.isdigit():
                    self._allowed_users.add(int(part))

        # Discord client setup
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)

        self._register_handlers()

    def _register_handlers(self):
        @self.client.event
        async def on_ready():
            await self.tree.sync()
            log.info(f"Discord bot logged in as {self.client.user} (ID: {self.client.user.id})")

        @self.client.event
        async def on_disconnect():
            log.warn("Discord bot disconnected from gateway")

        @self.client.event
        async def on_resumed():
            log.info("Discord bot resumed connection")

        @self.tree.command(name="chat", description="Chat with Riycol AI (remembers conversation)")
        @app_commands.describe(message="Your message for the AI")
        async def chat_slash(interaction: discord.Interaction, message: str):
            await self._handle_slash(interaction, message)

        @self.tree.command(name="ask", description="Ask Riycol AI a one-shot question (no history)")
        @app_commands.describe(question="Your question for the AI")
        async def ask_slash(interaction: discord.Interaction, question: str):
            await self._handle_ask(interaction, question)

    def _check_allowed(self, user_id: int) -> bool:
        return not self._allowed_users or user_id in self._allowed_users

    def _save_dm_channel(self, user_id: int):
        """Record that this user can receive DMs."""
        try:
            memory_store.put(MEMORY_AGENT_NAME, f"user_{user_id}", str(user_id))
        except Exception:
            pass

    async def _handle_slash(self, interaction: discord.Interaction, message: str):
        """Slash command /chat — uses AIChat with conversation history."""
        if not self._check_allowed(interaction.user.id):
            await interaction.response.send_message("You are not authorized.", ephemeral=True)
            return

        self._save_dm_channel(interaction.user.id)
        await interaction.response.defer()

        user_key = f"discord_{interaction.user.id}"
        reply = await asyncio.to_thread(self.ai.get_reply, user_key, message)

        await self._send_chunks(interaction.followup.send, reply)

    async def _handle_ask(self, interaction: discord.Interaction, question: str):
        """Slash command /ask — one-shot question."""
        if not self._check_allowed(interaction.user.id):
            await interaction.response.send_message("You are not authorized.", ephemeral=True)
            return

        self._save_dm_channel(interaction.user.id)
        await interaction.response.defer()

        user_key = f"discord_{interaction.user.id}"
        reply = await asyncio.to_thread(self.ai.get_reply, user_key, question)

        await self._send_chunks(interaction.followup.send, reply)

    async def _send_chunks(self, send_fn, text: str):
        """Split text at 2000-char boundaries and send each chunk."""
        chunks = self._split_text(text)
        for chunk in chunks:
            await send_fn(chunk)

    @staticmethod
    def _split_text(text: str) -> list[str]:
        """Split long text at paragraph/word boundaries to fit Discord's 2000-char limit."""
        if len(text) <= DISCORD_MAX_MSG_LEN:
            return [text]
        chunks = []
        while len(text) > DISCORD_MAX_MSG_LEN:
            split_at = text.rfind("\n", 0, DISCORD_MAX_MSG_LEN)
            if split_at == -1:
                split_at = text.rfind(" ", 0, DISCORD_MAX_MSG_LEN)
            if split_at == -1:
                split_at = DISCORD_MAX_MSG_LEN
            chunks.append(text[:split_at].strip())
            text = text[split_at:].strip()
        if text:
            chunks.append(text)
        return chunks

    def send_dm(self, user_id: str, message: str) -> bool:
        """Thread-safe public API to send DM. Called from outside async context."""
        if not self._loop or not self._loop.is_running():
            return False
        coro = self._send_dm_async(str(user_id), message)
        asyncio.run_coroutine_threadsafe(coro, self._loop)
        return True

    async def _send_dm_async(self, user_id: str, message: str):
        """Internal async method to send DM."""
        try:
            uid = int(user_id)
            user = self.client.get_user(uid)
            if user is None:
                try:
                    user = await self.client.fetch_user(uid)
                except discord.NotFound:
                    log.warn(f"Discord: user {user_id} not found for DM")
                    return
                except discord.HTTPException:
                    log.warn(f"Discord: could not fetch user {user_id}")
                    return

            chunks = self._split_text(message)
            for chunk in chunks:
                await user.send(chunk)
            log.info(f"Discord: DM sent to user {user_id} ({len(message)} chars)")
        except discord.Forbidden:
            log.warn(f"Discord: cannot DM user {user_id} (DMs closed)")
        except Exception as e:
            log.error(f"Discord: DM error for user {user_id}: {e}")

    def start(self):
        """Start the Discord bot in a background thread."""
        self.running = True
        # Apply proxy from TG_PROXY for Discord (China network)
        proxy = CFG.TG_PROXY
        if proxy:
            self._proxy = proxy
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy
            log.info(f"Discord bot using proxy: {proxy}")
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="discord-bot")
        self._thread.start()
        log.info("Discord bot thread started")

    def _run_loop(self):
        """Run the asyncio event loop in this thread."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self.client.start(CFG.DISCORD_BOT_TOKEN))
            except Exception as e:
                log.error(f"Discord bot error: {e}")
            finally:
                try:
                    self._loop.close()
                except Exception:
                    pass
                if self.running:
                    log.warn("Discord bot disconnected unexpectedly")
        except Exception as e:
            log.error(f"Discord bot thread crashed: {e}")

    def stop(self):
        """Gracefully stop the bot."""
        self.running = False
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.client.close(), self._loop)
        # Clean up proxy env vars
        if self._proxy:
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)
        log.info("Discord bot stopped")
