from discord import Embed

def error_embed(ctx, error_message):
    return Embed(description=error_message, color=ctx.bot.errors.error_embed_colour)

def info_embed(ctx, description):
    return Embed(description=description, color=ctx.bot.config.embed_colour)