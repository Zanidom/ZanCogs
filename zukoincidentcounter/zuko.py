import discord
from redbot.core import commands, Config
from datetime import datetime, timezone, timedelta
import os
from PIL import Image, ImageDraw, ImageFont

class Zuko(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1567841278963)
        self.config.register_guild(last_reset=None)

    @commands.group()
    async def zuko(self, ctx):
        """Zuko incident counter."""
        pass

    @zuko.command()
    async def counter(self, ctx):
        """Shows how many days since the last incident..."""
        last_reset = await self.config.guild(ctx.guild).last_reset()
        if not last_reset:
            await ctx.send("The counter has not been set yet.")
            return

        last_dt = datetime.fromisoformat(last_reset)
        now = datetime.now(timezone.utc)
        days = (now - last_dt).days

        base_path = os.path.join(os.path.dirname(__file__), "zuko_base.png")
        output_path = os.path.join(os.path.dirname(__file__), "zuko_rendered.png")

        if not os.path.exists(base_path):
            await ctx.send(f"{days} day{'s' if days != 1 else ''} since last incident.")
            return

        try:
            img = Image.open(base_path).convert("RGB")
            draw = ImageDraw.Draw(img)
            region = (178, 88, 270, 145)
            draw.rectangle(region, fill="#CAC8A1")

            text = str(days)
            try:
                font_path = os.path.join(os.path.dirname(__file__), "arialbd.ttf")
                font = ImageFont.truetype(font_path, 48)

            except:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = (bbox[2] - bbox[0]) 
            text_height = (bbox[3] - bbox[1]) 
            text_x = region[0] + (region[2] - region[0] - text_width) // 2
            text_y = (region[1] + (region[3] - region[1] - text_height) // 2) - 5
            draw.text((text_x, text_y), text, fill="#A3282A", font=font)

            img.save(output_path)
            file = discord.File(output_path, filename="zuko.png")
            await ctx.send(file=file)

        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    @zuko.command()
    async def reset(self, ctx):
        """Reset the counter (admins only)."""
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("Get an admin to reset the counter!")
            return

        now = datetime.now(timezone.utc).isoformat()
        await self.config.guild(ctx.guild).last_reset.set(now)

        file_path = os.path.join(os.path.dirname(__file__), "zuko_base.png")
        if os.path.exists(file_path):
            file = discord.File(file_path, filename="zuko_base.png")
            await ctx.send("Counter reset!", file=file)
        else:
            await ctx.send("Counter reset! 0 days since last incident.")