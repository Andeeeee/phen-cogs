from .embed import EmbedUtils

__red_end_user_data_statement__ = "This cog stores End User Data when storing the author of an embed."

def setup(bot):
    cog = EmbedUtils(bot)
    bot.add_cog(cog)