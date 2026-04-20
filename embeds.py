"""Branded embed factory for a consistent professional UI."""
import discord
from datetime import datetime, timezone
from utils.database import get_config


async def _cfg():
    return await get_config()


async def _color(kind: str) -> discord.Color:
    cfg = await _cfg()
    c = cfg.get("colors", {})
    return discord.Color(c.get(kind, 5793266))


async def _footer(embed: discord.Embed) -> discord.Embed:
    cfg = await _cfg()
    embed.set_footer(text=cfg.get("footer", "StockGen"))
    embed.timestamp = datetime.now(timezone.utc)
    return embed


async def success(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"✅  {title}", description=description, color=await _color("success"))
    return await _footer(e)


async def error(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"❌  {title}", description=description, color=await _color("error"))
    return await _footer(e)


async def warning(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"⚠️  {title}", description=description, color=await _color("warning"))
    return await _footer(e)


async def info(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=await _color("info"))
    return await _footer(e)


async def branded(title: str, description: str = "", kind: str = "primary") -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=await _color(kind))
    return await _footer(e)


async def gen_delivery(category: str, service: str, item: str, remaining: int) -> discord.Embed:
    cat_emoji = {"free": "🆓", "premium": "💎", "booster": "🚀"}.get(category, "📦")
    color = await _color(category if category in ("free", "premium", "booster") else "primary")
    e = discord.Embed(
        title=f"{cat_emoji}  {service.title()}  •  Delivery",
        description=f"```{item}```",
        color=color,
    )
    e.add_field(name="Category", value=f"`{category.upper()}`", inline=True)
    e.add_field(name="Service", value=f"`{service}`", inline=True)
    e.add_field(name="Remaining Stock", value=f"`{remaining}`", inline=True)
    e.add_field(
        name="Notice",
        value="Please do **not** share this item. Each generation is logged.",
        inline=False,
    )
    return await _footer(e)


async def gen_public(category: str, service: str, user: discord.abc.User) -> discord.Embed:
    cat_emoji = {"free": "🆓", "premium": "💎", "booster": "🚀"}.get(category, "📦")
    color = await _color(category if category in ("free", "premium", "booster") else "primary")
    e = discord.Embed(
        title=f"{cat_emoji}  Generation Successful",
        description=f"{user.mention} generated **{service}** from **{category.upper()}**.\nCheck your **Direct Messages** for the item.",
        color=color,
    )
    return await _footer(e)
