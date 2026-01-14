from __future__ import annotations
import discord


class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass


class BountyBoardView(discord.ui.View):
    """Simple next/prev browser. Not persistent across restarts in v1."""

    def __init__(self, cog, guild_id: int, start_index: int, author_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild_id = guild_id
        self.index = start_index
        self.author_id = author_id

    async def _get_sorted(self):
        guild = self.cog.bot.get_guild(self.guild_id)
        if not guild:
            return guild, []
        b = list((await self.cog.store.get_all(guild)).values())
        b.sort(key=lambda x: x["id"])
        return guild, b

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This board isn't yours. Run /bounty board to open your own.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild, b = await self._get_sorted()
        if not guild or not b:
            await interaction.response.edit_message(content="No bounties.", embed=None, view=None)
            return
        self.index = (self.index - 1) % len(b)
        await interaction.response.edit_message(embed=self.cog._embed(guild, b[self.index]), view=self)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild, b = await self._get_sorted()
        if not guild or not b:
            await interaction.response.edit_message(content="No bounties.", embed=None, view=None)
            return
        self.index = (self.index + 1) % len(b)
        await interaction.response.edit_message(embed=self.cog._embed(guild, b[self.index]), view=self)
