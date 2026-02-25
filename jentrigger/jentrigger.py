from redbot.core import commands, Config, checks
from discord import Embed, ButtonStyle
from discord.ui import Button, View
import discord
from redbot.core import bank
import asyncio
import aiohttp
from discord.ext.commands import CommandError
import re

class ConfirmationView(discord.ui.View):
    def __init__(self, ctx, cost, cog, callback, command_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctx = ctx
        self.cost = cost
        self.cog = cog
        self.callback = callback  # Store the callback function
        self.command_name = command_name
        self.hasTriggered = False

    @discord.ui.button(label="Confirm", style=ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You cannot confirm this action.", ephemeral=True)
        if self.hasTriggered:
            await interaction.response.defer()
            return
        
        self.hasTriggered = True
        hasEnough = await self.cog.verify_currency(self.ctx, self.command_name)

        if (hasEnough == False):
            await interaction.response.send_message(f"You do not have enough currency to perform this action.", ephemeral=True)
            await interaction.message.delete()
            return

        try:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(self.ctx)
            else:
                self.callback(self.ctx)
                
            await self.cog.deduct_currency(self.ctx, self.command_name)
            await interaction.response.send_message("Action confirmed.", ephemeral=True)
        except CommandError as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
        await interaction.message.delete()

    @discord.ui.button(label="Cancel", style=ButtonStyle.danger, emoji="🚫")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You cannot cancel this action.", ephemeral=True)
        await interaction.response.send_message("Action cancelled.", ephemeral=True)
        await interaction.message.delete()

class jentrigger(commands.Cog):
    """Cog to let you fire off a custom command at Jen!"""
    def __init__(self, bot):
        self.bot = bot
        self.__configRegister()

    def __configRegister(self):
        self.config = Config.get_conf(self, identifier=123432123, force_registration=True)
        
        default_guild = {
            "commands": {}
        }
        
        self.config.register_guild(**default_guild)

    def add_dynamic_command(self, guild, command_name):
        """Dynamically add a Jen command to the bot."""

        @commands.command(name=command_name)
        async def _dynamic_command(ctx):
            await self.dynamic_command_handler(ctx, command_name)

        self.__class__.__cog_commands__ = tuple(list(self.__class__.__cog_commands__) + [_dynamic_command])
        self.bot.add_command(_dynamic_command)


    def remove_dynamic_command(self, guild, command_name):
        """Dynamically remove a Jen command from the bot."""
        command = self.bot.get_command(command_name)
        if command:
            self.bot.remove_command(command_name)

    async def verify_currency(self, ctx, command_name):
        """Verifies the user has enough currency to perform the specified command."""
        user_balance = await bank.get_balance(ctx.author)
        commands_config = await self.config.guild(ctx.guild).commands()
        command_config = commands_config.get(command_name, {})
        cost = int(command_config.get("cost", 100))

        return (user_balance >= cost)


    async def deduct_currency(self, ctx, command_name):
        """Deduct the specified amount of currency, adjusted by percentage, and optionally transfer to a recipient, based on a specific command's configuration."""
        # Fetch the command-specific configuration
        commands_config = await self.config.guild(ctx.guild).commands()
        command_config = commands_config.get(command_name, {})

        cost = int(command_config.get("cost", 100))
        percentage = int(command_config.get("percentage", 100)) 
        recipient_id = command_config.get("user", None) 

        await bank.withdraw_credits(ctx.author, cost)
        adjusted_amount = int(cost * (percentage / 100))

        if recipient_id is not None:
            recipient = ctx.guild.get_member(recipient_id)
            if recipient:
                await bank.deposit_credits(recipient, adjusted_amount)
            else:
                await ctx.send(f"Recipient user with ID {recipient_id} not found in guild {ctx.guild.name}.")

    async def action_post_webhook(self, ctx, command_name):
        """Send a PUT request to the configured webhook URL for a specific command."""
        # Fetch the command-specific configuration
        commands_config = await self.config.guild(ctx.guild).commands()
        command_config = commands_config.get(command_name, {})
        
        url = command_config.get('webhookurl', 'unconfigured')
        data_template = command_config.get('webhooktext', 'Default webhook message')
        
        data = data_template.replace("$USERNAME$", ctx.author.name)
        method = str(command_config.get("webhookaction", "PUT")).upper()

        if url == "unconfigured":
            raise CommandError("Webhook URL has not been configured for this command.")
        
        headers = {'Content-Type': 'application/json'}
        
        async with aiohttp.ClientSession() as session:
            try:
                req = session.request
                async with req(method, url, json={"data": data}, headers=headers) as response:
                    if response.status <= 200 or response.status >= 300:
                        text = await response.text()
                        raise CommandError(f"Failed to send webhook request. HTTP {response.status}: {text[:300]}")
                    if method.upper() == "GET":
                        output = await response.text()
                        await ctx.send(f"{output}")
            except asyncio.TimeoutError:
                raise CommandError("The webhook request timed out.")
            except aiohttp.ClientError as e:
                raise CommandError(f"An error occurred while sending the webhook request: {type(e).__name__}: {e}")

    async def action_send_dm(self, user, message):
        """Send a DM to the specified user with the given message."""
        target = self.bot.get_user(user)
        try:
            await target.send(message)
        except Exception as e:
            print(f"Failed to send DM to {user} - {e}")

    async def action_send_dmembed(self, ctx, embed_config):
        """Send a DM embed to the specified user with the given message."""
        targetid = embed_config.get('privatemessageuser', ctx.author.id)
        embed = discord.Embed(color=discord.Color.from_str(embed_config.get('embedcolour', '#FFFFFF')))
        if 'embedtext' in embed_config:
            embed.description = embed_config['embedtext']
        if 'embedtitle' in embed_config:
            embed.title = embed_config['embedtitle']
        if 'embedavatarurl' in embed_config:
            embed.set_thumbnail(url=embed_config['embedavatarurl'])
            print(embed_config['embedavatarurl'])
        if 'embedpretext' in embed_config:
            pretext = embed_config['embedpretext']
        else:
            pretext = ""
            
        target = self.bot.get_user(targetid)
        try:
            await target.send(pretext, embed=embed, allowed_mentions=discord.AllowedMentions(everyone=False, roles=True, users=True))
        except Exception as e:
            print(f"Failed to send DM to {target} - {e}")

    async def action_post_embed(self, ctx, embed_config):
        """Post an embed in the specified channel based on embed_config."""
        embed = discord.Embed(color=discord.Color.from_str(embed_config.get('embedcolour', '#FFFFFF')))
        if 'embedtext' in embed_config:
            embed.description = embed_config['embedtext']
        if 'embedtitle' in embed_config:
            embed.title = embed_config['embedtitle']
        if 'embedavatarurl' in embed_config:
            embed.set_thumbnail(url=embed_config['embedavatarurl'])
            print(embed_config['embedavatarurl'])
        if 'embedpretext' in embed_config:
            pretext = embed_config['embedpretext']
        else:
            pretext = ""
        try:
            await ctx.channel.send(pretext, embed=embed, allowed_mentions=discord.AllowedMentions(everyone=False, roles=True, users=True))
        except discord.HTTPException as e:
            print(f"Failed to send embed message: {e}.")


    async def dynamic_command_handler(self, ctx, command_name):
        """Handle the execution of dynamically added commands."""
        commands_config = await self.config.guild(ctx.guild).commands()
        command_config = commands_config.get(command_name)

        if command_config is None:
            await ctx.send("This command is not configured.")
            return

        cost = int(command_config.get('cost', 100))
        percentage = int(command_config.get('percentage', 100))

        if "user" in command_config:
            userName = self.bot.get_user(command_config['user']).name
            etherString = f"{int(cost * (percentage / 100))} goes to {userName} and {int(cost - cost *(percentage / 100))} will be vanished into the ether."
        else:
            etherString = f"All {int(cost)} will be vanished into the ether."
        
        from functools import partial
        callback_action = partial(self.command_action_callback, command_name=command_name)

        view = ConfirmationView(ctx=ctx, cost=cost, cog=self, callback=callback_action, command_name=command_name)
        embed = Embed(title="Confirmation", description=f"This will cost {cost}.\n{etherString}\n\nAre you sure?", color=discord.Color.blue())
        
        await ctx.send("Please confirm this action:", embed=embed, view=view)
    
    async def command_action_callback(self, ctx, command_name):
        commands_config = await self.config.guild(ctx.guild).commands()
        command_config = commands_config.get(command_name, {})
        if command_config['mode'] == 'dm':
            message = command_config.get('privatemessage', 'Default message')
            target = command_config.get('privatemessageuser', ctx.author.id)
            await self.action_send_dm(target, message)
            return
        elif command_config['mode'] == 'webhook':
            webhook_url = command_config.get('webhookurl', '')
            if webhook_url:
                await self.action_post_webhook(ctx, command_name)
            else:
                raise Exception("Command set to webhook but no URL configured.")
            return
        elif command_config['mode'] == 'embed':
            await self.action_post_embed(ctx, command_config)
            return
        elif command_config['mode'] == 'dmembed':
            await self.action_send_dmembed(ctx, command_config)
            return
        elif command_config['mode'] == 'dm+embed':
            message = command_config.get('privatemessage', 'Default message')
            target = command_config.get('privatemessageuser', ctx.author.id)
            await self.action_send_dm(target, message)
            await self.action_post_embed(ctx, command_config)
            return
        elif command_config['mode'] == 'dmembed+embed':
            await self.action_send_dmembed(ctx, command_config)
            await self.action_post_embed(ctx, command_config)
            return
        elif command_config['mode'] == 'webhook+embed':
            webhook_url = command_config.get('webhookurl', '')
            if webhook_url:
                await self.action_post_webhook(ctx, command_name)
            else:
                raise Exception("Command set to webhook but no URL configured.")
            await self.action_post_embed(ctx, command_config)
            return

    @commands.command(name="jen", autohelp=False)
    async def jen(self, ctx, command_name: str, *args):
        """List of commands for Jen!\n\n
        <Admin> [p]jen add <commandname> to add a new command.\n<Admin> [p]jen set <commandname> <parameter> <value> to set a parameter.\n<Admin> [p]jen remove <commandname> to remove a command.\n<Admin> [p]jen show <commandname> shows the config for a given command.\n<Admin> [p]jen clear <commandname> <parameter> clears a parameter for a command.\n\n[p]jen list shows a list of all commands with their cost.\n"""
        
        if command_name.lower() == "help":
            await ctx.send_help("jen")
            return

        def check_permissions(ctx):
            return ctx.author.guild_permissions.manage_guild or ctx.author.guild_permissions.administrator
        
        if command_name.lower() in ["add", "set", "clear", "remove", "delete", "show", "view", "copy"]:
            if not check_permissions(ctx):
                await ctx.send("You do not have the necessary permissions to perform this action.")
                return

            if command_name.lower() == "add":
                if len(args) < 1:
                    await ctx.reply("Failed, please specify a valid command name.")
                    return
                await self.jen_add(ctx, args[0])
            elif command_name.lower() == "set":
                if len(args) < 2:
                    await ctx.reply("Failed, please specify correct arguments.")
                    return
                await self.jen_set(ctx, *args)
            elif command_name.lower() == "remove" or command_name.lower() == "delete":
                if len(args) < 1:
                    await ctx.reply("Failed, please specify a valid command name.")
                    return
                await self.jen_remove(ctx, args[0])
            elif command_name.lower() == "clear":
                if len(args) < 2:
                    await ctx.reply("Failed, please specify correct arguments.")
                    return
                await self.jen_clear(ctx, args[0], args[1])
                return
            elif command_name.lower() == "view" or command_name.lower() == "show":
                await self.jen_show(ctx, args[0])
                return
            elif command_name.lower() == "copy":
                if len(args) < 1:
                    await ctx.reply("Failed, please specify correct guild ID to copy from.")
                    return
                await self.jen_copy(ctx, args[0])
                return
            
        elif command_name.lower() == "list":
            await self.jen_list(ctx)
            return
        else:
            await self.dynamic_command_handler(ctx, command_name)

    async def jen_copy(self, ctx, source_guild: int):
        """
        Copy configuration from another discord server.
        Usage: [p]copy <guild_id>
        """
        try:
            guildCast = int(source_guild)
        except:
            await ctx.send("Something went wrong with the provided guild ID, verify it's correct")
            return

        source_data = await self.config.guild_from_id(guildCast).all()

        if not source_data:
            await ctx.send("No configuration data was found for the provided guild ID.")
            return

        await self.config.guild(ctx.guild).clear()
        await self.config.guild(ctx.guild).set(source_data)

        await ctx.send(f"Configuration from guild {guildCast} has been copied to this guild.")


    async def jen_add(self, ctx, command_name: str):
        """Add a new custom command."""
        if command_name.lower() in ["add", "set", "clear", "show", "view", "remove", "delete", "list", "copy"]:
            await ctx.send(f"The command `{command_name}` is a system command.")
            return
        async with self.config.guild(ctx.guild).commands() as commands:
            if command_name in commands:
                await ctx.send(f"The command `{command_name}` already exists.")
                return
            commands[command_name] = {"mode": "dm", "message": "This is a test message."}
        self.add_dynamic_command(ctx.guild, command_name)
        await ctx.send(f"Command {command_name} added.")

    async def jen_set(self, ctx, *args):
        """Set a configuration for a custom command."""
        if len(args) < 3:
            await ctx.send(f"Not enough arguments supplied.")
            return
        
        valid_settings = ["cost", "user", "percentage", "mode", "embedtitle", "embedtext", "embedpretext", "embedcolour", "embedcolor", "embedavatarurl", "privatemessage", "privatemessageuser", "webhookurl", "webhooktext", "webhookaction"]
        if args[1].lower() not in valid_settings:
            await ctx.send(f"Invalid setting. Valid settings are: {', '.join(valid_settings)}")
            return
        
        args_list = list(args)

        lowered = args_list[1].lower()
        args_list[2] = args_list[2].lower()
        if lowered == "mode":
            if args_list[2].lower() not in ['webhook', 'dm', 'embed', 'dmembed', 'dm+embed', 'dmembed+embed', 'webhook+embed']:
                await ctx.send(f"Valid options for mode are 'webhook', 'dm', 'embed', 'dmembed', 'dm+embed', 'dmembed+embed', 'webhook+embed'.")
                return

        if lowered == "user" or lowered == "privatemessageuser":
            try:
                user_id_match = re.findall(r'\d+', args_list[2])
                if user_id_match:  
                    user_id = user_id_match[0]  
                    args_list[2] = int(user_id) 
                else:
                    raise ValueError("Invalid user mention.")
            except Exception as e:
                print (e)
                await ctx.send("Something went wrong; please try again. Make sure you're mentioning a user.")
                return

        if lowered == "embedcolor":
            args_list[1] = "embedcolour"
        
        if lowered == "webhookaction":
            allowed = ["get", "post", "put", "patch", "delete", "head", "options"]
            if args_list[2].lower() not in allowed:
                await ctx.send("Valid options for webhookaction are: " + ", ".join(sorted(allowed)).upper().replace(", ", ", "))
                return
            args_list[2] = args_list[2].upper()

        if lowered == "embedcolour":
            if args_list[2][0] != '#':
                args_list[2] = '#' + args_list[2].lower()

        if (lowered == "privatemessage" or lowered == "embedtext" or lowered == "embedtitle" or lowered == "embedpretext"):
            args_list[2] = " ".join(args[2:])

        if lowered == "embedavatarurl":
            args_list[2] = args[2]

        async with self.config.guild(ctx.guild).commands() as commands:
            if args_list[0] not in commands:
                await ctx.send(f"The command `{args_list[0]}` does not exist.")
                return
            commands[args_list[0]][args_list[1].lower()] = args_list[2]
        await ctx.send(f"Configuration for `{args_list[0]} - {args_list[1]}` updated.")

        
    async def jen_clear(self, ctx, command_name: str, parameter: str):
        """Clears a specific parameter for the given command."""
        async with self.config.guild(ctx.guild).commands() as commands:
            if command_name not in commands:
                await ctx.send(f"The command `{command_name}` does not exist.")
                return

            if parameter not in commands[command_name]:
                await ctx.send(f"The parameter `{parameter}` does not exist for the command `{command_name}`.")
                return

            del commands[command_name][parameter]
            await ctx.send(f"The parameter `{parameter}` for the command `{command_name}` has been cleared.")

    async def jen_remove(self, ctx, command_name: str):
        """Remove a custom command."""
        async with self.config.guild(ctx.guild).commands() as commands:
            if command_name not in commands:
                await ctx.send(f"The command `{command_name}` does not exist.")
                return
            del commands[command_name]
        self.remove_dynamic_command(ctx.guild, command_name)
        await ctx.send(f"Command `{command_name}` removed.")

    async def jen_list(self, ctx):
        """Lists all custom commands configured for the guild."""
        commands_config = await self.config.guild(ctx.guild).commands()

        if not commands_config:
            await ctx.send("No custom commands have been configured.")
            return

        commands_list = "\n".join([f";jen {command_name} - Costs {commands_config[command_name].get('cost', '100')}" for command_name in commands_config.keys()])

        embed = discord.Embed(title="Custom Commands List",
                              description=commands_list,
                              color=discord.Color.blue())
        await ctx.send(embed=embed)

        
    async def jen_show(self, ctx, command_name: str):
        """Shows all configuration keys and values for the given command."""
        commands_config = await self.config.guild(ctx.guild).commands()
        
        if command_name not in commands_config:
            await ctx.send(f"The command `{command_name}` does not exist.")
            return

        command_config = commands_config[command_name]

        config_lines = [f"`{key}`: {value}" for key, value in command_config.items()]
        config_message = "\n".join(config_lines)

        if len(config_message) > 2000:
            await ctx.send("The command's configuration is too long to display in one message.")
            return

        embed = discord.Embed(title=f"Configuration for `{command_name}`",
                              description=config_message,
                              color=discord.Color.blue())
        await ctx.send(embed=embed)
