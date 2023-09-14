from .omniball import Omniball

async def setup(bot):
    cog = Omniball(bot)
    await bot.add_cog(cog)