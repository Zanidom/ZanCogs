from .threadalert import ThreadAlert

async def setup(bot):
  await bot.add_cog(ThreadAlert(bot))