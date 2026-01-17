from __future__ import annotations

import discord
from discord.ui import Modal, TextInput

from ..constants import MAX_TEXT_LEN, WEIGHT_MIN, WEIGHT_MAX, MODAL_TIMEOUT


class PunishmentModal(Modal, title="Punishment"):
    def __init__(self, *, cog,  target: discord.Member, mode: str,
        edit_id: int | None = None, default_text: str = "", default_weight: str = "1",):
        super().__init__(timeout=MODAL_TIMEOUT)

        self.cog = cog
        self.target = target
        self.mode = mode
        self.edit_id = edit_id

        self.desc = TextInput(label="Descriptor",style=discord.TextStyle.paragraph,max_length=MAX_TEXT_LEN,
            required=True,default=default_text[:MAX_TEXT_LEN],placeholder="e.g. Take a pie to the face",)
        self.weight = TextInput(label=f"Weight ({WEIGHT_MIN}-{WEIGHT_MAX}) (more weight, more likely)",style=discord.TextStyle.short,
            max_length=3, required=True, default=str(default_weight)[:3], placeholder="1",)

        self.add_item(self.desc)
        self.add_item(self.weight)

    async def on_submit(self, interaction: discord.Interaction):
        text = (self.desc.value or "").strip()
        if not text:
            return await interaction.response.send_message("Descriptor can't be empty.", ephemeral=True)

        try:
            weight = int((self.weight.value or "").strip())
        except ValueError:
            return await interaction.response.send_message("Weight must be a whole, positive number.", ephemeral=True)

        if not (WEIGHT_MIN <= weight <= WEIGHT_MAX):
            return await interaction.response.send_message(f"Weight must be between {WEIGHT_MIN} and {WEIGHT_MAX}.", ephemeral=True,)

        if self.mode == "add":
            new_id = await self.cog._add_punishment(self.target, text=text, weight=weight)
            await interaction.response.send_message(f"Added punishment **#{new_id}** for {self.target.mention}.\n"
                f"> {discord.utils.escape_markdown(text)} (weight {weight})",ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),)
            return

        if self.edit_id is None:
            return await interaction.response.send_message("Internal error: missing edit id. @ Zan to investigate", ephemeral=True)

        ok = await self.cog._edit_punishment(self.target, punishId=self.edit_id, text=text, weight=weight)
        if not ok:
            return await interaction.response.send_message(
                f"Couldn't find punishment **#{self.edit_id}** for {self.target.mention}.", ephemeral=True,)

        await interaction.response.send_message(
            f"Updated punishment **#{self.edit_id}** for {self.target.mention}.\n" f"> {discord.utils.escape_markdown(text)} (weight {weight})",
            ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),)


class RuleModal(Modal, title="Rule"):
    def __init__(self, *, cog,  target: discord.Member, mode: str, edit_id: int | None = None, default_text: str = "",):
        super().__init__(timeout=MODAL_TIMEOUT)
        self.cog = cog
        self.target = target
        self.mode = mode
        self.edit_id = edit_id

        self.text = TextInput(label="Rule text", style=discord.TextStyle.paragraph, max_length=MAX_TEXT_LEN,
            required=True, default=default_text[:MAX_TEXT_LEN], placeholder="e.g. Only 3 (or lower) syllable words for 24h",)
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction):
        text = (self.text.value or "").strip()
        if not text:
            return await interaction.response.send_message("Rule text can't be empty.", ephemeral=True)

        if self.mode == "add":
            new_id = await self.cog._add_rule(self.target, text=text)
            await interaction.response.send_message(f"Added rule **#{new_id}** for {self.target.mention}.\n"
                f"> {discord.utils.escape_markdown(text)}", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            return

        if self.edit_id is None:
            return await interaction.response.send_message("Internal error: missing edit id.", ephemeral=True)

        ok = await self.cog._edit_rule(self.target, rid=self.edit_id, text=text)
        if not ok:
            return await interaction.response.send_message(f"Couldn't find rule **#{self.edit_id}** for {self.target.mention}.", ephemeral=True)

        await interaction.response.send_message(f"Updated rule **#{self.edit_id}** for {self.target.mention}.\n" 
            f"> {discord.utils.escape_markdown(text)}", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
