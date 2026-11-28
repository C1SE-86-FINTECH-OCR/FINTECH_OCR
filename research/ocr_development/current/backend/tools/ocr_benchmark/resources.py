import ctypes
from ctypes import wintypes as wt
import os
import subprocess
from threading import Event, Thread
from time import monotonic


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("size", wt.DWORD), ("usage", wt.DWORD), ("pid", wt.DWORD),
        ("heap", ctypes.c_size_t), ("module", wt.DWORD), ("threads", wt.DWORD),
        ("parent", wt.DWORD), ("priority", wt.LONG), ("flags", wt.DWORD),
        ("executable", wt.WCHAR * 260),
    ]


class MemoryCounters(ctypes.Structure):
    _fields_ = [("size", wt.DWORD), ("faults", wt.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "peak_working", "working", "peak_paged", "paged",
            "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile",
        )
    ]


class WindowsMemory:
    def __init__(self):
        self.api = ctypes.WinDLL("kernel32")
        watch = ctypes.WinDLL("psapi")
        self.memory = watch.GetProcessMemoryInfo
        self.memory.argtypes = [wt.HANDLE, ctypes.POINTER(MemoryCounters), wt.DWORD]
        self.api.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
        self.api.CreateToolhelp32Snapshot.restype = wt.HANDLE
        self.api.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self.api.OpenProcess.restype = wt.HANDLE
        self.api.CloseHandle.argtypes = [wt.HANDLE]
        self.api.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(ProcessEntry)]
        self.api.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(ProcessEntry)]

    def descendants(self, root):
        snapshot = self.api.CreateToolhelp32Snapshot(2, 0)
        if snapshot in (None, ctypes.c_void_p(-1).value):
            return {root}
        children = {}
        entry = ProcessEntry(size=ctypes.sizeof(ProcessEntry))
        try:
            ok = self.api.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                children.setdefault(entry.parent, []).append(entry.pid)
                ok = self.api.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            self.api.CloseHandle(snapshot)
        pending, found = [root], {root}
        while pending:
            pid = pending.pop()
            new = set(children.get(pid, ())) - found
            found.update(new)
            pending.extend(new)
        return found

    def working_set_mib(self, pid):
        handle = self.api.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            usage = MemoryCounters(size=ctypes.sizeof(MemoryCounters))
            if self.memory(handle, ctypes.byref(usage), usage.size):
                return usage.working / (1024 ** 2)
            return None
        finally:
            self.api.CloseHandle(handle)


def gpu_memory_mib(pid):
    try:
        response = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    values = [value.strip().split(",") for value in response.stdout.splitlines()]
    matches = [mem.strip() for owner, mem in (x for x in values if len(x) == 2) if owner.strip() == str(pid)]
    # WDDM can return N/A even if the GPU process is active.
    return sum(int(value) for value in matches) if matches and all(v.isdecimal() for v in matches) else None


class Monitor:
    def __init__(self, device="cpu", interval=0.1):
        self.pid, self.device, self.interval = os.getpid(), device, interval
        self.memory = WindowsMemory() if os.name == "nt" else None
        self.stop = Event()
        self.thread = Thread(target=self._poll, daemon=True)
        self.ram_peak = self.vram_peak = None
        self.ram_samples = self.vram_samples = 0
        self.child_working_set_samples = 0

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join()

    def _poll(self):
        next_gpu = 0
        while True:
            if self.memory:
                values = {pid: self.memory.working_set_mib(pid) for pid in self.memory.descendants(self.pid)}
                if values[self.pid] is not None:
                    self.ram_samples += 1
                    self.child_working_set_samples += any(
                        pid != self.pid and value is not None for pid, value in values.items()
                    )
                    self.ram_peak = max(self.ram_peak or 0, sum(x for x in values.values() if x is not None))
            if self.device.startswith("gpu") and monotonic() >= next_gpu:
                value = gpu_memory_mib(self.pid)
                if value is not None:
                    self.vram_samples += 1
                    self.vram_peak = max(self.vram_peak or 0, value)
                next_gpu = monotonic() + 0.5
            if self.stop.wait(self.interval):
                break

    def report(self):
        return {
            "ram_peak_mib": round(self.ram_peak, 2) if self.ram_peak is not None else None,
            "ram_samples": self.ram_samples,
            "samples_including_children": self.child_working_set_samples,
            "ram_method": "Windows sampled process-tree working set" if self.memory else "unavailable",
            "sampling_interval_s": self.interval,
            "vram_peak_mib": self.vram_peak,
            "vram_samples": self.vram_samples,
            "vram_status": ("not_applicable_cpu" if self.device == "cpu" else
                            "sampled" if self.vram_samples else "unavailable"),
        }
