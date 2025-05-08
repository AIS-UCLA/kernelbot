from typing import Optional
import discord
from discord.app_commands import autocomplete, command, describe
from discord.ext.commands import Cog

from utils import active_chals, challenge_ac, make_leaderboard
from db import db, Perm
from utils import check_user

class ShowCog(Cog):
  @command()
  @check_user(Perm.USER, Perm.ADMIN)
  @autocomplete(challenge=challenge_ac)
  @describe(
    challenge="Name of the challenge to show submissions for",
  )
  async def show(self, interaction: discord.Interaction, challenge:Optional[str]):
    """Show leaderboard for a challenge"""
    await interaction.response.send_message("generating listing...")
    if challenge is None:
      await interaction.edit_original_response(content="## Active Challenges\n" + "\n".join([f"- `{chal}`" for chal in active_chals()]))
    else: await interaction.edit_original_response(content=make_leaderboard(challenge))