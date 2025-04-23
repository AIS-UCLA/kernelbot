from tinygrad.runtime.ops_cuda import CUDAAllocator, CUDADevice, CUDAProgram
from tinygrad.runtime.support.compiler_cuda import CUDACompiler, PTXCompiler

device = CUDADevice("cuda:0")
compilers = {
  'CUDA': CUDACompiler(device.arch),
  'PTX': PTXCompiler(device.arch)
}
cualloc = CUDAAllocator(device)

def cc(kernel:str, ktype:str, name:str) -> CUDAProgram:
  return CUDAProgram(device, name, compilers[ktype].compile(kernel))

def run(prog:CUDAProgram, global_size:tuple[int,int,int], local_size:tuple[int,int,int]) -> int:
  a = cualloc.alloc(256 * 256 * 4)
  return min([prog(a, global_size=global_size, local_size=local_size, wait=True) for _ in range(20)])

