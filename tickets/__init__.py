from .bettertickets import BetterTickets

async def setup(bot):
    cog = BetterTickets(bot)
    await bot.add_cog(cog)