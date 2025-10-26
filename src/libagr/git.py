'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import time
from multiprocessing import pool

from libagr import defs
from libagr import config
from libagr import log
from libagr import cache
from libagr import cmd


@cache.Cache.runonce
def repopath(rname):
    return os.path.join(defs.REPO_PATH, rname)


@cache.Cache.runonce
def repopkgpath(rname, pkgpath):
    return os.path.join(repopath(rname), pkgpath)


@cache.Cache.runonce
def originurl(repopath):
    try:
        return cmd.run_stdout("git", "config", "--get", "remote.origin.url", cwd=repopath, env=defs.ENV_GIT)
    except OSError:
        return None


def syncsub(subfolder, rpath):
    spath = os.path.join(rpath, subfolder)
    maxretry = 3
    for retry in range(maxretry):
        try:
            cmd.run_interactive("git", "submodule", "update", "--init", "--recursive", "--remote", "--force",
                                subfolder, cwd=rpath, env=defs.ENV_GIT)
            cmd.run_interactive("git", "clean", "-d", "-x", "-f", "-f", cwd=spath, env=defs.ENV_GIT)
            return
        except OSError as e:
            if retry == maxretry:
                raise(e)
            log.logger.info(f"Retrying {retry + 1} to sync {rpath}: {subfolder}")
            time.sleep(0.1)


def syncsubs(rpath):
    submodules = cmd.run_stdout("git", "submodule", cwd=rpath, env=defs.ENV_GIT)
    if submodules == "":
        return
    args = []
    for submodule in submodules.split("\n"):
        info = submodule.split(" ")
        if info[0].strip() == "":
            info.pop(0)
        subfolder = info[1]
        args.append([subfolder, rpath])
    with pool.ThreadPool(8) as p:
        p.starmap(syncsub, args)


@cache.Cache.runonce
def syncremote(rname):
    log.logger.info(f"Looking up remote: {rname}: {config.CFG.getremote(rname)}")

    remote, branch = config.CFG.getremote(rname)
    rpath = repopath(rname)
    if os.path.exists(rpath):
        oldremote = originurl(rpath)
        if (oldremote == remote):
            cmd.run_stdout("git", "fetch", "origin", branch, cwd=rpath, env=defs.ENV_GIT)
            cmd.run_stdout("git", "clean", "-d", "-x", "-f", "-f", cwd=rpath, env=defs.ENV_GIT)
            cmd.run_stdout("git", "reset", "--hard", f"origin/{branch}", cwd=rpath, env=defs.ENV_GIT)
            syncsubs(rpath)
            return
        cmd.run_stdout("rm", "-rf", rpath)
    os.makedirs(rpath, exist_ok=True)
    cmd.run_stdout("git", "clone", "-b", branch, remote, ".", cwd=rpath, env=defs.ENV_GIT)
    syncsubs(rpath)


def getcommit(path):
    if path == ".":
        path = ""
    return cmd.run_stdout("git", "rev-parse", "HEAD", cwd=path)
