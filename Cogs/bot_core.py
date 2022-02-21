from discord.ext import commands
from discord import slash_command
from datetime import datetime
import requests
import discord

server_array = None
def setup(bot):
    global server_array
    server_array = bot.config.debug_guilds
    bot.add_cog(BotCore(bot))

class BotCore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @slash_command(guild_ids=server_array)
    async def ping(self, ctx:discord.ApplicationContext):
        """Gets the ping"""
        start = datetime.now()
        requests.get(url='https://discord.com/api/oauth2/')
        end = datetime.now()
        ms = int((end - start).microseconds / 1000)
        await ctx.respond(f"**Pong:** `{ms}`ms")

    @slash_command(guild_ids=server_array)
    async def invite(self, ctx:discord.ApplicationContext):
        pass
