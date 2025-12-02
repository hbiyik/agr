'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import re
import time
import hashlib

from libagr import cache
from libagr import defs
from libagr import git
from libagr import log
from libagr import version
from libagr import cmd


SHELL_ISDYNAMIC = "echo \"$(type -t pkgver)\""
with open("/usr/share/makepkg/srcinfo.sh", "r") as f:
    SHELL_SRCINFO = "\n" + f.read()
SHELL_SRCINFO += "\nwrite_srcinfo"
SHELL_MAKEDEPS = 'echo "${makedepends[*]}"'


def foldername(path):
    path = os.path.realpath(path)
    if path.endswith("/"):
        path = path[:-1]
    if path.endswith(".git"):
        path = path[:-4]
    return os.path.split(path)[-1]


class PkgNotInSync(Exception):
    pass


class PkgNotBuilt(Exception):
    pass


class PkgNotExists(Exception):
    pass


class Package:
    def __init__(self, pkgstring, pkgbuild=None):
        self.pkgname = pkgstring
        self.compare = None
        self.version = None
        self.pkgbuild = pkgbuild
        if "gitweb-dlagent" in pkgstring:
            pass
        for delim in [defs.COMP_GE, defs.COMP_LE, defs.COMP_G, defs.COMP_L, defs.COMP_EQ]:
            if delim in pkgstring:
                dependsplit = pkgstring.split(delim)
                self.pkgname = dependsplit[0].strip()
                self.version = version.Version(dependsplit[1].strip())
                self.compare = delim
                break

    @staticmethod
    def fnameparse(fname):
        fname = os.path.basename(fname)
        parts = fname.split("-")
        if len(parts) < 4:
            return None, None, None
        pkgrel = parts[-2]
        if not pkgrel.isdigit():
            return None, None, None
        pkgrel = int(pkgrel)
        pkgver = parts[-3].replace(":", ".")
        pkgname = "-".join(parts[:-3])
        return pkgname, pkgver, pkgrel

    def __eq__(self, other):
        if isinstance(other, str):
            return other == self.pkgname
        return self.pkgname == other.pkgname

    def __hash__(self):
        return hash(self.pkgname)

    def __repr__(self):
        if self.compare:
            return f"{self.pkgname}{self.compare}{self.version}"
        return self.pkgname

    def isinstalled(self, container, strict=False):
        syspkg = None
        for _syspkg in container.installed.get(self, []):
            if strict and not self.pkgname == _syspkg.pkgname:
                continue
            if strict and not self.compare:
                continue
            if strict and not _syspkg.version.compare(self.compare, self.version):
                continue
            syspkg = _syspkg
            break
        return syspkg

    def needsupdate(self, container):
        if container.name == defs.CONTAINER_NATIVE:
            syspkg = self.isinstalled(container)
            if syspkg and self.version.compare(defs.COMP_G, syspkg.version):
                return syspkg.version
        else:
            isbuilt = self.pkgbuild.hasartifact(self)
            if isbuilt and isbuilt.compare(defs.COMP_L, self.version):
                return isbuilt
        return None


