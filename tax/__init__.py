from .tax import Tax

async def setup(bot):
    cog = Tax(bot)
    await bot.add_cog(cog)