from __future__ import annotations

import discord
from discord.ui import View, Button

class ConfirmView(View):
    def __init__(self, *, author_id: int, confirm_label: str="Confirm", confirm_style: discord.ButtonStyle= discord.ButtonStyle.danger, cancel_label: str="Cancel", timeout: float = 120):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.confirmed: bool | None = None

        self.btn_confirm = Button(label=confirm_label, style=confirm_style)
        self.btn_cancel = Button(label=cancel_label, style=discord.ButtonStyle.secondary)

        self.btn_confirm.callback = self._confirm
        self.btn_cancel.callback = self._cancel

        self.add_item(self.btn_confirm)
        self.add_item(self.btn_cancel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        
        await interaction.response.send_message("This confirmation isn't for you!", ephemeral=True)
        return False

    async def _confirm(self, interaction: discord.Interaction):
        self.confirmed = True
        self._disable()
        await interaction.response.edit_message(view=self)
        self.stop()

    async def _cancel(self, interaction: discord.Interaction):
        self.confirmed = False
        self._disable()
        await interaction.response.edit_message(view=self)
        self.stop()

    def _disable(self):
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
