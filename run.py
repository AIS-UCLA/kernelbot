import safetensors.numpy
import numpy as np
from tinygrad import GlobalCounters
from tinygrad.helpers import flat_mv
from tinygrad.runtime.ops_cuda import CUDAAllocator, CUDADevice, CUDAProgram
from tinygrad.runtime.support.compiler_cuda import CUDACompiler, PTXCompiler
from statistics import fmean
from discord.app_commands import Choice
from typing import Callable, Tuple

from utils import all_same, logger, prod

ktypes = ["CUDA", "PTX"]
async def ktype_ac(_, curr): return [Choice(name=kt, value=kt) for kt in ktypes if curr.lower() in kt.lower()]

device = CUDADevice("cuda:0")
compilers = {
  'CUDA': CUDACompiler(device.arch),
  'PTX': PTXCompiler(device.arch)
}
cualloc = CUDAAllocator(device)

def cc(kernel:str, ktype:str, name:str) -> CUDAProgram: return CUDAProgram(device, name, compilers[ktype].compile(kernel))

def run(prog:CUDAProgram, global_size:tuple[int,int,int], local_size:tuple[int,int,int], *args) -> int:
  return prog(*args, global_size=global_size, local_size=local_size, wait=True)

def gen_tests(prog:CUDAProgram, global_size:tuple[int,int,int], local_size:tuple[int,int,int],
              in_shapes:list[Tuple[int,...]], out_shape:Tuple[int,...], dtype,
              rand_fn:Callable[...,np.ndarray], num_tests:int) -> Tuple[bytes, int, float]:
  assert num_tests > 0, "must generate at least one test"
  tensors, times, ops = {}, [], []
  for i in range(num_tests):
    # create tensors and buffers
    args = [rand_fn(*shape).astype(dtype) for shape in in_shapes]
    tg_args = [cualloc.alloc(arg.size * arg.itemsize) for arg in args]
    for arg, tg in zip(args, tg_args): cualloc._copyin(tg, bytearray(arg))
    print(dtype)
    out_tg = cualloc.alloc(prod(out_shape) * dtype.itemsize)
    # run kernel
    GlobalCounters.reset()
    times.append(run(prog, global_size, local_size, *tg_args, out_tg))
    ops.append(GlobalCounters.global_ops)
    # store to safetensors
    for j, t in enumerate(args): tensors[f"test{i}.in.{j}"] = t
    cualloc._copyout(flat_mv((out:=np.empty(out_shape, dtype=dtype)).data), out_tg)
    tensors[f"test{i}.out"] = out

  if not all_same(ops): logger.info("discrepancy detected in flopcount, using last")
  return safetensors.numpy.save(tensors), ops[-1], fmean(times)

def run_tests(prog:CUDAProgram, global_size:tuple[int,int,int], local_size:tuple[int,int,int],
              tensors: bytes) -> float:
  # determin number of tests
  tensor_dict = safetensors.numpy.load(tensors)
  num_tests = len(set([k.split('.')[0] for k in tensor_dict.keys()]))
  num_args = max([int(k.split('.')[-1]) for k in tensor_dict.keys() if 'in' in k]) + 1
  times = []
  for i in range(num_tests):
    # create tensors and buffers
    args = [tensor_dict[f"test{i}.in.{j}"] for j in range(num_args)]
    tg_args = [cualloc.alloc(arg.size * arg.itemsize) for arg in args]
    for arg, tg in zip(args, tg_args): cualloc._copyin(tg, bytearray(arg))
    out_tg = cualloc.alloc(tensor_dict[f"test{i}.out"].size * tensor_dict[f"test{i}.out"].itemsize)
    # run kernel
    GlobalCounters.reset()
    times.append(run(prog, global_size, local_size, *tg_args, out_tg))
    # check output
    out = np.empty(tensor_dict[f"test{i}.out"].shape, dtype=tensor_dict[f"test{i}.out"].dtype)
    cualloc._copyout(flat_mv(out.data), out_tg)
    np.testing.assert_allclose(out, tensor_dict[f"test{i}.out"], rtol=1e-3, atol=1e-3)
  return fmean(times)

