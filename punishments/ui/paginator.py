import discord
from discord.ui import View, Button

class EmbedPaginator(View):
    def __init__(self, embeds: list[discord.Embed], *, author_id: int, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.author_id = author_id
        self.index = 0

        self.prev_btn = Button(label="Prev", style=discord.ButtonStyle.secondary)
        self.next_btn = Button(label="Next", style=discord.ButtonStyle.secondary)

        self.prev_btn.callback = self._prev
        self.next_btn.callback = self._next

        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)

        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self.prev_btn.disabled = (self.index <= 0)
        self.next_btn.disabled = (self.index >= len(self.embeds) - 1)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message("This isn't for you!", ephemeral=True)
        return False

    async def _prev(self, interaction: discord.Interaction):
        self.index = max(0, self.index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    async def _next(self, interaction: discord.Interaction):
        self.index = min(len(self.embeds) - 1, self.index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)
