from .admintimebomb import Adminbomb

async def setup(bot):
    cog = Adminbomb(bot)
    await bot.add_cog(cog)