from sys import exception
import discord
from discord import Embed
from redbot.core import commands
from redbot.core.commands import Context

class Adminbomb(commands.Cog):
    def __init__(self, bot):
        self.botRef = bot
        pass
    
    @commands.command(name="admintimebomb", hidden=True, autohelp=False)
    async def _test4(self, ctx):
        emb = Embed(colour=0x000000, description="You want to play a game?")
        emb.set_image(url="https://cdn.discordapp.com/icons/712295641467846807/a_922d4cca0e4f4c38f6c2a3e8057e4d1d.gif")
        emb.title = "Admin drive!!!!!!!!!!!"
        emb.add_field(name="", value="So, you want to try and find our supersecret drive?\nWell here's a good place to start:<pastebinlink idk>")
        emb.set_footer(text="Good luck! >:)")
        try:
            await ctx.message.delete()
        except:
            if not isinstance(ctx.channel, discord.DMChannel):
                return
        await ctx.author.send(embed=emb)