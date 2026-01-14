from .cog import Bounties

async def setup(bot):
    await bot.add_cog(Bounties(bot))
