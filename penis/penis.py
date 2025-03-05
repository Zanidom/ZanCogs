import discord
import random
from enum import Enum
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import pagify

class PenisOption(Enum):
    OPTIN = 1
    OPTOUT = 2

class Penis(commands.Cog):
    """Penis related commands."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=140060511)
        default_member = {
            "option": 1
        }
        self.config.register_member(**default_member)

    @commands.group(name="penis", autohelp=False, invoke_without_command=True)
    async def penis(self, ctx, *users: discord.Member):
        """Detects user's penis length

        This is 100% accurate.
        Enter multiple users for an accurate comparison!"""

        opted_in_users = []
        for user in users:
            user_option = await self.config.member(user).option()
            if user_option != PenisOption.OPTOUT.value:
                opted_in_users.append(user)

        if not users:
            await ctx.send_help()
            return

        if not opted_in_users:
            await ctx.send("None of the users you mentioned have opted in to penis commands.")
            return

        dongs = {}
        msg = ""
        state = random.getstate()

        for user in opted_in_users:
            random.seed(str(user.id))

            if ctx.bot.user.id == user.id:
                length = 50
            else:
                length = random.randint(0, 30)

            dongs[user] = "8{}D".format("=" * length)

        random.setstate(state)
        dongs = sorted(dongs.items(), key=lambda x: x[1])

        for user, dong in dongs:
            if user.id == 430064150438215681:
                msg += "**{}'s size:**\nLength exceeds Discord Message Limit - redacted.\n".format(user.display_name)
            else:
                msg += "**{}'s size:**\n{}\n".format(user.display_name, dong)

        for page in pagify(msg):
            await ctx.send(page)

    @penis.command(name="optin")
    async def optin(self, ctx):
        await self.config.member(ctx.author).option.set(PenisOption.OPTIN.value)
        await ctx.send(f"{ctx.author.mention}, you have opted into penis commands.")

    @penis.command("optout")
    async def optout(self, ctx):
        await self.config.member(ctx.author).option.set(PenisOption.OPTOUT.value)
        await ctx.send(f"{ctx.author.mention}, you have opted out of penis commands.")