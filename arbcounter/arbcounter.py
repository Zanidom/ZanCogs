from redbot.core import Config, commands

DEFAULT_COUNTER = {
    "value": 0
}

class ArbCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        self.config.register_global(**DEFAULT_COUNTER)

    @commands.group(name="ac")
    async def arbcounter(self, ctx):
        """Arbitrary counter commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @arbcounter.command(name="set")
    async def ac_set(self, ctx, counterToken: str, value: int):
        """Set a value for a counter token"""
        await self.config.counterToken.set(value)
        await ctx.send(f"Set `{counterToken}` to {value}.")

    @arbcounter.command(name="delete")
    async def ac_delete(self, ctx, counterToken: str):
        """Delete a counter token"""
        await self.config.clear_raw(counterToken)
        await ctx.send(f"Deleted `{counterToken}`.")

    @arbcounter.command(name="++")
    async def ac_increment(self, ctx, counterToken: str):
        """Increment a counter token by 1"""
        current_value = await self.config.counterToken()
        await self.config.counterToken.set(current_value + 1)
        await ctx.send(f"Incremented `{counterToken}` to {current_value + 1}.")

    @arbcounter.command(name="--")
    async def ac_decrement(self, ctx, counterToken: str):
        """Decrement a counter token by 1"""
        current_value = await self.config.counterToken()
        await self.config.counterToken.set(current_value - 1)
        await ctx.send(f"Decreased `{counterToken}` to {current_value - 1}.")

    @arbcounter.command()
    async def ac(self, ctx, counterToken: str):
        """Show the current value of a counter token"""
        value = await self.config.counterToken()
        if value is None:
            await ctx.send("This token has not been set.")
        else:
            await ctx.send(f"The value of `{counterToken}` is {value}.")