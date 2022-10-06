import asyncio
import datetime
import time
import discord
from discord.utils import get
from redbot.core import commands
from redbot.core import checks, Config, bank

class Kotr(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.version = "b0.1"
        self.redver = "3.3.9"
        self.config = Config.get_conf(self, identifier=6942069, force_registration=True)
        default_guild = {
            "Config": {
                "Cost": 100,
                "MinCost": 100,
                "Increase": 100,
                "Decrease": 5,
                "Timer": 300,
                "LastPurchase":0,
                "LastPaid":0,
                "Cooldown": 600,
                "Registered": False,
                "RecentlyStarted":False
            },
            "OwnerInfo":{
                "Owner": 1,
            },
            "RoleInfo":{
                "Role": "",
            },

            "Colours":{
                "Light Blue":0xAAE2FF,
                "Blue":0x5479FF,
                "Dark Blue":0x2D4189,
                "Light Red":0xFF6D79,
                "Red":0xFF2335,
                "Dark Red":0xAD1824,
                "Light Pink":0xFF84E2,
                "Dark Pink":0xAD0580,
                "Light Orange":0xFF9359,
                "Orange":0xFF5400,
                "Dark Orange":0xC43E00,
                "Brown":0x824024,
                "Light Purple":0x7F00C9,
                "Dark Purple":0x580082,
                "White":0xFFFFFF
                }
        }
        self.config.register_guild(**default_guild)
      
    @commands.group(no_pm=True, pass_context=True)
    async def kotr(self, ctx):
        """Set config options for KotR"""
        pass

    @kotr.command(name="owner")
    async def _info_kotr(self, ctx):
        """Shows info about the current role owner."""
        guild = ctx.guild
        await self.check_server_settings(guild)
        serverConfig = await self.config.guild(guild).Config()
        ownerInfo = await self.config.guild(guild).OwnerInfo()
        ownerId = ownerInfo["Owner"]
        
        try:
            ownerUser = await self.bot.fetch_user(ownerId)
        except:
            await ctx.send("Error looking up user. The role may not have been bought yet.")
            return

        avatar = ownerUser.avatar_url
        embed = discord.Embed(colour=0x0066FF, description="\n")
        embed.title = "{} current KotR settings:".format(guild.name)
        embed.set_thumbnail(url=avatar)
        embed.add_field(name="Current KotR owner", value=ownerUser.display_name)
        embed.add_field(name="Currently owned since", value=datetime.datetime.fromtimestamp(serverConfig["LastPurchase"]).strftime('%Y-%m-%d %H:%M:%S'))
        embed.add_field(name="Bought for", value=serverConfig["LastPaid"])
        await ctx.send(embed=embed)

    @kotr.command(name="config")
    @checks.admin_or_permissions(manage_guild=True)
    async def _config_kotr(self, ctx):
        """Shows the Kotr configuration for this server."""
        guild = ctx.guild
        await self.check_server_settings(guild)
        serverConfig = await self.config.guild(guild).Config()
        ownerInfo = await self.config.guild(guild).OwnerInfo()
        roleInfo = await self.config.guild(guild).RoleInfo()
        ownerId = ownerInfo["Owner"]

        role = get(ctx.guild.roles, name=roleInfo["Role"])

        if role is None:
            role = "Invalid role configuration."

        try:
            ownerUser = await self.bot.fetch_user(ownerId)
        except:
            ownerUser = "Not yet owned."
            
        curTime = int(time.time())
        timeDif = curTime - serverConfig["LastPurchase"]
        cost = serverConfig["Cost"] - int((timeDif / serverConfig["Timer"])) * serverConfig["Decrease"]
        if cost < serverConfig["MinCost"]:
            cost = serverConfig["MinCost"]

        embed = discord.Embed(colour=0x0066FF, description="\n")
        embed.title = "{} current KotR settings:".format(guild.name)
        embed.add_field(name="Current KotR cost", value=cost)
        embed.add_field(name="Current minimum cost:", value=serverConfig["MinCost"])
        embed.add_field(name="Current increase on purchase", value=serverConfig["Increase"])
        embed.add_field(name="Current decrease per tick:", value=serverConfig["Decrease"])
        embed.add_field(name="Current time per tick:", value=serverConfig["Timer"])
        embed.add_field(name="Current cooldown between purchases:", value=serverConfig["Cooldown"])
        embed.add_field(name="Current role:", value=role)
        embed.add_field(name="Current owner:", value=ownerUser)
        await ctx.send(embed=embed)

    @kotr.command(name="buyrole")
    async def _buy_kotrRole(self, ctx):
        """Makes you the shiny new owner of the KotR role!"""
        config = await self.config.guild(ctx.guild).Config()
        author = ctx.message.author
        costIncrease = config["Increase"]
        curBal = await bank.get_balance(ctx.author)
        ownerInfo = await self.config.guild(ctx.guild).OwnerInfo()
        roleInfo = await self.config.guild(ctx.guild).RoleInfo()
        role = get(ctx.guild.roles, name=roleInfo["Role"])

        if author.id == ownerInfo["Owner"]:
            await ctx.send("You already own the role!")
            return

        curTime = int(time.time())
        timeDif = curTime - config["LastPurchase"]
        cost = config["Cost"] - int((timeDif / config["Timer"])) * config["Decrease"]
        if cost < config["MinCost"]:
            cost = config["MinCost"]

        if timeDif < config["Cooldown"]:
            await ctx.send(str("It's too soon! Buying this role is still on cooldown for another ~{} seconds.").format(config["Cooldown"]-timeDif))
            return

        if role is None:
            await ctx.send("Error looking up role. The role may not have been configured.")
            return

        if not curBal >= cost:
            await ctx.send("You don't have enough BMB to buy the role!\nYou have {0} and it currently costs {1}.".format(curBal,cost))
            return
        else:
            await ctx.send("You have enough BMB to buy the role.\nYou have {0} and it currently costs {1}.\nAre you sure you want to buy? (yes/no/y/n)".format(curBal,cost))
        check = lambda m: m.author == author
        
        try:
            response = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled purchase. You took too long.")
            return
        
        if response.content.title().lower() == "no" or response.content.title().lower() == "n":
            await ctx.send("Cancelled purchase.")
            return

        if response.content.title().lower() == "yes" or response.content.title().lower() == "ye" or response.content.title().lower() == "y":
            
            try:
                oldOwner = ctx.guild.get_member(ownerInfo["Owner"])
            except:
                oldOwner = None
                await ctx.send("No previous owner! Congratulations on being the first.")
           
            ownerInfo["Owner"] = author.id
            await bank.withdraw_credits(author, cost)

            try:
                if oldOwner != None:
                    await oldOwner.remove_roles(role)
                await author.add_roles(role)
            except:
                await ctx.send("Something went wrong - possible permissions issue. Exiting procedure.")
                return
            
            newCost = cost+costIncrease
            await ctx.send("Purchase successful. New price: {0}".format(newCost))
            config["Cost"] = newCost
            config["LastPurchase"] = curTime
            config["LastPaid"] = cost
            await self.config.guild(ctx.guild).Config.set(config)
            await self.config.guild(ctx.guild).OwnerInfo.set(ownerInfo)
            return
        return

    @kotr.command(name="help")
    async def _kotrHelp(self, ctx):
        """Get some info about the KotR cog!"""
        await ctx.send("KotR - King of the Role - is a small game with a role that only one person can own at a time.\nIf you want to buy the role, try ;kotr buyrole. If you own the role, you can set your own colour with ;kotr setcolor\n\nIf this is newly installed, you'll want to use ;setkotr and check out some of the configuration options.\nMessage Zan#6176 if you have any feedback or requests.")

    @kotr.command(name="setcolour")
    async def _set_kotrColour(self, ctx, stringput = "", stringput2 ="", stringput3 = "", stringput4 = "", stringput5 = "",  useColor = False):  #little hacky way to get around Discord telling me inputs are wrong. Will error if there's a long ass colour name. lol.
        """If you're the owner, you can choose your colour!"""
        colourList = await self.config.guild(ctx.guild).Colours()
        author = ctx.message.author
        ownerInfo = await self.config.guild(ctx.guild).OwnerInfo()
        roleInfo = await self.config.guild(ctx.guild).RoleInfo()
        role = get(ctx.guild.roles, name=roleInfo["Role"])

        colourText = "color" if useColor else "colour"
        commandLength = 15 if useColor else 16
        response = None
        

        if len(ctx.message.content) > commandLength:
            response = ctx.message.content[commandLength:]

        if role is None:
            await ctx.send("Error looking up role. The role may not have been configured.")
            return
       
        if author.id != ownerInfo["Owner"]:
            await ctx.send("You don't own the role currently!\nOnly the owner of the role may set their {}.".format(colourText))
            return

        check = lambda m: m.author == author
        
        if response is None:
            
            await self._get_colours(ctx)

            try:
                response = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                await ctx.send("Cancelled change. You took too long.")
                return
            
            if response.content.title().lower() == "cancel" or response.content.title().lower() == "exit":
                await ctx.send("Cancelled change.")
                return

            if response.content.title() in colourList:
                newcolour = colourList[response.content.title()]
        elif response.title() in colourList:
            newcolour = colourList[response.title()]
        else:
            await ctx.send("That's not a valid colour.")
            return

        try:
            await role.edit(colour=newcolour)
        except:
            await ctx.send("Miscellaneous error when changing {}, probably a permissions issue.".format(colourText))
            return
        
        await ctx.send("Change successful! Enjoy your new {}.".format(colourText))
        return

    @kotr.command(name="setcolor", hidden=True)
    async def _set_kotrColor(self, ctx):
        await self._set_kotrColour(ctx,useColor=True)


    @kotr.command(name="cost")
    async def _get_kotrCostr(self, ctx):
        config = await self.config.guild(ctx.guild).Config()
        await ctx.send("The role currently costs {}.".format(config["Cost"]))

    @kotr.command(name="colourlist")
    async def _get_colours(self,ctx):
        """Shows a list of all configured colours on the server."""
        colourList = await self.config.guild(ctx.guild).Colours()
        new_colourList = {}
        for c in sorted(colourList, key=len, reverse=True):
            new_colourList[c] = colourList[c]

        await ctx.send("Current options:")
        colours = "```"
        for colour, colourValue in new_colourList.items():
            colours += "{0}: {1}\n".format(colour,format(colourValue, 'X').zfill(6))
        colours += "```\nYou can check these colours out here: https://g.co/kgs/KpKq4S"
        await ctx.send(colours)

    @kotr.command(name="colorlist", hidden=True)
    async def _get_colors(self,ctx):
        await self._get_colours(ctx)

    @commands.group(no_pm=True, pass_context=True)
    async def setkotr(self, ctx):
        """Set config options for KotR"""
        pass

    @setkotr.command(name="role", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrrole(self, ctx, roleName: str):
        """Set the current cost of the role."""
        guild = ctx.guild
        roleInfo = await self.config.guild(guild).RoleInfo()
        if "<@&" in roleName:
            role = guild.get_role(int(roleName[3:-1]))
        else:
            role = get(guild.roles, name=roleName)
        if role is None:
            await ctx.send(str("Couldn't find a role with the name {}. Exiting.").format(roleName))
            return
        roleInfo["Role"] = role.name
        await self.config.guild(ctx.guild).RoleInfo.set(roleInfo)
        await ctx.send("Command succeeded. New role: {0}".format(roleInfo))
        pass  

    @setkotr.command(name="cost", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrcost(self, ctx, newCost: int):
        """Set the current cost of the role."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["Cost"] = newCost
        await ctx.send("Command succeeded. New price: {0}".format(newCost))
        await self.config.guild(guild).Config.set(config) #save our changes
        pass  
    
    @setkotr.command(name="mincost", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrmincost(self, ctx, newCost: int):
        """Set the minimum cost of the role."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["MinCost"] = newCost
        await ctx.send("Command succeeded. New minimum cost: {0}".format(newCost))
        await self.config.guild(guild).Config.set(config) #save our changes
        pass  

    @setkotr.command(name="increase", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrincrease(self, ctx, newIncrease: int):
        """Set how much the cost increases when purchased."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["Increase"] = newIncrease
        await ctx.send("Command succeeded. New increase on purchase: {0}".format(newIncrease))
        await self.config.guild(guild).Config.set(config) #save our changes
        pass  

    @setkotr.command(name="decrease", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrdecrease(self, ctx, newDecrease: int):
        """Set how much the price decreases by each tick."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["Decrease"] = newDecrease
        await ctx.send("Command succeeded. New decrease each tick: {0}".format(newDecrease))
        await self.config.guild(guild).Config.set(config) #save our changes
        pass   

    @setkotr.command(name="timer", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrtimer(self, ctx, newTimer: int):
        """Set the time between ticks."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["Timer"] = newTimer
        await ctx.send("Command succeeded. New time between ticks: {0}".format(newTimer))
        await self.config.guild(guild).Config.set(config) #save our changes
        pass  

    @setkotr.command(name="cooldown", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrcooldown(self, ctx, newCooldown: int):
        """Set the cooldown between the role being bought."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["Cooldown"] = newCooldown
        await ctx.send("Command succeeded. New cooldown prior to more purchases: {0}".format(newCooldown))
        await self.config.guild(guild).Config.set(config) #save our changes
        pass  

    @setkotr.command(name="addcolour", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_addcolour(self, ctx, useColor = False):
        """Add a colour to the list."""
        colourList = await self.config.guild(ctx.guild).Colours()
        check = lambda m: m.author == ctx.author
        newColourName = ""
        
        colourText = "color" if useColor else "colour"

        await ctx.send("Please input your new {} name.".format(colourText))
        try:
            response = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled, you took too long.")
            return

        if response.content in colourList:
            await ctx.send("That {} name already exists - would you like to overwrite it?".format(colourText))
            try:
                response = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                await ctx.send("Cancelled, you took too long.")
                return
            if response.content.title().lower() == "no" or response.content.title().lower() == "n":
                await ctx.send("Cancelled adding {}.".format(colourText))
                return
            if response.content.title().lower() == "yes" or response.content.title().lower() == "ye" or response.content.title().lower() == "y":
                newColourName = response.content.title()
        else:
           newColourName = response.content.title()
           
        await ctx.send("What {} value would you like this to be?\nFormats:   0x123456    #123456    or    123456    accepted".format(colourText))
        try:
            response = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled, you took too long.")
            return

        try:
            if "0x" in response.content.lower():
                newColour = int(response.content.lower()[2:], base=16)
                await ctx.send("0x found, trying to parse {}".format(response.content.lower()[2:]))
            elif "#" in response.content.lower():
                newColour = int(response.content.lower()[1:], base=16)
                await ctx.send("0x found, trying to parse {}".format(response.content.lower()[1:]))
            else:
                newColour = int(response.content.lower(), base=16)
                await ctx.send("0x found, trying to parse {}".format(response.content.lower()))
        except:
            await ctx.send("Could not parse your input, cancelling.")
            return

        colourList[newColourName] = newColour
        await ctx.send("Successfully added {0} with value {1} to the {2} list.".format(newColourName,format(newColour,'X').zfill(6),colourText))
        await self.config.guild(ctx.guild).Colours.set(colourList)

    @setkotr.command(name="addcolor", pass_context=True, hidden=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_addcolor(self, ctx):
        await self._output_addcolour(ctx, True)

    @setkotr.command(name="removecolour", pass_context=True, hidden=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_removecolour(self, ctx, useColor = False):
        """Removes a colour from the list."""
        colourList = await self.config.guild(ctx.guild).Colours()
        check = lambda m: m.author == ctx.author

        colourText = "color" if useColor else "colour"

        await ctx.send("Please input the {} you want to delete.".format(colourText))
        try:
            colourNameMSG = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled, you took too long.")
            return

        colourName = colourNameMSG.content.title()
        if colourName not in colourList:
            await ctx.send("No {} with that name found. Exiting.".format(colourText))
            return
        
        colourVal = colourList[colourName]

        await ctx.send("Are you sure you want to delete {0} with {2} value {1}?".format(colourName, format(colourVal,'X').zfill(6),colourText))
        try:
            response = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled, you took too long.")
            return

        if response.content.title().lower() == "no" or response.content.title().lower() == "n":
            await ctx.send("Cancelled {} removal.".format(colourText))
            return

        if response.content.title().lower() == "yes" or response.content.title().lower() == "ye" or response.content.title().lower() == "y":
            del colourList[colourName]
            await self.config.guild(ctx.guild).Colours.clear_raw(colourName)
            await ctx.send("Successfully deleted {0} with value {1} from the {2} list.".format(colourName,format(colourVal,'X').zfill(6),colourText))
            await self.config.guild(ctx.guild).Colours.set(colourList)  
        else:
            await ctx.send("Invalid reponse received. Cancelled {} removal.".format(colourText))

    @setkotr.command(name="removecolor", pass_context=True, hidden=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_removecolor(self, ctx):
        await self._output_removecolour(ctx, True)
    
    async def check_server_settings(self, guild):
        cur = await self.config.guild(guild).Config()
        if not cur["Registered"]:
            cur["Registered"] = True
            await self.config.guild(guild).Config.set(cur)
          