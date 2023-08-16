from .bankprune import Bankpruner

async def setup(bot):
    cog = Bankpruner(bot)
    await bot.add_cog(cog)