'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import shutil


from libagr import defs
from libagr import cmd


def reponame(remote):
    if remote.endswith("/"):
        remote = remote[:-1]
    return os.path.split(remote)[-1]


def repopath(remote):
    return os.path.join(defs.REPO_PATH, reponame(remote))


def repopkgpath(remote, pkgpath):
    return os.path.join(repopath(remote), pkgpath)


def originurl(repopath):
    return cmd.stdout("git", "config", "--get", "remote.origin.url", cwd=repopath)


def syncremote(remote, branch=defs.DEF_BRANCH):
    rpath = repopath(remote)
    if os.path.exists(rpath):
        oldremote = originurl(rpath)
        if (oldremote == remote):
            cmd.stdout("git", "fetch", "origin", branch, "--quiet", cwd=rpath)
            cmd.stdout("git", "clean", "-d", "-x", "-f", "--quiet", cwd=rpath)
            cmd.stdout("git", "reset", "--hard", f"origin/{branch}", "--quiet", cwd=rpath)
            return
        cmd.stdout("rm", "-rf", reponame(remote), cwd=defs.REPO_PATH)
    cmd.stdout("git", "clone", "-b", branch, remote, cwd=defs.REPO_PATH)


def syncworking(remote, pkgpath, workpath):
    rppath = repopkgpath(remote, pkgpath)
    for fname in os.listdir(rppath):
        spath = os.path.join(rppath, fname)
        if not os.path.isdir(spath):
            shutil.copyfile(os.path.join(rppath, fname), os.path.join(workpath, fname), follow_symlinks=False)
