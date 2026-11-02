"""Linux x86_64 parser-only syscall allowlist; no file opens/network/fork/exec."""

import ctypes
import errno
import fcntl
import os
import platform
import resource
import stat

from rag_platform.ingestion.extraction import ExtractionError


class Filter(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_ushort),
        ("jt", ctypes.c_ubyte),
        ("jf", ctypes.c_ubyte),
        ("k", ctypes.c_uint),
    ]


class Program(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ushort), ("filters", ctypes.POINTER(Filter))]


# Linux v6.8 arch/x86/entry/syscalls/syscall_64.tbl. Unknown calls return EPERM.
# No open/openat/openat2, socket/connect, clone/fork, exec, ptrace, signal-to-peer,
# file-handle reopening, io_uring, process_vm_* or pidfd_getfd is allowed.
ALLOWED = (
    0,
    1,
    3,
    5,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    17,
    19,
    20,
    24,
    25,
    28,
    39,
    60,
    72,
    96,
    97,
    98,
    102,
    104,
    107,
    108,
    131,
    186,
    202,
    228,
    231,
    273,
    302,
    318,
    334,
)


def seal(*, cpu_seconds=30, address_bytes=512 * 1024 * 1024):
    if (
        platform.system() != "Linux"
        or platform.machine() != "x86_64"
        or type(cpu_seconds) is not int
        or not 1 <= cpu_seconds <= 30
        or type(address_bytes) is not int
        or not 64 * 1024 * 1024 <= address_bytes <= 512 * 1024 * 1024
    ):
        raise ExtractionError("SANDBOX_UNAVAILABLE")
    info = os.fstat(0)
    if (
        not stat.S_ISREG(info.st_mode)
        or (fcntl.fcntl(0, fcntl.F_GETFL) & os.O_ACCMODE) != os.O_RDONLY
    ):
        raise ExtractionError("SANDBOX_UNAVAILABLE")
    # Reject inherited descriptors before parsing. os.listdir's own FD may have
    # disappeared by fstat; any genuinely open extra descriptor fails closed.
    for entry in os.listdir("/proc/self/fd"):
        number = int(entry)
        if number <= 2:
            continue
        try:
            os.fstat(number)
        except OSError:
            continue
        raise ExtractionError("SANDBOX_UNAVAILABLE")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (address_bytes, address_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    libc = ctypes.CDLL(None, use_errno=True)
    # BPF: validate audit architecture, load syscall number, allow exactly the list.
    instructions = [
        Filter(0x20, 0, 0, 4),
        Filter(0x15, 1, 0, 0xC000003E),
        Filter(0x06, 0, 0, 0x80000000),
        Filter(0x20, 0, 0, 0),
    ]
    for number in ALLOWED:
        instructions += [Filter(0x15, 0, 1, number), Filter(0x06, 0, 0, 0x7FFF0000)]
    instructions.append(Filter(0x06, 0, 0, 0x00050000 | errno.EPERM))
    filters = (Filter * len(instructions))(*instructions)
    program = Program(len(filters), filters)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(22, 2, ctypes.byref(program)) != 0:
        raise ExtractionError("SANDBOX_UNAVAILABLE")
