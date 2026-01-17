from __future__ import annotations
import discord
from redbot.core import app_commands


def register(bounty_group: app_commands.Group, cog):
    @bounty_group.command(name="list", description="List all active bounties.")
    @app_commands.guild_only()
    async def lst(interaction: discord.Interaction):
        assert interaction.guild is not None
        if await cog._blocked(interaction):
            return

        bounties = list((await cog.store.get_all(interaction.guild)).values())
        bounties.sort(key=lambda b: b["id"])
        if not bounties:
            await interaction.response.send_message("No active bounties.", ephemeral=True)
            return

        lines = []
        for b in bounties:
            owner = interaction.guild.get_member(b["owner_id"])
            owner_name = owner.display_name if owner else str(b["owner_id"])
            lines.append(f"#{b['id']} - “{b['title']}” - {owner_name}")

        chunks = []
        cur = ""
        for ln in lines:
            if len(cur) + len(ln) + 1 > 1900:
                chunks.append(cur)
                cur = ""
            cur += ln + "\n"
        if cur:
            chunks.append(cur)

        await interaction.response.send_message(chunks[0], ephemeral=False)
        for c in chunks[1:]:
            await interaction.followup.send(c, ephemeral=False)
