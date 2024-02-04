'''
Created on Jan 30, 2024

@author: boogie
'''
import subprocess
import os
import uuid

from libagr import log


def interactive(*cmd, **kwargs):
    log.logger.debug(f"Executing: '{' '.join(cmd)}', kwargs: {kwargs}")
    p = subprocess.Popen(cmd, **kwargs)
    p.wait()
    if p.returncode == 0:
        return True


def stdout(*cmd, **kwargs):
    log.logger.debug(f"Executing: '{' '.join(cmd)}', kwargs: {kwargs}")
    buf = ""
    p = subprocess.Popen(cmd, **kwargs, stdout=subprocess.PIPE)
    for line in iter(p.stdout.readline, b""):
        line = line.decode()
        buf += line
        log.logger.debug("STDOUT: " + line if not line.endswith("\n") else line[:-1])
    p.wait()
    if p.returncode != 0:
        raise OSError(p.returncode)
    if buf.endswith("\n"):
        buf = buf[:-1]
    return buf


def source_stdout(source, cmd, **kwargs):
    log.logger.debug(f"Executing: '{cmd}', with source: {source}, kwargs: {kwargs}")
    cwd = kwargs.get("cwd") or os.getcwd()
    scriptfile = os.path.join(cwd, str(uuid.uuid4()))
    with open(scriptfile, "w") as f:
        f.write(f"source {source} && {cmd}")
    out = stdout("bash", scriptfile, **kwargs)
    os.remove(scriptfile)
    return out
