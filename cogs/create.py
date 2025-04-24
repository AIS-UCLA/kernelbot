from typing import Tuple
import discord
import numpy as np
from discord.app_commands import Choice, autocomplete, command
from discord.ext.commands import Cog
from ast import literal_eval

from utils import Perm, check_user, db, active_chals, fmt_time
from run import cc, gen_tests, ktypes, ktype_ac

dtypes = {"double":np.dtype("float64"),"single":np.dtype("float32"),"half":np.dtype("float16")}
rand_fns = {"rand":np.random.rand,"randn":np.random.randn,"randint":np.random.randint}

class CreateCog(Cog):
  async def dtype_ac(self, _, curr): return [Choice(name=dt, value=dt) for dt in dtypes.keys() if curr.lower() in dt]
  async def rand_fn_ac(self, _, curr): return [Choice(name=dt, value=dt) for dt in rand_fns.keys() if curr.lower() in dt]

  @command()
  @check_user(Perm.CREATE_CHALLENGE)
  @autocomplete(dtype=dtype_ac, rand_fn=rand_fn_ac, ktype=ktype_ac)
  async def create(self, interaction: discord.Interaction, name:str, desc:str, ktype:str, input_shapes:str,
                   output_shape:str, global_size:str, local_size:str, dtype:str, rand_fn:str, num_tests:int,
                   reference_code: discord.Attachment):
    assert isinstance(interaction.channel, discord.TextChannel)
    # verify arguments
    if name in active_chals(): return await interaction.response.send_message(f"challenge with name {name} already exists", ephemeral=True)
    if ktype not in ktypes: return await interaction.response.send_message("invalid ktype", ephemeral=True)
    try:
      in_shapes:list[Tuple[int,...]] = literal_eval(input_shapes)
      assert isinstance(in_shapes, list) and all(isinstance(shape, tuple) and all(isinstance(s, int) for s in shape) for shape in in_shapes)
    except: return await interaction.response.send_message("invalid input shapes, expected list[tuple[int,...]]", ephemeral=True)
    try:
      out_shape:Tuple[int,...] = literal_eval(output_shape)
      assert isinstance(out_shape, tuple) and all(isinstance(s, int) for s in out_shape)
    except: return await interaction.response.send_message("invalid output shape, expected tuple[int,...]", ephemeral=True)
    try:
      g_sz:Tuple[int,int,int] = literal_eval(global_size)
      assert isinstance(g_sz, tuple) and len(g_sz) == 3 and all(isinstance(s, int) for s in g_sz)
    except: return await interaction.response.send_message("invalid input shapes, expected tuple[int,int,int]]", ephemeral=True)
    try:
      l_sz:Tuple[int,int,int] = literal_eval(local_size)
      assert isinstance(l_sz, tuple) and len(l_sz) == 3 and all(isinstance(s, int) for s in l_sz)
    except: return await interaction.response.send_message("invalid input shapes, expected tuple[int,int,int]]", ephemeral=True)
    if dtype not in dtypes: return await interaction.response.send_message(f"invalid dtype {dtype}", ephemeral=True)
    if rand_fn not in rand_fns: return await interaction.response.send_message(f"invalid rand function {rand_fn}", ephemeral=True)
    # download and compile program
    await interaction.response.send_message("loading reference code...", ephemeral=True)
    try: prog = cc((await reference_code.read()).decode('utf-8'), ktype, name)
    except Exception as e:
      return await interaction.edit_original_response(content=f"failed to load reference code: {e}")
    # generate tests
    await interaction.edit_original_response(content="generating tests...")
    try: tests, tm = gen_tests(prog, g_sz, l_sz, in_shapes, out_shape, dtypes[dtype], rand_fns[rand_fn], num_tests)
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
