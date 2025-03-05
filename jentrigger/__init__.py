from .jentrigger import jentrigger

async def setup(bot):
    cog = jentrigger(bot)
    await bot.add_cog(cog)