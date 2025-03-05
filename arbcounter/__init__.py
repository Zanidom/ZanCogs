from .arbcounter import ArbCounter

async def setup(bot):
    cog = ArbCounter(bot)
    await bot.add_cog(cog)