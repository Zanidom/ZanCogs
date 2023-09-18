from redbot.core import checks, Config, commands
import re

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
            indivStrings = [s for s in indivStrings if s.strip()]

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
                output = await self.ParseNonCommand(ctx, lastMessage)
                if output is None:
                    try:
                        val = int(serverConfig[lastMessage.lower()])
                    except:
                        val = 0
                    await ctx.send(f"`{lastMessage.lower()}` is {val}.")
                    pass
                else:
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

    @arbcounter.command(name="delete", autohelp=False, aliases=['del','remove','d'])
    async def ac_delete(self, ctx, counterToken: str):
        """Delete a counter token"""
        
        guild = ctx.guild
        await self.check_server_settings(guild)
        serverConfig = await self.config.guild(guild).Config()
        success = True
        try:
            del serverConfig[counterToken]
        except:
            success = False

        if success:
            await self.config.clear_raw(counterToken)
            await self.config.guild(guild).Config.set(serverConfig) #save our changes
            await ctx.send(f"Deleted `{counterToken}`.")
        else:
            await ctx.send(f"Couldn't find {counterToken}.")

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
    

    async def ParseNonCommand(self, ctx, instring:str):
        instring = re.sub(r'\s+', '', instring)
        match = re.search(r'([-+]\d+)$', instring)

        if match:
            operation = match.group(1)
            token = instring[:match.start()].strip()
            number = int(operation)
            guild = ctx.guild

            serverConfig = await self.config.guild(guild).Config()

            try:
                print("Made it!")
                current_value = int(serverConfig[token])
                serverConfig[token] = current_value + number
            except:
                serverConfig[token] = number

            await self.config.guild(guild).Config.set(serverConfig) #save our changes

            await ctx.send(f"`{token.lower()}` is now {serverConfig[token]}.")
            return serverConfig[token]
        else:
            return None
