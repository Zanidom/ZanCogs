from redbot.core import checks, Config, commands
import discord 
import re
import io

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

    @commands.group(name="ac", autohelp=False, invoke_without_command=True)
    async def arbcounter(self, ctx, *, lastMessage = ""):
        """Arbitrary counter commands"""
        if ctx.invoked_subcommand is None:
            print("Break")
            if lastMessage == "" or len(lastMessage) < 2:
                return

            guild = ctx.guild
            await self.check_server_settings(guild)
            serverConfig = await self.config.guild(guild).Config()

            indivStrings = lastMessage.replace('\n','').split(" ")
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

            if indivStrings[0] == "search":
                if len(indivStrings) < 2:
                    await ctx.send("Not enough arguments supplied.")
                    return
                await self.ac_search(ctx, indivStrings[1])
                return
            
            mesSuffix = lastMessage[-2:]

            if mesSuffix == "++":
                tokenName = ''.join(indivStrings)[:-2].lower()

                try:
                    val = int(serverConfig[tokenName]) + 1
                    serverConfig[tokenName] = val
                except:
                    await ctx.send(f"`{tokenName}` isn't initialized yet. Try using ac set {tokenName} first.")
                    return
                await self.config.guild(guild).Config.set(serverConfig) #save our changes
                await ctx.send(f"`{tokenName}` is now {val}.")
            elif mesSuffix == "--":
                tokenName = ''.join(indivStrings)[:-2].lower()
                try:
                    val = int(serverConfig[tokenName]) - 1
                    serverConfig[tokenName] = val
                except:
                    await ctx.send(f"`{tokenName}` isn't initialized yet. Try using ac set {tokenName} first.")
                    return
                await self.config.guild(guild).Config.set(serverConfig) #save our changes
                await ctx.send(f"`{tokenName}` is now {val}.")

            else:
                output = await self.ParseNonCommand(ctx, lastMessage)
                if output is None:
                    try:
                        val = int(serverConfig[lastMessage.lower()])
                    except:
                        await ctx.send(f"`{lastMessage.lower()}` has no value yet.")
                        return True
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

    @arbcounter.command(name="search")
    async def ac_searchcom(self, ctx, searchString: str):
        """Search all tokens for a given string - ac search <search>"""
        await self.ac_search(ctx, searchString)
        pass   

    async def check_server_settings(self, guild):
        cur = await self.config.guild(guild).Config()
        if not cur["Registered"]:
            cur["Registered"] = True
            await self.config.guild(guild).Config.set(cur)
    
    async def ac_search(self, ctx, search_term):
        """Searches for keys in the dictionary containing the search term."""
        search_term = search_term.strip()

        if not search_term:
            await ctx.send("Please provide a search term.")
            return

        guild = ctx.guild
        serverConfig = await self.config.guild(guild).Config()

        results = {k: v for k, v in serverConfig.items() if search_term.lower() in k.lower() and k != "Registered"}

        if not results:
            await ctx.send(f"No results found for '{search_term}'.")
            return
        
        output = "\n".join([f"{k}: {v}" for k, v in results.items()])

        if len(output) > 4000:
            middle = len(output) // 2  # Integer division to get the midpoint
            first_half = output[:middle]
            second_half = output[middle:]
            embedOut = discord.Embed(title=search_term, description=first_half)
            await ctx.send(embed = embedOut)
            embedOut = discord.Embed(title=search_term, description=second_half)
            await ctx.send(embed = embedOut)
        else:
            embedOut = discord.Embed(title=search_term, description=output)
            await ctx.send(embed = embedOut)

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
                current_value = int(serverConfig[token])
                serverConfig[token] = current_value + number
            except:
                serverConfig[token] = number

            await self.config.guild(guild).Config.set(serverConfig) #save our changes

            await ctx.send(f"`{token.lower()}` is now {serverConfig[token]}.")
            return serverConfig[token]
        else:
            return None
        
    @arbcounter.command(name="clean")
    @checks.admin_or_permissions(manage_guild=True)
    async def cleandata(self, ctx):
        """Cleans the dictionary by removing invalid entries."""
        guild = ctx.guild
        serverConfig = await self.config.guild(guild).Config()
        serverConfig = clean_dictionary(serverConfig)
        await self.config.guild(guild).Config.set(serverConfig) #save our changes
        await ctx.send("Dictionary has been cleaned.")

    @arbcounter.command(name="download")
    @checks.admin()
    async def download(self, ctx):
        """Download the data as a text file."""
        guild = ctx.guild
        serverConfig = await self.config.guild(guild).Config()
        content = "\n".join([f"{key}: {value}" for key, value in serverConfig.items()])
        
        with io.StringIO(content) as file:
            discord_file = discord.File(file, filename="data.txt")
            await ctx.author.send("Here's your data:", file=discord_file)
            await ctx.send("Data has been sent to you in a private message.")

def clean_dictionary(data: dict) -> dict:
    """
    Remove keys from dictionary which have whitespaces or upper-case characters, excluding the "Registered" key.
    
    Parameters:
    - data (dict): The dictionary to clean.

    Returns:
    - dict: Cleaned dictionary.
    """
    to_remove = [key for key in data if key != "Registered" and (any(c.isspace() or c.isupper() or '\n' in c for c in key))]

    for key in to_remove:
        del data[key]

    return data
