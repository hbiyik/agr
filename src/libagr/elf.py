"""
 Copyright (C) 2025 boogie

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import tarfile
import stat
import struct
import re
import os

from libagr import cmd
from libagr import log
from libagr import defs

try:
    import pyzstd
except ImportError:
    pyzstd = None


MACHMAP = {
    0x3: defs.ARCH_i686,
    0x3e: defs.ARCH_X86_64,
    0x28: defs.ARCH_ARMV7H,
    0xb7: defs.ARCH_AARCH64}


class Elf32:
    section_headeroffset = 0x20
    section_headersize = 0x2E
    section_headernum = 0x30
    section_offset = 0x10
    section_size = 0x14
    section_entsize = 0x24
    read_size = 4


class Elf64:
    section_headeroffset = 0x28
    section_headersize = 0x3A
    section_headernum = 0x3C
    section_offset = 0x18
    section_size = 0x20
    section_entsize = 0x38
    read_size = 8


class ElfFileException(Exception):
    pass


class ElfFile:
    def __init__(self, fullpath, is64bit=None, machine=None, f=None):
        self.fullpath = fullpath
        self.path = os.path.basename(fullpath)
        self.f = f
        if machine is not None:
            self.machine = machine
        if is64bit is not None:
            self.is64bit = is64bit
        self.header = None
        if machine is None or is64bit is None:
            if not self.f:
                self.f = open(fullpath, "rb")
            self.f.seek(0)
            self.header = self.f.read(0x3E)
            if not len(self.header) == 0x3E:
                raise ElfFileException("Not an Elf File, possibly a script?")
            signature = self.header[0:4]
            if signature != b"\x7FELF":
                raise ElfFileException("Not an Elf File, possibly a script?")
            if is64bit is None:
                is64bit = self.read(self.header, 4, 1)
                if is64bit == 1:
                    self.is64bit = False
                elif is64bit == 2:
                    self.is64bit = True
                else:
                    raise ElfFileException(f"Unknown class: {is64bit}")
            if machine is None:
                self.machine = self.read(self.header, 0x12, 2)

    @property
    def arch(self):
        return MACHMAP.get(self.machine, self.machine)

    def close(self):
        if self.f:
            self.f.close()
            self.f = None

    def read(self, buffer, offset, size):
        chars = {1: "B",
                 2: "H",
                 4: "I",
                 8: "Q"}
        return struct.unpack(chars[size], buffer[offset: offset + size])[0]

    def iterdynamic(self):
        # big endian is not supported, only little
        if self.is64bit == 1:
            e_arch = Elf64()
        else:
            e_arch = Elf32()
        e_shoff = self.read(self.header, e_arch.section_headeroffset, e_arch.read_size)
        e_shsize = self.read(self.header, e_arch.section_headersize, 2)
        e_shnum = self.read(self.header, e_arch.section_headernum, 2)
        self.f.seek(e_shoff)
        sections = self.f.read(e_shnum * e_shsize)
        dynamic = None
        dynstr = None
        for i in range(e_shnum):
            if dynamic is not None:
                break
            soffset = i * e_shsize
            s_type = self.read(sections, soffset + 4, 4)
            s_offset = self.read(sections, soffset + e_arch.section_offset, e_arch.read_size)
            s_filesz = self.read(sections, soffset + e_arch.section_size, e_arch.read_size)
            s_entsz = self.read(sections, soffset + e_arch.section_entsize, e_arch.read_size)
            # SHT_STRTAB
            if s_type == 0x3:
                self.f.seek(s_offset)
                dynstr = self.f.read(s_filesz)
            # SHT_DYNAMIC
            if s_type == 0x6 and dynstr is not None:
                self.f.seek(s_offset)
                dynamic = self.f.read(s_filesz)
                found_tag = False
                for ent in range(int(s_filesz / s_entsz)):
                    if found_tag:
                        break
                    tag_offset = ent * s_entsz
                    tag = self.read(dynamic, tag_offset, e_arch.read_size)
                    if tag == 1:
                        found_tag = True
                        ptr = self.read(dynamic, tag_offset + e_arch.read_size, e_arch.read_size)
                        lib = ""
                        for i in range(512):
                            c = dynstr[ptr + i: ptr + i + 1]
                            if c == b"\x00":
                                break
                            lib += c.decode()
                        yield SoFile(lib, self.is64bit, self.machine)

    def issameabi(self, other):
        return self.machine == other.machine and self.is64bit == other.is64bit

    def __repr__(self):
        return f"{self.path}(Arch:{self.arch}, 64:{self.is64bit})"

    def __eq__(self, other):
        return self.path == other.path and self.issameabi(other)

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.path + str(self.machine) + str(self.is64bit))


class SoFile(ElfFile):
    def __init__(self, fullpath, is64bit=None, machine=None, f=None):
        super().__init__(fullpath, is64bit, machine, f)
        parts = re.search(r"(.+?)\.so(.*)", self.path)
        if parts is None:
            raise ElfFileException(f"Not an elf library: {self.path}")
        self.libname = parts.group(1)
        version = parts.group(2)
        if version and len(version) == 1:
            raise ElfFileException(f"Unknown so version {version}")
        self.version = version
        self.neededby = []

    def issamelib(self, other):
        return self.libname == other.libname

    def __qt__(self, other):
        if not self.issamelib(other):
            return
        if not self.issameabi(other):
            return
        if not self.version.count(".") == other.version.count("."):
            return
        elif int(cmd.run_stdout("vercmp", self.version, other.version)) > 0:
            return True
        return False

    def __lt__(self, other):
        if not self.issamelib(other):
            return
        if not self.issameabi(other):
            return
        if not self.version.count(".") == other.version.count("."):
            return
        elif int(cmd.run_stdout("vercmp", self.version, other.version)) < 0:
            return True
        return False

    def __ge__(self, other):
        return self == other or self > other

    def __le__(self, other):
        return self == other or self < other


def ldcache(close=True):
    entries = []
    magic = b"glibc-ld.so.cache1.1"
    path = "/etc/ld.so.cache"
    f = open(path, "rb")
    if not f.read(len(magic)) == magic:
        return
    lib_count = struct.unpack("I", f.read(4))[0]
    strs_len = struct.unpack("I", f.read(4))[0]
    offset = f.tell() + 20
    for i in range(lib_count):
        f.seek(offset + i * 24)
        # flags, key, value, osver, hwcap
        entries.append(struct.unpack("IIIIQ", f.read(24)))
    for entry in f.read(strs_len).split(b"\x00"):
        if not entry:
            continue
        try:
            fname = entry.decode()
            if os.path.isdir(fname):
                continue
            if not os.stat(fname).st_mode | stat.S_IEXEC:
                continue
            so = SoFile(fname, f=open(fname, "rb"))
            yield so
            if close:
                so.close()
        except (ElfFileException, PermissionError, FileNotFoundError) as e:
            log.logger.debug("%s: %s", entry, e)


def lddirs():
    paths = []
    ldpaths = os.environ.get("LD_LIBRARY_PATH")
    if ldpaths:
        for ldpath in ldpaths.split(":"):
            if ldpath and ldpath not in paths and os.path.exists(ldpath):
                paths.append(ldpath)
                yield ldpath
    for path in re.findall(r"SEARCH_DIR\(\"\=?(.+?)\"\)", cmd.run_stdout("ld", "--verbose")):
        if path and path not in paths and os.path.exists(path):
            paths.append(path)
            yield path


def searchdirs(close=True):
    for path in lddirs():
        for fname in os.listdir(path):
            fullpath = os.path.join(path, fname)
            if os.path.isdir(fullpath):
                continue
            if not os.stat(fullpath).st_mode | stat.S_IEXEC:
                continue
            try:
                so = SoFile(fullpath, f=open(fullpath, "rb"))
                yield so
                if close:
                    so.close()
            except (ElfFileException, PermissionError, FileNotFoundError) as e:
                log.logger.debug("%s: %s", fullpath, e)


def finddeplibs(pkgpath):
    provides = []
    libs = []
    execs = []
    deps = []
    f = None
    if pkgpath.endswith(".zst"):
        if pyzstd is None:
            raise RuntimeError("pyzstd is required to analyze .pkg.tar.zst types. Please install python-pyzstd.")
        f = pyzstd.ZstdFile(pkgpath, mode='r')
        t = tarfile.open(fileobj=f)
    else:
        t = tarfile.open(pkgpath, mode="r:*")
    for tinfo in t.getmembers():
        if tinfo.isdir():
            continue
        if bool(tinfo.mode & stat.S_IEXEC):
            try:
                f = t.extractfile(tinfo)
            except KeyError:
                log.logger.warning(f"Link file {tinfo.path} does not have target {tinfo.linkpath} in package {os.path.basename(pkgpath)}")
                continue
            if f is None:
                continue
            sofile = None
            elffile = None
            try:
                sofile = SoFile(tinfo.name, f=f)
            except ElfFileException:
                try:
                    elffile = ElfFile(tinfo.name, f=f)
                except ElfFileException:
                    log.logger.debug("Skipping analysis of non-elf executable %s in package %s",
                                     os.path.basename(tinfo.name),
                                     os.path.basename(pkgpath))
                    continue
            log.logger.info("Analyzing executable %s in package %s",
                            sofile or elffile,
                            os.path.basename(pkgpath))
            if sofile:
                provides.append(sofile)
            if tinfo.size and sofile:
                libs.append(sofile)
            if tinfo.size and elffile:
                execs.append(elffile)
    for elfs in [libs, execs]:
        for elf in elfs:
            log.logger.info("Checking dependecies of %s in package %s",
                            elf,
                            os.path.basename(pkgpath))
            for dep in elf.iterdynamic():
                if dep not in provides:
                    if dep not in deps:
                        deps.append(dep)
                    dep = deps[deps.index(dep)]
                    if elf not in dep.neededby:
                        dep.neededby.append(elf)
    # close elfs
    [[x.close() for x in y] for y in [libs, execs, provides]]
    return provides, deps


def findsystemlibs():
    libs = []
    for source in [ldcache(), searchdirs()]:
        for lib in source:
            if lib and lib not in libs:
                yield lib
                libs.append(lib)


PROC = ElfFile("/proc/self/exe")
PROC.close()
