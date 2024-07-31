'''
Created on May 8, 2024

@author: boogie
'''
import argparse
import configparser
import io
import re
import os

from libagr.container import native
from libagr import cmd as agrcmd
from libagr import defs
from libagr import log


class Host(native.Native):
    cont_arch = defs.ARCH_HOST
    host_archs = [defs.ARCH_HOST]
    name = f"host-{cont_arch}"
    packages = native.Native.packages + ["arch-install-scripts", "systemd"]
    cppflags = []
    cflags = []
    cxxflags = []
    ldflags = []

    def __init__(self):
        self.checkpkgs(self.parsepacman(agrcmd.run_stdout("pacman", "-Qi")))
        # init dirs for container
        self.cont_path = os.path.join(defs.CONT_PATH, self.name)
        self.rootfs_path = os.path.join(self.cont_path, self.name)
        self.immutable_path = os.path.join(self.cont_path, "immutable")
        self.mutable_path = os.path.join(self.cont_path, "mutable")
        self.runner_path = os.path.join(self.cont_path, "autoexec.sh")
        self.pacmanconf_path = os.path.join(self.cont_path, "pacman.conf")
        self.pacstrapconf_path = os.path.join(self.cont_path, "pacstrap.conf")
        self.makepkgconf_path = os.path.join(self.cont_path, "makepkg.conf")
        self.sudoers_path = os.path.join(self.cont_path, "sudoall")
        os.makedirs(self.cont_path, exist_ok=True)  # create with logged in user
        agrcmd.run_interactive("sudo", "mkdir", "-p", self.rootfs_path)  # create with root
        self.immutables = ["/boot", "/etc", "/mnt", "/opt", "/root", "/srv", "/usr", "/var"]
        self.mutables = ["/var/cache/pacman"]
        mkdirs = []
        rms = []
        for immutable in self.immutables:
            mkdirs.append(f"{self.immutable_path}{immutable}")
            rms.append(f"{self.immutable_path}{immutable}/")
        for mutable in self.mutables:
            mkdirs.append(f"{self.mutable_path}{mutable}")
        agrcmd.run_interactive("sudo", "mkdir", "-p", *mkdirs)
        agrcmd.run_interactive("sudo", "rm", "-rf", *rms)
        self._installed = None
        self._available = None
        self._update = None
        self._env = None
        self._pkgext = None

    def update(self, noconfirm=False):
        if not self._update:
            pacmancmd = ["pacman", "-Syu"]
            if noconfirm:
                pacmancmd.append("--noconfirm")
            self.run_interactive(*pacmancmd, root=True, immutable=False)
            self._update = True

    @property
    def installed(self):
        if self._installed is None:
            self._installed = self.parsepacman(self.run_stdout("pacman", "-Qi"))
        return self._installed

    @property
    def available(self):
        if self._available is None:
            self._available = self.parsepacman(self.run_stdout("pacman", "-Si"), 1)
        return self._available

    @property
    def env(self):
        if self._env is None:
            self._env = {}
            try:
                envtxt = self.run_stdout("printenv")
                pass
            except OSError:
                envtxt = ""
                pass
            for envline in envtxt.split("\n"):
                splits = envline.split("=")
                if len(splits) > 2:
                    splits = [splits[0], "=".join(splits[1:])]
                if len(splits) == 2:
                    self._env[splits[0]] = splits[1]
            for k, v in native.Native.env.items():
                if k not in self.env:
                    self._env[k] = v
        return self._env.copy()

    def makepkgconf(self, actual):
        changes = {"CPPFLAGS": " ".join(self.cppflags) if self.cppflags else None,
                   "CFLAGS": " ".join(self.cflags) if self.cflags else None,
                   "CXXFLAGS": " ".join(self.cxxflags) if self.cxxflags else None,
                   "LDFLAGS": " ".join(self.ldflags) if self.ldflags else None,
                   "MAKEFLAGS": f"-j{defs.NUMCORES}"}

        def replacer(m):
            if m is not None:
                key = m.group(1)
                value = changes[key]
                return f'\n{key}="{value}"'

        for key, value in changes.items():
            if value:
                new = re.sub(f'\n#*?({key})=\"(.*?)\"', replacer, actual, flags=re.DOTALL)
                if new == actual:
                    raise RuntimeError(f"Error processing {key}={value} in makepkg.conf")
                actual = new
        return actual

    def pacmanconf(self, _strap=True):
        contcfg = configparser.ConfigParser(allow_no_value=True, strict=False)
        contcfg.optionxform = str
        systemcfg = configparser.ConfigParser(allow_no_value=True, strict=False)
        systemcfg.optionxform = str
        systemcfg.read("/etc/pacman.conf")
        for section in systemcfg.sections():
            if section.lower() == "options":
                contcfg.add_section(section)
                contcfg.set("options", "Architecture", systemcfg[section]["Architecture"])
            else:
                contcfg.add_section(section)
                for k in systemcfg[section]:
                    if k.lower() == "include":
                        with open(systemcfg[section][k]) as f:
                            server = re.search(r"server\s*\=\s*(.+)", f.read(), re.IGNORECASE)
                            contcfg.set(section, "Server", server.group(1))
                    else:
                        contcfg.set(section, k, systemcfg[section][k])
        with io.StringIO() as ss:
            contcfg.write(ss)
            ss.seek(0)
            conf = ss.read()
            log.logger.debug(conf)
            return conf

    def runner(self):
        runner = f"export PATH=/usr/bin/core_perl:$PATH\n"
        runner += f"export PATH=/usr/bin/vendor_perl:$PATH\n"
        runner += f"export PATH=/usr/bin/site_perl:$PATH\n"
        runner += '"$@"'
        return runner

    @property
    def keyrings(self):
        return agrcmd.run_stdout("pacman", "-Qqs", "keyring").split("\n")

    @classmethod
    def config_commands(cls, parser):
        cmd = super(Host, cls).config_commands(parser)
        cont_p = cmd.choices[defs.CMD_CONT]
        for cmd_cont in cont_p._actions:
            if cmd_cont.dest == "cmd_cont":
                break
        cmd_cont.add_parser(defs.CMD_CONT_WIPE, help="Wipe active container")
        cmd_cont.add_parser(defs.CMD_CONT_CREATE, help="(Re)Create the selected container")
        cmd_cont.add_parser(defs.CMD_CONT_MAINTAIN, help="Maintain the container with bash shell")
        exec_p = cmd_cont.add_parser(defs.CMD_CONT_EXEC, help="Execute command in the active container (immutable)")
        exec_p.add_argument('exec', nargs=argparse.REMAINDER)
        return cmd

    def cmd_container(self, report, cmd_cont, name=None, exec=None):
        if not native.Native.cmd_container(self, report, cmd_cont, name):
            if cmd_cont == defs.CMD_CONT_WIPE:
                log.logger.info(f"Cleaning {self.cont_path}")
                agrcmd.run_interactive("sudo", "rm", "-rf", self.cont_path)
                return True
            elif cmd_cont == defs.CMD_CONT_CREATE:
                self.create()
                return True
            elif cmd_cont == defs.CMD_CONT_EXEC:
                self.run_interactive(*exec, hostdir=os.getcwd())
                return True
            elif cmd_cont == defs.CMD_CONT_MAINTAIN:
                self.run_interactive("bash", hostdir=os.getcwd(), immutable=False)
                return True

    def process_args(self, *cmd, immutable=True, root=False, hostdir=None, cwd=None, env=None, **kwargs):
        cmd = list(cmd)

        # update reqested env with current env in the host
        if env is not None:
            curenv = self.env
            curenv.update(env)
            env = curenv
        else:
            env = self.env
        log.logger.debug(f"Executing in container: {self.name}: '{' '.join(cmd)}', kwargs: {kwargs}, root: {root}, cwd: {cwd}")

        # run in container, map home dir to container so that we can take advantage of ~/.agr folder
        precmd = ["sudo",
                  "systemd-nspawn",
                  "-q",
                  f"--bind=/home/{os.getlogin()}",
                  "-D", self.rootfs_path]

        # mount overlay fs to mutable parts of the container so that they will be kept if immutable
        if immutable:
            for overlay in self.immutables:
                precmd += f"--overlay={self.rootfs_path}{overlay}:{self.immutable_path}{overlay}:{overlay}",
            for overlay in self.mutables:
                precmd += f"--overlay={self.rootfs_path}{overlay}:{self.mutable_path}{overlay}:{overlay}",
            # precmd += ["--volatile=overlay"]
            # precmd += ["--tmpfs=/"]

        # set login user of container
        if not root:
            precmd += ["-u", os.getlogin()]

        # set cwd of the container
        if hostdir:
            cwd = hostdir
            precmd += ["--bind", hostdir]
        if cwd:
            precmd += ["--chdir", cwd]

        # pass environment to container
        for k, v in env.items():
            precmd += ["-E", f"{k}={v}"]

        # transfer host users to container
        for ro_bind in ["/etc/group", "/etc/passwd", "/etc/shadow"]:
            precmd += ["--bind-ro", ro_bind]

        # map modified configs to container
        confs = {"/etc/pacman.conf": self.pacmanconf_path,
                 "/etc/makepkg.conf": self.makepkgconf_path,
                 "/etc/sudoers.d/sudoall": self.sudoers_path}
        for conf_cont, conf_host in confs.items():
            if os.path.exists(conf_host):
                precmd += ["--bind", f"{conf_host}:/{conf_cont}"]
        precmd += [self.runner_path]

        # dont do security checks to improve container execution speed
        sysenv = native.Native.env.copy()
        sysenv["SYSTEMD_SECCOMP"] = "0"
        kwargs["env"] = sysenv

        return precmd + cmd, kwargs

    def run_interactive(self, *cmd, **kwargs):
        cmd, cmdargs = self.process_args(*cmd, **kwargs)
        return agrcmd.run_interactive(*cmd, **cmdargs)

    def run_stdout(self, *cmd, **kwargs):
        cmd, cmdargs = self.process_args(*cmd, **kwargs)
        return agrcmd.run_stdout(*cmd, **cmdargs).replace("\r", "")

    def create(self):
        # clean config files as root
        agrcmd.run_stdout("sudo", "rm", "-f", self.pacstrapconf_path, self.pacmanconf_path, self.makepkgconf_path, self.sudoers_path)

        # create the container with pacstrap
        with open(self.pacstrapconf_path, "w") as f:
            f.write(self.pacmanconf(True))
        packages = native.Native.packages + self.keyrings
        agrcmd.run_interactive("sudo", "pacstrap", "-C", self.pacstrapconf_path, self.rootfs_path, *packages)

        # create pacman.conf for container
        with open(self.pacmanconf_path, "w") as f:
            f.write(self.pacmanconf(False))

        # create makepkg.conf for container
        with open(self.makepkgconf_path, "w") as f:
            f.write(self.makepkgconf(agrcmd.run_stdout("sudo", "cat", os.path.join(self.rootfs_path, "etc", "makepkg.conf"))))

        # allow all users in container to run sudo without password
        with open(self.sudoers_path, "w") as f:
            f.write("ALL ALL=(ALL) NOPASSWD:ALL")
        agrcmd.run_interactive("sudo", "chown", "root", self.sudoers_path)

        # create a runner script that arranges paths. This is ran each time run_* methods invoked
        with open(self.runner_path, "w") as f:
            f.write(self.runner())
        agrcmd.run_interactive("chmod", "+x", self.runner_path)

        self.run_interactive("pacman-key", "--init", immutable=False, root=True)
        self.run_interactive("pacman-key", "--populate", immutable=False, root=True)
