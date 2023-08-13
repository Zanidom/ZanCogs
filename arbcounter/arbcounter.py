from redbot.core import checks, Config, commands

class ArbCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.version = "b0.1"
        self.redver = "3.5.3"
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "Config":{
                "Registered":False
                }
            }
        self.config.register_guild(**default_guild)

    @commands.group(name="ac", autohelp=False)
    async def arbcounter(self, ctx, *, lastMessage = ""):
        """Arbitrary counter commands"""
        if ctx.invoked_subcommand is None:
            if lastMessage == "" or len(lastMessage) < 2:
                return

            guild = ctx.guild
            await self.check_server_settings(guild)
            serverConfig = await self.config.guild(guild).Config()

            indivStrings = lastMessage.split(" ")
            if indivStrings[0].lower() == "set":
                if len(indivStrings) < 3:
                    await ctx.send("Not enough arguments supplied.")
                    return
                await self.ac_set(ctx, indivStrings[1], indivStrings[2])
                return

            if indivStrings[0] == "delete":
                if len(indivStrings) < 2:
                    await ctx.send("Not enough arguments supplied.")
                    return
                await self.ac_delete(ctx, indivStrings[1])
                return

            mesSuffix = lastMessage[-2:]

            if mesSuffix == "++":
                tokenName = lastMessage[:-2].lower()
                try:
                    val = int(serverConfig[tokenName]) + 1
                    serverConfig[tokenName] = val
                except:
                    val = 1
                    serverConfig[tokenName] = val
                await self.config.guild(guild).Config.set(serverConfig) #save our changes
                await ctx.send(f"`{tokenName}` is now {val}.")
            elif mesSuffix == "--":
                tokenName = lastMessage[:-2].lower()
                try:
                    val = int(serverConfig[tokenName]) - 1
                    serverConfig[tokenName] = val
                except:
                    val = -1
                    serverConfig[tokenName] = val

                await self.config.guild(guild).Config.set(serverConfig) #save our changes
                await ctx.send(f"`{tokenName}` is now {val}.")

            else:
                try:
                    val = int(serverConfig[lastMessage.lower()])
                except:
                    val = 0
                await ctx.send(f"`{lastMessage.lower()}` is {val}.")
                pass
            pass
        return True
    
    async def ac_set(self, ctx, counterToken: str, value: int):
        """Set a value for a counter token"""
        guild = ctx.guild
        await self.check_server_settings(guild)
        serverConfig = await self.config.guild(guild).Config()
        serverConfig[counterToken.lower()] = value
        await self.config.guild(guild).Config.set(serverConfig) #save our changes
        await ctx.send(f"Set `{counterToken.lower()}` to {value}.")

    @arbcounter.command(name="delete")
    async def ac_delete(self, ctx, counterToken: str):
        """Delete a counter token"""
        
        guild = ctx.guild
        await self.check_server_settings(guild)
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

    async def check_server_settings(self, guild):
        cur = await self.config.guild(guild).Config()
        if not cur["Registered"]:
            cur["Registered"] = True
            await self.config.guild(guild).Config.set(cur)
          