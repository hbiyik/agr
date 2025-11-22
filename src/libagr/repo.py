'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import traceback
from multiprocessing import pool
from libagr import config
from libagr import defs
from libagr import git
from libagr import log
from libagr import pkgbuild
from libagr import cache
from libagr import autorel


def iterpkgpaths(rname):
    rpath = git.repopath(rname)
    for root, _subdirs, files in os.walk(rpath, followlinks=False):
        if defs.IGNORE_FLAG in files or defs.PKGBUILD not in files:
            continue
        pkgpath = os.path.relpath(root, rpath)
        yield pkgpath


def tempsync(pkgbuilds):
    def _tempsync(pkgb):
        pkgb.gensrcinfo()
        try:
            pkgb.parse()
        except Exception:
            log.logger.warning(f"Can not parse package: {pkgb}")
            log.logger.debug(traceback.format_exc())

    with pool.ThreadPool(min(defs.NUMCORES, 8)) as p:
        p.map(_tempsync, pkgbuilds)
    return pkgbuilds


def iterpkgbuilds(repo=None, no_repo=None):
    repo = repo or []
    no_repo = no_repo or []
    if not repo == defs.FILTER_NONE or not no_repo == defs.FILTER_ALL:
        for remote in config.CFG.iterremotes():
            if repo and repo != defs.FILTER_ALL and remote not in repo:
                continue
            elif no_repo and no_repo != defs.FILTER_NONE and remote in no_repo:
                continue
            for pkgpath in iterpkgpaths(remote):
                yield remote, pkgpath


@cache.Cache.runonce
def allpkgbuilds(container, repo=None, no_repo=None):
    pkgbuilds = []
    for rname, pkgpath in iterpkgbuilds(repo, no_repo):
        pkgb = pkgbuild.getpkgbuild(container, rname, pkgpath)
        if pkgb and not pkgb.isbroken:
            pkgbuilds.append(pkgb)
    return pkgbuilds


def getpackages(container, pkgnames, repo=None, no_repo=None):
    result = []
    for pkgb in allpkgbuilds(container, repo, no_repo):
        if pkgnames == defs.FILTER_NONE:
            continue
        elif pkgnames == defs.FILTER_ALL:
            result.extend(pkgb.pkgname)
            continue
        for pkgname in pkgnames:
            package = pkgb.getpackage(pkgname)
            if package and package not in result:
                package = pkgb.getpackage(pkgname)
                result.append(package)
    return result


def select_alts(container, package, repo=None, no_repo=None, agrfirst=False, noconfirm=False, pacman=True):
    # search in agr
    found_agr_deps = []

    # search in pacman
    found_sys_deps = []

    # total_alts = found_agr_deps + found_sys_deps if agrfirst else found_sys_deps + found_agr_deps

    # check if the found alternative satisfies the package version dependency
    # filtered_alts = []
    for dest, source in [(found_agr_deps, getpackages(container, [package.pkgname], repo, no_repo)),
                         (found_sys_deps, container.available.get(package, []))]:
        for alt in source:
            if alt.version is None:
                pass
            if package.compare and alt.compare and not alt.version.compare(package.compare, package.version):
                log.logger.debug(f"{alt}{alt.version.compare}{alt.version.version} does not satify {package}{package.version.compare}{package.version.version}")
                continue
            dest.append(alt)

    # select the alternative
    if not len(found_agr_deps) and not len(found_sys_deps):
        return  # no package available
    elif len(found_agr_deps) == 1 and not len(found_sys_deps):
        return found_agr_deps[0]
    elif len(found_sys_deps) and not len(found_agr_deps):
        return found_sys_deps[0]  # let the pacman/makepkg choose
    elif noconfirm:
        return found_agr_deps[0] if len(found_agr_deps) and (agrfirst or not len(found_sys_deps)) else found_sys_deps[0]
    else:
        msgs = []
        if len(found_agr_deps):
            msgs.append(f"{len(found_agr_deps)} AGR")
        if len(found_sys_deps):
            msgs.append(f"{len(found_sys_deps)} PACMAN")
        log.logger.info(f"Found " + ",".join(msgs) + f" candidates for package '{package.pkgname}'")
        log.logger.info("Please select which variant to use")
        index = 0
        pacmanopt = None
        for alternative in found_agr_deps:
            index += 1
            log.logger.info(f"{index}) AGR: {alternative.pkgbuild.remotename}: {alternative.pkgname}")
        if len(found_sys_deps):
            index += 1
            pacmanopt = index
            log.logger.info(f"{index}) Let pacman choose from {found_sys_deps}")
        defval = pacmanopt if pacmanopt is not None and not agrfirst else 0
        offset = defval
        while True:
            offset = input(f"Enter a number in between 1-{index}, (Default: {defval}): ")
            if offset.isdigit() and int(offset) > 0 and int(offset) <= index:
                offset = int(offset) - 1
                break
            elif offset.strip() == "":
                offset = defval
                break
        return found_agr_deps[offset] if offset < len(found_agr_deps) else found_sys_deps[0]


