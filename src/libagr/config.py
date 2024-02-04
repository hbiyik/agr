'''
Created on Jan 30, 2024

@author: boogie
'''
import json
import os
from libagr import defs

KEY_REMOTES = "remotes"


class Config:
    def __init__(self):
        self.cfg = None
        self.load()
        if not self.cfg.get(KEY_REMOTES):
            self.cfg[KEY_REMOTES] = {}

    def load(self):
        if os.path.exists(defs.CFG_PATH):
            with open(defs.CFG_PATH, "r") as f:
                self.cfg = json.load(f)
        else:
            self.cfg = {}

    def save(self):
        with open(defs.CFG_PATH, "w") as f:
            self.cfg = json.dump(self.cfg, f)

    def iterremotes(self):
        for name, (remote, branch) in self.cfg[KEY_REMOTES].items():
            yield name, remote, branch

    def setremote(self, name, remote, branch=defs.DEF_BRANCH):
        self.cfg[KEY_REMOTES][name] = (remote, branch)
        self.save()

    def delremote(self, name):
        if name in self.cfg[KEY_REMOTES]:
            self.cfg[KEY_REMOTES].pop(name)
        self.save()
