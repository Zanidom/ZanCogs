from .gallery import Gallery


async def setup(bot):
    cog = Gallery(bot)
    await bot.add_cog(cog)
