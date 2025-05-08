from ast import literal_eval
import discord, logging, functools, operator, inspect
from discord.app_commands import Choice
from typing import Iterable, TypeVar, Union, get_args, get_origin, get_type_hints

from db import db, Perm

def check_user(*perms:Perm):
    def dec(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # For the USER permission, check if they have the "cuda-coda" role
            if Perm.USER in perms and any(role.name.lower() == "cuda-coda" for role in interaction.user.roles):
                # If we only need USER permission, proceed
                if all(p == Perm.USER for p in perms):
                    return await func(self, interaction, *args, **kwargs)
            
            # For ADMIN permission, check if they have an "admin" role
            if Perm.ADMIN in perms and any(role.name.lower() == "kernelbot-admin" for role in interaction.user.roles):
                return await func(self, interaction, *args, **kwargs)
            
            # If we got here, permissions are insufficient
            missing_perms = []
            if Perm.USER in perms and not any(role.name.lower() == "cuda-coda" for role in interaction.user.roles):
                missing_perms.append("CUDA-CODA role")
            if Perm.ADMIN in perms and not any(role.name.lower() == "kernelbot-admin" for role in interaction.user.roles):
                missing_perms.append("ADMIN role")
                
            await interaction.response.send_message(
                f"Missing permissions: {', '.join(missing_perms)}", 
                ephemeral=True
            )
        return wrapper
    return dec

def init_logger():
  formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%b %d %H:%M:%S")
  handler = logging.StreamHandler()
  handler.setFormatter(formatter)
  logger = logging.getLogger(__name__)
  logger.setLevel(logging.INFO)
  logger.addHandler(handler)
  return logger, formatter

logger, formatter = init_logger()

def convert_literals(func):
  hints = get_type_hints(func)
  sig = inspect.signature(func)
  anno = { name: param for name, param in sig.parameters.items() if param.annotation is not inspect._empty or name == "self" }
  new_params = [param.replace(annotation=str) if name != "self" and get_origin(hints[name]) in (list, tuple) else param for name, param in anno.items()]

  def check(val, typ:type) -> bool:
    origin = get_origin(typ)
    args = get_args(typ)
    if origin is tuple:
      if not isinstance(val, tuple): return False
      if len(args) == 2 and args[1] is Ellipsis: return all(check(v, args[0]) for v in val)
      if len(val) != len(args): return False
      return all(check(v, t) for v, t in zip(val, args))
    if origin is list:
      if not isinstance(val, list): return False
      return all(check(v, args[0]) for v in val)
    return isinstance(val, typ)

  @functools.wraps(func)
  async def wrapper(self, i:discord.Interaction, *args, **kwargs):
    bound = sig.bind(self, i, *args, **kwargs)
    bound.apply_defaults()

    for arg, param in anno.items():
      if arg in bound.arguments:
        if get_origin(param.annotation) in (list, tuple) and isinstance(val:=bound.arguments[arg], str):
          val = literal_eval(val)
          if not check(val, param.annotation): await i.response.send_message(f"invalid argument {arg}, expected {param.annotation}", ephemeral=True)
          bound.arguments[arg] = val
    return await func(*bound.args, **bound.kwargs)
  wrapper.__signature__ = sig.replace(parameters=new_params)
  return wrapper

@functools.cache
def active_chals() -> list[str]: return [t[0] for t in db.execute("SELECT name FROM challenges;").fetchall()]

async def challenge_ac(_, curr): return [Choice(name=chal, value=chal) for chal in active_chals() if curr.lower() in chal.lower()]

@functools.cache
def make_leaderboard(chal:str) -> str:
  resp = db.execute("""
    SELECT user_id, name, type, timing
    FROM submissions
    WHERE comp_id = (SELECT id FROM challenges WHERE name = ?)
    ORDER BY timing ASC;""", (chal,)).fetchall()
  return f"# Challenge: `{chal}`\n"+"\n".join([f"{i+1}. `{name} ({ktype})` in {fmt_time(tm)} by <@{uid}>" for i, (uid, name, ktype, tm) in enumerate(resp)])

T = TypeVar("T")
def all_same(items:list[T]): return all(x == items[0] for x in items)
def prod(x:Iterable[T]) -> Union[T,int]: return functools.reduce(operator.mul, x, 1)
def fmt_time(tm:float) -> str: return f"{tm*1e6:.2f} us" if tm < 1e-3 else f"{tm*1e3:.2f} ms" if tm < 1 else f"{tm:.2f} s"
