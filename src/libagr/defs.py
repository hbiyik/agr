'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import multiprocessing

BASE_PATH = os.path.join(os.path.expanduser('~'), ".agr")
REPO_PATH = os.path.join(BASE_PATH, "gitrepos")
PKG_PATH = os.path.join(BASE_PATH, "packages")
CACHE_PATH = os.path.join(BASE_PATH, "cache")
CFG_PATH = os.path.join(BASE_PATH, "config.json")
VERSION = "0.0.5"
SRCINFO = ".SRCINFO"
PKGBUILD = "PKGBUILD"

DEF_BRANCH = "master"
IGNORE_FLAG = ".agrignore"

COMP_GE = ">="
COMP_G = ">"
COMP_LE = "<="
COMP_L = "<"
COMP_EQ = "="

VERSION_SEPS = [":", "-"]

UNCACHED = -1

DIRS = [REPO_PATH, PKG_PATH, CACHE_PATH]
ENV = os.environ.copy()
ENV_GITNOSTDIN = os.environ.copy()
ENV_GITNOSTDIN["GIT_TERMINAL_PROMPT"] = "0"


NUMCORES = multiprocessing.cpu_count()

for d in DIRS:
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
