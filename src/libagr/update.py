'''
Created on Jan 30, 2024

@author: boogie
'''

from libagr import cmd
from libagr import repo
from libagr import log


def updateagr():
    cmd.interactive("python", "-m", "pip", "install", "https://github.com/hbiyik/agr/archive/master.zip",
                    "--break-system-packages", "--force-reinstall")
    cmd.interactive("python", "-m", "agr", "--version")


def pkgstoupdate(*ignores):
    updates = []
    for pkgb in repo.allpkgbuilds():
        skip = False
        for ignore in ignores:
            if pkgb.pkgrealname(ignore):
                log.logger.info(f"Ignoring {pkgb.pkgbase}")
                skip = True
                break
        if skip:
            continue
        for pkg in pkgb.pkgname:
            syspkg = repo.checkinstall(pkg)
            if syspkg and pkg not in updates:
                if pkgb.isdynamic:
                    if repo.installdlagents(pkgb):
                        pkgb.sync()
                    else:
                        raise Exception("Can not continue, there is an error sycing the package")
                if pkgb.version.segments != syspkg.version.segments and pkgb.pkgbase not in updates:
                    log.logger.info(f"Updating {pkg}: {syspkg.version.version} -> {pkgb.version.version}")
                    updates.append(pkg)
    return updates
