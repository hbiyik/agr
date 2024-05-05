'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import shutil
import time

from libagr import defs
from libagr import cmd
from libagr import config
from libagr import log
from libagr import cache
from libagr import multi


@cache.Cache.runonce
def repopath(rname):
    return os.path.join(defs.REPO_PATH, rname)


@cache.Cache.runonce
def repopkgpath(rname, pkgpath):
    return os.path.join(repopath(rname), pkgpath)


@cache.Cache.runonce
def originurl(repopath):
    try:
        return cmd.stdout("git", "config", "--get", "remote.origin.url", cwd=repopath, env=defs.ENV_GITNOSTDIN)
    except OSError:
        return None


def syncsub(subfolder, rpath):
    spath = os.path.join(rpath, subfolder)
    maxretry = 3
    for retry in range(maxretry):
        try:
            cmd.stdout("git", "submodule",  "update", "--init", "--recursive", "--remote", "--force", subfolder,
                       cwd=rpath, env=defs.ENV_GITNOSTDIN)
            cmd.stdout("git", "clean", "-d", "-x", "-f", "-f", cwd=spath, env=defs.ENV_GITNOSTDIN)
        except OSError as e:
            if retry == maxretry:
                raise(e)
            log.logger.warning(f"Retrying {retry + 1} to sync {rpath}:{subfolder}")
            time.sleep(0.1)


def syncsubs(rpath):
    submodules = cmd.stdout("git", "submodule", cwd=rpath, env=defs.ENV_GITNOSTDIN)
    if submodules == "":
        return
    pman = multi.ProcMan(8)
    for submodule in submodules.split("\n"):
        info = submodule.split(" ")
        if info[0].strip() == "":
            info.pop(0)
        subfolder = info[1]
        pman.add(syncsub, subfolder, rpath)
    pman.join()
    error = None
    for result, args, _kwargs in pman.returns.values():
        if isinstance(result, Exception):
            error = result
            log.logger.error(f"Error synching repo {args[0]}:{args[1]}")
    if error:
        raise(error)


@cache.Cache.runonce
def syncremote(rname):
    log.logger.info(f"Looking up remote: {rname}:{config.CFG.getremote(rname)}")

    remote, branch = config.CFG.getremote(rname)
    rpath = repopath(rname)
    if os.path.exists(rpath):
        oldremote = originurl(rpath)
        if (oldremote == remote):
            cmd.stdout("git", "fetch", "origin", branch, cwd=rpath, env=defs.ENV_GITNOSTDIN)
            cmd.stdout("git", "clean", "-d", "-x", "-f", "-f", cwd=rpath, env=defs.ENV_GITNOSTDIN)
            cmd.stdout("git", "reset", "--hard", f"origin/{branch}", cwd=rpath, env=defs.ENV_GITNOSTDIN)
            syncsubs(rpath)
            return
        cmd.stdout("rm", "-rf", rpath)
    os.makedirs(rpath, exist_ok=True)
    cmd.stdout("git", "clone", "-b", branch, remote, ".", cwd=rpath, env=defs.ENV_GITNOSTDIN)
    syncsubs(rpath)


@cache.Cache.runonce
def syncworking(rname, pkgfullpath, workpath):
    if not os.path.exists(workpath):
        os.makedirs(workpath)
    pkgfullpath = repopkgpath(rname, pkgfullpath)
    for fname in os.listdir(pkgfullpath):
        spath = os.path.join(pkgfullpath, fname)
        if not os.path.isdir(spath) and fname != defs.SRCINFO:
            shutil.copyfile(os.path.join(pkgfullpath, fname), os.path.join(workpath, fname), follow_symlinks=False)


def getcommit(root, path=""):
    if path == ".":
        path = ""
    return cmd.stdout("git", "rev-parse", "HEAD", cwd=os.path.join(root, path))
