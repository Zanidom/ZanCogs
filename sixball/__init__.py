from .sixball import Sixball

async def setup(bot):
    cog = Sixball(bot)
    await bot.add_cog(cog)