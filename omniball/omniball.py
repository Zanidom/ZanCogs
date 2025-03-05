from ast import alias
from redbot.core import Config, commands
import random

class Omniball(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.version = "b0.1"
        self.redver = "3.5.3"
        self.SixBallAnswers = ["Password required",
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
        
        self.SevenBallAnswers = ["You'll want to be hydrated for this",
                        "A star in the making",
                        "Yes... But..?",
                        "Needs to be about 20% sluttier",
                        "Make sure to get an STD test first",
                        "Don't forget protection",
                        "Wait until Reddit sees this",
                        "Paint the town red",
                        "🤫",
                        "Its going to be a banner day",
                        "Get verified and ask again",
                        "Take off your clothes and try again",
                        "Depends on what you mean by 'win'",
                        "More nudes required to answer",
                        "Nafjre rapbqrq",
                        "No... But...?",
                        "No, and just for asking go do 20 spanks",
                        "Go big or go home",
                        "NUDES! Sorry. NUDES! Sorry. NUDES!",
                        "Is that it?"]
        
        self.EightBallAnswers = ["It is certain",
                        "It is decidedly so",
                        "Without a doubt",
                        "Yes definitely",
                        "You may rely on it",
                        "As I see it, yes",
                        "Most likely",
                        "Outlook good",
                        "Yes",
                        "Signs point to yes",
                        "Reply hazy, try again",
                        "Ask again later",
                        "Better not tell you now",
                        "Cannot predict now",
                        "Concentrate and ask again",
                        "Don't count on it",
                        "My reply is no",
                        "My sources say no",
                        "Outlook not so good",
                        "Very doubtful"]
        
        self.NineBallAnswers = ["Good luck with that",
                        "You can't handle the truth",
                        "Well duh!",
                        "Battery low",
                        "Obviously",
                        "Not in a million years",
                        "Ask me again never",
                        "Yes, unless you screw it up",
                        "Of course, stupid question",
                        "Ask someone who cares",
                        "Whatever",
                        "#NotHappening",
                        "Are you serious?",
                        "Yes, if you leave me alone",
                        "Forget about it",
                        "Just Google it",
                        "Yeah, I don't think so",
                        "Like that'll happen",
                        "If you must",
                        "Loading..."]
        
        self.PosiVibesStone = ["If you can dream it, you can do it",
                        "Your energy is magnetic",
                        "You are a work in progress",
                        "Your younger self would be proud",
                        "Haters wish they were you",
                        "There is nobody doing it like you",
                        "Don't overthink things",
                        "You are bigger than your fears",
                        "Your opinion matters",
                        "You shine like a diamond",
                        "You are smart and capable",
                        "You are a badass",
                        "Trust your journey",
                        "You are braver than you know",
                        "You are your own superhero",
                        "Ambition looks good on you",
                        "Don't sweat the small stuff"]




    @commands.command(name="6", autohelp=False, aliases=['6ball','sixball','six'])
    async def sixball(self, ctx):
        """Six-ball! Ask and see what it says."""
        sixballresponse = random.choice(self.SixBallAnswers)
        await ctx.reply(sixballresponse)
        

    @commands.command(name="7", autohelp=False, aliases=['7ball','sevenball','seven'])
    async def sevenball(self, ctx, *, lastMessage = ""):
        """Seven-ball! Ask and see what it says."""
        sevenballresponse = random.choice(self.SevenBallAnswers)
        await ctx.reply(sevenballresponse)
        

    @commands.command(name="9", autohelp=False, aliases=['9ball','nineball','nine'])
    async def nineball(self, ctx, *, lastMessage = ""):
        """Nine-ball! Ask and see what it says."""
        nineballresponse = random.choice(self.NineBallAnswers)
        await ctx.reply(nineballresponse)

    @commands.command(name="posi", autohelp=False, aliases=['vibes','pos'])
    async def posivibes(self, ctx, *, lastMessage = ""):
        """A stone that gives you positive vibes."""
        posiChoice = random.choice(self.PosiVibesStone)
        await ctx.reply(posiChoice)
    
    @commands.command(name="omni", autohelp=False, aliases=['omniball','ball','0'])
    async def omniball(self, ctx, *, lastMessage = ""):
        """Omni-ball! It could say anything!"""
        answerPool = self.SixBallAnswers + self.SevenBallAnswers + self.EightBallAnswers + self.NineBallAnswers
        sixballresponse = random.choice(answerPool)
        await ctx.reply(sixballresponse)