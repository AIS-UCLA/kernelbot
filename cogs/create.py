import discord
import numpy as np
from discord.app_commands import Choice, autocomplete, command
from discord.ext.commands import Cog

from utils import convert_literals, active_chals, fmt_time
from db import db, Perm, check_user
from run import cc, gen_tests, ktypes, ktype_ac

dtypes = {"double":np.dtype("float64"),"single":np.dtype("float32"),"half":np.dtype("float16")}
rand_fns = {"rand":np.random.rand,"randn":np.random.randn,"randint":np.random.randint}

class CreateCog(Cog):
  async def dtype_ac(self, _, curr): return [Choice(name=dt, value=dt) for dt in dtypes.keys() if curr.lower() in dt]
  async def rand_fn_ac(self, _, curr): return [Choice(name=dt, value=dt) for dt in rand_fns.keys() if curr.lower() in dt]

  @command()
  @check_user(Perm.CREATE_CHALLENGE)
  @autocomplete(dtype=dtype_ac, rand_fn=rand_fn_ac, ktype=ktype_ac)
  @convert_literals
  async def create(self, interaction: discord.Interaction, name:str, desc:str, ktype:str, input_shapes:list[tuple[int,...]],
                   output_shape:tuple[int,...], global_size:tuple[int,int,int], local_size:tuple[int,int,int], dtype:str, rand_fn:str,
                   num_tests:int, reference_code:discord.Attachment):
    assert isinstance(interaction.channel, discord.TextChannel)
    # verify arguments
    if name in active_chals(): return await interaction.response.send_message(f"challenge with name {name} already exists", ephemeral=True)
    if ktype not in ktypes: return await interaction.response.send_message("invalid ktype", ephemeral=True)
    if dtype not in dtypes: return await interaction.response.send_message(f"invalid dtype {dtype}", ephemeral=True)
    if rand_fn not in rand_fns: return await interaction.response.send_message(f"invalid rand function {rand_fn}", ephemeral=True)
    # download and compile program
    await interaction.response.send_message("loading reference code...", ephemeral=True)
    try: prog = cc((await reference_code.read()).decode('utf-8'), ktype, name)
    except Exception as e:
      return await interaction.edit_original_response(content=f"failed to load reference code: {e}")
    # generate tests
    await interaction.edit_original_response(content="generating tests...")
    try: tests, tm = gen_tests(prog, global_size, local_size, input_shapes, output_shape, dtypes[dtype], rand_fns[rand_fn], num_tests)
    except Exception as e:
      import traceback
      print(traceback.format_exc())
      return await interaction.edit_original_response(content=f"failed to generate tests: {e}")
    await interaction.edit_original_response(content="creating challenge...")
    db.execute("INSERT INTO challenges (name, desc, creator_id, tests, timing) VALUES (?, ?, ?, ?, ?, ?);",
               (name, desc, interaction.user.id, tests, tm))
    db.commit()
    active_chals.cache_clear()
    await interaction.delete_original_response()
    await interaction.channel.send(content=f"""# New Challenge: `{name}`
Author: {interaction.user.mention}
Input Shapes: `{input_shapes}`, Output Shape: `{out_shape}` Dtype: `{dtype}`
Baseline time: {fmt_time(tm)}

{desc}
""")
