from .safeword import Safeword

async def setup(bot):
    await bot.add_cog(Safeword(bot))
