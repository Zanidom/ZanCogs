from .JenTracker import JenTracker

async def setup(bot):
    cog = JenTracker(bot)
    await bot.add_cog(cog)