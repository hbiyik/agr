#!/usr/bin/python

import argparse
import sys
import logging

from libagr import config
from libagr import defs
from libagr import repo
from libagr import log

CMD_REM = "rem"
CMD_REM_SET = "set"
CMD_REM_DEL = "del"
CMD_REM_LIST = "list"
CMD_LIST = "list"
CMD_INSTALL = "install"
CMD_UPDATE = "update"
CMD_STATUS = "status"

cfg = config.Config()


def logpkgstate(pkgb, pkgname, versions, issub):
    retval = "  +- " if issub else ""
    retval += pkgname
    isins, sysver = pkgb.checkinstall(pkgname)
    retval += f", installed: {isins}"
    if versions and not issub:
        retval += f", version: {pkgb.version}"
        if isins:
            retval += f", system: {sysver}"
            if pkgb.version.segments != sysver.segments:
                retval += f", needsupdate"
    return retval


def status(detailed=False):
    with log.Report() as report:
        for rname, remote, branch in cfg.iterremotes():
            report.log(f"Repository: {rname}")
            for pkgb in repo.iterpkgs(remote, branch):
                report.log(logpkgstate(pkgb, pkgb.pkgbase, detailed, False))
                if pkgb.pkgnames:
                    for pkgname in pkgb.pkgnames:
                        if pkgname != pkgb.pkgbase:
                            report.log(logpkgstate(pkgb, pkgname, detailed, True))


def installpkgs(report, *packages, **kwargs):
    built_pkgs = []
    pkgnames = []
    for pkgname in packages:
        pkgrealname = repo.haspkg(pkgname)
        if not pkgrealname:
            log.logger.error(f"Can not find package {pkgname}")
            return
        else:
            pkgnames.append(pkgrealname)
            log.logger.info(f"Found package {pkgrealname}")
    deps = list(repo.getdeps(*packages))
    deps.reverse()
    for pkgb, pkgname, compare, version in deps:
        pkgver = pkgb.version
        skip = False
        isins, sysver = pkgb.checkinstall(pkgname)
        if pkgname not in pkgnames:
            if isins and ((compare and sysver.compare(compare, version)) or compare is None):
                skip = True
            if compare and pkgver.compare(compare, version):
                log.logger.error(f"Can not find package with version{compare}{version.version}")
                return
        if skip:
            report.log(f"Skipped {pkgname} installed: {sysver.version} pkgver: {pkgver.version}")
            log.logger.info(f"Skipped {pkgname} installed: {sysver.version} pkgver: {pkgver.version}")
        else:
            if pkgb not in built_pkgs:
                if not pkgb.install(**kwargs):
                    log.logger.error(f"Error installing {pkgname}:{pkgb.version.version}")
                    return
                else:
                    report.log(f"Installed {pkgname}:{pkgb.version.version}")
                built_pkgs.append(pkgb)


def main():
    parser = argparse.ArgumentParser(description='AGR (Archlinux Git Repositories)')
    parser.add_argument("-d", "--debug", required=False, action="store_true",
                        help="debug logging")
    parser.add_argument("-v", "--version", required=False, action="store_true",
                        help="debug logging")
    cmd = parser.add_subparsers(dest="cmd", required=False)

    _status_p = cmd.add_parser(CMD_STATUS, help="Show current status of the packages available")

    rem_p = cmd.add_parser(CMD_REM, help="edit, remove, list remote agr repositories")
    cmd_rem = rem_p.add_subparsers(dest="cmd_rem", required=True)

    rem_set_p = cmd_rem.add_parser(CMD_REM_SET, help="Add or update a remote")
    rem_set_p.add_argument("name", help="user defined name of the remote repository")
    rem_set_p.add_argument("uri", help="git compatible uri of the remote repo")
    rem_set_p.add_argument("--branch", default=defs.DEF_BRANCH, required=False,
                           help="use specific branch of the remote repository")

    rem_del_p = cmd_rem.add_parser(CMD_REM_DEL, help="Delete a remote")
    rem_del_p.add_argument("name", help="name of the repository to delete")

    _rem_list_p = cmd_rem.add_parser(CMD_REM_LIST, help="List active list of remote repositories")

    install_p = cmd.add_parser(CMD_INSTALL, help="Install packages")
    update_p = cmd.add_parser(CMD_UPDATE, help="Update packages")
    update_p.add_argument("--ignore", required=False, metavar="pkg1,pkg2,..",
                          help="list of comma seperated packages to ignore")
    install_p.add_argument('pkgname', nargs='+', help="list of packages to install")
    for p in [install_p, update_p]:
        p.add_argument("-f", "--force", required=False, action="store_true",
                       help="force rebuild of the package")
        p.add_argument("-A", "--ignorearch", required=False, action="store_true",
                       help="Ignore the arch field in PKGBUILD")
        p.add_argument("--skipchecksums", required=False, action="store_true",
                       help="Do not verify checksums of the source files")
        p.add_argument("--skipinteg", required=False, action="store_true",
                       help="Do not perform any verification checks on source files")
        p.add_argument("--skippgpcheck", required=False, action="store_true",
                       help="Do not verify source files with PGP signatures")
        p.add_argument("--noconfirm", required=False, action="store_true",
                       help="Do not ask for confirmation when resolving dependencies")

    args = parser.parse_args(sys.argv[1:])

    if args.debug:
        log.setlevel(logging.DEBUG)
    elif args.version:
        log.logger.info(f"version: {defs.VERSION}")
        return
    log.logger.debug(args)

    if args.cmd == CMD_REM:
        if args.cmd_rem == CMD_REM_SET:
            cfg.setremote(args.name, args.uri, args.branch)
        if args.cmd_rem == CMD_REM_DEL:
            cfg.delremote(args.name)
        if args.cmd_rem == CMD_REM_LIST:
            for name, remote, branch in cfg.iterremotes():
                print(name, remote, branch)
    elif args.cmd == CMD_INSTALL:
        with log.Report() as report:
            installpkgs(report, *args.pkgname, force=args.force, ignorearch=args.ignorearch,
                        skipchecksums=args.skipchecksums, skipinteg=args.skipinteg,
                        skippgpcheck=args.skippgpcheck, noconfirm=args.noconfirm)
    elif args.cmd == CMD_UPDATE:
        with log.Report() as report:
            updates = []
            if args.ignore is not None:
                ignores = [x.strip() for x in args.ignore.split(",")]
            ignores = []
            for _rname, remote, branch in cfg.iterremotes():
                for pkgb in repo.iterpkgs(remote, branch):
                    if pkgb.pkgbase in ignores:
                        continue
                    isins, sysver = pkgb.checkinstall(pkgb.pkgbase)
                    if isins and pkgb.version.segments != sysver.segments and pkgb.pkgbase not in updates:
                        report.log(f"Updating {pkgb.pkgbase}: {sysver.version} -> {pkgb.version.version}")
                        updates.append(pkgb.pkgbase)
            installpkgs(report, *updates, force=args.force, ignorearch=args.ignorearch,
                        skipchecksums=args.skipchecksums, skipinteg=args.skipinteg,
                        skippgpcheck=args.skippgpcheck, noconfirm=args.noconfirm)
    elif args.cmd == CMD_STATUS:
        status(True)
    else:
        status()


if __name__ == "__main__":
    main()
