"""
 Copyright (C) 2025 boogie

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import os

from libagr import elf
from libagr import log
from libagr import cmd

DEP_OK = 0
DEP_NEW = -1
DEP_OLD = -2
DEP_NA = -3


def checkpkg(pkgpath):
    _provides, deps = elf.finddeplibs(pkgpath)
    syslibs = list(elf.findsystemlibs())
    older = None
    newer = None
    notfound = None
    basepath = os.path.basename(pkgpath)
    for dep in deps:
        if dep in syslibs:
            log.logger.debug("dep library %s is found for %s",
                             syslibs[syslibs.index(dep)].fullpath,
                             basepath)
            continue

        found = False
        for syslib in syslibs:
            if syslib > dep:
                log.logger.warning("Dep library %s required by %s is older than system library %s for %s",
                                   dep, dep.neededby, syslib.path, basepath)
                older = DEP_OLD
                found = True
                break
            elif syslib < dep:
                log.logger.warning("Dep library %s required by %s is newer than system library %s for %s",
                                   dep, dep.neededby, syslib.path, basepath)
                newer = DEP_NEW
                found = True
                break

        if not found:
            log.logger.warning("dep library %s required by %s is not found for %s", dep, dep.neededby, basepath)
            notfound = DEP_NA

    retval = older or newer or notfound or DEP_OK
    if retval == DEP_OK:
        log.logger.info("No dependency issue is found for %s", basepath)
    return retval


def syncsysdeps(container, package, noconfirm=False, agrinstalls=None):
    agrpkgs = []
    for agrpkg in agrinstalls or []:
        agrpkgs.extend(agrpkg.pkgbuild.pkgnames)
    sysinstalls = []
    packages = package.pkgbuild.provides.get(package, [])
    if package not in packages:
        packages.append(package)
    for package in packages:
        if not package.pkgbuild:
            continue
        for dep in package.pkgbuild.depends.get(package, []):
            if dep in agrpkgs:
                continue
            if dep not in sysinstalls and not dep.isinstalled(container):
                sysinstalls.append(dep.pkgname)
    if not sysinstalls:
        return
    pacmancmd = ["sudo", "pacman", "-S", "--needed"] + sysinstalls
    if noconfirm:
        pacmancmd.append("--noconfirm")
    if not container.run_interactive(*pacmancmd):
        log.logger.error(f"Error installing dependencies")
        return


def suggestdeps(pkgpath):
    # just all packages not top-levels
    packages = []
    _provides, deps = elf.finddeplibs(pkgpath)
    paths = list(elf.lddirs())
    for dep in deps:
        for path in paths:
            try:
                package = cmd.run_stdout("pacman", "-Qoq", os.path.join(path, dep.path))
            except Exception:
                continue
            if package not in packages:
                packages.append(package)
            break
    return packages
