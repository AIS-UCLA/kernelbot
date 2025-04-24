from ast import literal_eval
import discord
from discord.app_commands import autocomplete, Choice, command
from discord.ext.commands import Cog

from run import cc, run_tests, ktypes, ktype_ac
from utils import check_user, active_chals, db, fmt_time


class SubmitCog(Cog):
  async def challenge_ac(self, _, curr): return [Choice(name=chal, value=chal) for chal in active_chals() if curr.lower() in chal.lower()]

  @command()
  @check_user()
  @autocomplete(challenge=challenge_ac, ktype=ktype_ac)
  async def submit(self, interaction: discord.Interaction, challenge:str, ktype:str, name:str, global_size:str, local_size:str,
                   kernel:discord.Attachment):
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
    try: tm = run_tests(prog, literal_eval(global_size), literal_eval(local_size), tensors)
    except Exception as e: return await interaction.edit_original_response(content=f"error while running tests: {e}")
    await interaction.edit_original_response(content=fmt_time(tm))

