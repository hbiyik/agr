'''
Created on May 6, 2024

@author: boogie
'''
import os
from libagr import defs
from libagr import repo
from libagr import git
from libagr import pkgbuild
from libagr.log import logger
from libagr.config import CFG
from libagr.container import common
from libagr import cmd as agrcmd


def iter_path(basepath, expected=None, sudo=False):
    if os.path.exists(basepath):
        for fname in os.listdir(basepath):
            path = os.path.join(basepath, fname)
            if expected and fname not in expected:
                logger.info(f"Cleaning {path}")
                cmd = []
                if sudo:
                    cmd.append("sudo")
                cmd.extend(["rm", "-rf", path])
                agrcmd.run_interactive(*cmd)
                continue
            yield fname


def iter_base_path():
    for fname in iter_path(defs.BASE_PATH, defs.PATHNAMES):
        yield fname


def iter_container_path(basepath):
    for fname in iter_path(basepath, [x.name for x in common.iter_containers()], True):
        yield fname


def iter_remote_path(basepath):
    for fname in iter_path(basepath, list(CFG.iterremotes())):
        yield fname


def iter_pkg_path(basepath, remotename):
    pkgs = []
    for pkgpath in repo.iterpkgpaths(remotename):
        pkgs.append(pkgbuild.foldername(git.repopkgpath(remotename, pkgpath)))
    for fname in iter_path(basepath, pkgs):
        yield fname


def clean_containers():
    for root in iter_base_path():
        if root == defs.CONT_PATH_NAME:
            for _cont in iter_container_path(os.path.join(defs.BASE_PATH, root)):
                pass


def clean_builds():
    for root in iter_base_path():
        if root == defs.BUILD_PATH_NAME:
            for cont in iter_container_path(os.path.join(defs.BASE_PATH, root)):
                for remote in iter_remote_path(os.path.join(defs.BASE_PATH, root, cont)):
                    for pkg in iter_pkg_path(os.path.join(defs.BASE_PATH, root, cont, remote), remote):
                        for _artifact in iter_path(os.path.join(defs.BASE_PATH, root, cont, remote, pkg), ["src", "pkg"]):
                            pass


def clean_caches():
    for root in iter_base_path():
        if root == defs.CACHE_PATH_NAME:
            for remote in iter_remote_path(os.path.join(defs.BASE_PATH, root)):
                pkgs = []
                for pkgpath in repo.iterpkgpaths(remote):
                    pkgs.append(pkgbuild.foldername(git.repopkgpath(remote, pkgpath)))
                basepath = os.path.join(defs.BASE_PATH, root, remote)
                for cachefile in iter_path(basepath):
                    fnames = cachefile.split(".")
                    if fnames:
                        fname = ".".join(fnames[:-1])
                        ext = "." + fnames[-1]
                        if fname in pkgs and ext in [defs.PKGHASH, defs.SRCINFO]:
                            continue
                    path = os.path.join(basepath, cachefile)
                    logger.info(f"Cleaning {path}")
                    agrcmd.run_interactive("rm", "-rf", path)


def clean_remotes():
    for root in iter_base_path():
        if root == defs.REPO_PATH_NAME:
            for _remote in iter_remote_path(os.path.join(defs.BASE_PATH, root)):
                pass


def clean_sources():
    for root in iter_base_path():
        if root == defs.SRC_PATH_NAME:
            for remote in iter_remote_path(os.path.join(defs.BASE_PATH, root)):
                for _pkg in iter_pkg_path(os.path.join(defs.BASE_PATH, root, remote), remote):
                    pass


def clean_dist():
    for root in iter_base_path():
        if root == defs.DIST_PATH_NAME:
            for cont in iter_container_path(os.path.join(defs.BASE_PATH, root)):
                for remote in iter_remote_path(os.path.join(defs.BASE_PATH, root, cont)):
                    for artifact in os.listdir(os.path.join(defs.BASE_PATH, root, cont, remote)):
                        path = os.path.join(os.path.join(defs.BASE_PATH, root, cont, remote, artifact))
                        if os.path.isdir(path):
                            logger.info(f"Cleaning {path}")
                            agrcmd.run_interactive("rm", "-rf", path)


def clean():
    clean_containers()
    clean_builds()
    clean_caches()
    clean_remotes()
    clean_sources()
    clean_dist()
