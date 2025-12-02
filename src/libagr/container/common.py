'''
Created on May 8, 2024

@author: boogie
'''
import platform
import re
import os
from libagr import config
from libagr import container
from libagr import cmd


def iter_containers(arch=None):
    arch = arch or platform.uname()[4]
    for cont in container.CONTAINERS:
        if cont.host_archs is None or arch in cont.host_archs:
            yield cont


def set_container(name):
    for cont in iter_containers():
        if cont.name == name:
            config.CFG.setcontainer(name)
            return
    raise RuntimeError(f"Container {name} not found")


def get_container(name=None):
    name = name or config.CFG.getcontainer()
    if name:
        for cont in iter_containers():
            if cont.name == name:
                return cont
    return container.native.Native


def ishostqemu():
    out = cmd.run_stdout("ps", "-q", str(os.getpid()), "-o", "cmd=")
    return bool(re.search(r"qemu-.+-static", out))
