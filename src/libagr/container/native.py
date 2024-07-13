'''
Created on May 8, 2024

@author: boogie
'''
import argparse
import os

from libagr import pkgbuild
from libagr import config
from libagr import repo as agrrepo
from libagr import log
from libagr import defs
from libagr import git
from libagr import clean
from libagr.container import common

from libagr import cmd as agrcmd


class SplitArgs(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values:
            values = [x.strip() for x in values.split(",")]
        else:
            values = None
        setattr(namespace, self.dest, values)


class Native:
    name = "native"
    host_archs = None
    cont_arch = os.uname()[4]
    makepkgconf_path = "/etc/makepkg.conf"
    packages = ["sudo", "base-devel", "git"]
    env = os.environ.copy()
    installed = {}

    def __init__(self):
        self.installed = self.parsepacman(self.run_stdout("pacman", "-Qi"))
        self.available = self.parsepacman(self.run_stdout("pacman", "-Si"), 1)
        self.checkpkgs(self.installed)
        self._update = False
        self._pkgext = None

    def __repr__(self):
        return self.name

    @property
    def pkgext(self):
        if self._pkgext is None:
            with open(self.makepkgconf_path, "r") as f:
                src = f.read()
            src += "\nprintf $PKGEXT"
            self._pkgext = agrcmd.run_stdout("bash", "-c", src)
        return self._pkgext

    @classmethod
    def config_commands(cls, parser):
        cmd = parser.add_subparsers(dest="cmd", required=False)

        rem_p = cmd.add_parser(defs.CMD_REM, help="edit, remove, list remote agr repositories")
        cmd_rem = rem_p.add_subparsers(dest="cmd_rem", required=True)

        rem_set_p = cmd_rem.add_parser(defs.CMD_REM_SET, help="Add or update a remote")
        rem_set_p.add_argument("name", help="user defined name of the remote repository")
        rem_set_p.add_argument("uri", help="git compatible uri of the remote repo")
        rem_set_p.add_argument("--branch", default=defs.DEF_BRANCH, required=False,
                               help="use specific branch of the remote repository")

        rem_del_p = cmd_rem.add_parser(defs.CMD_REM_DEL, help="Delete a remote")
        rem_del_p.add_argument("name", help="name of the repository to delete")

        _rem_list_p = cmd_rem.add_parser(defs.CMD_REM_LIST, help="List active list of remote repositories")

        sync_p = cmd.add_parser(defs.CMD_CONT_SYNC, help="Synchronize remotes, packages and containers")
        update_p = cmd.add_parser(defs.CMD_UPDATE, help="Update packages")
        build_p = cmd.add_parser(defs.CMD_BUILD, help="Build packages")

        for p in [build_p, update_p]:
            p.add_argument("-f", "--force", required=False, action="store_true",
                           help=f"Force rebuild the package")

        build_p.add_argument('pkgname', nargs='+', help=f"list of packages to build")

        parsers = [sync_p, build_p, update_p]
        if cls.name == "native":
            install_p = cmd.add_parser(defs.CMD_INSTALL, help="Install packages")
            install_p.add_argument('pkgname', nargs='+', help="list of packages to build")
            parsers.append(install_p)

        for p in [sync_p, update_p]:
            p.add_argument("--pkg", required=False, metavar="pkg1,pkg2,..", action=SplitArgs,
                           help="limit to the only list of comma seperated packages")
            p.add_argument("--no-pkg", required=False, metavar="pkg1,pkg2,..", action=SplitArgs,
                           help="ignore the comma seperated list of pkgs")

        for p in parsers:
            p.add_argument("-A", "--ignorearch", required=False, action="store_true",
                           help=f"Ignore the arch field in {defs.PKGBUILD}")
            p.add_argument("--skipinteg", required=False, action="store_true",
                           help="Do not perform any verification checks on source files")
            p.add_argument("--skippgpcheck", required=False, action="store_true",
                           help="Do not verify source files with PGP signatures")
            p.add_argument("--skipchecksum", required=False, action="store_true",
                           help="Do not verify checksums of the source files")
            p.add_argument("--noconfirm", required=False, action="store_true",
                           help="Do not ask for confirmation when resolving dependencies")
            p.add_argument("--agrfirst", required=False, action="store_true",
                           help="Prefer the agr packages over pacman packages")
            p.add_argument("--repo", required=False, metavar="reponame1,reponame2,..", action=SplitArgs,
                           help="limit to the only list of comma seperated repos")
            p.add_argument("--no-repo", required=False, metavar="reponame1,reponame2,..", action=SplitArgs,
                           help="ignore the comma seperated list of pkgs")

        update_p.add_argument("--agr", required=False, action="store_true", help="update the agr tool itself")

        cont_p = cmd.add_parser(defs.CMD_CONT, help="list, set, get, create containers")
        cmd_cont = cont_p.add_subparsers(dest="cmd_cont", required=True)
        cmd_cont.add_parser(defs.CMD_CONT_LIST, help="List available containers")
        cmd_cont.add_parser(defs.CMD_CONT_GET, help="Get active container")
        set_p = cmd_cont.add_parser(defs.CMD_CONT_SET, help="Set active container")
        set_p.add_argument("name", help="name of the container")
        return cmd

    def argstokwargs(self, args, *keys):
        kwargs = {}
        for k in ["pkg", "repo", "no_pkg", "no_repo"]:
            if k in keys:
                val = getattr(args, k)
                kwargs[k] = None if val is None else val.split(",")
        for f in ["ignorearch", "skipinteg", "skippgpcheck", "force", "agr", "noconfirm"]:
            if f in keys:
                kwargs[f] = getattr(args, f)
        return kwargs

    def cmd_rem(self, report, cmd_rem, name=None, uri=None, branch=None):
        if cmd_rem == defs.CMD_REM_SET:
            config.CFG.setremote(name, uri, branch)
        elif cmd_rem == defs.CMD_REM_DEL:
            config.CFG.delremote(name)
        elif cmd_rem == defs.CMD_REM_LIST:
            for rname in config.CFG.iterremotes():
                # TODO: Print description
                report.log(f"{rname}: {config.CFG.getremote(rname)}")

    def cmd_build(self, report, pkgname=None, repo=None, no_repo=None, agrfirst=False,
                  skipinteg=False, skippgpcheck=False, skipchecksum=False,
                  noconfirm=False, ignorearch=False, force=False):
        self.update(noconfirm)
        _, packages, no_packages = agrrepo.filterpkgs(self, pkgname, repo, defs.FILTER_NONE, no_repo, agrfirst, noconfirm)
        return agrrepo.buildpkgs(self, packages, no_packages, repo, no_repo, agrfirst, skippgpcheck, skipchecksum, skipinteg, noconfirm, ignorearch=ignorearch, force=force)

    def cmd_install(self, report, pkgname=None, repo=None, no_repo=None, agrfirst=False,
                    skipinteg=False, skippgpcheck=False, skipchecksum=False,
                    noconfirm=False, ignorearch=False):
        packages = self.cmd_build(report, pkgname, repo, no_repo, agrfirst, skipinteg, skippgpcheck, skipchecksum, noconfirm, ignorearch)
        return agrrepo.installpkgs(self, packages, skippgpcheck, skipchecksum, skipinteg, noconfirm, False, ignorearch)

    def cmd_update(self, report, pkg=None, repo=None, no_pkg=None, no_repo=None, agrfirst=False,
                   skipinteg=False, skipchecksum=False, skippgpcheck=False,
                   noconfirm=False, ignorearch=False, agr=False, force=False):
        if agr:
            retval = agrcmd.run_interactive("python", "-m", "pip", "install", "https://github.com/hbiyik/agr/archive/master.zip",
                                            "--break-system-packages", "--force-reinstall")
            agrcmd.run_interactive("python", "-m", "agr", "--version")
            return retval

        pkgbs, _, no_packages = agrrepo.filterpkgs(self, pkg, repo, no_pkg, no_repo, agrfirst, noconfirm)

        updates = []
        for pkgb in pkgbs:
            for package in pkgb.pkgname:
                if package not in updates:
                    needsupdate = package.needsupdate(self)
                    if needsupdate:
                        report.log(f"Update: {package.pkgname} {needsupdate}->{package.version}", True)
                        updates.append(package)

        packages = agrrepo.buildpkgs(self, updates, no_packages, repo, no_repo, agrfirst, skippgpcheck, skipchecksum, skipinteg, noconfirm, force, ignorearch)
        if self.name == "native":
            return agrrepo.installpkgs(self, packages, skippgpcheck, skipchecksum, skipinteg, noconfirm, False, ignorearch)
        else:
            return True

    def cmd_sync(self, report, pkg=None, repo=None, no_pkg=None, no_repo=None, agrfirst=False,
                 skipinteg=False, skipchecksum=False, skippgpcheck=False,
                 noconfirm=False, ignorearch=False):
        clean.clean()
        self.update(noconfirm)

        # sync remote git repos
        for remote in config.CFG.iterremotes():
            if (no_repo is None or remote not in no_repo) and (repo is None or remote in repo):
                git.syncremote(remote)

        # TO-DO: handle all default dlagents
        # get necessary dlagents to sync dynmic packages
        # this stage indirectly sycs static packages therefore cpu bound
        agrrepo.tempsync(agrrepo.allpkgbuilds(self))

        pkgbs, _, _ = agrrepo.filterpkgs(self, pkg, repo, no_pkg, no_repo, agrfirst, noconfirm)

        dlagents = []
        for pkgb in pkgbs:
            agr_installs, sys_installs = agrrepo.needsinstall(self, pkgb.dlagents(), repo, no_repo, agrfirst, noconfirm)
            if sys_installs:
                raise pkgbuild.PkgNotExists(f"You need to install {sys_installs} from pacman to continue")
            for dlagent in agr_installs:
                if dlagent not in dlagents:
                    dlagents.append(dlagent)

        if dlagents:
            agrrepo.installpkgs(self, dlagents, skippgpcheck, skipchecksum, skipinteg, noconfirm, False, ignorearch, immutable=False)

        # this stage only syncs the dynamic packages, therefore IO/Net bound
        for pkgb in pkgbs:
            try:
                pkgb.sync(skipinteg, skippgpcheck)
                if pkgb.isbroken:
                    self.report.log(f"Failed to sync {pkgb}")
                else:
                    self.report.log(f"Synced {pkgb}")
            except Exception:
                log.logger.warning(f"Error syncing {pkgb.refname} check {defs.PKGBUILD}")
                self.report.log(f"Failed to sync {pkgb}")
        # in case remote repo folder structure changes
        clean.clean()

    def cmd_container(self, report, cmd_cont, name=None):
        if cmd_cont == defs.CMD_CONT_LIST:
            for cont in common.iter_containers():
                report.log(f"Container: name({cont.name}), host({cont.host_archs}), target: ({cont.cont_arch})")
            return True
        elif cmd_cont == defs.CMD_CONT_GET:
            cont = common.get_container()
            report.log(f"Active Container: name({cont.name}), host({cont.host_archs}), target: ({cont.cont_arch})")
            return True
        elif cmd_cont == defs.CMD_CONT_SET:
            common.set_container(name)
            return True

    def exec_commands(self, report, args):
        log.logger.debug(args)
        self.report = report
        kwargs = vars(args)
        cmd = kwargs.pop("cmd")
        _debug = kwargs.pop("debug")
        _version = kwargs.pop("version")
        if cmd:
            getattr(self, f"cmd_{cmd}")(report, **kwargs)
            return True

    def logpkgstate(self, report, pkgb):
        for package in pkgb.pkgname:
            syspkg = package.isinstalled(self)
            tags = []
            builtver = pkgb.hasartifact(package)
            needsupdate = package.needsupdate(self)
            if syspkg:
                version = syspkg.version
            elif builtver:
                version = builtver
            else:
                version = pkgb.version
            tags.append("[U]" if needsupdate else "   ")
            tags.append("[B]" if builtver else "   ")
            tags.append("[I]" if syspkg else "   ")

            retval = "".join(tags)
            retval = f"{retval:<10}"
            retval += package.pkgname
            retval += f", version: {version.version}"
            if needsupdate:
                retval += f" -> {pkgb.version}"
            report.log(retval)

    def status(self, report):
        self.installed
        self.available
        self.pkgext
        for rname in config.CFG.iterremotes():
            header = f"Repository: {rname}: {config.CFG.getremote(rname)}"
            report.log("")
            report.log(header)
            report.log("-" * len(header))
            # with pool.ThreadPool(defs.NUMCORES) as p:
            #    p.starmap(self.logpkgstate, [(report, x) for x in agrrepo.allpkgbuilds(self, rname) if not x.isbroken])
            for pkgb in agrrepo.allpkgbuilds(self, rname):
                self.logpkgstate(report, pkgb)
        report.log("")
        report.log("[B] = Built")
        report.log("[I] = Installed")
        report.log("[U] = Needs Update")
        report.log("")

    def process_args(self, *cmd, **kwargs):
        return cmd, kwargs

    def update(self, noconfirm=False):
        pass

    def checkpkgs(self, installed):
        notinstalled = []
        for pkg in self.packages:
            if pkg not in installed:
                notinstalled.append(pkg)
        if notinstalled:
            msg = f"Please install {' '.join(notinstalled)} packages to use container {self.name}"
            log.logger.error(msg)
            raise(RuntimeError(msg))

    def parsepacman(self, pacman, offset=0):
        installed = {}
        index = 0
        for line in pacman.split("\n"):
            matches = line.split(" : ")
            if matches and len(matches) == 2:
                index += 1
                if index == 1 + offset:
                    pkgname = matches[1].strip()
                elif index == 2 + offset:
                    vers = matches[1].strip()
                elif index == 8 + offset:
                    provides = matches[1].strip()
                elif index > 8 + offset:
                    continue
            elif line == "":
                index = 0
                if not provides[0].isupper():
                    provideslist = [pkgbuild.Package(x) for x in provides.split(" ") if x != ""]
                else:
                    provideslist = []
                pkg = pkgbuild.Package(f"{pkgname}={vers}")
                if pkg not in provideslist:
                    provideslist.append(pkg)
                for provide in provideslist:
                    if provide not in installed:
                        installed[provide] = [pkg]
                    if pkg not in installed[provide]:
                        installed[provide].append(pkg)
        return installed.copy()

    def run_interactive(self, *cmd, **kwargs):
        return agrcmd.run_interactive(*cmd, **kwargs)

    def run_stdout(self, *cmd, **kwargs):
        return agrcmd.run_stdout(*cmd, **kwargs)
