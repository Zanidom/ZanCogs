from .kotr import Kotr

async def setup(bot):
    cog = Kotr(bot)
    await bot.add_cog(cog)