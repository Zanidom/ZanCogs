from tickets import Tickets

async def setup(bot):
    cog = Tickets(bot)
    await bot.add_cog(cog)
    await cog.initialize()