from __future__ import annotations
import discord
from redbot.core import app_commands


def register(bounty_group: app_commands.Group, cog):
    @bounty_group.command(name="view", description="View a bounty by id or exact title.")
    @app_commands.guild_only()
    async def view(interaction: discord.Interaction, key: str):
        assert interaction.guild is not None
        if await cog._blocked(interaction):
            return

        bounty = await cog.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        await interaction.response.send_message(embed=cog._embed(interaction.guild, bounty))
