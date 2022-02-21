from distutils.command import config
import logging
import random
import string
from dotenv import load_dotenv
import discord
from dotenv import load_dotenv
import os
import time
import json
import os
import subprocess

from multidict import upstr
from utils.errors import NotVoiceChannel
from utils.parse_config import Config, ErrorMessages
from motor import motor_asyncio

load_dotenv()


# Setup the bot and cogs
config_dict = json.load(open('./config.json'))
intents = discord.Intents().all()
bot = discord.Bot(help_command=None, intents=intents)
bot.config = Config(**config_dict['bot_setup'])
bot.errors = ErrorMessages(**config_dict['errors'])

client = motor_asyncio.AsyncIOMotorClient(os.getenv('MONGO_URI'))
allowed_guilds_collection = client[bot.config.database_name]['allowed_guilds']

allowed_guilds = []

for filename in os.listdir('./Cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'Cogs.{filename[:-3]}')

# Logger
logging.basicConfig(filename=f"./{bot.config.logging['log_file']}", level=logging.INFO, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

@bot.event
async def on_ready():
    print(f"Logged in as\n{bot.user}\n-----------")
    cursor = allowed_guilds_collection.find()
    for document in await cursor.to_list(length=None):
        allowed_guilds.append(document['guild_id'])
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=bot.config.version))


@bot.event
async def on_application_command_error(context, exception) -> None:
    if isinstance(exception, NotVoiceChannel):
        pass
    else:
        raise exception

@bot.event
async def on_interaction(interaction:discord.Interaction):
    if interaction.guild_id is None:
        return
    if str(interaction.guild_id) not in allowed_guilds:
        return
    else:
        await bot.process_application_commands(interaction)


bind_channel = 835886494770135054
@bot.event
async def on_message(message:discord.Message):
    if message.content.startswith("-log") and message.author.id in bot.config.bot_owner_discord_ids:
        await message.channel.send(file=discord.File("./chizuru_bot.log"))
        logger.info("----------------------------------------Last -log ends here--------------------------------------------")
    elif message.content.startswith("-add") and message.author.id in bot.config.bot_owner_discord_ids:
        args = message.content.split(" ")[1:]
        if len(args) == 2:
            access_token = get_random_string()
            await allowed_guilds_collection.update_one({'guild_id': args[0]}, {"$set":{'guild_id': args[0], 'user_id': args[1], 'access_token': access_token}}, upsert=True)
            allowed_guilds.append(args[0])
            await message.channel.send("Guild ID: " + args[0] + "\nUser ID: " + args[1] + "\nAccess Token: " + access_token)
        else:
            return
    elif message.content.startswith("-get") and message.author.id in bot.config.bot_owner_discord_ids:
        guild_id = message.content.split(" ")[1]
        document = await allowed_guilds_collection.find_one({'guild_id': guild_id})
        await message.channel.send("Guild ID: " + guild_id + "\nUser ID: " + document['user_id'] + "\nAccess Token: " + document['access_token'])
    return

def get_random_string():
    # choose from all lowercase letter
    letters = string.ascii_lowercase + string.ascii_uppercase + "0123456789"
    result_str = ''.join(random.choice(letters) for i in range(10))
    return result_str


bot.run(os.getenv("TOKEN"))