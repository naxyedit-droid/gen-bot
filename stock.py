"""Stock management cog - add, remove, view stock & services."""
import io
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
                embed=await embeds.error("Permission Denied", "You need administrator permission."),
                ephemeral=True,
            )
            return False
        return True

    return app_commands.check(predicate)


class Stock(commands.Cog):
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
            # Handle subcommand nesting
            for sub in opt.get("options", []) or []:
                if sub.get("name") == "category":
                    category = sub.get("value")
                    break
        if not category:
            return []
        services = await db.list_services(category)
        current = (current or "").lower()
        return [app_commands.Choice(name=s, value=s) for s in services if current in s.lower()][:25]

    # ---------- /stock ----------
    @app_commands.command(name="stock", description="View current stock across all sections.")
    async def stock(self, interaction: discord.Interaction):
        await interaction.response.defer()
        all_stock = await db.list_all_stock()
        total = sum(sum(v.values()) for v in all_stock.values())

        embed = await embeds.branded(
            "📦  Stock Overview",
            f"Total items available: **{total}**",
        )

        for cat in ("free", "premium", "booster"):
            services = all_stock.get(cat, {})
            if not services:
                value = "*no services*"
            else:
                lines = [f"`{svc}` — **{cnt}**" for svc, cnt in sorted(services.items())]
                value = "\n".join(lines) or "*empty*"
            emoji = {"free": "🆓", "premium": "💎", "booster": "🚀"}[cat]
            embed.add_field(
                name=f"{emoji}  {cat.upper()}  ({sum(services.values())})",
                value=value[:1024],
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    # ---------- /addservice ----------
    @app_commands.command(name="addservice", description="Create a new empty service in a section.")
    @app_commands.describe(category="Section", service="Service name (e.g. netflix)")
    @app_commands.choices(category=CATEGORY_CHOICES)
    @admin_only()
    async def addservice(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        service: str,
    ):
        service = service.strip().lower().replace(" ", "_")
        if not service.replace("_", "").replace("-", "").isalnum():
            return await interaction.response.send_message(
                embed=await embeds.error("Invalid Name", "Use letters, numbers, `-`, or `_` only."),
                ephemeral=True,
            )
        created = await db.create_service(category.value, service)
        if not created:
            return await interaction.response.send_message(
                embed=await embeds.warning("Already Exists", f"`{service}` already exists in `{category.value}`."),
                ephemeral=True,
            )
        await interaction.response.send_message(
            embed=await embeds.success(
                "Service Created",
                f"Created `{service}` in **{category.value.upper()}**. Use `/addstock` to add items.",
            )
        )

    # ---------- /removeservice ----------
    @app_commands.command(name="removeservice", description="Delete a service entirely.")
    @app_commands.describe(category="Section", service="Service name")
    @app_commands.choices(category=CATEGORY_CHOICES)
    @admin_only()
    async def removeservice(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        service: str,
    ):
        service = service.strip().lower()
        removed = await db.remove_service(category.value, service)
        if not removed:
            return await interaction.response.send_message(
                embed=await embeds.error("Not Found", f"`{service}` doesn't exist in `{category.value}`."),
                ephemeral=True,
            )
        await interaction.response.send_message(
            embed=await embeds.success("Service Removed", f"Deleted `{service}` from **{category.value.upper()}**.")
        )

    @removeservice.autocomplete("service")
    async def _rs_ac(self, interaction, current):
        return await self._service_autocomplete(interaction, current)

    # ---------- /addstock (text) ----------
    @app_commands.command(name="addstock", description="Add stock lines to a service (newline-separated).")
    @app_commands.describe(
        category="Section",
        service="Service name",
        items="Stock items separated by newlines (or | for single line)",
    )
    @app_commands.choices(category=CATEGORY_CHOICES)
    @admin_only()
    async def addstock(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        service: str,
        items: str,
    ):
        service = service.strip().lower()
        raw_lines = items.replace("|", "\n").splitlines()
        added = await db.add_stock(category.value, service, raw_lines)
        if added == 0:
            return await interaction.response.send_message(
                embed=await embeds.error("Nothing Added", "No valid lines were found."),
                ephemeral=True,
            )
        total = await db.count_stock(category.value, service)
        await interaction.response.send_message(
            embed=await embeds.success(
                "Stock Added",
                f"Added **{added}** items to `{category.value}/{service}`.\nTotal now: **{total}**",
            ),
            ephemeral=True,
        )

    @addstock.autocomplete("service")
    async def _as_ac(self, interaction, current):
        return await self._service_autocomplete(interaction, current)

    # ---------- /addstockfile ----------
    @app_commands.command(name="addstockfile", description="Upload a .txt file to add stock (one item per line).")
    @app_commands.describe(category="Section", service="Service name", file=".txt file with lines")
    @app_commands.choices(category=CATEGORY_CHOICES)
    @admin_only()
    async def addstockfile(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        service: str,
        file: discord.Attachment,
    ):
        service = service.strip().lower()
        if file.size > 5 * 1024 * 1024:
            return await interaction.response.send_message(
                embed=await embeds.error("File Too Large", "Max 5 MB."),
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        raw = await file.read()
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        lines = text.splitlines()
        added = await db.add_stock(category.value, service, lines)
        total = await db.count_stock(category.value, service)
        await interaction.followup.send(
            embed=await embeds.success(
                "Stock Added (file)",
                f"Added **{added}** items from `{file.filename}` to `{category.value}/{service}`.\nTotal now: **{total}**",
            ),
            ephemeral=True,
        )

    @addstockfile.autocomplete("service")
    async def _asf_ac(self, interaction, current):
        return await self._service_autocomplete(interaction, current)

    # ---------- /removestock ----------
    @app_commands.command(name="removestock", description="Clear ALL stock lines of a service (keeps service).")
    @app_commands.describe(category="Section", service="Service name")
    @app_commands.choices(category=CATEGORY_CHOICES)
    @admin_only()
    async def removestock(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        service: str,
    ):
        service = service.strip().lower()
        if not await db.service_exists(category.value, service):
            return await interaction.response.send_message(
                embed=await embeds.error("Not Found", f"`{service}` doesn't exist."),
                ephemeral=True,
            )
        # Clear items by removing & re-creating
        await db.db().stock.update_one(
            {"_id": f"{category.value}/{service}"},
            {"$set": {"items": []}},
        )
        await interaction.response.send_message(
            embed=await embeds.success("Stock Cleared", f"All stock removed from `{category.value}/{service}`."),
            ephemeral=True,
        )

    @removestock.autocomplete("service")
    async def _rst_ac(self, interaction, current):
        return await self._service_autocomplete(interaction, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stock(bot))
