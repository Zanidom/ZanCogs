import string
from redbot.core import commands

async def get_text_or_reply(ctx, text: str):
    """Helper function to get the text or fetch the content of the replied message or the previous message."""
    if not text:
        # Check if the command message is a reply to another message
        if ctx.message.reference:
            # Fetch the referenced message
            referenced_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            return referenced_msg.content
        else:
            # Fetch message history and get the message immediately before the user's command
            messages = []
            async for message in ctx.channel.history(limit=2):
                messages.append(message)
                
            if len(messages) == 2:  # Ensure there's a previous message
                return messages[1].content  # The first message is the user's command, so we take the second
    return text


class Ciphers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ROT13", aliases=['rot13','rotthirteen'])
    async def ROT13(self, ctx, *, text: str = ""):
        """ROT13 cipher"""
        text = await get_text_or_reply(ctx, text)
        result = str.maketrans(string.ascii_lowercase + string.ascii_uppercase,
                               string.ascii_lowercase[13:] + string.ascii_lowercase[:13] +
                               string.ascii_uppercase[13:] + string.ascii_uppercase[:13])
        await ctx.send(text.translate(result))

    @commands.command(name="ROT13.5", aliases=['rot13.5', 'rot13_5', 'ROT13_5'])
    async def ROT13_5(self, ctx, *, text: str = ""):
        """ROT13.5 cipher (ROT13 for letters, ROT5 for numbers)"""
        text = await get_text_or_reply(ctx, text)
        result = str.maketrans(
            string.ascii_lowercase + string.ascii_uppercase + "0123456789",
            string.ascii_lowercase[13:] + string.ascii_lowercase[:13] +
            string.ascii_uppercase[13:] + string.ascii_uppercase[:13] +
            "5678901234")
        await ctx.send(text.translate(result))

    @commands.command(name="ROT47", aliases=['rot47'])
    async def ROT47(self, ctx, *, text: str = ""):
        """ROT47 cipher"""
        text = await get_text_or_reply(ctx, text)
        result = str.maketrans(
            "".join(chr(i) for i in range(33, 80)),
            "".join(chr(i) for i in range(47, 94)))
        await ctx.send(text.translate(result))

    @commands.command(name='caesar', aliases=['caeser'])
    async def caeser(self, ctx, shift: int, *, text: str = ''):
        """Caesar cipher with custom shift"""
        if not (-26 <= shift <= 26):
            await ctx.send("Shift amount should be between -26 and 26.")
            return

        # If text is empty, attempt to get text from a replied-to message
        if not text:
            if ctx.message.reference:
                referenced_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                text = referenced_msg.content

        # If text is still empty or None, inform the user and return
        if not text:
            await ctx.send("Please provide text or reply to a message to cipher.")
            return

        result = str.maketrans(
            string.ascii_lowercase + string.ascii_uppercase,
            string.ascii_lowercase[shift:] + string.ascii_lowercase[:shift] +
            string.ascii_uppercase[shift:] + string.ascii_uppercase[:shift])
    
        await ctx.send(text.translate(result))

    @commands.command(name="a1z26",aliases=['az'])
    async def a1z26(self, ctx, *, text: str = ""):
        """A1Z26 cipher (converts letters to corresponding numbers)"""
        text = await get_text_or_reply(ctx, text)
        result = ' '.join([str(ord(char) - 96) if char in string.ascii_lowercase else char for char in text.lower()])
        await ctx.send(result)
