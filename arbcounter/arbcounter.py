from redbot.core import Config, commands

class ArbCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789011, force_registration=True)
        default_guild = {}
        self.config.register_guild(**default_guild)

    @commands.group(name="ac")
    async def arbcounter(self, ctx, *, lastMessage = ""):
        """Arbitrary counter commands"""
        if ctx.invoked_subcommand is None:
            guild = ctx.guild
            serverConfig = await self.config.guild(guild).Config()

            mesSuffix = lastMessage[-2]

            if mesSuffix == "++":
                tokenName = lastMessage[:-2]
                val = serverConfig[tokenName] + 1
                serverConfig[tokenName] = val
                await self.config.guild(guild).Config.set(serverConfig) #save our changes
                await ctx.send(f"{lastMessage}` is now {val}.")
            elif mesSuffix == "--":
                tokenName = lastMessage[:-2]
                val = serverConfig[tokenName] - 1
                serverConfig[tokenName] = val
                await self.config.guild(guild).Config.set(serverConfig) #save our changes
                await ctx.send(f"{lastMessage}` is now {val}.")
            else:
                val = serverConfig[lastMessage]
                if val is None:
                    await ctx.send("This token has not been set.")
                else:
                    await ctx.send(f"The value of `{lastMessage}` is {val}.")
                pass
            pass
        pass

    @arbcounter.command(name="set")
    async def ac_set(self, ctx, counterToken: str, value: int):
        """Set a value for a counter token"""
        guild = ctx.guild
        serverConfig = await self.config.guild(guild).Config()
        serverConfig[counterToken] = value
        await self.config.guild(guild).Config.set(serverConfig) #save our changes
        await ctx.send(f"Set `{counterToken}` to {value}.")

    @arbcounter.command(name="delete")
    async def ac_delete(self, ctx, counterToken: str):
        """Delete a counter token"""
        
        guild = ctx.guild
        serverConfig = await self.config.guild(guild).Config()
        del serverConfig[counterToken]
        await self.config.clear_raw(counterToken)
        await self.config.guild(guild).Config.set(serverConfig) #save our changes
        await ctx.send(f"Deleted `{counterToken}`.")

    @arbcounter.command(name="++")
    async def ac_increment(self, ctx, counterToken: str):
        """Increment a counter token by 1 - ac tokenname++"""
        pass

    @arbcounter.command(name="--")
    async def ac_decrement(self, ctx, counterToken: str):
        """Decrement a counter by 1 - ac tokenname--"""
        pass
