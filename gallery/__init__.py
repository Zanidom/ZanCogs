from .gallery import Gallery


def setup(bot):
    await bot.add_cog(Gallery(bot))
