from .zuko import Zuko

async def setup(bot):
    await bot.add_cog(Zuko(bot))
