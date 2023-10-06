import string
from redbot.core import commands

class Ciphers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ROT13", aliases=['rot13','rotthirteen'])
    async def ROT13(self, ctx, *, text: str):
        """ROT13 cipher"""
        result = str.maketrans(string.ascii_lowercase + string.ascii_uppercase,
                               string.ascii_lowercase[13:] + string.ascii_lowercase[:13] +
                               string.ascii_uppercase[13:] + string.ascii_uppercase[:13])
        await ctx.send(text.translate(result))

    @commands.command(name="ROT13.5", aliases=['rot13.5', 'rot13_5', 'ROT13_5'])
    async def ROT13_5(self, ctx, *, text: str):
        """ROT13.5 cipher (ROT13 for letters, ROT5 for numbers)"""
        result = str.maketrans(
            string.ascii_lowercase + string.ascii_uppercase + "0123456789",
            string.ascii_lowercase[13:] + string.ascii_lowercase[:13] +
            string.ascii_uppercase[13:] + string.ascii_uppercase[:13] +
            "5678901234")
        print(result)
        await ctx.send(text.translate(result))

    @commands.command(name="ROT47", aliases=['rot47'])
    async def ROT47(self, ctx, *, text: str):
        """ROT47 cipher"""
        result = str.maketrans(
            "".join(chr(i) for i in range(33, 80)),
            "".join(chr(i) for i in range(47, 94)))
        await ctx.send(text.translate(result))

    @commands.command(name='caesar', aliases=['caeser'])
    async def caeser(self, ctx, *, args: str):
        """Caesar cipher with custom shift"""
        *text, shift = args.rsplit(" ", 1)
        text = " ".join(text)
        try:
            shift = int(shift)
            if -26 <= shift <= 26:
                result = str.maketrans(
                    string.ascii_lowercase + string.ascii_uppercase,
                    string.ascii_lowercase[shift:] + string.ascii_lowercase[:shift] +
                    string.ascii_uppercase[shift:] + string.ascii_uppercase[:shift])
                await ctx.send(text.translate(result))
            else:
                await ctx.send("Shift amount should be between -26 and 26.")
        except ValueError:
            await ctx.send("Please provide a valid integer for the shift amount.")

    @commands.command(name="a1z26",aliases=['az'])
    async def a1z26(self, ctx, *, text: str):
        """A1Z26 cipher (converts letters to corresponding numbers)"""
        result = ' '.join([str(ord(char) - 96) if char in string.ascii_lowercase else char for char in text.lower()])
        await ctx.send(result)
