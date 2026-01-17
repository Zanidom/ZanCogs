from .punishments import Punishments

async def setup(bot):
    await bot.add_cog(Punishments(bot))
