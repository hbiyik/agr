'''
Created on May 8, 2024

@author: boogie
'''
import os
import tempfile
import urllib.request

from libagr.container import host
from libagr import cmd
from libagr import defs


class Alarm64(host.Host):
    # rustup default stable-armv7-unknown-linux-gnueabihf
    cont_arch = defs.ARCH_AARCH64
    host_archs = [defs.ARCH_X86_64]
    name = f"alarm-{cont_arch}"
    tc_url = "https://archlinuxarm.org/builder/xtools/x-tools8.tar.xz"
    tc_triplet = "aarch64-unknown-linux-gnu"
    packages = host.Host.packages + ["tar", "qemu-user-static", "qemu-user-static-binfmt"]
    qemu_elfconf = ":qemu-aarch64:M::\\x7fELF\\x02\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\xb7\\x00:\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\x00\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xfe\\xff\\xff\\xff:/usr/bin/qemu-aarch64-static:FPC\n"

    def __init__(self):
        self.cont_path = os.path.join(defs.CONT_PATH, self.name)
        self.rootfs_path = os.path.join(self.cont_path, self.name)
        self.tc_base = self.tc_url.split("/")[-1].split(".")[0]
        self.ldcache = os.path.join(self.cont_path, "ldcache")
        self.ldconf = os.path.join(self.cont_path, "ldconfig")
        self.native_path = os.path.join(self.rootfs_path, "opt", defs.ARCH_X86_64)
        self.qemuconf_path = os.path.join(self.cont_path, "qemu.conf")
        host.Host.__init__(self)
        cmd.run_interactive("sudo", "mkdir", "-p", self.native_path)

    def pacmanconf(self, strap=False):
        def addrepo(conf, repo, strap):
            conf += f"[{repo}]\n"
            conf += f"Server = http://mirror.archlinuxarm.org/$arch/$repo\n"
            if strap:
                conf += f"SigLevel = TrustAll\n"
            return conf

        conf = "[options]\n"
        conf += f"Architecture = {self.cont_arch}\n"
        conf = addrepo(conf, "core", strap)
        conf = addrepo(conf, "extra", strap)
        conf = addrepo(conf, "alarm", strap)
        conf = addrepo(conf, "aur", strap)
        return conf

    def process_args(self, *cmd, immutable=True, root=False, hostdir=None, cwd=None, env=None, **kwargs):
        cmd, kwargs = host.Host.process_args(self, *cmd, immutable=immutable, root=root, hostdir=hostdir, cwd=cwd, env=env, **kwargs)
        if os.path.exists(self.ldcache):
            cmd.insert(2, f"--bind-ro={self.ldcache}:/etc/ld.so.cache")
        return cmd, kwargs

    def runner(self):
        runner = f"export PATH=/opt/{self.tc_base}/{self.tc_triplet}/bin:$PATH\n"
        runner += host.Host.runner(self)
        return runner

    @property
    def keyrings(self):
        return ["archlinuxarm-keyring"]

    def qemu_workaround(self):
        with open(self.qemuconf_path, "w") as f:
            f.write(self.qemu_elfconf)
        cmd.run_interactive("sudo", "cp", "-f", self.qemuconf_path, os.path.join("/etc", "binfmt.d", f"qemu-{self.cont_arch}-static.conf"))
        cmd.run_interactive("sudo", "systemctl", "restart", "systemd-binfmt")

    def create(self):
        # create the actual container
        host.Host.create(self)

        try:
            self.run_stdout("sudo", "uname")
        except OSError as e:
            # https://wiki.archlinux.org/title/QEMU#sudo_in_chroot
            if "nosuid" in e.strerror:
                self.qemu_workaround()

        self.create_toolchain()

    def create_toolchain(self):
        # create a minimal x86_64 system just to get dependencies of gcc including linker and c-libs
        conf = host.Host.pacmanconf(self)
        with tempfile.NamedTemporaryFile(delete=False) as cfg:
            cfg.write(conf.encode())
            cfg.close()
            cmd.run_interactive("sudo", "pacstrap", "-G", "-C", cfg.name, self.native_path, "base-devel")

        # mimic the interpreter path /lib64/ld-linux-x86_64.so* path
        lib64 = os.path.join(self.rootfs_path, "lib64")
        if os.path.exists(lib64):
            cmd.run_interactive("sudo", "rm", "-rf", lib64)
        self.run_interactive("ln", "-sf", f"/opt/{defs.ARCH_X86_64}/lib", "/lib64", root=True, immutable=False)

        # generate so cache for 86_64 libs
        with open(self.ldconf, "w") as f:
            f.write("/lib64")
        env = self.env.copy()
        self.run_interactive(f"{self.native_path}/bin/ldconfig", "-C", self.ldcache, "-f", self.ldconf, env=env, root=True, immutable=False)

        # dont allow ldcache to be updated
        self.run_interactive("sudo", "rm", "-f", "/usr/bin/ldconfig", root=True, immutable=False)
        self.run_interactive("sudo", "ln", "-sf", "/usr/bin/true", "/usr/bin/ldconfig", root=True, immutable=False)

        # download and prepare the toolchain
        tc_archive = os.path.join(self.cont_path, "toolchain.tar.gz")
        urllib.request.urlretrieve(self.tc_url, tc_archive)
        cmd.run_interactive("sudo", "tar", "-xf", tc_archive, "-C", os.path.join(self.rootfs_path, "opt"))

        # replace the tc sysroot, with container sysroot
        sysroot = os.path.join(self.rootfs_path, "opt", self.tc_base, self.tc_triplet, self.tc_triplet, "sysroot")
        if os.path.exists(sysroot) and os.path.isdir(sysroot):
            backup_sysroot = sysroot + ".backup"
            if os.path.exists(backup_sysroot):
                cmd.run_interactive("sudo", "rm", "-rf", backup_sysroot)
            cmd.run_interactive("sudo", "mv", sysroot, backup_sysroot)
            self.run_interactive("sudo", "ln", "-sf", "/",
                                 os.path.join("/opt", self.tc_base, self.tc_triplet, self.tc_triplet, "sysroot"),
                                 root=True,
                                 immutable=False)


class Alarm32(Alarm64):
    cont_arch = defs.ARCH_ARMV7H
    name = f"alarm-{cont_arch}"
    tc_url = "https://archlinuxarm.org/builder/xtools/x-tools7h.tar.xz"
    tc_triplet = "arm-unknown-linux-gnueabihf"
    qemu_elfconf = ":qemu-arm:M::\\x7fELF\\x01\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\x28\\x00:\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\xfe\\xff\\xff\\xff:/usr/bin/qemu-arm-static:FPC\n"
    cflags = ["-march=armv7-a", "-mfloat-abi=hard", "-mfpu=neon", "-O2", "-pipe",
              "-fstack-protector-strong", "-fno-plt", "-fexceptions",
              "-Wp,-D_FORTIFY_SOURCE=2", "-Wformat", "-Werror=format-security",
              "-fstack-clash-protection"]
    cxxflags = cflags + ["-Wp,-D_GLIBCXX_ASSERTIONS"]
    cflags += ["-Wno-incompatible-pointer-types"]
    ldflags = ["-Wl,-O1", "-Wl,--sort-common", "-Wl,--as-needed", "-Wl,-z,relro", "-Wl,-z,now"]
