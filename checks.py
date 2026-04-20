"""Permission and role helpers."""
import discord
from utils.database import get_config, is_blacklisted as _is_bl


async def is_blacklisted(user_id: int) -> bool:
    return await _is_bl(user_id)


async def is_admin(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    cfg = await get_config()
    admin_role_id = cfg.get("roles", {}).get("admin")
    if admin_role_id:
        return any(r.id == admin_role_id for r in member.roles)
    return False


async def user_access_level(member: discord.Member) -> str:
    """Return highest tier the member has access to: booster > premium > free."""
    cfg = await get_config()
    roles = cfg.get("roles", {})
    member_role_ids = {r.id for r in member.roles}

    booster_id = roles.get("booster")
    premium_id = roles.get("premium")

    # Server Nitro booster detection (automatic role assigned by Discord)
    is_nitro_booster = getattr(member, "premium_since", None) is not None

    if (booster_id and booster_id in member_role_ids) or is_nitro_booster:
        return "booster"
    if premium_id and premium_id in member_role_ids:
        return "premium"
    return "free"


async def can_access_category(member: discord.Member, category: str) -> bool:
    level = await user_access_level(member)
    hierarchy = {"free": 0, "premium": 1, "booster": 2}
    return hierarchy.get(level, 0) >= hierarchy.get(category, 0)