def getdeps(container, packages, no_packages=None, repo=None, no_repo=None, agrfirst=False, noconfirm=False, make=False, excludes=None, alternatives=None):
    no_packages = no_packages or []
    excludes = excludes or []
    if alternatives is None:
        alternatives = {}
    deps = []

    for package in packages:
        if package in no_packages:
            continue
        if package.pkgbuild:
            for dep in package.pkgbuild.makedepends if make else package.pkgbuild.depends.get(package, []):
                if dep in no_packages:
                    continue
                if dep in alternatives:
                    alternative = alternatives[dep]
                else:
                    alternative = select_alts(container, dep, repo, no_repo, agrfirst, noconfirm, False)
                    if alternative:
                        alternatives[dep] = alternative
                if not alternative or alternative.pkgbuild is None:
                    # pacman package, dead code?
                    continue
                if alternative not in excludes:
                    excludes.append(alternative)
                    if alternative not in deps:
                        deps.append(alternative)
    if deps:
        subdeps = getdeps(container, deps, no_packages, repo, no_repo, agrfirst, noconfirm, make, excludes, alternatives)
        if subdeps:
            deps = subdeps + deps
    return deps


def buildpkgs(container, packages, no_packages=None, repo=None, no_repo=None, agrfirst=False, skippgpcheck=False,
              skipchecksum=False, skipinteg=False, noconfirm=False, force=False, ignorearch=False):
    # depends
    bases, deps = resolvepkgs(container, packages, no_packages, repo, no_repo, agrfirst, noconfirm, False)
    # make_depends
    _, make_deps = resolvepkgs(container, packages, no_packages, repo, no_repo, agrfirst, noconfirm, True)
    for dep in make_deps:
        if dep not in deps and dep not in bases:
            deps.append(dep)

    # if dep is also in base packages, first build it and then install it
    basedeps = []
    for base in bases:
        if base in deps:
            deps.remove(base)
            basedeps.append(base)

    agr_installs, _sys_installs = needsinstall(container, deps, repo=repo, no_repo=no_repo, agrfirst=agrfirst, noconfirm=noconfirm)
    if agr_installs:
        log.logger.info(f"Installing dependecies from agr: {agr_installs}")
    if not installpkgs(container, agr_installs, skippgpcheck, skipchecksum, skipinteg, noconfirm, force, ignorearch):
        return False
    for base_package in bases:
        git.syncremote(base_package.pkgbuild.remotename)
        if not base_package.pkgbuild:
            continue
        artifact = base_package.pkgbuild.getartifact(base_package)
        if artifact and not force:
            if container.name == "native":
                try:
                    artifact = base_package.pkgbuild.latestbuild(base_package)
                    autorel.syncsysdeps(container, base_package, noconfirm, agr_installs)
                except Exception as e:
                    log.logger.warning("Can not analyse %s, assuming it is already built without any issue, Error:%s",
                                       base_package, e)
                else:
                    if autorel.checkpkg(artifact) == autorel.DEP_OLD:
                        autorel.bumprel(base_package.pkgbuild, artifact)
            log.logger.info(f"already built, {artifact}")
        elif base_package.pkgbuild.build(force, skippgpcheck, skipchecksum, skipinteg, noconfirm, ignorearch) is False:
            log.logger.error(f"Error building {base_package}")
            return False
        # install previously built package if it was in deps list
        if base_package in basedeps and not base_package.isinstalled(container):
            if not installpkgs(container, [base_package], skippgpcheck, skipchecksum, skipinteg, noconfirm, force, ignorearch):
                return False
            agr_installs.append(base_package)
    return packages


