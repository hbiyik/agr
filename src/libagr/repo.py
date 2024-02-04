'''
Created on Jan 30, 2024

@author: boogie
'''
import os
from libagr import git
from libagr import config
from libagr import defs
from libagr import pkgbuild

cfg = config.Config()


def iterpkgs(remote, branch=defs.DEF_BRANCH):
    git.syncremote(remote, branch)
    rpath = git.repopath(remote)
    for root, _subdirs, files in os.walk(rpath, followlinks=False):
        if defs.IGNORE_FLAG in files or "PKGBUILD" not in files:
            continue
        pkgpath = os.path.relpath(root, rpath)
        yield pkgbuild.Pkgbuild(remote, pkgpath)


def haspkg(pkgname):
    pkgbuilds = []
    for _rname, remote, branch in cfg.iterremotes():
        for pkgb in iterpkgs(remote, branch):
            pkgbuilds.append(pkgb)

    pkgrealname = None
    for pkgb in pkgbuilds:
        pkgrealname = pkgb.haspkg(pkgname)
        if pkgrealname:
            break
    return pkgrealname


def getdeps(*pkgnames):
    deps = []
    pkgbuilds = []
    for _rname, remote, branch in cfg.iterremotes():
        for pkgb in iterpkgs(remote, branch):
            pkgbuilds.append(pkgb)

    for pkgname in pkgnames:
        for pkgb in pkgbuilds:
            realpkgname = pkgb.haspkg(pkgname)
            if realpkgname:
                deps.append([pkgb, realpkgname, None, None])
                for pdep, delim, vers in pkgb.deps(realpkgname):
                    for dpkgb in pkgbuilds:
                        realdepname = dpkgb.haspkg(pdep)
                        if realdepname:
                            hasdep = False
                            for dep in deps:
                                if dep[0] == realdepname:
                                    hasdep = True
                                    break
                            if not hasdep and realdepname != realpkgname:
                                deps.append([dpkgb, realdepname, delim, vers])
    if deps:
        subdeps = getdeps(*deps)
        if subdeps:
            for subdep in subdeps:
                deps.append(subdep)
    return deps
