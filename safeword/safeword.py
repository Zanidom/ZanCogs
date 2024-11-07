import discord
from enum import Enum
from redbot.core import commands, app_commands, Config, checks
import asyncio

#class Response(Enum):
#    PING_ADMINS = 1
#    SLOWMODE = 2
#    LOCK_CHANNEL = 3
#
#class ResponseList(discord.ui.)
#
#class AddSafewordActionModal(discord.ui.Modal, title="Add a safeword"):
#    newSafeWord = discord.ui.TextInput(label=f"Please input a safeword:", style=discord.TextStyle.short, required=True, max_length = 20, placeholder = "Safeword")
#    newSafeWordResponse = discord.ui.Select(placeholder=Response.PING_ADMINS, )
#
#
#    async def on_submit(self, interaction:discord.Interaction):
#        await interaction.response.send_message(text=f"Added safeword {self.newSafeWord.value} with action {self.newSafeWordResponse.value}", )
#
#class EditSafewordActionModal(discord.ui.Modal, title="Edit a safeword"):
#    answer = discord.ui.TextInput(label=f"Please input a safeword:", style=discord.TextStyle.short, required=True, max_length = 20, placeholder = "Safeword")
#
#    async def on_submit(self, interaction:discord.Interaction):
#        await interaction.response.defer()
#
#        await interaction.followup.send(f"Something went wrong with your input:\n{self.answer.value}\nPlease try again.", ephemeral=True)
#
#class DeleteSafewordActionModal(discord.ui.Modal, title="Truth or Dare"):
#    answer = discord.ui.TextInput(label=f"Please input a safeword:", style=discord.TextStyle.short, required=True, max_length = 20, placeholder = "Safeword")
#
#    async def on_submit(self, interaction:discord.Interaction):
#        await interaction.response.defer()
#
#        await interaction.followup.send(f"Something went wrong with your input:\n{self.answer.value}\nPlease try again.", ephemeral=True)
#
#
#
#
#class Safeword (commands.Cog):
#
#    comGroup = app_commands.Group(name="safeword", description="Commands for safewords")
#
#    def __init__ (self, bot):
#        self.bot = bot
#        self.config = Config.get_conf(self, identifier=24681357, force_registration=True)
#        default_guild = {
#            "Safewords": {
#            "SAFEWORD": Response.PING_ADMINS
#            }
#        }
#        self.config.register_guild(**default_guild)
#
#    @app_commands.command()
#    @app_commands.guild_only()
#    @checks.admin_or_permissions(manage_guild=True)
#    @comGroup.command(name="add")
#    async def AddSafeword():
#        guildSafewords = self.config.guild(message.guild)
#
#    @app_commands.command()
#    @app_commands.guild_only()
#    @checks.admin_or_permissions(manage_guild=True)
#    @comGroup.command(name="edit")
#    async def EditSafeword():
#        guildSafewords = self.config.guild(message.guild)
#        
#    @app_commands.command()
#    @app_commands.guild_only()
#    @checks.admin_or_permissions(manage_guild=True)
#    @comGroup.command(name="add")
#    async def DeleteSafeword(self, interaction: discord.Interaction,):
#        guildSafewords = self.config.guild(message.guild)
#
#
#    @commands.Cog.listener()
#    async def on_message(self, message):
#        guildSafewords = self.config.guild(message.guild).Safewords()
#        for word, action  in guildSafewords:
#            if word in message.content:
#                match action:
#                    case Response.PING_ADMINS:
#                        message.reply(f"")
#                    case Response.SLOWMODE:
#
#                    case Response.LOCK_CHANNEL:
#
class Safeword (commands.Cog):
    def __init__ (self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_channel = {"slowmode_duration": 300}
        self.config.register_channel(**default_channel)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if "SAFEWORD" in message.content and not message.author.bot:
            adminRole = discord.utils.get(message.guild.roles, name="Admin")
            if adminRole is not None:
                await message.reply(f"<@&{adminRole.id}>", allowed_mentions=discord.AllowedMentions(everyone=False, roles=True, users=False))
            
            slowmode_duration = await self.config.channel(message.channel).slowmode_duration()
            # Set the slowmode if the bot has permissions
            if message.channel.permissions_for(message.guild.me).manage_channels:
                await message.channel.edit(slowmode_delay=slowmode_duration)
                self.bot.loop.create_task(self.reset_slowmode(message.channel))

    async def reset_slowmode(self, channel):
        slowmode_duration = await self.config.channel(channel).slowmode_duration()
        await asyncio.sleep(slowmode_duration)
        await channel.edit(slowmode_delay=0)

    @commands.group()
    @commands.guild_only()
    async def safeword(self, ctx):
        """Commands related to safeword functionality."""
        pass

    @safeword.command()
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int, channel: discord.TextChannel = None):
        """
        Set the safeword slowmode duration for a channel.

        Usage: [p]safeword slowmode <seconds> [channel]
        If channel is not specified, the current channel is used.
        """
        if channel is None:
            channel = ctx.channel
        if seconds < 0:
            await ctx.send("The slowmode duration must be a non-negative integer.")
            return
        await self.config.channel(channel).slowmode_duration.set(seconds)
        await ctx.send(f"Safeword slowmode duration for {channel.mention} set to {seconds} seconds.")


