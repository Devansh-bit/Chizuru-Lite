from discord.errors import DiscordException
from discord.ext import commands

class MissingPermissions(DiscordException):
    def __init__(self, interaction, perms):
        message = "Missing permissions: "
        for perm in perms:
            message += perm
        self.perms = perms
        self.interaction = interaction
        super().__init__(message)

class NotVoiceChannel(commands.CommandError):
    def __init__(self, interaction, message):
        self.interaction = interaction
        self.message = message
        super().__init__(message)


