from .sbpay import SBPay

async def setup(bot):
    cog = SBPay(bot)
    await bot.add_cog(cog)