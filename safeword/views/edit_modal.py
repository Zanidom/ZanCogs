import discord

class SafewordEditModal(discord.ui.Modal, title="Edit Safeword"):
    def __init__(self, ctx, index, safewords, config, view, entry):
        super().__init__()
        self.ctx = ctx
        self.index = index
        self.safewords = safewords
        self.config = config
        self.view = view
        self.entry = entry

        self.trigger = discord.ui.TextInput(label="Trigger", style=discord.TextStyle.short, required=True, max_length=100, placeholder=entry["trigger"])
        self.message = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, required=False, max_length=1000, placeholder=entry["message"])

        self.response_type = discord.ui.TextInput(label="Response (SEND_MESSAGE / SLOWMODE)", style=discord.TextStyle.short, placeholder=entry["response"], required=True,max_length=20)
        self.slowmode = discord.ui.TextInput(label="Slowmode duration (If slowmode)", style=discord.TextStyle.short, required=False, max_length=1000)
        
        self.add_item(self.trigger)
        self.add_item(self.message)
        self.add_item(self.response_type)
        self.add_item(self.slowmode)


    async def on_submit(self, interaction: discord.Interaction):
        trigger = self.trigger.value
        message = self.message.value
        response_value = self.response_type.value.upper()
        if response_value not in ["NO_RESPONSE", "SEND_MESSAGE", "SLOWMODE"]:
            await interaction.response.send_message("Invalid response type.", ephemeral=True)
            return
        
        try:
            slowmode = int(self.slowmode.value)
            if slowmode < 0:
                raise ValueError("Negative value not allowed.")
        except ValueError:
            await interaction.response.send_message("Invalid slowmode duration. Please enter a non-negative number.", ephemeral=True)
            return

        self.safewords[self.index] = {
            "trigger": trigger,
            "message": message,
            "response": response_value,
            "slowmode_duration": slowmode,
        }

        await self.config.guild(self.ctx.guild).safewords.set(self.safewords)
        await interaction.response.send_message(f"Safeword `{trigger}` updated.", ephemeral=True)
        self.view.update_buttons()
        await self.view.message.edit(embed=self.view.make_embed(), view=self.view)
