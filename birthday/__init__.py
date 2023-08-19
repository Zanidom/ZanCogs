from .birthday import Birthday

__red_end_user_data_statement__ = "This cog will store a user's birthday."


async def setup(bot):
    cog = Birthday(bot)
    await bot.add_cog(cog)
