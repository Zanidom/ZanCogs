from tickets import Ticketer

async def setup(bot):
    cog = Ticketer(bot)
    await bot.add_cog(cog)
    await cog.initialize()