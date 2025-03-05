from redbot.core import commands

from .tod import ToDCog

async def setup(bot):
    cog = ToDCog(bot)
    await bot.add_cog(cog)