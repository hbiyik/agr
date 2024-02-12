#!/usr/bin/python

import argparse
import logging

from libagr import defs
from libagr import repo
from libagr import log
from libagr import multi
from libagr import config
from libagr import update


CMD_REM = "rem"
CMD_REM_SET = "set"
CMD_REM_DEL = "del"
CMD_REM_LIST = "list"
CMD_LIST = "list"
CMD_INSTALL = "install"
CMD_UPDATE = "update"


def logpkgstate(pkgb):
    logs = []
    for pkgname in pkgb.pkgname:
        syspkg = repo.checkinstall(pkgname)
        retval = "[I] " if syspkg else "    "
        retval += pkgname
        version = pkgb.version
        if version:
            retval += f", version: {version.version}"
        if syspkg and not (version and version.segments == syspkg.version.segments):
            retval += f", installed: {syspkg.version}"
        if syspkg and version and version.segments != syspkg.version.segments:
            retval = f"[U]{retval[3:]}"
        logs.append(retval)
    return logs


def status(report):
    for rname, remote, _branch in config.CFG.iterremotes():
        header = f"Repository: {rname} : {remote}"
        report.log("")
        report.log("    " + header)
        report.log("    " + "-" * len(header))
        pman = multi.ProcMan(numworkers=defs.NUMCORES * 2, waittime=0)
        for pkgb in repo.allpkgbuilds(remote=remote):
            if isinstance(pkgb, Exception):
                continue
            pman.add(logpkgstate, pkgb)
        pman.join()
        for loglines, _args, _kwargs in pman.returns.values():
            for logline in loglines:
                report.log(logline)
    report.log("")
    report.log("[I] = Installed")
    report.log("[U] = Needs Update")
    report.log("")


def main():
    parser = argparse.ArgumentParser(description='AGR (Archlinux Git Repositories)')
    parser.add_argument("-d", "--debug", required=False, action="store_true",
                        help="debug logging")
    parser.add_argument("-v", "--version", required=False, action="store_true",
                        help="debug logging")

    cmd = parser.add_subparsers(dest="cmd", required=False)

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
    update_p.add_argument("--agr", required=False, action="store_true",
                          help="update the agr tool itself")
    install_p.add_argument('pkgname', nargs='+', help="list of packages to install")
    for p in [install_p, update_p]:
        p.add_argument("-f", "--force", required=False, action="store_true",
                       help=f"Force rebuild the package")
        p.add_argument("-A", "--ignorearch", required=False, action="store_true",
                       help=f"Ignore the arch field in {defs.PKGBUILD}")
        p.add_argument("--skipchecksums", required=False, action="store_true",
                       help="Do not verify checksums of the source files")
        p.add_argument("--skipinteg", required=False, action="store_true",
                       help="Do not perform any verification checks on source files")
        p.add_argument("--skippgpcheck", required=False, action="store_true",
                       help="Do not verify source files with PGP signatures")
        p.add_argument("--noconfirm", required=False, action="store_true",
                       help="Do not ask for confirmation when resolving dependencies")

    args = parser.parse_args()
    with log.Report() as report:
        if args.debug:
            log.setlevel(logging.DEBUG)
        elif args.version:
            report.log(f"version: {defs.VERSION}")
            return
        log.logger.debug(args)

        if args.cmd == CMD_REM:
            if args.cmd_rem == CMD_REM_SET:
                config.CFG.setremote(args.name, args.uri, args.branch)
            if args.cmd_rem == CMD_REM_DEL:
                config.CFG.delremote(args.name)
            if args.cmd_rem == CMD_REM_LIST:
                for name, remote, branch in config.CFG.iterremotes():
                    report.log(f"{name}:{remote}:{branch}")
        elif args.cmd == CMD_INSTALL:
            for line in repo.installpkgs(*args.pkgname, ignorearch=args.ignorearch,
                                         skipchecksums=args.skipchecksums, skipinteg=args.skipinteg,
                                         skippgpcheck=args.skippgpcheck, noconfirm=args.noconfirm,
                                         force=args.force):
                report.log(line)
        elif args.cmd == CMD_UPDATE:
            if args.agr:
                update.updateagr()
                report.log(f"Agr updated")
                return
            ignores = []
            if args.ignore is not None:
                ignores = [x.strip() for x in args.ignore.split(",")]
            for line in repo.installpkgs(*update.pkgstoupdate(*ignores), ignorearch=args.ignorearch,
                                         skipchecksums=args.skipchecksums, skipinteg=args.skipinteg,
                                         skippgpcheck=args.skippgpcheck, noconfirm=args.noconfirm,
                                         force=args.force):
                report.log(line)
        else:
            status(report)


if __name__ == "__main__":
    main()
