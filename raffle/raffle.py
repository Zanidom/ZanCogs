import discord
from redbot.core import commands, Config
import random

class Raffle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71812389074, force_registration=True)
        default_global = {
            "entries": {}
        }
        self.config.register_global(**default_global)

    async def _clean_invalid_entries(self):
        """Utility function to remove invalid entries."""
        entries = await self.config.entries()
        invalid_users = [user_id for user_id, count in entries.items() if count <= 0]
        for user_id in invalid_users:
            del entries[user_id]
        await self.config.entries.set(entries)

    @commands.group()
    @commands.admin_or_permissions(manage_guild=True, autohelp=False)
    async def raffle(self, ctx):
        """Raffle management commands"""
        pass

    @raffle.command(name="add")
    async def _add(self, ctx, member: discord.Member, num_entries: int = 1):
        """Add a member to the raffle with specified number of entries"""
        entries = await self.config.entries()
        member_id_str = str(member.id)
        entries[member_id_str] = entries.get(member_id_str, 0) + num_entries
        await self.config.entries.set(entries)
        await ctx.send(f"Added {num_entries} entries for {member.display_name}. Total entries: {entries[member_id_str]}")
        await self._clean_invalid_entries()

    @raffle.command(name="remove", aliases=['delete', 'minus'])
    async def _remove(self, ctx, member: discord.Member, num_entries: int = 1):
        """Remove a member from the raffle with specified number of entries. If they're zero, they are removed entirely."""
        entries = await self.config.entries()
        member_id_str = str(member.id)
        entries[member_id_str] = entries.get(member_id_str, 0) - num_entries
        await self.config.entries.set(entries)
        await ctx.send(f"Removed {num_entries} entries for {member.display_name}. Total entries: {entries[member_id_str]}")
        await self._clean_invalid_entries()

    @raffle.command(name="draw")
    async def _draw(self, ctx):
        """Draw a random member from the raffle, considering multiple entries"""
        entries = await self.config.entries()
        if not entries:
            await ctx.send("The raffle is empty. No one to draw.")
            return
        
        all_entries = [user_id for user_id, count in entries.items() for _ in range(count)]
        winner_id_str = random.choice(all_entries)
        winner = self.bot.get_user(int(winner_id_str))
        await ctx.send(f"🎉 Congratulations {winner.mention}! You've won the raffle! 🎉", )

    @raffle.command(name="clearentries")
    async def _clearentries(self, ctx):
        """Clear all entries from the raffle"""
        await self.config.entries.set({})
        await ctx.send("All raffle entries have been cleared.")

    @raffle.command(name="showentries")
    async def _showentries(self, ctx):
        """Show all members in the raffle with their entry counts"""
        await self._clean_invalid_entries()
        entries = await self.config.entries()
        if not entries:
            await ctx.send("The raffle is empty.")
            return
    
        sorted_entries = dict(sorted(entries.items(), key=lambda item: item[1], reverse=True))
        member_entries = [f"{self.bot.get_user(int(entry_id)).display_name} - {count}" for entry_id, count in sorted_entries.items()]
        embed = discord.Embed(title="Raffle Participants", description='\n'.join(member_entries), color=discord.Color.blue())
        await ctx.send(embed=embed)