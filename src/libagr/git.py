'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import shutil

from libagr import defs
from libagr import cmd
from libagr import log
from libagr import cache


@cache.Cache.runonce
def reponame(remote):
    if remote.endswith("/"):
        remote = remote[:-1]
    if remote.endswith(".git"):
        remote = remote[:-4]
    return os.path.split(remote)[-1]


@cache.Cache.runonce
def repopath(remote):
    return os.path.join(defs.REPO_PATH, reponame(remote))


@cache.Cache.runonce
def repopkgpath(remote, pkgpath):
    return os.path.join(repopath(remote), pkgpath)


@cache.Cache.runonce
def originurl(repopath):
    return cmd.stdout("git", "config", "--get", "remote.origin.url", cwd=repopath, env=defs.ENV_GITNOSTDIN)


@cache.Cache.runonce
def syncremote(remote, branch=defs.DEF_BRANCH):
    log.logger.info(f"Looking up remote: {remote}")

    def syncsubs(rpath):
        cmd.stdout("git", "submodule",  "update", "--init", "--recursive", cwd=rpath, env=defs.ENV_GITNOSTDIN)
        cmd.stdout("git", "submodule",  "foreach", "--recursive",
                   "git", "fetch", cwd=rpath, env=defs.ENV_GITNOSTDIN)
        cmd.stdout("git", "submodule",  "foreach", "--recursive",
                   "git", "clean", "-d", "-x", "-f", "-f", cwd=rpath, env=defs.ENV_GITNOSTDIN)
        cmd.stdout("git", "submodule", "update", "--recursive",
                   "--remote", "--force", cwd=rpath, env=defs.ENV_GITNOSTDIN)

    rpath = repopath(remote)
    if os.path.exists(rpath):
        oldremote = originurl(rpath)
        if (oldremote == remote):
            cmd.stdout("git", "fetch", "origin", branch, cwd=rpath, env=defs.ENV_GITNOSTDIN)
            cmd.stdout("git", "clean", "-d", "-x", "-f", "-f", cwd=rpath, env=defs.ENV_GITNOSTDIN)
            cmd.stdout("git", "reset", "--hard", f"origin/{branch}", cwd=rpath, env=defs.ENV_GITNOSTDIN)
            syncsubs(rpath)
            return
        cmd.stdout("rm", "-rf", reponame(remote), cwd=defs.REPO_PATH)
    cmd.stdout("git", "clone", "-b", branch, remote, cwd=defs.REPO_PATH, env=defs.ENV_GITNOSTDIN)
    syncsubs(rpath)


@cache.Cache.runonce
def syncworking(remote, pkgfullpath, workpath):
    if not os.path.exists(workpath):
        os.makedirs(workpath)
    pkgfullpath = repopkgpath(remote, pkgfullpath)
    # log.logger.info(f"Getting package: {reponame(pkgfullpath)} from remote: {remote}")
    for fname in os.listdir(pkgfullpath):
        spath = os.path.join(pkgfullpath, fname)
        if not os.path.isdir(spath) and fname != defs.SRCINFO:
            shutil.copyfile(os.path.join(pkgfullpath, fname), os.path.join(workpath, fname), follow_symlinks=False)


def getcommit(root, path=""):
    if path == ".":
        path = ""
    head = f"HEAD:{path}"
    return cmd.stdout("git", "rev-parse", head, cwd=root)
