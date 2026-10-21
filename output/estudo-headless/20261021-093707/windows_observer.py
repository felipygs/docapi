"""WinEvent fora de contexto + Toolhelp. Sem títulos, conteúdo ou injeção."""
import ctypes as c
from ctypes import wintypes as w
import os
import threading
import time

user = c.WinDLL('user32', use_last_error=True)
kernel = c.WinDLL('kernel32', use_last_error=True)
CALLBACK = c.WINFUNCTYPE(None, w.HANDLE, w.DWORD, w.HWND, w.LONG, w.LONG, w.DWORD, w.DWORD)
ENUM = c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
user.SetWinEventHook.argtypes = [w.DWORD,w.DWORD,w.HMODULE,CALLBACK,w.DWORD,w.DWORD,w.DWORD]
user.SetWinEventHook.restype = w.HANDLE
user.UnhookWinEvent.argtypes = [w.HANDLE]
user.IsWindowVisible.argtypes = [w.HWND]
user.GetWindowThreadProcessId.argtypes = [w.HWND,c.POINTER(w.DWORD)]
user.GetForegroundWindow.restype = w.HWND
user.EnumWindows.argtypes = [ENUM,w.LPARAM]
user.PeekMessageW.argtypes = [c.POINTER(w.MSG),w.HWND,w.UINT,w.UINT,w.UINT]
user.TranslateMessage.argtypes = [c.POINTER(w.MSG)]
user.DispatchMessageW.argtypes = [c.POINTER(w.MSG)]
user.DispatchMessageW.restype = c.c_ssize_t
kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD,w.DWORD]
kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
kernel.CloseHandle.argtypes = [w.HANDLE]
kernel.OpenProcess.argtypes = [w.DWORD,w.BOOL,w.DWORD]
kernel.OpenProcess.restype = w.HANDLE
kernel.GetProcessTimes.argtypes = [w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)]
kernel.GetExitCodeProcess.argtypes = [w.HANDLE,c.POINTER(w.DWORD)]
kernel.TerminateProcess.argtypes = [w.HANDLE,w.UINT]

class ProcessEntry(c.Structure):
    _fields_ = [('dwSize',w.DWORD),('cntUsage',w.DWORD),('th32ProcessID',w.DWORD),
                ('th32DefaultHeapID',c.c_size_t),('th32ModuleID',w.DWORD),
                ('cntThreads',w.DWORD),('th32ParentProcessID',w.DWORD),
                ('pcPriClassBase',w.LONG),('dwFlags',w.DWORD),('szExeFile',w.WCHAR*260)]

kernel.Process32FirstW.argtypes = [w.HANDLE,c.POINTER(ProcessEntry)]
kernel.Process32NextW.argtypes = [w.HANDLE,c.POINTER(ProcessEntry)]

