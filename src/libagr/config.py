'''
Created on Jan 30, 2024

@author: boogie
'''
import json
import os
import re
from libagr import defs
from libagr import cmd
from libagr import log

KEY_REMOTES = "remotes"
KEY_CONTAINER = "container"


class Config:
    def __init__(self):
        self.cfg = None
        self.load()
        if not self.cfg.get(KEY_REMOTES):
            self.cfg[KEY_REMOTES] = {}
        if not self.cfg.get(KEY_CONTAINER):
            self.cfg[KEY_CONTAINER] = None

    def load(self):
        if os.path.exists(defs.CFG_PATH):
            with open(defs.CFG_PATH, "r") as f:
                self.cfg = json.load(f)
        else:
            self.cfg = {}

    def save(self):
        with open(defs.CFG_PATH, "w") as f:
            self.cfg = json.dump(self.cfg, f)

    def getremote(self, name):
        return self.cfg[KEY_REMOTES].get(name, (None, None))

    def iterremotes(self):
        for name in self.cfg[KEY_REMOTES]:
            yield name

    def setremote(self, name, remote, branch=defs.DEF_BRANCH):
        if not branch:
            match = re.search(r"ref\:\s*?(.+?)\s*?HEAD", cmd.run_stdout("git", "ls-remote", "--symref", remote, "HEAD", env=defs.ENV_GIT), re.DOTALL)
            if match:
                branch = match.group(1).strip().split("/")[-1].strip()
        if not branch:
            log.logger.error(f"Can not get branch for {remote}, please check url or define --branch")
            return
        self.cfg[KEY_REMOTES][name] = (remote, branch)
        self.save()

    def delremote(self, name):
        if name in self.cfg[KEY_REMOTES]:
            self.cfg[KEY_REMOTES].pop(name)
        self.save()

    def setcontainer(self, name):
        self.cfg[KEY_CONTAINER] = name
        self.save()

    def getcontainer(self):
        return self.cfg.get(KEY_CONTAINER)


CFG = Config()
