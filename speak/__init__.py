import json
from pathlib import Path

from .speak import Speak

with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]


async def setup(bot):
    cog = Speak(bot)
    await bot.add_cog(cog)