def processes():
    handle = kernel.CreateToolhelp32Snapshot(2,0)
    if handle == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    result = {}
    try:
        entry = ProcessEntry(dwSize=c.sizeof(ProcessEntry))
        ok = kernel.Process32FirstW(handle,c.byref(entry))
        while ok:
            result[entry.th32ProcessID] = dict(pid=entry.th32ProcessID,parent=entry.th32ParentProcessID,name=entry.szExeFile)
            ok = kernel.Process32NextW(handle,c.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return result

def identity(pid, terminate=False):
    handle = kernel.OpenProcess(0x1000 | (1 if terminate else 0),False,pid)
    if not handle:
        return None
    created, exited, kt, ut = w.FILETIME(),w.FILETIME(),w.FILETIME(),w.FILETIME()
    code = w.DWORD()
    try:
        if not kernel.GetProcessTimes(handle,c.byref(created),c.byref(exited),c.byref(kt),c.byref(ut)):
            return None
        kernel.GetExitCodeProcess(handle,c.byref(code))
        return dict(created=(created.dwHighDateTime<<32)|created.dwLowDateTime,alive=code.value==259)
    finally:
        kernel.CloseHandle(handle)

def terminate_owned(pid, created):
    handle = kernel.OpenProcess(0x1001,False,pid)
    if not handle:
        return False
    try:
        ft, a,b,d = w.FILETIME(),w.FILETIME(),w.FILETIME(),w.FILETIME()
        if not kernel.GetProcessTimes(handle,c.byref(ft),c.byref(a),c.byref(b),c.byref(d)):
            return False
        if ((ft.dwHighDateTime<<32)|ft.dwLowDateTime) != created:
            raise RuntimeError('PID reutilizado: encerramento recusado')
        return bool(kernel.TerminateProcess(handle,1))
    finally:
        kernel.CloseHandle(handle)

class Observer:
    def __init__(self):
        self.root = os.getpid()
        self.known = {}
        self.events = []
        self.inventories = []
        self.errors = []
        self.ready = threading.Event()
        self.stop_event = threading.Event()
        self.external_events = 0
        self.max_scan_gap = 0

    def _scan(self):
        current = processes()
        eligible = {self.root}
        # Include historic parents only when the same PID identity is alive.
        for pid, info in self.known.items():
            observed = identity(pid)
            if observed and observed['created']==info.get('created'):
                eligible.add(pid)
        while True:
            children = {pid for pid,p in current.items() if p['parent'] in eligible}
            if children <= eligible:
                break
            eligible |= children
        for pid in eligible:
            if pid in current:
                stamp = identity(pid)
                if stamp:
                    self.known[pid] = dict(current[pid],**stamp)

    def _window(self,hwnd):
        pid = w.DWORD()
        user.GetWindowThreadProcessId(hwnd,c.byref(pid))
        return dict(pid=pid.value, hwnd=int(hwnd or 0), visible=bool(user.IsWindowVisible(hwnd)))

    def _inventory(self):
        windows = []
        @ENUM
        def enum(hwnd,param):
            item = self._window(hwnd)
            if item['pid'] in self.known:
                windows.append(item)
            return True
        user.EnumWindows(enum,0)
        foreground = self._window(user.GetForegroundWindow())
        self.inventories.append(dict(t=time.time(),windows=windows,
                                      foreground_owned=foreground['pid'] in self.known,
                                      foreground=foreground if foreground['pid'] in self.known else None))

    def _run(self):
        hooks = []
        try:
            @CALLBACK
            def callback(hook,event,hwnd,obj,child,thread,tick):
                if not hwnd or (event != 3 and (obj != 0 or child != 0)):
                    return
                try:
                    item = self._window(hwnd)
                    # Buffer numeric events before PID attribution, never titles.
                    self.events.append(dict(item,event=int(event),t=time.time(),os_tick=int(tick)))
                except Exception:
                    self.errors.append('callback_error')
            self.callback = callback
            for first,last in ((3,3),(0x8000,0x8003)):
                hook = user.SetWinEventHook(first,last,None,callback,0,0,0)
                if not hook:
                    raise c.WinError(c.get_last_error())
                hooks.append(hook)
            self.started = time.time()
            self._scan()
            self._inventory()
            self.ready.set()
            previous = time.monotonic()
            msg = w.MSG()
            while not self.stop_event.is_set():
                while user.PeekMessageW(c.byref(msg),None,0,0,1):
                    user.TranslateMessage(c.byref(msg))
                    user.DispatchMessageW(c.byref(msg))
                now = time.monotonic()
                if now-previous >= .1:
                    self.max_scan_gap = max(self.max_scan_gap,now-previous)
                    self._scan()
                    self._inventory()
                    previous = now
                self.stop_event.wait(.01)
            # Drain pending notifications after all workers ended.
            while user.PeekMessageW(c.byref(msg),None,0,0,1):
                user.DispatchMessageW(c.byref(msg))
            self._scan()
            self._inventory()
        except Exception as exc:
            self.errors.append(type(exc).__name__)
            self.ready.set()
        finally:
            self.ended = time.time()
            for hook in hooks:
                user.UnhookWinEvent(hook)

    def start(self):
        self.thread = threading.Thread(target=self._run,daemon=True)
        self.thread.start()
        if not self.ready.wait(5) or self.errors:
            raise RuntimeError('Observador não iniciou')
        return self

    def finish(self):
        self.stop_event.set()
        self.thread.join(5)
        if self.thread.is_alive():
            self.errors.append('observer_join_timeout')
        owned = [e for e in self.events if e['pid'] in self.known and e['pid'] != self.root]
        self.external_events = len(self.events)-len(owned)
        alive = []
        for pid,info in self.known.items():
            stamp = identity(pid)
            if pid != self.root and stamp and stamp['alive'] and stamp['created']==info['created']:
                alive.append(info)
        return dict(started=self.started,ended=self.ended,errors=self.errors,
                    processes=list(self.known.values()),events=owned,
                    external_event_count=self.external_events,inventories=self.inventories,
                    max_inventory_gap_seconds=round(self.max_scan_gap,4),
                    visible_events=sum(e['event']==0x8002 or e['visible'] for e in owned),
                    foreground_events=sum(e['event']==3 for e in owned),alive_after=alive,
                    coverage='WinEvent create/show/hide/destroy + foreground; inventories ~100ms; no absolute flash guarantee')
