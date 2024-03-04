'''
Created on Jan 30, 2024

@author: boogie
'''
import os

from libagr import cache
from libagr import config
from libagr import defs
from libagr import git
from libagr import log
from libagr import cmd
from libagr import pkgbuild
from libagr import multi
from libagr.pkgbuild import Dependency


cfg = config.Config()


@cache.Cache.runonce
def getinstalled():
    installed = {}
    index = 0
    for line in cmd.stdout("pacman", "-Qi").split("\n"):
        matches = line.split(" : ")
        if matches and len(matches) == 2:
            index += 1
            if index == 1:
                pkgname = matches[1].strip()
            elif index == 2:
                version = matches[1].strip()
            elif index == 8:
                provides = matches[1].strip()
            elif index > 8:
                continue
        else:
            index = 0
            if not provides[0].isupper():
                provideslist = [pkgbuild.Dependency(x) for x in provides.split(" ") if x != ""]
            else:
                provideslist = []
            pkg = Dependency(f"{pkgname}={version}")
            if pkgname not in [x.pkgname for x in provideslist]:
                provideslist.append(pkg)
            for provide in provideslist:
                if provide.pkgname not in installed:
                    installed[provide.pkgname] = pkg
    return installed


INSTALLED = getinstalled()


def checkinstall(pkgname):
    return INSTALLED.get(pkgname)


def iterpkgs(remote, branch=defs.DEF_BRANCH):
    git.syncremote(remote, branch)
    rpath = git.repopath(remote)
    for root, _subdirs, files in os.walk(rpath, followlinks=False):
        if defs.IGNORE_FLAG in files or defs.PKGBUILD not in files:
            continue
        pkgpath = os.path.relpath(root, rpath)
        yield pkgpath


@cache.Cache.runonce
def allpkgbuilds(remote=None):
    pman = multi.ProcMan(numworkers=defs.NUMCORES * 2, waittime=0)
    for _rname, premote, branch in cfg.iterremotes():
        if remote is not None and remote != premote:
            continue
        for pkgpath in iterpkgs(premote, branch):
            pman.add(pkgbuild.getpkgbuild, premote, pkgpath)
    pman.join()
    pkgbuilds = []
    excs = []
    for result, args, _kwargs in pman.returns.values():
        if isinstance(result, Exception):
            log.logger.warning(f"Error in {git.reponame(args[0])}:{args[1]} check {defs.SRCINFO}")
            excs.append(result)
        else:
            pkgbuilds.append(result)
    return pkgbuilds + excs


@cache.Cache.runonce
def getpkgbuild(pkgname):
    for pkgb in allpkgbuilds():
        pkgrealname = pkgb.pkgrealname(pkgname)
        if pkgrealname:
            return pkgb, pkgrealname
    return None, None


@cache.Cache.runonce
def getdeps(*pkgnames, make=False, excludes=None):
    deps = []
    if excludes is None:
        excludes = []

    for pkgname in pkgnames:
        pkgb, pkgrealname = getpkgbuild(pkgname)
        if pkgb:
            if pkgrealname not in excludes:
                excludes.append(pkgrealname)
            for dep in pkgb.makedepends if make else pkgb.depends.get(pkgrealname, []):
                dep_pkgb, dep_pkgrealname = getpkgbuild(dep.pkgname)
                if dep_pkgb and dep_pkgrealname not in excludes:
                    dep.pkgname = dep_pkgrealname
                    excludes.append(dep_pkgrealname)
                    if dep_pkgrealname not in [x.pkgname for x in deps]:
                        deps.append(dep)
    if deps:
        subdeps = getdeps(*[x.pkgname for x in deps], make=make, excludes=excludes)
        if subdeps:
            deps.extend(subdeps)
    return deps


def installdlagents(pkgb, **kwargs):
    dlagents = pkgb.dlagents()
    agr_installs, sys_installs = needsinstall(*dlagents)
    if sys_installs:
        raise Exception(f"You need to install {' '.join(sys_installs)} dlagents to continue")
    if agr_installs and not installpkgs(*agr_installs, **kwargs):
        return False
    return True


def installpkgs(*packages, **kwargs):
    report = []
    if not packages:
        return report
    installs = []
    for pkgname in packages:
        pkgb, pkgrealname = getpkgbuild(pkgname)
        if not pkgb:
            log.logger.error(f"Can not find package {pkgname}")
            return report
        if pkgrealname not in installs:
            installs.append(pkgrealname)
    deps = list(getdeps(*packages)) + list(getdeps(*packages, make=True))
    deps.reverse()
    agr_installs, _sys_installs = needsinstall(*deps)
    installs = agr_installs + installs
    log.logger.info(f"Installing {' '.join(installs)}")
    for install in installs:
        ins_pkgb, ins_pkgrealname = getpkgbuild(install)
        if not ins_pkgb.install(ins_pkgrealname, **kwargs):
            log.logger.error(f"Error installing {ins_pkgrealname}:{ins_pkgb.version.version}")
            return report
        else:
            report.append(f"Installed {ins_pkgrealname}:{ins_pkgb.version.version}")
    return report


def needsinstall(*packages):
    agr_installs = []
    sys_installs = []
    for package in packages:
        syspkg = checkinstall(package.pkgname)
        if syspkg and ((package.compare and syspkg.version.compare(package.compare, package.version)) or package.compare is None):
            continue
        pkgb, pkgrealname = getpkgbuild(package.pkgname)
        if pkgb:
            if pkgb.isdynamic and pkgb.islocal:
                # sync to local and make srcinfo on local
                if installdlagents(pkgb):
                    pkgb = pkgb.sync()
                else:
                    return
            if package.compare and not pkgb.version.compare(package.compare, package.version):
                log.logger.error(f"Can not find package {package.pkgname} with version{package.compare}{pkgb.version}")
                return
            if pkgrealname not in agr_installs:
                agr_installs.append(pkgrealname)
        elif not syspkg:
            sys_installs.append(package.pkgname)
    return agr_installs, sys_installs
