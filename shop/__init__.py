from .shop import Shop

__red_end_user_data_statement__ = "This cog stores discord IDs as needed for operation."


await def setup(bot):
    cog = Shop()
    await bot.add_cog(cog)
