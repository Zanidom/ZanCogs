from .purge import Purge

async def setup(bot):
    cog = Purge(bot)
    await bot.add_cog(cog)