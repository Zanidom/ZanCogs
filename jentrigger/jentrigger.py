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
        try:
            await self.cog.send_webhook_request(interaction.user, interaction.guild)
            await self.cog.deduct_currency(interaction.guild, interaction.user)
            await interaction.response.send_message("Edge confirmed, and sent to Jen.", ephemeral=False)
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
    """Cog to let you buy edges for Jen!"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=12343212, force_registration=True)
        
        default_guild = {
            "cost": 100,
            "webhook_url": "unconfigured",
            "webhook_data_template": "$USERNAME$_triggered",
            "percentage": 100,  # New configuration option for percentage
            "recipient_user": None  # New configuration option for recipient user (store as ID)
        }
        
        self.config.register_guild(**default_guild)

    @commands.command(name="jentrigger", autohelp=False, aliases=["jenedge", "jengasm"])
    async def jentrigger(self, ctx):
        """Trigger a Jen edge."""
        guild_data = await self.config.guild(ctx.guild).all()
        cost = guild_data["cost"]
        percentage = guild_data["percentage"]
        
        if not await self.check_currency(ctx.author, cost):
            return await ctx.send("You do not have enough currency to perform this action.")
        
        embed = Embed(title="Confirmation", description=f"This will cost {cost}.\n{int(cost * (percentage / 100))} goes to Jen and {int(cost - cost *(percentage / 100))} will be vanished into the ether.\n\nAre you sure?", color=discord.Color.blue())
        
        view = ConfirmationView(ctx.author, cost, self)
        
        message = await ctx.send(embed=embed, view=view)

    @commands.group(name="jenset")
    @checks.admin_or_permissions(manage_guild=True)
    async def jenset(self, ctx):
        """Configuration settings for JenTrigger."""
        pass

    @jenset.command(name="cost")
    async def set_cost(self, ctx, cost: int):
        """Set the cost for a jen edge."""
        await self.config.guild(ctx.guild).cost.set(cost)
        await ctx.send(f"Cost for edging set to {cost}.")

    @jenset.command(name="webhookurl")
    async def set_webhook_url(self, ctx, *, url: str):
        """Set the webhook URL."""
        await self.config.guild(ctx.guild).webhook_url.set(url)
        await ctx.send(f"Webhook URL set to {url}.")

    @jenset.command(name="webhookdata")
    async def set_webhook_data_template(self, ctx, *, template: str):
        """Set the webhook data template. User: $USERNAME$"""
        await self.config.guild(ctx.guild).webhook_data_template.set(template)
        await ctx.send("Webhook data template set.")

    @jenset.command(name="percentage")
    async def set_percentage(self, ctx, percentage: int):
        """Set what percentage cut Jen gets!"""
        if 0 <= percentage <= 100:
            await self.config.guild(ctx.guild).percentage.set(percentage)
            await ctx.send(f"Jen's Cut percentage set to {percentage}%.")
        else:
            await ctx.send("Percentage must be between 0 and 100.")

    @jenset.command(name="recipient", aliases=['user'])
    async def set_recipient_user(self, ctx, user: discord.Member):
        """Set the recipient user who receives the currency."""
        await self.config.guild(ctx.guild).recipient_user.set(user.id)
        await ctx.send(f"Recipient user set to {user.display_name}.")

    async def check_currency(self, user, amount):
        """Check if the user has enough currency."""
        current_balance = await bank.get_balance(user)
        return current_balance >= amount

    async def deduct_currency(self, guild, user):
        """Deduct the specified amount of currency, adjusted by percentage, and optionally transfer to a recipient."""
        settings = await self.config.guild(guild).all()
        cost = settings["cost"]
        percentage = settings["percentage"]
        recipient_id = settings["recipient_user"]

        adjusted_amount = int(cost * (percentage / 100))

        await bank.withdraw_credits(user, adjusted_amount)
    
        if recipient_id is not None:
            recipient = guild.get_member(recipient_id)
            if recipient:
                await bank.deposit_credits(recipient, adjusted_amount)
            else:    
                await bank.withdraw_credits(user, cost)

    async def send_webhook_request(self, user, guild):
        """Send a PUT request to the configured webhook URL."""
        url = str(await self.config.guild(guild).webhook_url())
        data_template = str(await self.config.guild(guild).webhook_data_template())
        data =  data_template.replace("$USERNAME$",user.name)
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
    
    @commands.command(name="jentriggerconfig")
    @checks.admin_or_permissions(manage_guild=True)
    async def jentrigger_config(self, ctx):
        """Displays the current configuration for JenTrigger."""
        guild_settings = await self.config.guild(ctx.guild).all()

        # Create an embed to display the settings
        embed = discord.Embed(title=f"JenTrigger Configuration for {ctx.guild.name}", color=discord.Color.blue())

        # Add fields for each configuration option
        embed.add_field(name="Cost", value=str(guild_settings["cost"]), inline=False)
        embed.add_field(name="Webhook URL", value=guild_settings["webhook_url"] or "Not configured", inline=False)
        embed.add_field(name="Webhook Data Template", value=guild_settings["webhook_data_template"], inline=False)
        embed.add_field(name="Percentage", value=str(guild_settings["percentage"]) + "%", inline=False)

        recipient_user = guild_settings["recipient_user"]
        if recipient_user:
            recipient_user = ctx.guild.get_member(recipient_user)
            recipient_name = recipient_user.display_name if recipient_user else "User not found"
        else:
            recipient_name = "No recipient set"
        embed.add_field(name="Recipient User", value=recipient_name, inline=False)
        await ctx.send(embed=embed)