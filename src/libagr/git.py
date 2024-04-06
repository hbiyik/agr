'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import shutil

from libagr import defs
from libagr import cmd
from libagr import config
from libagr import log
from libagr import cache


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


@cache.Cache.runonce
def syncremote(rname):
    log.logger.info(f"Looking up remote: {rname}:{config.CFG.getremote(rname)}")

    def syncsubs(rpath):
        cmd.stdout("git", "submodule",  "update", "--init", "--recursive", cwd=rpath, env=defs.ENV_GITNOSTDIN)
        cmd.stdout("git", "submodule",  "foreach", "--recursive",
                   "git", "fetch", cwd=rpath, env=defs.ENV_GITNOSTDIN)
        cmd.stdout("git", "submodule",  "foreach", "--recursive",
                   "git", "clean", "-d", "-x", "-f", "-f", cwd=rpath, env=defs.ENV_GITNOSTDIN)
        cmd.stdout("git", "submodule", "update", "--recursive",
                   "--remote", "--force", cwd=rpath, env=defs.ENV_GITNOSTDIN)

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
        shutil.rmtree(rpath, ignore_errors=True)
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
    head = f"HEAD:{path}"
    return cmd.stdout("git", "rev-parse", head, cwd=root)
