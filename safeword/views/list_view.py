import discord
from .edit_modal import SafewordEditModal

class SafewordListView(discord.ui.View):
    def __init__(self, ctx, safewords, config):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.safewords = safewords
        self.config = config
        self.index = 0
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        back_button = discord.ui.Button(label="⬅️ Back", style=discord.ButtonStyle.secondary, disabled=self.index == 0)
        if self.ctx.author.guild_permissions.manage_guild:
            edit_button = discord.ui.Button(label="✏️ Edit", style=discord.ButtonStyle.primary)
        next_button = discord.ui.Button(label="➡️ Next", style=discord.ButtonStyle.secondary, disabled=self.index == len(self.safewords) - 1)

        back_button.callback = self.prev_page
        if self.ctx.author.guild_permissions.manage_guild:
            edit_button.callback = self.edit_safeword
        next_button.callback = self.next_page

        self.add_item(back_button)
        if self.ctx.author.guild_permissions.manage_guild:
            self.add_item(edit_button)
        self.add_item(next_button)


    async def send_initial(self):
        embed = self.make_embed()
        self.message = await self.ctx.send(embed=embed, view=self)

    def make_embed(self):
        entry = self.safewords[self.index]
        embed = discord.Embed(
            title=f"Safeword [{self.index+1} of {len(self.safewords)}]",
            description=f"Trigger: `{entry['trigger']}`",
            color=discord.Color.orange()
        )
        embed.add_field(name="Response", value=entry['response'], inline=False)
        if entry.get("message"):
            embed.add_field(name="Message", value=entry['message'], inline=False)

        if entry.get("slowmode_duration") and entry['response'] == "SLOWMODE":
            embed.add_field(name="Slowmode Duration", value=entry['slowmode_duration'], inline=False)

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.ctx.author

    async def prev_page(self, interaction: discord.Interaction):
        self.index = max(self.index - 1, 0)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.index = min(self.index + 1, len(self.safewords) - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def edit_safeword(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You don't have permission to edit safewords.", ephemeral=True)
            return

        entry = self.safewords[self.index]
        modal = SafewordEditModal(self.ctx, self.index, self.safewords, self.config, self, entry)
        await interaction.response.send_modal(modal)
