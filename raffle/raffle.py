import discord
from redbot.core import commands, Config
import random

class Raffle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71812389075)
        default_global = {
            "entries": []
        }
        self.config.register_global(**default_global)

    @commands.group()
    @commands.admin_or_permissions(manage_guild=True, autohelp=False)
    async def raffle(self, ctx):
        """Raffle management commands"""
        pass

    @raffle.command(name="add")
    async def _add(self, ctx, member: discord.Member):
        """Add a member to the raffle"""
        async with self.config.entries() as entries:
            if member.id not in entries:
                entries.append(member.id)
                await ctx.send(f"{member.display_name} has been added to the raffle!")
            else:
                await ctx.send(f"{member.display_name} is already in the raffle.")

    @raffle.command(name="draw")
    async def _draw(self, ctx):
        """Draw a random member from the raffle"""
        entries = await self.config.entries()
        if not entries:
            await ctx.send("The raffle is empty. No one to draw.")
            return

        winner_id = random.choice(entries)
        winner = self.bot.get_user(winner_id)
        await ctx.send(f"🎉 Congratulations {winner.mention}! You've won the raffle! 🎉", allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))

    @raffle.command(name="clearentries")
    async def _clearentries(self, ctx):
        """Clear all entries from the raffle"""
        await self.config.entries.set([])
        await ctx.send("All raffle entries have been cleared.")

    @raffle.command(name="showentries")
    async def _showentries(self, ctx):
        """Show all members in the raffle"""
        entries = await self.config.entries()
        if not entries:
            await ctx.send("The raffle is empty.")
            return

        members = [self.bot.get_user(entry_id).display_name for entry_id in entries]
        embed = discord.Embed(title="Raffle Participants", description='\n'.join(members), color=discord.Color.blue())
        await ctx.send(embed=embed)