def installpkgs(container, packages, skippgpcheck=False, skipchecksum=False, skipinteg=False,
                noconfirm=False, force=False, ignorearch=False, immutable=True):
    for package in packages:
        if not force and package.isinstalled(container):
            continue
        git.syncremote(package.pkgbuild.remotename)
        if package.pkgbuild.build(force, skippgpcheck, skipchecksum, skipinteg, noconfirm, ignorearch) is False:
            log.logger.error(f"Error building {package}")
            return False
        artifact = package.pkgbuild.getartifact(package)
        pacmancmd = ["sudo", "pacman", "-U", artifact]
        kwargs = {}
        if noconfirm:
            pacmancmd.append("--noconfirm")
        if container.name != "native":
            kwargs["immutable"] = immutable
        if not container.run_interactive(*pacmancmd, **kwargs):
            log.logger.error(f"Error installing {artifact}")
            return False
    return True


def needsinstall(container, packages, repo=None, no_repo=None, agrfirst=None, noconfirm=None):
    agr_installs = []
    sys_installs = []
    for package in packages:
        # check if already installed
        if package.isinstalled(container, True):
            continue
        # select install candidates
        if not package.pkgbuild:
            package = select_alts(container, package, repo, no_repo, agrfirst, noconfirm)
        if package:
            pkgb = package.pkgbuild
            if pkgb:
                if package.compare and not pkgb.version.compare(package.compare, package.version):
                    log.logger.error(f"Can not find package {package} with version{package.compare}{package.version}")
                    return
                if package not in agr_installs:
                    agr_installs.append(package)
            elif package not in sys_installs:
                sys_installs.append(package)
    return agr_installs, sys_installs


def filterpkgs(container, pkg=None, repo=None, no_pkg=None, no_repo=None, agrfirst=False, noconfirm=False):
    packages = getpackages(container, pkg or defs.FILTER_ALL, repo or defs.FILTER_ALL, no_repo=no_repo or defs.FILTER_NONE)
    no_packages = getpackages(container, no_pkg or defs.FILTER_NONE, repo or defs.FILTER_ALL, no_repo=no_repo or defs.FILTER_NONE)
    if pkg or no_pkg or repo or no_repo:
        pkgbs = []
        for make in [True, False]:
            bases, deps = resolvepkgs(container, packages, no_packages, repo, no_repo, agrfirst, noconfirm, make)
            for pkgb in set(bases + deps):
                if pkgb.pkgbuild and pkgb.pkgbuild not in pkgbs:
                    pkgbs.append(pkgb.pkgbuild)
    else:
        pkgbs = allpkgbuilds(container)
    return pkgbs, packages, no_packages


def resolvepkgs(container, packages, no_packages=None, repo=None, no_repo=None, agrfirst=False, noconfirm=False, make=False):
    # get all packages in allowed repos with all its dependencies
    deps = []
    bases = []
    alternatives = {}
    for package in packages:
        pkgnames = []
        for base in package.pkgbuild.pkgname:
            if base not in bases and base not in no_packages:
                pkgnames.append(base)
        bases.extend(pkgnames)
        for pkgdep in getdeps(container, pkgnames, no_packages, repo, no_repo, agrfirst, noconfirm, make, alternatives=alternatives):
            if pkgdep not in deps:
                deps.append(pkgdep)

    for dep in reversed(deps):
        if dep in bases:
            bases.insert(0, bases.pop(bases.index(dep)))

    return bases, deps
