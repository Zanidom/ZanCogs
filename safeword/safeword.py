import discord
from enum import Enum
from redbot.core import commands, Config
import asyncio
from .views.list_view import SafewordListView

class Response(Enum):
    NO_RESPONSE = 0
    SEND_MESSAGE = 1
    SLOWMODE = 2

class Safeword(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_guild(safewords=[])
        self.config.register_channel(slowmode_duration=300)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        safewords = await self.config.guild(message.guild).safewords()
        trigger_map = {entry["trigger"]: entry for entry in safewords}
        words = set(message.content.split())

        matched = next((entry for trigger, entry in trigger_map.items() if trigger in words), None)
        if matched:
            response_type = Response[matched["response"]]
            if response_type in (Response.SEND_MESSAGE, Response.SLOWMODE):
                response_text = matched.get("message", "")
                if response_text:
                    await message.channel.send(
                        f"{response_text}",
                        allowed_mentions=discord.AllowedMentions(roles=True, users=False)
                    )

            if response_type == Response.SLOWMODE:
                if message.channel.permissions_for(message.guild.me).manage_channels:
                    duration = await self.config.channel(message.channel).slowmode_duration()
                    await message.channel.edit(slowmode_delay=duration)
                    self.bot.loop.create_task(self.reset_slowmode(message.channel))

    async def reset_slowmode(self, channel: discord.TextChannel):
        duration = await self.config.channel(channel).slowmode_duration()
        await asyncio.sleep(duration)
        await channel.edit(slowmode_delay=0)

    @commands.group()
    @commands.guild_only()
    async def safeword(self, ctx):
        """Commands related to safewords."""
        pass

    @safeword.command()
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx, trigger: str, *, message: str = ""):
        """
        Add a new safeword with default response (SEND_MESSAGE).
        Response can be edited later via ;safeword list -> Edit.
        """
        safewords = await self.config.guild(ctx.guild).safewords()
        trigger = trigger

        if any(word["trigger"] == trigger for word in safewords):
            await ctx.send("That safeword already exists.")
            return

        safewords.append({
            "trigger": trigger,
            "response": "SEND_MESSAGE",
            "message": message
        })
        await self.config.guild(ctx.guild).safewords.set(safewords)
        await ctx.send(f"Safeword `{trigger}` added.")


    @safeword.command()
    @commands.has_permissions(manage_guild=True)
    async def delete(self, ctx, trigger: str):
        """
        Deletes a safeword entirely.
        """
        safewords = await self.config.guild(ctx.guild).safewords()
        trigger = trigger
        new_list = [word for word in safewords if word["trigger"] != trigger]
        if len(new_list) == len(safewords):
            await ctx.send("That safeword doesn't exist.")
            return

        await self.config.guild(ctx.guild).safewords.set(new_list)
        await ctx.send(f"Safeword `{trigger}` deleted.")

    @safeword.command()
    @commands.has_permissions(manage_guild=True)
    async def edit(self, ctx, trigger: str, response: Response, *, message: str = ""):
        """
        Edits an existing safeword.
        """
        safewords = await self.config.guild(ctx.guild).safewords()
        trigger = trigger
        for word in safewords:
            if word["trigger"] == trigger:
                word["response"] = response.name
                word["message"] = message
                await self.config.guild(ctx.guild).safewords.set(safewords)
                await ctx.send(f"Safeword `{trigger}` updated.")
                return
        await ctx.send("Safeword not found.")

    @safeword.command()
    @commands.has_permissions(manage_guild=True)
    async def list(self, ctx):
        """
        Lists out all existing safewords. Allows editing on a per-item basis for admins.
        """
        safewords = await self.config.guild(ctx.guild).safewords()
        if not safewords:
            await ctx.send("No safewords configured.")
            return

        view = SafewordListView(ctx, safewords, self.config)
        await view.send_initial()
