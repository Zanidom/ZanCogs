from .raffle import Raffle

async def setup(bot):
    cog = Raffle(bot)
    await bot.add_cog(cog)