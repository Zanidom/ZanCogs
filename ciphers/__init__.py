from .ciphers import Ciphers

async def setup(bot):
    cog = Ciphers(bot)
    await bot.add_cog(cog)