from __future__ import annotations
import discord

class AddBountyModal(discord.ui.Modal, title="Create bounty"):
    bounty_title = discord.ui.TextInput(label="Title (must be unique)", max_length=80)
    desc = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=2000)
    reward = discord.ui.TextInput(label="Reward (number)", max_length=12)
    max_payouts = discord.ui.TextInput(label="Max payouts (number)", default="1", max_length=6)
    open_fulfil = discord.ui.TextInput(label="Open fulfil? (true/false)", default="false", max_length=5)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            reward = int(str(self.reward.value).strip())
            max_payouts = int(str(self.max_payouts.value).strip())
            open_fulfil = str(self.open_fulfil.value).strip().lower() in ("true", "t", "1", "yes", "y")
            if reward <= 0 or max_payouts <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("Reward and Max payouts must be positive integers.", ephemeral=True)
            return

        await self.cog.create_bounty_from_modal(
            interaction,
            title=str(self.bounty_title.value),
            desc=str(self.desc.value),
            reward=reward,
            max_payouts=max_payouts,
            open_fulfil=open_fulfil,
        )


class EditBountyModal(discord.ui.Modal, title="Edit bounty"):
    bounty_title = discord.ui.TextInput(label="Title (unique)", max_length=80)
    desc = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=2000)
    reward = discord.ui.TextInput(label="Reward (number)", max_length=12)
    max_payouts = discord.ui.TextInput(label="Remaining payouts (number)", max_length=6)
    open_fulfil = discord.ui.TextInput(label="Open fulfil? (true/false)", max_length=5)

    def __init__(self, cog, bounty_id: int, seed: dict):
        super().__init__()
        self.cog = cog
        self.bounty_id = bounty_id

        self.bounty_title.default = seed.get("title", "")
        self.desc.default = seed.get("desc", "")
        self.reward.default = str(seed.get("reward", 1))
        self.max_payouts.default = str(seed.get("max_payouts", 1))
        self.open_fulfil.default = "true" if seed.get("open_fulfil") else "false"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            reward = int(str(self.reward.value).strip())
            max_payouts = int(str(self.max_payouts.value).strip())
            open_fulfil = str(self.open_fulfil.value).strip().lower() in ("true", "t", "1", "yes", "y")
            if reward <= 0 or max_payouts <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("Reward and Remaining payouts must be positive integers.", ephemeral=True)
            return

        await self.cog.apply_edit_from_modal(interaction, self.bounty_id, title=str(self.bounty_title.value),
            desc=str(self.desc.value), reward=reward, max_payouts=max_payouts, open_fulfil=open_fulfil,
        )
