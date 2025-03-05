from .syllables import Syllables

async def setup(bot):
    cog = Syllables(bot)
    await bot.add_cog(cog)