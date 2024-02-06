'''
Created on Jan 30, 2024

@author: boogie
'''
import os

BASE_PATH = os.path.join(os.path.expanduser('~'), ".agr")
REPO_PATH = os.path.join(BASE_PATH, "gitrepos")
PKG_PATH = os.path.join(BASE_PATH, "packages")
CFG_PATH = os.path.join(BASE_PATH, "config.json")
VERSION = "0.0.4"

DEF_BRANCH = "master"
IGNORE_FLAG = ".agrignore"

DIRS = [REPO_PATH, PKG_PATH]
ENV = os.environ.copy()

for d in DIRS:
    if not os.path.exists(d):
        os.makedirs(d)
