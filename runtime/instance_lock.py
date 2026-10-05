"""Process-owned Windows mutex, with a file-lock fallback for tests on Unix."""

import ctypes
import hashlib
import os


def instance_mutex_name(data_dir):
    """Return the process identity shared with Windows installation tools."""
    name = hashlib.sha256(os.path.normcase(str(data_dir.resolve())).encode()).hexdigest()
    return f"Local\\RestauranteLocal-{name}"


class InstanceLock:
    """Keep exclusive runtime ownership for one data directory."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.handle = None
        self.file = None

    def acquire(self):
        """Acquire ownership without waiting.

        Returns:
            bool: Whether this process acquired the installation lock.
        """
        if self.handle is not None or self.file is not None:
            raise RuntimeError("Mutex já adquirido por este objeto.")
        if os.name == "nt":
            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            api.CreateMutexW.restype = ctypes.c_void_p
            api.CloseHandle.argtypes = [ctypes.c_void_p]
            ctypes.set_last_error(0)
            handle = api.CreateMutexW(None, False, instance_mutex_name(self.data_dir))
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            if ctypes.get_last_error() == 183:
                api.CloseHandle(handle)
                return False
            self.handle = handle
        else:
            import fcntl

            self.file = (self.data_dir / "instance.lock").open("a+b")
            try:
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.file.close()
                self.file = None
                return False
        return True

    def release(self):
        """Release ownership after all components have stopped."""
        if self.handle is not None:
            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.CloseHandle.argtypes = [ctypes.c_void_p]
            api.CloseHandle(self.handle)
            self.handle = None
        if self.file is not None:
            self.file.close()
            self.file = None
