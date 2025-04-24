from tinygrad import Tensor, Device
from tinygrad.helpers import dedup, to_function_name
from tinygrad.engine.realize import get_kernel, CompiledRunner
from tinygrad.engine.memory import memory_planner
from tinygrad.ops import Ops

import numpy as np
import argparse

N = 4096
def fxn(A:Tensor, B:Tensor):
  return A@B

if __name__ == "__main__":
  parser = argparse.ArgumentParser(prog="gen_chal")
  parser.add_argument('-n', '--name', help="function name")
  parser.add_argument('output_file', help="file to write to")
  args = parser.parse_args()

  A = Tensor(np.random.rand(N,N).astype("float")).realize()
  B = Tensor(np.random.rand(N,N).astype("float")).realize()

  C = fxn(A, B)
  sched = memory_planner(C.schedule(A, B))

  asts = dedup([si.ast for si in sched if si.ast.op is Ops.SINK])
  if len(asts) > 1:
    print("emitting multiple kernels, can't rename")
    for ast in asts:
      k = get_kernel(Device[Device.DEFAULT].renderer, ast).linearize()
      func = CompiledRunner(k.to_program())
      print(f"writing {to_function_name(k.name)}, launch params: {func.p.launch_dims({})}")
      with open(f"{args.output_file.rsplit('.', 1)[0]}.{to_function_name(k.name)}.{args.output_file.rsplit('.', 1)[0]}", 'w') as f:
        f.write(func.p.src)
    print(f"wrote {len(asts)} kernels")
  else:
    k = get_kernel(Device[Device.DEFAULT].renderer, asts[0]).linearize()
    func = CompiledRunner(k.to_program())
    print(f"writing {args.name if args.name else to_function_name(k.name)}, launch params: {func.p.launch_dims({})}")
    with open(args.output_file, 'w') as f:
      f.write(func.p.src.replace(to_function_name(k.name), args.name) if args.name else func.p.src)
    print("wrote 1 kernel")
