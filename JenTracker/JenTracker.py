from redbot.core import commands
from redbot.core import Config

class JenTracker(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="orgasms")
    async def JenTrackerOrgs(self, ctx):
        await ctx.send("https://docs.google.com/spreadsheets/d/12JRd6Oi6JLfDYsDAGlOmx0ZfkQVmp-mpoBpwKkFwa4A/edit#gid=1074722484")
        
    @commands.command(name="orgasmtracker")
    async def JenTrackerOrgT(self, ctx):
        await ctx.send("https://docs.google.com/spreadsheets/d/12JRd6Oi6JLfDYsDAGlOmx0ZfkQVmp-mpoBpwKkFwa4A/edit#gid=1074722484")

    @commands.command(name="jengasms")
    async def JenTrackerJengs(self, ctx):
        await ctx.send("https://docs.google.com/spreadsheets/d/12JRd6Oi6JLfDYsDAGlOmx0ZfkQVmp-mpoBpwKkFwa4A/edit#gid=1074722484")

    @commands.command(name="jentracker")
    async def JenTrackerJenT(self, ctx):
        await ctx.send("https://docs.google.com/spreadsheets/d/12JRd6Oi6JLfDYsDAGlOmx0ZfkQVmp-mpoBpwKkFwa4A/edit#gid=1074722484")
