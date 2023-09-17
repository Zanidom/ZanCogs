from redbot.core import Config, commands
import requests

class Syllables(commands.Cog):
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

    @commands.group(name="syllables", autohelp=False, aliases=['syl','syllable','sc'])

    async def syllables(self, ctx, *, lastMessage = ""):
        """Syllable counter"""
        if ctx.invoked_subcommand is None:
            if lastMessage == "":
                await ctx.send("No word found.")
                return
        # Define the API URL with the word as a parameter
        url = f"https://api.datamuse.com/words?sp={lastMessage}&md=s"

        # Make the API request
        response = requests.get(url)
        nSyllables = 0
        # Check for a valid response
        if response.status_code == 200:
            data = response.json()
            if data and 'numSyllables' in data[0]:
                try:
                    nSyllables = int(data[0]['numSyllables'])
                except:
                    await ctx.send("Invalid response received [1].")
                    return
            else:
                #It'll reach here if we send something and get a valid response but no syllables
                if '-' in lastMessage:
                    nSyllables = self.hyphenTry(lastMessage)
                    if nSyllables == 0:
                        await ctx.send(f"No syllable data for {lastMessage}.")
                    else:
                        sylPlural = "syllables"
                        if nSyllables == 1:
                            sylPlural = "syllable"
                        await ctx.send(f"\"{lastMessage}\" has {nSyllables} {sylPlural}.")
                else:
                    await ctx.send(f"No syllable data for {lastMessage}.")
                return
        else:
             await ctx.send("Invalid response received [3].")
             return

        sylPlural = "syllables"
        if nSyllables == 1:
            sylPlural = "syllable"
        await ctx.send(f"\"{lastMessage}\" has {nSyllables} {sylPlural}.")

    def hyphenTry(self, input:str):
        syllableCount = 0
        strOut = input.split('-')

        for word in strOut:
            url = f"https://api.datamuse.com/words?sp={word}&md=s"

            response = requests.get(url)
            nSyllables = 0
            if response.status_code == 200:
                data = response.json()
                if data and 'numSyllables' in data[0]:
                    try:
                        nSyllables = int(data[0]['numSyllables'])
                    except:
                        return 0
                else:
                    return 0
            else:
                 return 0
            syllableCount += nSyllables

        return syllableCount