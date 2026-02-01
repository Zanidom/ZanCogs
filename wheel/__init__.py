from .wheel import Wheel

async def setup(bot):
    await bot.add_cog(Wheel(bot))
