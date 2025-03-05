from .wpc import WPC

async def setup(bot):
    cog = WPC(bot)
    await bot.add_cog(cog)