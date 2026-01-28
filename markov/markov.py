import discord
import logging
import random
import re
from typing import Callable, Dict, Optional, Tuple

from redbot.core import checks, Config, commands

log = logging.getLogger("red.cbd-cogs.markov")

UNIQUE_ID = 0x6D61726B6F76
CONTROL_TOKEN = f"{UNIQUE_ID}"
WORD_TOKENIZER = re.compile(r"(\W+)")

Model = Dict[str, Dict[str, int]]          # state -> (gram -> weight)
AllUserChains = Dict[str, Model]           # f"{mode}-{depth}" -> model
class Markov(commands.Cog):
    """A markov-chain-based text generator cog."""
    def __init__(self, bot):
        self.bot = bot
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_user(chains={}, chain_depth=1, mode="word", enabled=False)
        self.conf.register_guild(channels=[])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Process messages from enabled channels for enabled users."""

        if message.author.bot:
            return
        if not message.content:
            return
        if not message.content[0].isalnum():
            return

        if message.guild is not None:
            enabled_channels = await self.conf.guild(message.guild).channels()
            if enabled_channels and message.channel.id not in enabled_channels:
                return

        enabled, chains, depth, mode = await self.get_user_config(message.author)
															
        if not enabled:
            return

        tokenizer, cleaner = self._get_tokenizer(mode)

        content = message.content.replace("`", "").strip()
        if not content:
            return

        tokens = self._tokenize(content, tokenizer, cleaner)
        if not tokens:
            return

        model_key = f"{mode}-{depth}"
        model = chains.get(model_key, {})

        state = CONTROL_TOKEN												
        tokens.append(CONTROL_TOKEN)

        for idx, gram in enumerate(tokens):
																
            next_weights = model.setdefault(state, {})
            next_weights[gram] = next_weights.get(gram, 0) + 1

            start = 1 + idx - depth if idx >= depth else 0
            state = "".join(cleaner(x) for x in tokens[start : idx + 1])

        chains[model_key] = model
        await self.conf.user(message.author).chains.set(chains)

    @commands.group()
    async def markov(self, ctx: commands.Context):
        """New users must `enable` and say some words before using `generate`."""
        pass

    @markov.command()
    async def generate(
        self, ctx: commands.Context, length: Optional[int] = None, user: Optional[discord.Member] = None):
        """
        Generate text based on user language models.

        Usage:
        - ;markov generate
        - ;markov generate <length 1-50>
        - ;markov generate <length 1-50> @user
        """
        user = user or ctx.author

        if length is not None:
            length = max(1, min(50, int(length)))

        enabled, chains, depth, mode = await self.get_user_config(user)
        if not enabled:
            await ctx.send(f"Sorry, {user} won't let me model their speech")
            return

        #try a few times to avoid unlucky dead-ends
        for attempt in range(1, 5):
            text = await self.generate_text(chains, depth, mode, forced_length=length)
            if text:
                await ctx.send(text[:2000])
                return

        await ctx.send("I tried to generate text 4 times and couldn't get anything usable.")

    @markov.command()
    async def enable(self, ctx: commands.Context):
        """Allow the bot to model your messages and generate text based on that."""
        await self.conf.user(ctx.author).enabled.set(True)
        await ctx.send("Markov modeling enabled!")

    @markov.command()
    async def disable(self, ctx: commands.Context):
        """Disallow the bot from modeling your message or generating text based on your models."""
        await self.conf.user(ctx.author).enabled.set(False)
        await ctx.send("Markov text generation is now disabled for your user.\n"
            "I will stop updating your language models, but they are still stored.\n"
            "You may want to use `[p]markov reset` to delete them.\n")

    @markov.command()
    async def mode(self, ctx: commands.Context, mode: str):
        """Set the tokenization mode for model building.
        Modes:
        - word
        - chunk / chunk5 / chunk10 (etc.)																			  
        """
        await self.conf.user(ctx.author).mode.set(mode)
        await ctx.send(f"Token mode set to '{mode}'.")

    @markov.command()
    async def depth(self, ctx: commands.Context, depth: int):
        """Set the modeling depth (the 'n' in 'ngrams')."""
        depth = max(1, min(10, int(depth)))  # small sanity clamp
        await self.conf.user(ctx.author).chain_depth.set(depth)
        await ctx.send(f"Ngram modeling depth set to {depth}.")

    @markov.command()
    async def show(self, ctx: commands.Context, user: discord.abc.User = None):
        """Show your current settings and models, or those of another user."""
        user = user or ctx.author
        enabled, chains, depth, mode = await self.get_user_config(user, lazy=False)
        models = "\n".join(chains.keys()) if chains else "(none)"
        await ctx.send(f"**Enabled:** {enabled}\n"
            f"**Chain Depth:** {depth}\n"
            f"**Token Mode:** {mode}\n"
            f"**Stored Models:**\n{models}")

    @markov.command()
    async def delete(self, ctx: commands.Context, model: str):
        """Delete a specific model from your profile (e.g. 'word-2', 'chunk5-3')."""
        chains = await self.conf.user(ctx.author).chains() or {}
        if model in chains:
            del chains[model]
            await self.conf.user(ctx.author).chains.set(chains)
            await ctx.send("Deleted model.")
        else:
            await ctx.send("Model not found.")

    @markov.command()
    async def reset(self, ctx: commands.Context):
        """Remove all language models from your profile."""
        await self.conf.user(ctx.author).chains.set({})
        await ctx.send("All models deleted.")

    @checks.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    @markov.command()
    async def channelmode(self, ctx: commands.Context, mode: str, channel: discord.TextChannel = None):
        """Toggle modeling of messages in a channel for enabled users.
        Modes:
        - enable
        - disable
        """
        channel = channel or ctx.channel
        enabled_channels = await self.conf.guild(ctx.guild).channels()

        mode_l = mode.lower()
        if mode_l == "enable":
            if channel.id not in enabled_channels:
                enabled_channels.append(channel.id)
                await ctx.send(f"Modeling enabled for {channel.mention}.")
            else:
                await ctx.send(f"Modeling already enabled for {channel.mention}.")
        elif mode_l == "disable":
            if channel.id in enabled_channels:
                enabled_channels.remove(channel.id)
                await ctx.send(f"Modeling disabled for {channel.mention}.")
            else:
                await ctx.send(f"Modeling already disabled for {channel.mention}.")
        else:
            await ctx.send("Invalid mode. Please use `enable` or `disable`.")
            return

        await self.conf.guild(ctx.guild).channels.set(enabled_channels)

    @checks.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    @markov.command()
    async def channelstatus(self, ctx: commands.Context):
        """Display the status of all channels in terms of modeling."""
        enabled_channel_ids = set(await self.conf.guild(ctx.guild).channels())
        enabled_lines = [f"{ch.name}: On" for ch in ctx.guild.text_channels if ch.id in enabled_channel_ids]

        status_output = "\n".join(enabled_lines) if enabled_lines else "(none)"
        await ctx.send(f"Modeling Status - Enabled:\n```{status_output}```")

    async def get_user_config(self, user: discord.abc.User, lazy: bool = True) -> Tuple[bool, AllUserChains, int, str]:
        """Get a user config, optionally short-circuiting if not enabled."""
        user_config = self.conf.user(user)
        enabled = await user_config.enabled()
        if lazy and not enabled:
            return (False,) * 4

        chains: AllUserChains = await user_config.chains() or {}
        depth = await user_config.chain_depth() or 1
        mode = (await user_config.mode() or "word").lower()
        return enabled, chains, depth, mode

    async def generate_text(self, chains: AllUserChains, depth: int, mode: str, forced_length: Optional[int] = None) -> Optional[str]:
        """Generate text based on the appropriate model for user settings.
        If forced_length is provided, tries to output exactly that many grams (skipping CONTROL_TOKEN).
        """

        generator = self._get_generator(mode)
        if generator is None:
            return f"Sorry, I don't have a text generator for token mode '{mode}'"

        model_key = f"{mode}-{depth}"
        model = chains.get(model_key)
        if not model:
            return "Sorry, I can't find a model to use."

        output_parts = []
        state = CONTROL_TOKEN

        if forced_length is None:
            #Natural mode: stop when we hit CONTROL_TOKEN
            last_gram = ""
            steps = 0
            while last_gram.strip() != CONTROL_TOKEN and steps < 500:
                last_gram = await generator(model, state)
                output_parts.append(last_gram)

                steps += 1
                start = max(0, steps - depth)
                state = "".join(output_parts[start:steps])

            if not output_parts:
                return None

            #drop trailing control token
            return "".join(output_parts[:-1]).strip() or None

        #Forced-length mode: produce exactly N grams, skipping CONTROL_TOKEN
        target = max(1, min(50, forced_length))
        produced = 0
        safety_steps = 0

        #allow extra sampling in case we hit CONTROL_TOKEN or dead-ends
        while produced < target and safety_steps < target * 25:
            gram = await generator(model, state)
            safety_steps += 1
            
            if gram.strip() == CONTROL_TOKEN:
                #Treat forced boundary as a soft sentence break, pop a cheeky space in there
                if output_parts and not output_parts[-1].endswith(" "):
                    output_parts.append(" ")
                state = CONTROL_TOKEN
                continue

            output_parts.append(gram)

            #only count "words" (tokens containing any alphanumeric), not raw punctuation
            #(had an issue where I was getting 5-10 less per request)
            if any(ch.isalnum() for ch in gram):
                produced += 1

            #maintain state window
            start = max(0, len(output_parts) - depth)
            state = "".join(output_parts[start:])

        text = "".join(output_parts).strip()
        return text or None

    def _get_generator(self, mode: str) -> Optional[Callable[[Model, str], "commands.Coroutine"]]:
        if mode == "word":
            return self.generate_word_gram
        if mode.startswith("chunk"):
            return self.generate_chunk_gram
        return None

    def _get_tokenizer(self, mode: str):
        """Return (tokenizer_regex, cleaner_callable)."""
        if mode == "word":
            return WORD_TOKENIZER, (lambda s: s.strip())

        if mode.startswith("chunk"):
            #mode can be "chunk" or "chunk5", etc.
            raw_len = mode[5:]  # "" if exactly "chunk"
            chunk_len = 3 if raw_len == "" else int(raw_len)
            chunk_len = max(1, min(50, chunk_len))
            return re.compile(fr"(.{{{chunk_len}}})"), (lambda s: s)

        #fallback: treat as word
        return WORD_TOKENIZER, (lambda s: s.strip())

    def _tokenize(self, content: str, tokenizer: re.Pattern, cleaner: Callable[[str], str]):
        """Split then clean, dropping empties."""
        parts = tokenizer.split(content)
        tokens = []
        for part in parts:
            cleaned = cleaner(part)
            if cleaned:
                tokens.append(cleaned)
        return tokens

    async def generate_word_gram(self, model: Model, state: str) -> str:
        """Generate text for word-mode vectorization."""
        gram = await self.choose_gram(model, state)
        needs_space = all(
            (
                state != CONTROL_TOKEN,
                gram and (gram[-1].isalnum() or gram in "\"([{|"),
                state and (state[-1] not in "\"([{'/-_"),
            )
        )
        return f"{' ' if needs_space else ''}{gram}"

    async def generate_chunk_gram(self, model: Model, state: str) -> str:
        """Generate text for chunk-mode vectorization."""
        return await self.choose_gram(model, state)

    async def choose_gram(self, model: Model, state: str) -> str:
        """Choose a next gram based on weighted transitions from a state."""
        gram = self._choose_from_state(model, state)
        if gram is not None:					   
            return gram

        gram = self._choose_from_state(model, state.replace(" ", ""))
        if gram is not None:
            return gram

        all_grams = []
        for transitions in model.values():
            all_grams.extend(transitions.keys())

        if not all_grams:
            return CONTROL_TOKEN

        return random.choice(all_grams)

    def _choose_from_state(self, model: Model, state: str) -> Optional[str]:
        transitions = model.get(state)
        if not transitions:
            return None

        grams = list(transitions.keys())
        weights = list(transitions.values())
        return random.choices(population=grams, weights=weights, k=1)[0]
