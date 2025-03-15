'''
Created on Jan 30, 2024

@author: boogie
'''
import os
from multiprocessing import pool
from libagr import config
from libagr import defs
from libagr import git
from libagr import log
from libagr import pkgbuild
from libagr import cache


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
        pkgb.parse()

    with pool.ThreadPool(defs.NUMCORES) as p:
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
            msgs.append(f"AGR: ({len(found_agr_deps)})")
        if len(found_sys_deps):
            msgs.append(f"PACMAN({len(found_sys_deps)})")
        log.logger.info(f"Found " + " ".join(msgs) + f" candidates for package '{package.pkgname}'")
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
            deps.extend(subdeps)
    deps.reverse()
    return deps


def buildpkgs(container, packages, no_packages=None, repo=None, no_repo=None, agrfirst=False, skippgpcheck=False,
              skipchecksum=False, skipinteg=False, noconfirm=False, force=False, ignorearch=False):
    packages_filtered = []

    # don't rebuild packages if already exists unless forced
    for package in packages:
        git.syncremote(package.pkgbuild.remotename)
        if package.pkgbuild:
            artifact = package.pkgbuild.getartifact(package)
            if artifact and not force:
                log.logger.info(f"already built, {artifact}")
                continue
        packages_filtered.append(package)
    # make depends
    base_packages, dep_packages = resolvepkgs(container, packages_filtered, no_packages, repo, no_repo, agrfirst, noconfirm, True)
    # depends
    bases, deps = resolvepkgs(container, packages_filtered, no_packages, repo, no_repo, agrfirst, noconfirm, False)
    for base in bases:
        if base not in base_packages:
            base_packages.append(base)
    for dep in deps:
        if dep not in dep_packages:
            dep_packages.append(dep)

    agr_installs, _sys_installs = needsinstall(container, dep_packages, repo=repo, no_repo=no_repo, agrfirst=agrfirst, noconfirm=noconfirm)
    if agr_installs:
        log.logger.info(f"Installing {agr_installs}")
    if not installpkgs(container, agr_installs, skippgpcheck, skipchecksum, skipinteg, noconfirm, force, ignorearch):
        return False
    for base_package in base_packages:
        if base_package.pkgbuild.build(force, skippgpcheck, skipchecksum, skipinteg, noconfirm, ignorearch) is False:
            log.logger.error(f"Error building {base_package}")
            return False
    return packages


def installpkgs(container, packages, skippgpcheck=False, skipchecksum=False, skipinteg=False,
                noconfirm=False, force=False, ignorearch=False, immutable=True):
    for package in packages:
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
            if pkgbuild:
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
    if packages or no_packages or repo or no_repo:
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

    return bases, deps
