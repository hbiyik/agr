'''
Created on Jan 30, 2024

@author: boogie
'''
import subprocess
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
    p = subprocess.Popen(cmd, **kwargs,
                         stdout=subprocess.PIPE,
                         stdin=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
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
