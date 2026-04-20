"""Beautiful help command with categorized embeds."""
import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all bot commands with usage.")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = await embeds.branded(
            "📖  StockGen Commands",
            "A premium generator bot with **Free**, **Premium**, and **Booster** tiers.\n"
            "Use the commands below to manage your server's stock.",
        )

        embed.add_field(
            name="🎯  Generator",
            value=(
                "`/gen <category> <service>` — Generate an item. Item is DM'd to you.\n"
                "`/stock` — Show all available services and counts.\n"
                "`/stats [user]` — View generation stats."
            ),
            inline=False,
        )

        embed.add_field(
            name="📦  Stock Management (Admin)",
            value=(
                "`/addservice <category> <name>` — Create a new service.\n"
                "`/removeservice <category> <name>` — Delete a service.\n"
                "`/addstock <category> <service> <items>` — Add lines (newline-separated).\n"
                "`/addstockfile <category> <service> <file>` — Upload a .txt of items.\n"
                "`/removestock <category> <service>` — Clear stock in a service."
            ),
            inline=False,
        )

        embed.add_field(
            name="🛠️  Admin",
            value=(
                "`/setup` — Configure gen channel, log channel, and tier roles.\n"
                "`/setcooldown <category> <seconds>` — Set cooldown per category.\n"
                "`/blacklist <user>` / `/unblacklist <user>` — Manage blacklist."
            ),
            inline=False,
        )

        embed.add_field(
            name="💎  Tier Access",
            value=(
                "**Free** — everyone\n"
                "**Premium** — requires premium role (set via `/setup`)\n"
                "**Booster** — server boosters, or members with booster role"
            ),
            inline=False,
        )

        embed.add_field(
            name="ℹ️  Notes",
            value="• Generated items are sent via DM. Enable DMs from server members.\n"
            "• Each generation is logged (if log channel is set).",
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
