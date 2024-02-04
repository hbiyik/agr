'''
Created on Jan 30, 2024

@author: boogie
'''
import os

from libagr import cmd
from libagr import defs
from libagr import git
from libagr import log
from libagr import version

# TODO: Manually parse more instead of interpreting srcinfo for better speed
SHELL_PKGBASE = "echo ${pkgbase}"
SHELL_PKGNAME = "echo ${pkgname[*]}"
SHELL_PKGVER = "echo ${pkgver}"
SHELL_DYNAMIC = "echo $(type -t pkgver)"


def get_system_packages():
    packages = cmd.stdout("pacman", "-Q")
    system_packages = {}
    for package in packages.split("\n"):
        pkg, ver = package.split(" ")
        system_packages[pkg] = version.Version(ver)
    return system_packages


class Pkgbuild:
    system_packages = get_system_packages()
    cache_srcinfo = {}
    cache_download = {}

    def __init__(self, remote, pkgpath):
        self.remote = remote
        self.pkgpath = git.repopkgpath(remote, pkgpath)
        self._workpath = None
        self.system_packages = {}

    def hascache(self, cache_type, key):
        cache = getattr(Pkgbuild, f"cache_{cache_type}")
        return key in cache

    def makecache(self, cache_type, key, value):
        cache = getattr(Pkgbuild, f"cache_{cache_type}")
        cache[key] = value

    def getcache(self, cache_type, key):
        cache = getattr(Pkgbuild, f"cache_{cache_type}")
        return cache[key]

    def delcache(self, cache_type, key):
        cache = getattr(Pkgbuild, f"cache_{cache_type}")
        return cache.pop(key)

    def isdnynamicver(self):
        return cmd.source_stdout("PKGBUILD", SHELL_DYNAMIC, cwd=self.pkgpath) == "function"

    @property
    def workpath(self):
        if self._workpath is None:
            self._workpath = os.path.join(defs.PKG_PATH, self.pkgbase)
            if not os.path.exists(self._workpath):
                os.makedirs(self._workpath)
            git.syncworking(self.remote, self.pkgpath, self._workpath)
        return self._workpath

    @property
    def srcinfo(self):
        if not self.hascache("srcinfo", self.pkgpath):
            log.logger.info(f"Getting SRCINFO of {git.reponame(self.pkgpath)}")
            self.makecache("srcinfo", self.pkgpath, cmd.stdout("makepkg", "--printsrcinfo", cwd=self.workpath))
        return self.getcache("srcinfo", self.pkgpath)

    def itersrcinfo(self):
        for line in self.srcinfo.split("\n"):
            splits = line.split(" = ")
            if len(splits) == 2:
                k, v = splits
                yield k.strip(), v.strip()

    def getsources(self):
        if not self.hascache("download", self.workpath):
            log.logger.info(f"Updating sources of {git.reponame(self.pkgpath)}")
            if cmd.interactive("makepkg", "-o", "-d", "-A", cwd=self.workpath):
                self.makecache("download", self.workpath, True)
        return self.getcache("download", self.workpath)

    def srcinfo_keys(self, key):
        for k, v in self.itersrcinfo():
            if k == key:
                yield v

    @property
    def pkgver(self):
        if self.isdnynamicver():
            if not self.hascache("download", self.workpath) and self.hascache("srcinfo", self.pkgpath):
                self.delcache("srcinfo", self.pkgpath)
            if self.getsources() is None:
                return None
        return self.srcinfo_keys("pkgver").__next__()

    @property
    def pkgrel(self):
        rel = list(self.srcinfo_keys("pkgrel"))
        if len(rel) > 0:
            return rel[0]

    @property
    def epoch(self):
        rel = list(self.srcinfo_keys("epoch"))
        if len(rel) > 0:
            return rel[0]

    @property
    def version(self):
        vers = ""
        epoch = self.epoch
        pkgrel = self.pkgrel
        pkgver = self.pkgver
        if self.epoch:
            vers = f"{epoch}:"
        vers += pkgver
        if pkgrel:
            vers += f"-{pkgrel}"
        return version.Version(vers)

    @property
    def pkgbase(self):
        base = cmd.source_stdout("PKGBUILD", SHELL_PKGBASE, cwd=self.pkgpath)
        if base == "":
            return self.pkgnames[0]
        else:
            return base

    @property
    def pkgnames(self):
        return cmd.source_stdout("PKGBUILD", SHELL_PKGNAME, cwd=self.pkgpath).split(" ")

    def checkinstall(self, pkgname=None):
        pkgname = pkgname or self.pkgbase
        if pkgname in Pkgbuild.system_packages:
            return True, Pkgbuild.system_packages[pkgname]
        else:
            return False, None

    def haspkg(self, pkgname):
        if(pkgname == self.pkgbase):
            return pkgname
        subpkgname = self.pkgbase
        for k, v in self.itersrcinfo():
            if k == "pkgname":
                if pkgname == v:
                    return pkgname
                subpkgname = v
            if k == "provides" and v.split("=")[0] == pkgname:
                return subpkgname

    def deps(self, pkgname):
        depends = []
        if pkgname == self.pkgbase:
            for k, v in self.itersrcinfo():
                if k == "pkgname":
                    break
                if k == "depends":
                    depends.append(v)
        subpkg = None
        if not depends:
            for k, v in self.itersrcinfo():
                if k == "pkgname" and v == pkgname:
                    subpkg = v
                if k == "depends" and subpkg:
                    depends.append(v)

        deps = []
        for depend in depends:
            delim = None
            dependsplit = []
            for delim in [">=", "<=", ">", "<", "=", None]:
                if not delim:
                    break
                if delim in depend:
                    dependsplit = depend.split(delim)
                    break
            depname = depend
            vers = None
            if delim:
                depname = dependsplit[0]
                vers = version.Version(dependsplit[1])
            deps.append([depname, delim, vers])
        return deps

    def install(self, **kwargs):
        args = []
        for k, v in kwargs.items():
            if v:
                args.append(f"--{k}")
        return cmd.interactive("makepkg", "-s", "-i", *args, cwd=self.workpath)
