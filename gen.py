"""Generation command cog - /gen with Free/Premium/Booster sections."""
import time
import discord
from discord import app_commands
from discord.ext import commands

from utils import database as db
from utils import embeds
from utils.checks import is_blacklisted, user_access_level, can_access_category


CATEGORY_CHOICES = [
    app_commands.Choice(name="🆓 Free", value="free"),
    app_commands.Choice(name="💎 Premium", value="premium"),
    app_commands.Choice(name="🚀 Booster", value="booster"),
]


class Gen(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _service_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        category = None
        for opt in interaction.data.get("options", []):
            if opt.get("name") == "category":
                category = opt.get("value")
                break
        if not category:
            return []
        services = await db.list_services(category)
        current = (current or "").lower()
        matches = [s for s in services if current in s.lower()][:25]
        return [app_commands.Choice(name=s, value=s) for s in matches]

    @app_commands.command(name="gen", description="Generate an item from Free, Premium, or Booster stock.")
    @app_commands.describe(category="Section to generate from", service="Service name")
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def gen(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        service: str,
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)
        cat = category.value
        service = service.strip().lower()

        # Blacklist
        if await is_blacklisted(interaction.user.id):
            return await interaction.followup.send(
                embed=await embeds.error("Blacklisted", "You are blacklisted from using this bot."),
                ephemeral=True,
            )

        # Gen channel check
        cfg = await db.get_config()
        gen_channel = cfg.get("gen_channel")
        if gen_channel and interaction.channel_id != gen_channel:
            channel_mention = f"<#{gen_channel}>"
            return await interaction.followup.send(
                embed=await embeds.error(
                    "Wrong Channel", f"Please use the gen command in {channel_mention}."
                ),
                ephemeral=True,
            )

        # Access level
        if interaction.guild is None:
            return await interaction.followup.send(
                embed=await embeds.error("Server Only", "Use this command inside a server."),
                ephemeral=True,
            )

        if not await can_access_category(interaction.user, cat):
            level = await user_access_level(interaction.user)
            return await interaction.followup.send(
                embed=await embeds.error(
                    "Access Denied",
                    f"Your tier is **{level.upper()}**. You cannot generate from **{cat.upper()}**.\n"
                    f"Upgrade by boosting the server or purchasing the premium role.",
                ),
                ephemeral=True,
            )

        # Service must exist
        if not await db.service_exists(cat, service):
            services = await db.list_services(cat)
            avail = ", ".join(f"`{s}`" for s in services) if services else "*none*"
            return await interaction.followup.send(
                embed=await embeds.error(
                    "Service Not Found",
                    f"`{service}` does not exist in **{cat.upper()}**.\n\nAvailable: {avail}",
                ),
                ephemeral=True,
            )

        # Cooldown
        cooldown = cfg.get("default_cooldowns", {}).get(cat, 0)
        last = await db.get_last_gen(interaction.user.id, cat, service)
        now = time.time()
        if cooldown and (now - last) < cooldown:
            remaining = int(cooldown - (now - last))
            mins, secs = divmod(remaining, 60)
            hrs, mins = divmod(mins, 60)
            parts = []
            if hrs:
                parts.append(f"{hrs}h")
            if mins:
                parts.append(f"{mins}m")
            parts.append(f"{secs}s")
            return await interaction.followup.send(
                embed=await embeds.warning(
                    "Cooldown Active",
                    f"Wait **{' '.join(parts)}** before generating `{service}` again.",
                ),
                ephemeral=True,
            )

        # Pop stock
        item = await db.pop_stock(cat, service)
        if not item:
            return await interaction.followup.send(
                embed=await embeds.error(
                    "Out of Stock",
                    f"No items left in **{cat.upper()} / {service}**. Please try again later.",
                ),
                ephemeral=True,
            )

        remaining = await db.count_stock(cat, service)

        # DM the user
        delivered = True
        try:
            await interaction.user.send(
                embed=await embeds.gen_delivery(cat, service, item, remaining)
            )
        except (discord.Forbidden, discord.HTTPException):
            delivered = False
            # Re-add the item back since we couldn't deliver
            await db.add_stock(cat, service, [item])

        if not delivered:
            return await interaction.followup.send(
                embed=await embeds.error(
                    "DMs Closed",
                    "I could not DM you. Please enable DMs from server members and try again.\n"
                    "Your item has been returned to stock.",
                ),
                ephemeral=True,
            )

        # Cooldown set + stats
        await db.set_last_gen(interaction.user.id, cat, service, now)
        await db.increment_stat(interaction.user.id, cat, service)

        # Reply in channel + log
        await interaction.followup.send(
            embed=await embeds.gen_public(cat, service, interaction.user),
            ephemeral=False,
        )

        log_channel_id = cfg.get("log_channel")
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = await embeds.info(
                    "📝 Generation Log",
                    f"**User:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"**Category:** `{cat.upper()}`\n"
                    f"**Service:** `{service}`\n"
                    f"**Remaining Stock:** `{remaining}`",
                )
                try:
                    await log_channel.send(embed=log_embed)
                except discord.HTTPException:
                    pass

    @gen.autocomplete("service")
    async def _svc_ac(self, interaction: discord.Interaction, current: str):
        return await self._service_autocomplete(interaction, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(Gen(bot))
