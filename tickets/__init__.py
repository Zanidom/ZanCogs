from tickets import tickets

async def setup(bot):
    cog = tickets(bot)
    await bot.add_cog(cog)
    await cog.initialize()