from __future__ import annotations

from typing import Any, Optional

from .util import utcnow_iso


class BountyStore:
    """All Config CRUD lives here."""

    def __init__(self, config):
        self.config = config

    async def get_all(self, guild) -> dict[str, dict[str, Any]]:
        return await self.config.guild(guild).bounties()

    async def get(self, guild, bounty_id: int) -> Optional[dict[str, Any]]:
        return (await self.get_all(guild)).get(str(bounty_id))

    async def save(self, guild, bounty: dict[str, Any]) -> None:
        bounty["updated_at"] = utcnow_iso()
        async with self.config.guild(guild).bounties() as b:
            b[str(bounty["id"])] = bounty

    async def delete(self, guild, bounty_id: int) -> None:
        async with self.config.guild(guild).bounties() as b:
            b.pop(str(bounty_id), None)

    async def allocate_id(self, guild) -> int:
        async with self.config.guild(guild).all() as g:
            bid = int(g["next_id"])
            g["next_id"] = bid + 1
            return bid

    async def find_by_key(self, guild, key: str) -> Optional[dict[str, Any]]:
        """key: int-like id OR exact title (case-insensitive)."""
        all_b = await self.get_all(guild)

        try:
            bid = int(key)
            return all_b.get(str(bid))
        except ValueError:
            pass

        k = key.strip().casefold()
        for b in all_b.values():
            if b.get("title", "").strip().casefold() == k:
                return b
        return None

    async def title_in_use(self, guild, title: str, *, exclude_id: int | None = None) -> bool:
        k = title.strip().casefold()
        all_b = await self.get_all(guild)
        for b in all_b.values():
            if exclude_id is not None and int(b.get("id", -1)) == exclude_id:
                continue
            if b.get("title", "").strip().casefold() == k:
                return True
        return False
