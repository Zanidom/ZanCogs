from ast import alias
from redbot.core import Config, commands
import random

class Sixball(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.version = "b0.1"
        self.redver = "3.5.3"
        self.Answers = ["Password required",
                        "You woke me up for this?",
                        "No legal basis to say...",
                        "Server error, try again later",
                        "I don't care",
                        "Let's circle back to that in a bit",
                        "What? Sorry, I wasn't listening",
                        "Beats me",
                        "What a terrible question!",
                        "Look, I'm just a toy...",
                        "42",
                        "Ask a different ball",
                        "In this economy?",
                        "Please deposit 25 cents and try again",
                        "That's a toughie",
                        r"¯\_(ツ)_/¯",
                        "Dunno",
                        "...Do I have to answer?",
                        "Ask again in pig latin"]

    @commands.group(name="6", autohelp=False, aliases=['6ball'])

    async def sixball(self, ctx, *, lastMessage = ""):
        """Six-ball! Ask and see what it says."""
        sixballresponse = random.choice(self.Answers)
        await ctx.reply(sixballresponse)