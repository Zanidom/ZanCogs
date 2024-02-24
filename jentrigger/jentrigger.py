from redbot.core import commands, Config, checks
from discord import Embed, ButtonStyle
from discord.ui import Button, View
import discord
from redbot.core import bank
import asyncio
import aiohttp
from discord.ext.commands import CommandError

class ConfirmationView(discord.ui.View):
    def __init__(self, user, cost, cog, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.cost = cost
        self.cog = cog

    @discord.ui.button(label="Confirm", style=ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("You cannot confirm this action.", ephemeral=True)
        print("passed auth check")
        try:
            await self.cog.send_webhook_request(interaction.user, interaction.guild)
            print("passed swr check")
            await self.cog.deduct_currency(interaction.user, self.cost)
            print("passed dc check")
            await interaction.response.send_message("Action confirmed, currency deducted, and Jen Triggered 😎", ephemeral=False)
        except CommandError as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
        await interaction.message.delete()

    @discord.ui.button(label="Cancel", style=ButtonStyle.danger, emoji="🚫")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("You cannot deny this action.", ephemeral=True)
        await interaction.response.send_message("Action cancelled.", ephemeral=True)
        await interaction.message.delete()

class jentrigger(commands.Cog):
    """JenTrigger Cog for triggering actions with confirmation and currency deduction."""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234321, force_registration=True)
        
        default_guild = {
            "cost": 100,
            "webhook_url": "unconfigured",
            "webhook_data_template": "$USERNAME$_triggered"
        }
        
        self.config.register_guild(**default_guild)

    @commands.group(name="jenset")
    @checks.admin_or_permissions(manage_guild=True)
    async def jenset(self, ctx):
        """Configuration settings for JenTrigger."""
        pass

    @jenset.command(name="cost")
    async def set_cost(self, ctx, cost: int):
        """Set the cost for triggering."""
        await self.config.guild(ctx.guild).cost.set(cost)
        await ctx.send(f"Cost for triggering set to {cost}.")

    @jenset.command(name="webhookurl")
    async def set_webhook_url(self, ctx, *, url: str):
        """Set the webhook URL."""
        await self.config.guild(ctx.guild).webhook_url.set(url)
        await ctx.send(f"Webhook URL set to {url}.")

    @jenset.command(name="webhookdata")
    async def set_webhook_data_template(self, ctx, *, template: str):
        """Set the webhook data template."""
        await self.config.guild(ctx.guild).webhook_data_template.set(template)
        await ctx.send("Webhook data template set.")

    async def check_currency(self, user, amount):
        """Check if the user has enough currency."""
        # Get the user's current balance
        current_balance = await bank.get_balance(user)
        
        # Return True if the balance is sufficient, False otherwise
        return current_balance >= amount

    async def deduct_currency(self, user, amount):
        """Deduct the specified amount of currency from the user's account."""
        # Withdraw the amount from the user's account
        await bank.withdraw_credits(user, amount)

    async def send_webhook_request(self, user, guild):
        """Send a PUT request to the configured webhook URL."""
        url = str(await self.config.guild(guild).webhook_url())
        data_template = str(await self.config.guild(guild).webhook_data_template())
        data =  data_template.replace("$USERNAME$",user.name)
        print (url + " - " + data)
        if url == "unconfigured":
            raise CommandError("Webhook URL has not been configured.")
        headers = {'Content-Type': 'application/json'}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.put(url, json={"data": data}, headers=headers) as response:
                    if response.status != 200:
                        raise CommandError("Failed to send webhook request.")
            except asyncio.TimeoutError:
                raise CommandError("The webhook request timed out.")
            except aiohttp.ClientError as e:
                raise CommandError(f"An error occurred while sending the webhook request: {type(e)}: {e}")
    

    @commands.command(name="jentrigger")
    async def jentrigger(self, ctx):
        """Trigger a Jen edge."""
        guild_data = await self.config.guild(ctx.guild).all()
        cost = guild_data["cost"]
        
        if not await self.check_currency(ctx.author, cost):
            return await ctx.send("You do not have enough currency to perform this action.")
        
        embed = Embed(title="Confirmation", description=f"This will cost {cost}, are you sure?", color=discord.Color.blue())
        
        view = ConfirmationView(ctx.author, cost, self)
        
        message = await ctx.send(embed=embed, view=view)

