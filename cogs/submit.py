import discord
from discord.app_commands import autocomplete, command
from discord.ext.commands import Cog

from run import cc, run_tests, ktypes, ktype_ac
from utils import check_user, convert_literals, challenge_ac, make_leaderboard
from db import db

class SubmitCog(Cog):

  @command()
  @check_user()
  @autocomplete(challenge=challenge_ac, ktype=ktype_ac)
  @convert_literals
  async def submit(self, interaction: discord.Interaction, challenge:str, ktype:str, name:str, global_size:tuple[int,int,int],
                   local_size:tuple[int,int,int], kernel:discord.Attachment):
    await interaction.response.send_message("checking...")
    if ktype not in ktypes: return await interaction.response.send_message("invalid ktype", ephemeral=True)
    chal, tensors = db.execute("SELECT id, tests FROM challenges as c WHERE c.name = ?", (challenge,)).fetchone()
    if chal is None: return await interaction.response.send_message(f"could not find challenge {challenge}", ephemeral=True)
    await interaction.edit_original_response(content="downloading...")
    src = (await kernel.read()).decode("utf-8")
    await interaction.edit_original_response(content="compiling...")
    try: prog = cc(src, ktype, name)
    except Exception as e: return await interaction.edit_original_response(content=f"failed to compile: {e}")
    await interaction.edit_original_response(content="running...")
    try: tm = run_tests(prog, global_size, local_size, tensors)
    except Exception as e: return await interaction.edit_original_response(content=f"error while running tests: {e}")
    db.execute("INSERT INTO submissions (name, type, source, comp_id, user_id, timing) VALUES (?, ?, ?, ?, ?, ?);",
               (name, ktype, src, chal, interaction.user.id, tm))
    db.commit()
    make_leaderboard.cache_clear()
    await interaction.edit_original_response(content=make_leaderboard(challenge))

