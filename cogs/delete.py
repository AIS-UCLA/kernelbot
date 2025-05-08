from typing import Optional
import discord
from discord.app_commands import autocomplete, command
from discord.ext.commands import Cog

from utils import challenge_ac
from db import db, Perm
from utils import check_user

class DeleteCog(Cog):
  @command()
  @check_user(Perm.ADMIN) 
  @autocomplete(challenge=challenge_ac)
  async def delete(self, interaction: discord.Interaction, challenge: str):
      """Delete a challenge from the database"""
      if not challenge:
          await interaction.response.send_message("Please specify a challenge to delete.", ephemeral=True)
          return
          
      challenge_data = db.execute("SELECT id FROM challenges WHERE name = ?", (challenge,)).fetchone()
      if not challenge_data:
          await interaction.response.send_message(f"Challenge `{challenge}` not found.", ephemeral=True)
          return
      
      challenge_id = challenge_data[0]
      
      try:
          db.execute("BEGIN TRANSACTION")
          # Use comp_id instead of challenge to reference the challenge
          db.execute("DELETE FROM submissions WHERE comp_id = ?", (challenge_id,))
          db.execute("DELETE FROM challenges WHERE name = ?", (challenge,))
          db.execute("COMMIT")
          
          await interaction.response.send_message(f"Challenge `{challenge}` and all associated submissions have been deleted.", ephemeral=True)
      except Exception as e:
          db.execute("ROLLBACK")
          await interaction.response.send_message(f"Error deleting challenge: {str(e)}", ephemeral=True)