"""MongoDB-backed async database layer for StockGen Discord bot.

Collections:
    config        - single document {_id: 'bot_config', ...}
    blacklist     - documents {_id: user_id}
    cooldowns     - documents {_id: user_id, last: { 'free/svc': epoch, ... }}
    stats         - documents {_id: user_id, total, by_category, by_service}
    stock         - documents {_id: 'category/service', category, service, items: [str]}
"""
import os
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient

BASE_DIR = Path(__file__).resolve().parent.parent

_client: AsyncIOMotorClient | None = None
_db = None

VALID_CATEGORIES = ("free", "premium", "booster")

DEFAULT_CONFIG = {
    "_id": "bot_config",
    "bot_name": "StockGen",
    "brand": "StockGen - Premium Generator",
    "footer": "StockGen • Premium Gen Bot",
    "colors": {
        "primary": 5793266,
        "success": 3066993,
        "error": 15158332,
        "warning": 15844367,
        "info": 3447003,
        "free": 9807270,
        "premium": 15844367,
        "booster": 16738740,
    },
    "default_cooldowns": {"free": 3600, "premium": 600, "booster": 60},
    "roles": {"premium": None, "booster": None, "admin": None, "blacklisted": None},
    "log_channel": None,
    "gen_channel": None,
    "guild_id": None,
}


def init_db() -> None:
    """Initialize Mongo connection. Call once at bot startup."""
    global _client, _db
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    _client = AsyncIOMotorClient(mongo_url)
    _db = _client[db_name]


def db():
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() at startup.")
    return _db


# --- Config ---
async def get_config() -> dict:
    doc = await db().config.find_one({"_id": "bot_config"})
    if not doc:
        await db().config.insert_one(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    return doc


async def update_config(fields: dict) -> None:
    await db().config.update_one({"_id": "bot_config"}, {"$set": fields}, upsert=True)


# --- Blacklist ---
async def get_blacklist() -> list[int]:
    cursor = db().blacklist.find({}, {"_id": 1})
    return [doc["_id"] async for doc in cursor]


async def is_blacklisted(user_id: int) -> bool:
    return await db().blacklist.find_one({"_id": user_id}) is not None


async def add_blacklist(user_id: int) -> None:
    await db().blacklist.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)


async def remove_blacklist(user_id: int) -> None:
    await db().blacklist.delete_one({"_id": user_id})


# --- Cooldowns ---
async def get_last_gen(user_id: int, category: str, service: str) -> float:
    doc = await db().cooldowns.find_one({"_id": user_id})
    if not doc:
        return 0.0
    return doc.get("last", {}).get(f"{category}/{service}", 0.0)


async def set_last_gen(user_id: int, category: str, service: str, ts: float) -> None:
    await db().cooldowns.update_one(
        {"_id": user_id},
        {"$set": {f"last.{category}/{service}": ts}},
        upsert=True,
    )


# --- Stats ---
async def increment_stat(user_id: int, category: str, service: str) -> None:
    await db().stats.update_one(
        {"_id": user_id},
        {
            "$inc": {
                "total": 1,
                f"by_category.{category}": 1,
                f"by_service.{category}/{service}": 1,
            }
        },
        upsert=True,
    )


async def get_user_stats(user_id: int) -> dict:
    doc = await db().stats.find_one({"_id": user_id})
    return doc or {"total": 0, "by_category": {}, "by_service": {}}


# --- Stock ---
def _stock_id(category: str, service: str) -> str:
    return f"{category}/{service.lower()}"


async def list_services(category: str) -> list[str]:
    cursor = db().stock.find({"category": category}, {"service": 1, "_id": 0})
    return sorted([doc["service"] async for doc in cursor])


async def list_all_stock() -> dict[str, dict[str, int]]:
    result = {cat: {} for cat in VALID_CATEGORIES}
    cursor = db().stock.find({}, {"category": 1, "service": 1, "items": 1, "_id": 0})
    async for doc in cursor:
        cat = doc.get("category")
        if cat in result:
            result[cat][doc["service"]] = len(doc.get("items", []))
    return result


async def count_stock(category: str, service: str) -> int:
    doc = await db().stock.find_one(
        {"_id": _stock_id(category, service)}, {"items": 1, "_id": 0}
    )
    if not doc:
        return 0
    return len(doc.get("items", []))


async def service_exists(category: str, service: str) -> bool:
    return await db().stock.find_one({"_id": _stock_id(category, service)}) is not None


async def create_service(category: str, service: str) -> bool:
    sid = _stock_id(category, service)
    existing = await db().stock.find_one({"_id": sid})
    if existing:
        return False
    await db().stock.insert_one(
        {"_id": sid, "category": category, "service": service.lower(), "items": []}
    )
    return True


async def remove_service(category: str, service: str) -> bool:
    result = await db().stock.delete_one({"_id": _stock_id(category, service)})
    return result.deleted_count > 0


async def add_stock(category: str, service: str, lines: list[str]) -> int:
    clean = [ln.strip() for ln in lines if ln.strip()]
    if not clean:
        return 0
    sid = _stock_id(category, service)
    await db().stock.update_one(
        {"_id": sid},
        {
            "$setOnInsert": {"category": category, "service": service.lower()},
            "$push": {"items": {"$each": clean}},
        },
        upsert=True,
    )
    return len(clean)


async def pop_stock(category: str, service: str) -> str | None:
    """Atomically remove and return the first item from the stock list."""
    sid = _stock_id(category, service)
    doc = await db().stock.find_one_and_update(
        {"_id": sid, "items.0": {"$exists": True}},
        {"$pop": {"items": -1}},
        projection={"items": {"$slice": 1}, "_id": 0},
    )
    if not doc:
        return None
    items = doc.get("items", [])
    return items[0] if items else None
