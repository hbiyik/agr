#!/usr/bin/python
import argparse
import logging

from libagr import log
from libagr import defs
from libagr import elf
from libagr.container import common


REMOTE_DBG = None

if REMOTE_DBG:
    import pydevd  # @UnresolvedImport
    pydevd.settrace(REMOTE_DBG, stdoutToServer=True, stderrToServer=True, suspend=True)


def main():
    with log.Report() as report:
        parser = argparse.ArgumentParser(description='AGR (Archlinux Git Repositories)')
        parser.add_argument("-d", "--debug", required=False, action="store_true",
                            help="debug logging")
        parser.add_argument("-v", "--version", required=False, action="store_true",
                            help="print version")
        cont = common.get_container()
        arch = ""
        if cont.name == defs.CONTAINER_NATIVE:
            arch = str(elf.PROC.arch)
            if common.ishostqemu():
                arch += f"-qemu"
        log.logger.info(f"Running in container {cont.name} {arch}")
        cont.config_commands(parser)
        args = parser.parse_args()
        if args.debug:
            log.setlevel(logging.DEBUG)
        elif args.version:
            report.log(f"version: {defs.VERSION}")
            return

        c = cont()
        if(not c.exec_commands(report, args)):
            c.status(report)


if __name__ == "__main__":
    main()
