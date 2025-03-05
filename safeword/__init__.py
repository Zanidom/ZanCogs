from redbot.core import commands

from .safeword import Safeword

async def setup(bot):
    cog = Safeword(bot)
    await bot.add_cog(cog)