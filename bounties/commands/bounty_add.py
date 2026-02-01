from __future__ import annotations
import discord
from redbot.core import app_commands
from ..ui.modals import AddBountyModal
from ..ui.views import BountyBoardView, CloseView
from ..ui.embeds import build_bounty_embed


def register(bounty_group: app_commands.Group, cog):
    @bounty_group.command(name="add", description="Post a new bounty.")
    @app_commands.guild_only()
    async def add(interaction: discord.Interaction):
        if await cog._blocked(interaction):
            return
        
        await interaction.response.send_modal(AddBountyModal(cog))

    @bounty_group.command(name="board", description="Browse bounties with next/prev buttons.")
    @app_commands.guild_only()
    async def board(interaction: discord.Interaction):
        if await cog._blocked(interaction):
            return

        bounties = list((await cog.store.get_all(interaction.guild)).values())
        bounties.sort(key=lambda b: b["id"])
        if not bounties:
            await interaction.response.send_message("No active bounties.", ephemeral=True)
            return

        view = BountyBoardView(cog, interaction.guild.id, start_index=0, author_id=interaction.user.id)
        await interaction.response.send_message(embed=cog._embed(interaction.guild, bounties[0]), view=view)

    @bounty_group.command(name="mine", description="Show your active bounties (ephemeral).")
    @app_commands.guild_only()
    async def mine(interaction: discord.Interaction):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await cog._blocked(interaction):
            return

        bounties = list((await cog.store.get_all(interaction.guild)).values())
        mine = [b for b in bounties if b["owner_id"] == interaction.user.id]
        mine.sort(key=lambda b: b["id"])
        if not mine:
            await interaction.response.send_message("You have no active bounties.", ephemeral=True, view=CloseView())
            return

        text = "\n".join(f"#{b['id']} - {b['title']} (remaining payouts: {b['max_payouts']})" for b in mine)[:1900]
        await interaction.response.send_message(text, ephemeral=True, view=CloseView())
