'''
Created on Jan 30, 2024

@author: boogie
'''
import os
import multiprocessing
import platform


BASE_PATH = os.path.join(os.path.expanduser('~'), ".agr")
SRC_PATH_NAME = "sources"
DIST_PATH_NAME = "tarballs"
BUILD_PATH_NAME = "builds"
CONT_PATH_NAME = "containers"
REPO_PATH_NAME = "gitrepos"
CACHE_PATH_NAME = "caches"
CFG_PATH_NAME = "config.json"
SRC_PATH = os.path.join(BASE_PATH, SRC_PATH_NAME)
DIST_PATH = os.path.join(BASE_PATH, DIST_PATH_NAME)
BUILD_PATH = os.path.join(BASE_PATH, BUILD_PATH_NAME)
CONT_PATH = os.path.join(BASE_PATH, CONT_PATH_NAME)
REPO_PATH = os.path.join(BASE_PATH, REPO_PATH_NAME)
CACHE_PATH = os.path.join(BASE_PATH, CACHE_PATH_NAME)

CFG_PATH = os.path.join(BASE_PATH, CFG_PATH_NAME)
VERSION = "1.0.5"
SRCINFO = ".SRCINFO"
PKGBUILD = "PKGBUILD"
PKGHASH = ".PKGHASH"

DEF_BRANCH = None
IGNORE_FLAG = ".agrignore"

COMP_GE = ">="
COMP_G = ">"
COMP_LE = "<="
COMP_L = "<"
COMP_EQ = "="

VERSION_SEPS = [":", "-", "+", "_", "@"]

UNCACHED = -1

PATHNAMES = [SRC_PATH_NAME, DIST_PATH_NAME, CONT_PATH_NAME, BUILD_PATH_NAME, REPO_PATH_NAME, CACHE_PATH_NAME, CFG_PATH_NAME]
DIRS = [SRC_PATH, DIST_PATH, BUILD_PATH, CONT_PATH, REPO_PATH, CACHE_PATH]
SKIPENV = ["LD_PRELOAD"]
ENV = os.environ.copy()
for k in SKIPENV:
    if k in ENV:
        ENV.pop(k)
ENV_GIT = ENV.copy()
ENV_GIT["GIT_TERMINAL_PROMPT"] = "0"
# ENV_GIT["GIT_HTTP_CONNECT_TIMEOUT"] = "10"
# ENV_GIT["GIT_HTTP_LOW_SPEED_LIMIT"] = "10240"
ENV_GIT["GIT_HTTP_LOW_SPEED_TIME"] = "10"

FILTER_ALL = 1
FILTER_NONE = 2


NUMCORES = multiprocessing.cpu_count()

for d in DIRS:
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

ARCH_X86_64 = "x86_64"
ARCH_AARCH64 = "aarch64"
ARCH_ARMV7H = "armv7h"
ARCH_HOST = platform.uname()[4]

CMD_REM = "rem"
CMD_CONT_LIST = "list"
CMD_CONT = "container"
CMD_BUILD = "build"
CMD_INSTALL = "install"
CMD_UPDATE = "update"
CMD_REM_SET = "set"
CMD_REM_DEL = "del"
CMD_REM_LIST = "list"
CMD_CONT_SET = "set"
CMD_CONT_GET = "get"
CMD_CONT_LIST = "list"
CMD_CONT_SYNC = "sync"
CMD_CONT_WIPE = "wipe"
CMD_CONT_CREATE = "create"
CMD_CONT_EXEC = "exec"
CMD_CONT_MAINTAIN = "maintain"
