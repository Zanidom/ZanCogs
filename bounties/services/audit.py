from __future__ import annotations

import discord


class AuditService:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    async def _get_messageable(self, guild: discord.Guild):
        audit_id = await self.config.guild(guild).audit_channel_id()
        if not audit_id:
            return None
        ch = guild.get_channel(audit_id)
        if ch:
            return ch
        try:
            return await guild.fetch_channel(audit_id)
        except Exception:
            return None

    async def log(self, guild: discord.Guild, content: str | None = None, *, embed: discord.Embed | None = None):
        target = await self._get_messageable(guild)
        if not target:
            return
        try:
            await target.send(content=content, embed=embed)
        except Exception:
            pass
