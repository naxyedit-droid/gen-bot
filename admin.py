"""Admin cog - setup, blacklist, cooldowns, stats."""
import discord
from discord import app_commands
from discord.ext import commands

from utils import database as db
from utils import embeds
from utils.checks import is_admin


CATEGORY_CHOICES = [
    app_commands.Choice(name="🆓 Free", value="free"),
    app_commands.Choice(name="💎 Premium", value="premium"),
    app_commands.Choice(name="🚀 Booster", value="booster"),
]


def admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=await embeds.error("Server Only", "Use this in a server."),
                ephemeral=True,
            )
            return False
        if not await is_admin(interaction.user):
            await interaction.response.send_message(
                embed=await embeds.error("Permission Denied", "Administrator only."),
                ephemeral=True,
            )
            return False
        return True

    return app_commands.check(predicate)


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- /setup ----------
    @app_commands.command(name="setup", description="Configure gen channel, log channel, and tier roles.")
    @app_commands.describe(
        gen_channel="Channel where /gen is allowed (optional)",
        log_channel="Channel where generations are logged (optional)",
        premium_role="Role granted Premium access (optional)",
        booster_role="Role granted Booster access (optional)",
        admin_role="Role that can manage stock (optional)",
    )
    @admin_only()
    async def setup_cmd(
        self,
        interaction: discord.Interaction,
        gen_channel: discord.TextChannel = None,
        log_channel: discord.TextChannel = None,
        premium_role: discord.Role = None,
        booster_role: discord.Role = None,
        admin_role: discord.Role = None,
    ):
        updates = {"guild_id": interaction.guild_id}
        if gen_channel:
            updates["gen_channel"] = gen_channel.id
        if log_channel:
            updates["log_channel"] = log_channel.id
        role_updates = {}
        if premium_role:
            role_updates["roles.premium"] = premium_role.id
        if booster_role:
            role_updates["roles.booster"] = booster_role.id
        if admin_role:
            role_updates["roles.admin"] = admin_role.id

        await db.update_config(updates)
        if role_updates:
            await db.db().config.update_one(
                {"_id": "bot_config"}, {"$set": role_updates}, upsert=True
            )

        desc_lines = []
        if gen_channel:
            desc_lines.append(f"**Gen Channel:** {gen_channel.mention}")
        if log_channel:
            desc_lines.append(f"**Log Channel:** {log_channel.mention}")
        if premium_role:
            desc_lines.append(f"**Premium Role:** {premium_role.mention}")
        if booster_role:
            desc_lines.append(f"**Booster Role:** {booster_role.mention}")
        if admin_role:
            desc_lines.append(f"**Admin Role:** {admin_role.mention}")
        if not desc_lines:
            desc_lines.append("No values provided. Provide at least one option.")

        await interaction.response.send_message(
            embed=await embeds.success("Setup Updated", "\n".join(desc_lines)),
            ephemeral=True,
        )

    # ---------- /setcooldown ----------
    @app_commands.command(name="setcooldown", description="Set cooldown (seconds) for a category.")
    @app_commands.describe(category="Section", seconds="Cooldown in seconds")
    @app_commands.choices(category=CATEGORY_CHOICES)
    @admin_only()
    async def setcooldown(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        seconds: app_commands.Range[int, 0, 604800],
    ):
        await db.db().config.update_one(
            {"_id": "bot_config"},
            {"$set": {f"default_cooldowns.{category.value}": seconds}},
            upsert=True,
        )
        await interaction.response.send_message(
            embed=await embeds.success(
                "Cooldown Updated",
                f"**{category.value.upper()}** cooldown set to `{seconds}` seconds.",
            ),
            ephemeral=True,
        )

    # ---------- /blacklist ----------
    @app_commands.command(name="blacklist", description="Blacklist a user from using the bot.")
    @app_commands.describe(user="User to blacklist")
    @admin_only()
    async def blacklist(self, interaction: discord.Interaction, user: discord.User):
        await db.add_blacklist(user.id)
        await interaction.response.send_message(
            embed=await embeds.success("User Blacklisted", f"{user.mention} has been blacklisted."),
            ephemeral=True,
        )

    # ---------- /unblacklist ----------
    @app_commands.command(name="unblacklist", description="Remove a user from the blacklist.")
    @app_commands.describe(user="User to unblacklist")
    @admin_only()
    async def unblacklist(self, interaction: discord.Interaction, user: discord.User):
        await db.remove_blacklist(user.id)
        await interaction.response.send_message(
            embed=await embeds.success("User Unblacklisted", f"{user.mention} can now use the bot."),
            ephemeral=True,
        )

    # ---------- /stats ----------
    @app_commands.command(name="stats", description="View your (or another user's) generation stats.")
    @app_commands.describe(user="Target user (optional)")
    async def stats(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        s = await db.get_user_stats(target.id)
        total = s.get("total", 0)
        by_cat = s.get("by_category", {})

        embed = await embeds.branded(
            f"📊  Stats for {target.display_name}",
            f"**Total Gens:** `{total}`",
        )
        embed.add_field(name="🆓 Free", value=f"`{by_cat.get('free', 0)}`", inline=True)
        embed.add_field(name="💎 Premium", value=f"`{by_cat.get('premium', 0)}`", inline=True)
        embed.add_field(name="🚀 Booster", value=f"`{by_cat.get('booster', 0)}`", inline=True)

        by_service = s.get("by_service", {})
        if by_service:
            top = sorted(by_service.items(), key=lambda x: -x[1])[:5]
            embed.add_field(
                name="Top Services",
                value="\n".join(f"`{svc}` — **{n}**" for svc, n in top),
                inline=False,
            )

        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
