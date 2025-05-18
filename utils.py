from ast import literal_eval
import discord, logging, functools, operator, inspect
from discord.app_commands import Choice
from typing import Iterable, TypeVar, Union, get_args, get_origin, get_type_hints
import datetime
import os
from db import db, Perm
import functools

def check_user(*perms:Perm):
    def dec(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            has_permission = False
            
            if Perm.USER in perms and any(role.name == "CUDA Coda" for role in interaction.user.roles):
                has_permission = True
                
            if Perm.ADMIN in perms and any(role.name == "kernelbot admin" for role in interaction.user.roles):
                has_permission = True
                
            if not has_permission:
                required_roles = []
                if Perm.USER in perms:
                    required_roles.append("CUDA Coda")
                if Perm.ADMIN in perms:
                    required_roles.append("kernelbot admin")
                
                role_list = " or ".join(f"`{r}`" for r in required_roles)
                await interaction.response.send_message(
                    f"Missing permissions: You need the {role_list} role to use this command.",
                    ephemeral=True
                )
                return
                
            return await func(self, interaction, *args, **kwargs)
            
        wrapper._check_user_perms = perms
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

def format_submission_result(challenge_name: str, user_id: str, kernel_name: str, kernel_type: str, timing: float) -> str:
  # Get the user's submissions for the challenge
  best_time = db.execute("""
    SELECT MIN(s.timing)
    FROM submissions s
    JOIN challenges c ON s.comp_id = c.id
    WHERE c.name = ? AND s.user_id = ?
  """, (challenge_name, user_id)).fetchone()[0]
  
  message = f"# Submission for: `{challenge_name}`\n"
  message += f"Kernel: `{kernel_name} ({kernel_type})`\n"
  message += f"Time: {fmt_time(timing)}\n"
  
  if timing <= best_time:
    message += "**This is your new personal best!** 🎉"
  else:
    message += f"Your best time is {fmt_time(best_time)}"
  
  return message

def get_submission_position(challenge: str, user_id: int) -> int:
    """Get position of the user in the leaderboard for this challenge"""
    leaderboard = db.execute("""
        WITH RankedSubmissions AS (
            SELECT 
                user_id, 
                MIN(timing) as best_time,
                ROW_NUMBER() OVER (ORDER BY MIN(timing) ASC) as position
            FROM submissions
            WHERE comp_id = (SELECT id FROM challenges WHERE name = ?)
            GROUP BY user_id
        )
        SELECT position 
        FROM RankedSubmissions
        WHERE user_id = ?
    """, (challenge, user_id)).fetchone()
    
    return leaderboard[0] if leaderboard else 0

def get_ordinal(n: int) -> str:
    """Return number with ordinal suffix (1st, 2nd, 3rd, etc)"""
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th'][n % 10]
    return f"{n}{suffix}"

@functools.cache
def make_leaderboard(chal:str, with_medals:bool=True) -> str:
  # Get best submission per user
  resp = db.execute("""
    WITH RankedSubmissions AS (
      SELECT 
        s.user_id, 
        s.name, 
        s.type, 
        s.timing,
        ROW_NUMBER() OVER (PARTITION BY s.user_id ORDER BY s.timing ASC) as rn
      FROM submissions s
      JOIN challenges c ON s.comp_id = c.id
      WHERE c.name = ?
    )
    SELECT user_id, name, type, timing
    FROM RankedSubmissions
    WHERE rn = 1
    ORDER BY timing ASC;
  """, (chal,)).fetchall()
  
  header = f"# Challenge: `{chal}`\n"
  
  if not resp:
    return header + "No submissions yet."
      
  rankings = []
  for i, (uid, name, ktype, tm) in enumerate(resp):
    position = i + 1
    
    if with_medals and position <= 3:
      if position == 1:
        medal = "🥇 "
      elif position == 2:
        medal = "🥈 "
      elif position == 3:
        medal = "🥉 "
      rankings.append(f"{medal} `{name} ({ktype})` in {fmt_time(tm)} by <@{uid}>")
    else:
      rankings.append(f"{position}. `{name} ({ktype})` in {fmt_time(tm)} by <@{uid}>")
  
  return header + "\n".join(rankings)

T = TypeVar("T")
def all_same(items:list[T]): return all(x == items[0] for x in items)
def prod(x:Iterable[T]) -> Union[T,int]: return functools.reduce(operator.mul, x, 1)
def fmt_time(tm:float) -> str: return f"{tm*1e6:.2f} us" if tm < 1e-3 else f"{tm*1e3:.2f} ms" if tm < 1 else f"{tm:.2f} s"
