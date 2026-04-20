"""
StockGen - Professional Discord Gen Bot
Entry point. Loads cogs, connects to MongoDB, syncs slash commands.
"""
import os
import asyncio
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv
from colorama import Fore, Style, init as colorama_init

from utils import database as db


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

colorama_init(autoreset=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stockgen")


intents = discord.Intents.default()
intents.members = True
intents.message_content = False  # slash commands only


class StockGenBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self) -> None:
        db.init_db()
        await db.get_config()  # seed default config if missing

        for cog in ("cogs.gen", "cogs.stock", "cogs.admin", "cogs.help"):
            await self.load_extension(cog)
            log.info(f"Loaded extension: {cog}")

        synced = await self.tree.sync()
        log.info(f"Synced {len(synced)} slash commands.")

    async def on_ready(self):
        print()
        print(Fore.MAGENTA + Style.BRIGHT + "╔══════════════════════════════════════════╗")
        print(Fore.MAGENTA + Style.BRIGHT + "║          StockGen  •  Online             ║")
        print(Fore.MAGENTA + Style.BRIGHT + "╚══════════════════════════════════════════╝")
        print(Fore.CYAN + f"  Logged in as  : {Style.BRIGHT}{self.user}")
        print(Fore.CYAN + f"  User ID       : {Style.BRIGHT}{self.user.id}")
        print(Fore.CYAN + f"  Guilds        : {Style.BRIGHT}{len(self.guilds)}")
        print(Fore.CYAN + f"  discord.py    : {Style.BRIGHT}{discord.__version__}")
        print()
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(type=discord.ActivityType.watching, name="/gen • /help"),
        )


async def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print(Fore.RED + "✖ DISCORD_TOKEN is missing. Copy .env.example to .env and set your token.")
        return
    if not os.environ.get("MONGO_URL") or not os.environ.get("DB_NAME"):
        print(Fore.RED + "✖ MONGO_URL or DB_NAME is missing in .env.")
        return

    bot = StockGenBot()
    try:
        await bot.start(token)
    except discord.LoginFailure:
        print(Fore.RED + "✖ Invalid Discord token.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nShutting down…")
