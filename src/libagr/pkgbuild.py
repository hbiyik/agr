'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import time

from libagr import cache
from libagr import cmd
from libagr import defs
from libagr import git
from libagr import log
from libagr import version
from libagr import config


SHELL_ISDYNAMIC = "\necho \"isdynamic = $(type -t pkgver)\""
with open("/usr/share/makepkg/srcinfo.sh", "r") as f:
    SHELL_SRCINFO = "\n" + f.read()
SHELL_SRCINFO += "\nwrite_srcinfo"
SHELL_SRCINFO += SHELL_ISDYNAMIC


class Dependency:
    def __init__(self, pkgstring):
        self.pkgname = pkgstring
        self.compare = None
        self.version = None
        for delim in [defs.COMP_GE, defs.COMP_LE, defs.COMP_G, defs.COMP_L, defs.COMP_EQ]:
            if delim in pkgstring:
                dependsplit = pkgstring.split(delim)
                self.pkgname = dependsplit[0].strip()
                self.version = version.Version(dependsplit[1].strip())
                self.compare = delim
                break

    def __eq__(self, other):
        return self.pkgname == other.pkgname


class Pkgbuild:
    def __init__(self, remote, pkgpath):
        self._srcinfo = None
        self.remote = remote
        self.pkgpath = pkgpath
        self.pkgfullpath = git.repopkgpath(remote, self.pkgpath)
        self.reponame = git.reponame(self.pkgfullpath)
        self.workpath = os.path.join(defs.PKG_PATH, self.reponame)
        self.epoch = None
        self.pkgrel = None
        self.pkgver = None
        self.pkgbase = None
        self.pkgdesc = None
        self.pkgname = []
        self.pkgnames = []
        self.depends = {}
        self.makedepends = []
        self.optdepends = {}
        self.provides = {}
        self.isdynamic = False
        self.remotename = None
        self.commit = git.getcommit(git.repopath(self.remote), self.pkgpath)
        for rname, rpath, _branch in config.CFG.iterremotes():
            if rpath == self.remote:
                self.remotename = rname
                break
        self.islocal = os.path.exists(self.srcinfo_path())
        self.parse()

    def parse(self):
        self.pkgname = []
        self.pkgnames = []
        self.depends = {}
        self.makedepends = []
        self.optdepends = {}
        self.provides = {}

        boolkeys = ["isdynamic"]
        strkeys = ["epoch", "pkgrel", "pkgver", "pkgbase"]
        listkeys = ["pkgname", "makedepends"]
        dictkeys = ["depends", "provides", "optdepends"]

        curpkgname = None
        for k, v in self.itersrcinfo():
            if k == "pkgbase" or k == "pkgname":
                curpkgname = v
            for boolkey in boolkeys:
                if k == boolkey:
                    setattr(self, boolkey, v != "")
                    break
            for strkey in strkeys:
                if k == strkey:
                    setattr(self, strkey, v)
                    break
            for listkey in listkeys:
                if k == listkey:
                    attr = getattr(self, listkey)
                    val = Dependency(v) if "depends" in listkey else v
                    if val not in attr:
                        attr.append(val)
            for dictkey in dictkeys:
                if k == dictkey:
                    attr = getattr(self, dictkey)
                    if curpkgname not in attr:
                        attr[curpkgname] = []
                    val = Dependency(v) if "depend" in dictkey else Dependency(v).pkgname
                    if val not in attr[curpkgname]:
                        attr[curpkgname].append(val)

        # collect all possible package name this pkgbuild provides under pkgnames
        for k, v in self.provides.items():
            for provide in v:
                if provide not in self.pkgnames:
                    self.pkgnames.append(provide)

        for pkg in self.pkgname:
            if pkg not in self.pkgnames:
                self.pkgnames.append(pkg)

    def itersrcinfo(self):
        for line in self.srcinfo.split("\n"):
            splits = line.split(" = ")
            if len(splits) == 2:
                k, v = splits
                yield k.strip(), v.strip()

    @cache.Cache.runonce
    def sync(self):
        git.syncworking(self.remote, self.pkgfullpath, self.workpath)
        self.islocal = True
        if self.isdynamic:
            t1 = time.time()
            log.logger.info(f"Started downloading sources of {self.reponame}")
            cmd.interactive("makepkg", "-o", "-d", "-A", cwd=self.workpath, env=defs.ENV_GITNOSTDIN)
            deltat = time.time() - t1
            log.logger.info(f"Finished downloading sources of {self.reponame} in {deltat:.2f} seconds")
            _srcinfo = self.srcinfo_cache()
            self._srcinfo = self.makesrcinfo(self.pkgbuild_path(), self.srcinfo_path())
        self.parse()

    def srcinfo_path(self, islocal=True):
        srcinfo_dir = os.path.join(defs.CACHE_PATH, self.remotename, self.pkgpath, "local" if islocal else "remote")
        srcinfo_name = f"{self.commit}{defs.SRCINFO}"
        return os.path.join(srcinfo_dir, srcinfo_name)

    def pkgbuild_path(self, islocal=True):
        return os.path.join(self.workpath if islocal else self.pkgfullpath, defs.PKGBUILD)

    def srcinfo_cache(self, islocal=True):
        srcinfo_path = self.srcinfo_path(islocal)
        srcinfo_dir = os.path.dirname(srcinfo_path)
        srcinfo_name = os.path.basename(srcinfo_path)
        os.makedirs(srcinfo_dir, exist_ok=True)
        srcinfo = None
        for fname in os.listdir(srcinfo_dir):
            fpath = os.path.join(srcinfo_dir, fname)
            if fname == srcinfo_name:
                with open(fpath, "r") as f:
                    srcinfo = f.read()
            else:
                # remove unused cache
                os.remove(fpath)
        return srcinfo

    def makesrcinfo(self, pkgbuild_path, srcinfo_path):
        # generate srcinfo
        with open(pkgbuild_path, "r") as f:
            src_pkgbuild = f.read()
        shell_script = src_pkgbuild + SHELL_SRCINFO
        srcinfo = cmd.stdout("bash", "-c", shell_script, cwd=os.path.dirname(pkgbuild_path))
        # cache srcinfo
        with open(srcinfo_path, "w") as f:
            f.write(srcinfo)
        return srcinfo

    @property
    def srcinfo(self):
        if not self._srcinfo:
            # check if cache exists
            srcinfo = self.srcinfo_cache(self.islocal)
            if srcinfo:
                self._srcinfo = srcinfo
            else:
                self._srcinfo = self.makesrcinfo(self.pkgbuild_path(self.islocal),
                                                 self.srcinfo_path(self.islocal))
        return self._srcinfo

    @property
    def version(self):
        if self.isdynamic and not self.islocal:
            return None
        vers = ""
        if self.epoch:
            vers = f"{self.epoch}:"
        vers += self.pkgver
        if self.pkgrel:
            vers += f"-{self.pkgrel}"
        return version.Version(vers)

    def pkgrealname(self, pkgname):
        if pkgname in self.pkgname:
            return pkgname
        if pkgname in self.pkgnames:
            for pkg, provides in self.provides.items():
                for provide in provides:
                    if provide == pkgname:
                        return pkg

    def install(self, *pkgs, **kwargs):
        installs = []

        self.sync()

        # build / install with actual name
        for pkg in pkgs:
            if pkg not in self.pkgname:
                raise RuntimeError(f"Pkgbuild has no package {pkg}")

        # parse makepkg flags
        args = []
        for k, v in kwargs.items():
            if v:
                args.append(f"--{k}")

        # check the artifacts that needs to be installed
        packages = cmd.stdout("makepkg", "--packagelist", *args, cwd=self.workpath)
        for package in [x.split("/")[-1] for x in packages.split("\n")]:
            if not pkgs and self.version in package:
                installs.append(package)
                continue
            for pkg in pkgs:
                if package.startswith(f"{pkg}-{self.version}"):
                    installs.append(package)
                    break

        # if all artifacts are available do not rebuild by default
        # if some exists and some dont, force rebuild
        hasall = True
        hassome = False
        for install in installs:
            # TO-DO: Check if pkgdestdir forced
            if not os.path.exists(os.path.join(self.workpath, install)):
                hasall = False
            else:
                hassome = True

        force = "--force" in args
        if not hasall or force:
            if hassome and not force:
                args.append("--force")
            build = cmd.interactive("makepkg", "-s", *args, cwd=self.workpath)
        else:
            build = True

        if build:
            # parse pacman flags from makepkg/agr flags
            pacmanflags = ["noconfirm"]
            for pacmanflag in pacmanflags:
                if pacmanflag in kwargs and kwargs[pacmanflag]:
                    installs.append(f"--{pacmanflag}")

            # install with pacman
            return cmd.interactive("sudo", "pacman", "-U", *installs, cwd=self.workpath)

    def dlagents(self):
        dlagents = []
        for dlagent in [x for x in self.makedepends if x.pkgname.endswith("-dlagent")]:
            if dlagent not in dlagents:
                dlagents.append(dlagent)
        return dlagents


@cache.Cache.runonce
def getpkgbuild(remote, pkgpath):
    return Pkgbuild(remote, pkgpath)