class Pkgbuild:
    def __init__(self, container, rname, pkgpath):
        self.container = container
        self._srcinfo = None
        self._isdynamic = None
        self._pkgsrc = None
        self._artifacts = None
        self.isbroken = False
        self.remotename = rname
        self.pkgpath = pkgpath
        self.pkgfullpath = git.repopkgpath(self.remotename, self.pkgpath)
        self.refname = foldername(self.pkgfullpath)
        self.srcpath = os.path.join(defs.SRC_PATH, self.remotename, self.refname)
        self.buildpath = os.path.join(defs.BUILD_PATH, self.container.name, self.remotename)
        self.distpath = os.path.join(defs.DIST_PATH, self.container.name, self.remotename)
        self.cachepath = os.path.join(defs.CACHE_PATH, self.remotename)
        self.srcinfo_path = os.path.join(self.cachepath, f"{self.refname}{defs.SRCINFO}")
        self.epoch = None
        self._pkgrel = 1
        self.pkgver = None
        self.pkgbase = None
        self.pkgdesc = None
        self.forcebuilt = False
        self.pkgname = []
        self.pkgnames = []
        self.arch = []
        self.depends = {}
        self.makedepends = []
        self.optdepends = {}
        self.provides = {}
        self.env = defs.ENV_GIT.copy()
        self.env["SRCDEST"] = self.srcpath
        self.env["SRCPKGDEST"] = self.srcpath
        self.env["PKGDEST"] = self.distpath
        self.env["BUILDDIR"] = self.buildpath
        for p in [self.srcpath, self.buildpath, self.distpath, self.cachepath]:
            os.makedirs(p, exist_ok=True)
        self.parse()

    @property
    def pkgrel(self):
        return self._pkgrel

    @pkgrel.setter
    def pkgrel(self, value):
        with open(os.path.join(self.pkgfullpath, "PKGBUILD"), "r") as f:
            pkgsource = f.read()
        new_pkgsource = re.sub(r"\npkgrel\=.+?", f"\npkgrel={value}", pkgsource)
        if new_pkgsource == pkgsource:
            new_pkgsource += f"\npkgrel={value}"
        with open(os.path.join(self.pkgfullpath, "PKGBUILD"), "w") as f:
            f.write(new_pkgsource)
        log.logger.info("pkgrel is bumped form %s to %s for %s",
                        self._pkgrel,
                        value,
                        self)
        self.gensrcinfo()
        self._pkgrel = value

    def __repr__(self):
        return f"{self.remotename}: {self.refname}"

    def parse(self):
        self.pkgname = []
        self.pkgnames = []
        self.makedepends = []
        self.arch = []
        self.depends = {}
        self.provides = {}
        self.optdepends = {}

        self._artifacts = None

        boolkeys = ["isbroken", "isdynamic"]
        strkeys = ["epoch", "pkgver", "pkgbase"]
        listkeys = ["pkgname", "makedepends", "arch"]
        dictkeys = ["depends", "provides", "optdepends"]

        curpkg = None
        for k, v in self.itersrcinfo():
            if k in boolkeys:
                setattr(self, k, v == "true")
            if k in ["pkgbase", "pkgname"]:
                curpkg = Package(v, self)
            if k in strkeys:
                if k == "pkgbase":
                    v = Package(v, self)
                setattr(self, k, v)
            if k in "pkgrel":
                self._pkgrel = int(v)
            if k in listkeys:
                attr = getattr(self, k)
                if v not in attr:
                    attr.append(Package(v))
            if k in dictkeys:
                attr = getattr(self, k)
                if curpkg not in attr:
                    attr[curpkg] = []
                if v not in attr[curpkg]:
                    if ":" in v:
                        v = v.split(":")[0]
                    attr[curpkg].append(Package(v))

        # collect all possible package name this pkgbuild provides under pkgnames
        for pkg in self.pkgname:
            if pkg not in self.pkgnames:
                self.pkgnames.append(pkg)

        for k, v in self.provides.items():
            for provide in v:
                if provide not in self.pkgnames:
                    self.pkgnames.append(provide)

        # use the pkgrel of latest built artifacts pkgrel
        for fname in os.listdir(self.distpath):
            pkgname, pkgver, pkgrel = Package.fnameparse(fname)
            if pkgname is None:
                continue
            if pkgname not in self.pkgname:
                continue
            if not self.pkgver == pkgver:
                continue
            if pkgrel > self.pkgrel:
                self.pkgrel = pkgrel

        for attr in [self.pkgname, self.pkgnames]:
            for pkg in attr:
                if not pkg.version:
                    pkg.compare = defs.COMP_EQ
                    pkg.version = self.version
                pkg.pkgbuild = self

        # inherit the versions from pkgver if not already given
        if self.pkgbase:
            self.pkgbase.compare = defs.COMP_EQ
            self.pkgbase.version = self.version
            self.pkgbase.pkgbuild = self

    def itersrcinfo(self):
        if self.srcinfo:
            for line in self.srcinfo.split("\n"):
                splits = line.split(" = ")
                if len(splits) == 2:
                    k, v = splits
                    yield k.strip(), v.strip()

    @property
    def artifacts(self):
        if self._artifacts is None:
            self._artifacts = []
            for package in self.pkgname:
                self._artifacts.append(self.getartifact(package, False))
        return self._artifacts

    @property
    def pkgsrc(self):
        if self._pkgsrc is None:
            fpath = os.path.join(self.pkgfullpath, defs.PKGBUILD)
            log.logger.debug(f"Read srcinfo {fpath}")
            with open(fpath) as f:
                self._pkgsrc = f.read()
        return self._pkgsrc

    @property
    def isdynamic(self):
        if self._isdynamic is None:
            log.logger.debug(f"Interpret isdynamic {self}")
            self._isdynamic = cmd.run_stdout("bash", "-c", self.pkgsrc + "\n" + SHELL_ISDYNAMIC,
                                                cwd=os.path.dirname(self.pkgfullpath), env=self.env) != ""
        return self._isdynamic

    @isdynamic.setter
    def isdynamic(self, val):
        self._isdynamic = val

    def gensrcinfo(self):
        log.logger.debug(f"Interpret srcinfo {self}")
        self._srcinfo = cmd.run_stdout("bash", "-c", self.pkgsrc + "\n" + SHELL_SRCINFO,
                                          cwd=os.path.dirname(self.pkgfullpath), env=self.env)
        self._srcinfo += f"\nisbroken = {'true' if self.isbroken else ''}"
        self._srcinfo += f"\nisdynamic = {'true' if self.isdynamic else ''}"

    def sync(self, skipinteg=False, skippgpcheck=False, download=True):
        # if dynamic, sync pkg sources, we can never know the correct pkgver otherwise
        if self.isdynamic:
            t1 = time.time()
            log.logger.info(f"Started downloading sources of {self.refname}")
            try:
                if download:
                    cmd = ["makepkg", "-o", "-d", "-A", "--noprepare"]
                    if skipinteg:
                        cmd.append("--skipinteg")
                    if skippgpcheck:
                        cmd.append("--skippgpcheck")
                    self.container.run_interactive(*cmd, cwd=self.pkgfullpath, env=self.env)
                    deltat = time.time() - t1
                    log.logger.info(f"Finished downloading sources of {self.refname} in {deltat:.2f} seconds")
                # update the pkbuild source
                with open(os.path.join(self.pkgfullpath, defs.PKGBUILD)) as f:
                    self._pkgsrc = f.read()
                self._srcinfo = None
            except OSError:
                log.logger.warning(f"Error in {self} check {defs.PKGBUILD}")
                self.isbroken = True

        pkghash_path = os.path.join(self.cachepath, f"{self.refname}{defs.PKGHASH}")
        pkghash = None
        actual_pkghash = hashlib.md5(self.pkgsrc.encode()).hexdigest()

        # read the cached pkghash
        if os.path.exists(pkghash_path):
            with open(pkghash_path, "r") as f:
                pkghash = f.read()
                log.logger.debug(f"Read pkg hash {pkghash_path}")

        # if cache is not valid regenerate srcinfo and cache it
        if not download or os.path.exists(self.srcinfo_path) or pkghash != actual_pkghash:
            log.logger.info(f"Syncing {self.srcinfo_path}")
            # generate srcinfo
            if not self._srcinfo:
                self.gensrcinfo()

            # cache srcinfo
            with open(self.srcinfo_path, "w") as f:
                log.logger.debug(f"Write srcinfo {self.srcinfo_path}")
                f.write(self._srcinfo)

            # cache pkghash
            with open(pkghash_path, "w") as f:
                log.logger.debug(f"Write pkghash {pkghash_path}")
                f.write(actual_pkghash)

    @property
    def srcinfo(self):
        if not self._srcinfo:
            if os.path.exists(self.srcinfo_path):
                with open(self.srcinfo_path, "r") as f:
                    log.logger.debug(f"Read srcinfo {self.srcinfo_path}")
                    self._srcinfo = f.read()
            else:
                pass
        return self._srcinfo

    @property
    def version(self):
        vers = ""
        if self.epoch:
            vers = f"{self.epoch}:"
        vers += self.pkgver
        if self.pkgrel:
            vers += f"-{self.pkgrel}"
        return version.Version(vers)

    def getpackage(self, pkgname):
        for pkg in self.pkgname:
            if pkgname == pkg:
                return pkg
        if pkgname in self.pkgnames:
            for pkg, provides in self.provides.items():
                for provide in provides:
                    if provide == pkgname:
                        return pkg

    def build(self, force=False, skippgpcheck=False, skipchecksum=False, skipinteg=False, noconfirm=False, ignorearch=False):
        hasall = True
        self._pkgsrc = None
        for artifact in self.artifacts:
            if not os.path.exists(os.path.join(self.distpath, artifact)):
                hasall = False

        if force and not self.forcebuilt:
            self.forcebuilt = True
        else:
            force = False

        if force:
            # do this only once for split packages
            cmd.run_stdout("rm", "-rf", os.path.join(self.buildpath, self.refname, ""))
            cmd.run_stdout("rm", "-rf", os.path.join(self.srcpath, ""))
        elif hasall:
            return
        else:
            # remove existing artifacts since all artifacts will be rebuilt
            for fname in os.listdir(self.distpath):
                pkgname, _, _ = Package.fnameparse(fname)
                if not pkgname:
                    continue
                if pkgname in self.pkgname:
                    cmd.run_stdout("rm", os.path.join(self.distpath, fname))

        # parse makepkg flags
        args = []
        if skippgpcheck:
            args.append(f"--skippgpcheck")
        if skipchecksum:
            args.append(f"--skipchecksum")
        if skipinteg:
            args.append(f"--skipinteg")
        if noconfirm:
            args.append(f"--noconfirm")
        if force:
            args.append(f"--force")
        if ignorearch:
            args.append(f"--ignorearch")

        retval = self.container.run_interactive("makepkg", "-s", *args, cwd=self.pkgfullpath, env=self.env)
        # remove unwanted chars from the artifact name
        for package in self.pkgname:
            artifact_orig = self.getartifact(package, False)
            if not artifact_orig:
                raise RuntimeError(f"{package} is not in {self.pkgname}")
            if not os.path.exists(artifact_orig):
                raise RuntimeError(f"Newly built artifact {artifact_orig} is not found")
            artifact_new = self.getartifact(package, False, True)
            if not artifact_orig == artifact_new:
                self.container.run_stdout("mv", "-f", artifact_orig, artifact_new)
        self.sync(skipinteg, skippgpcheck, False)
        self.parse()
        return retval

    def hasartifact(self, package):
        latest = None
        for fname in os.listdir(self.distpath):
            segments = fname.split("-")
            if len(segments) > 1 and fname.endswith(self.container.pkgext):
                name = "-".join(segments[:-1])
                arch = segments[-1].split(".")
                if arch:
                    arch = arch[0]
                    if name.startswith(package.pkgname) and arch in ["any", self.container.cont_arch]:
                        vers = name[len(package.pkgname) + 1:]
                        if not vers.startswith("debug-"):
                            newvers = version.Version(vers)
                            if not latest:
                                latest = newvers
                            elif newvers.compare(defs.COMP_G, latest):
                                latest = newvers
        return latest

    def latestbuild(self, package):
        artifact_ver = None
        artifact = None
        for fname in os.listdir(self.distpath):
            pkgname, pkgver, pkgrel = Package.fnameparse(fname)
            if not pkgname == package.pkgname:
                continue
            fname = os.path.join(self.distpath, fname)
            ver = version.Version(f"{pkgver}.{pkgrel}")
            if not artifact_ver or ver.compare(defs.COMP_GE, artifact_ver):
                artifact = fname
                artifact_ver = ver

        return artifact

    def getartifact(self, package, checkexists=True, filterchars=True):
        if package.pkgname not in self.pkgname:
            return

        if "any" in self.arch:
            arch = "any"
        else:
            arch = self.container.cont_arch

        artifact = f"{package.pkgname}-{self.version}-{arch}{self.container.pkgext}"
        artifact = os.path.join(self.distpath, artifact)
        if filterchars:
            for c in [":"]:
                artifact = artifact.replace(c, ".")
        if not checkexists or os.path.exists(artifact):
            return artifact

    def install(self, *packages, noconfirm=False):
        installs = []

        # build / install with actual name
        for package in packages:
            if package not in self.pkgname:
                raise PkgNotExists(f"Pkgbuild has no package {package}")

        # check the artifacts that needs to be installed
        for artifact in self.artifacts:
            # all artifacts
            if not packages and self.version in artifact:
                installs.append(artifact)
                continue
            # specific artifacts
            for package in packages:
                if artifact.startswith(f"{package}-{self.version}"):
                    installs.append(artifact)
                    break

        # check if built
        for install in installs:
            if not os.path.exists(os.path.join(self.distpath, install)):
                raise PkgNotBuilt(f"{install} not yet built in {self.refname}")

        # parse pacman flags
        if noconfirm:
            installs.append(f"--noconfirm")

        # install with pacman
        return self.container.run_interactive("sudo", "pacman", "-U", *installs, cwd=self.distpath)

    def dlagents(self):
        dlagents = []
        for dlagent in [x for x in self.makedepends if x.pkgname.endswith("-dlagent")]:
            if dlagent not in dlagents:
                dlagents.append(dlagent)
        return dlagents


@cache.Cache.runonce
def getpkgbuild(container, rname, pkgpath):
    try:
        return Pkgbuild(container, rname, pkgpath)
    except Exception:
        log.logger.warning(f"Error in {rname} {pkgpath} check {defs.PKGBUILD}")
