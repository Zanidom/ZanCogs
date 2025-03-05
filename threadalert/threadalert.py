import discord
from redbot.core import commands, Config

class ThreadAlert(commands.Cog):
    """Penis related commands."""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=147147147123, force_registration=True)
        default_guild = {"output_channel": None}
        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.command(name="settachannel")
    async def set_output_channel(self, ctx, channel: discord.TextChannel):
        """Set the output channel for new thread notifications."""
        await self.config.guild(ctx.guild).output_channel.set(channel.id)
        await ctx.send(f"Set the output channel for new thread alerts to {channel.mention}.")

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        await thread.join()
        output_channel_id = await self.config.guild(thread.guild).output_channel()
        if output_channel_id:
            output_channel = self.bot.get_channel(output_channel_id)
            if output_channel:
                await output_channel.send(f"New thread created by {thread.owner.display_name}: {thread.jump_url}")