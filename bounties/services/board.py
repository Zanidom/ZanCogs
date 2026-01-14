from __future__ import annotations

from typing import Any
import discord


class BoardService:
    """Keeps one message per bounty in a configured board channel/thread."""

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    async def _get_messageable(self, guild: discord.Guild):
        board_id = await self.config.guild(guild).board_channel_id()
        if not board_id:
            return None
        ch = guild.get_channel(board_id)
        if ch:
            return ch
        try:
            return await guild.fetch_channel(board_id)
        except Exception:
            return None

    async def upsert(self, guild: discord.Guild, bounty: dict[str, Any], embed: discord.Embed) -> Optional[int]:
        target = await self._get_messageable(guild)
        if not target:
            return None

        msg_id = bounty.get("board_message_id")
        if msg_id:
            try:
                msg = await target.fetch_message(int(msg_id))
                await msg.edit(embed=embed)
                return msg.id
            except: 
                pass

        #fallback mechanism: post new embed (icky)
        try:
            msg = await target.send(embed=embed)
            return msg.id
        except:
            pass
        return None

    async def delete(self, guild: discord.Guild, bounty: dict[str, Any]):
        target = await self._get_messageable(guild)
        if not target:
            return

        msg_id = bounty.get("board_message_id")
        if not msg_id:
            return

        try:
            msg = await target.fetch_message(msg_id)
            await msg.delete()
        except Exception:
            pass
