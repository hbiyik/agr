# AGR (Archlinux Git Repositories)

## What is AGR?

`agr` is a tool that acts like a package manager with a twist. The user sets the remote git addresses where there are bunch of different `PKGBUILD` files in it. Then the user can build and install the package maintained in this repo. So in this sense, it is more like an `AUR` with git backend.

The major difference difference of AGR from other package managers is, AGR manages the .SRCINFO on the user/client side, meaning that the versions of each package is calculated dynamically and maintainer does not need to specifically maintain the versions of the packages.

## The concept of containers and cross compilation

You can use AGR as a native package manager on the running existing archlinux installation, or you can build individual packages in sterile container that can later be installed to your target archlinux based OS.

Current containers are:

1. **native** *(default)*: Packages are build in your native OS and installed to your native OS.
2. **host-x86_64**: A replica of your current OS is created is created, and packages are built inside this sterile container. The architecture tar can be different is you are running in another arch. Ie: if you run it under `alarm-aarch64` OS, your container name will be `native-aarch64`. You can list the available containers with `agr container list`
3. **alarm-aarch64**: This is a cross compiling container which runs on `x86_64` and generates `aarch64` packages based on Archlinux ARM toolchain.
4. **alarm-armv7h**: This is a cross compiling container which runs on `x86_64` and generates `armv7h` packages based on Archlinux ARM toolchain.

## Installation

To install or update the tool, just install with pip as below.

```shell
python -m pip install https://github.com/hbiyik/agr/archive/master.zip --break-system-packages --force-reinstall
```

or if pip is already in your path, simply:

```shell
pip install https://github.com/hbiyik/agr/archive/master.zip --break-system-packages --force-reinstall
```

Don't worry, you wont break the system packages because there is no agr system package as of yet, instead we are using python pip installer.
Pip installer by default installs the scripts under `~/.local/bin/` if this path is already in your system path, you can directly run `agr` command form shell

if not, you can either add `~/.local/bin/` to your `PATH` or, your can create a symbolic link of agr to `~/.local/bin/agr` as below  

```shell
sudo ln -s ~/.local/bin/agr /usr/local/bin/agr
```

or you can run `agr` inside the python interpreter as below

```shell
python -m agr
```

### Basic Usage

To add an example repo of https://github.com/hbiyik/agrrepo.git with an alias/name of of "boogie"

```shell
agr rem set boogie https://github.com/hbiyik/agrrepo.git
```

verify the remote repo is added

```shell
agr rem list
```

sync the packages in the repo

```shell
agr sync --noconfirm
```


list the packages in the active repos added

```shell
agr
```

will output

```
     INFO | Running in container native
      AGR | 
      AGR | Repository: boogie: ['/home/boogie/src/agrrepo', 'master']
      AGR | ----------------------------------------------------------
      AGR |           libmali-valhall-g610-base, version: g13p0.10-1
      AGR |           libmali-valhall-g610-dummy, version: g13p0.10-1
      AGR |           libmali-valhall-g610-gbm, version: g13p0.10-1
      AGR |           libmali-valhall-g610-wayland-gbm, version: g13p0.10-1
      AGR |           libmali-valhall-g610-x11-gbm, version: g13p0.10-1
      AGR |           libmali-valhall-g610-x11-wayland-gbm, version: g13p0.10-1
      AGR |           dri2to3-git, version: r6.43a51c6-1
      AGR |           libv4l-rkmpp-git, version: 1.7.1-1
      AGR |           v4l-utils-mpp, version: 1.26.1-1
      AGR |       [I] gitweb-dlagent, version: 0.3-1
      AGR |           r8125-dkms-git, version: 9.013.02.1.1-1
      AGR |           linux-aarch64-rockchip-bsp6.1-joshua-git, version: 6.1.75.r1272305.aa54fa4e0712-1
      AGR |           linux-aarch64-rockchip-bsp6.1-joshua-git-headers, version: 6.1.75.r1272305.aa54fa4e0712-1
      AGR |           linux-aarch64-rk3588-collabora-git, version: 6.10rc1.r1279437.b8c754a7-1
      AGR |           linux-aarch64-rk3588-collabora-git-headers, version: 6.10rc1.r1279437.b8c754a7-1
      AGR |           linux-aarch64-rockchip-bsp5.10-radxa-git-headers, version: 5.10.1082245.36d94f0525-1
      AGR |           linux-aarch64-rockchip-bsp5.10-radxa-git, version: 5.10.1082245.36d94f0525-1
      AGR |           mesa-panfork-git, version: r164486.2e8aead0016-1
      AGR |           mpp-git, version: 1.0.6.r3644.8753dc63-1
      AGR |           8852be-dkms-git, version: 1.15.10.0.5.0.4-1
      AGR |           ffmpeg-mpp-git, version: 7.0.1.r114633.342fe8368c-1
      AGR |           chromium-mpp, version: 122.0.6261.128-1
      AGR |           8852bu-dkms-git, version: 1.15.7.112.2-1
      AGR |       [I] gl4es-git, version: r2687.52e0c496-1
      AGR |           mesa-panvk-git, version: 19.2.branchpoint.r76971.g4659c0c87bd-1
      AGR |           mesa-panfrost-git, version: r187624.4ab19044967-1
      AGR |           icecream-git, version: r2207.57c6fa6-1
      AGR |           kodi-mpp-git, version: r175782.7e5bb325bd-1
      AGR |    [B][I] kodi-binary-addons-git, version: r24014-1
      AGR |           librga-multi, version: 1.10.0.d7a0a485ed-1
      AGR | 
      AGR | [B] = Built
      AGR | [I] = Installed
      AGR | [U] = Needs Update
      AGR | 
      AGR | Result time: 0.57 seconds

```

### install a package from the remote repo
to install `ffmpeg-mpp-git` from the `boogie` repo

```shell
agr install ffmpeg-mpp-git
```

to automatically say "yes" to each question asked

```shell
agr install ffmpeg-mpp-git --noconfirm
```



### update the system 

to update the installed packages with their newest versions

```shell
agr update --noconfirm
```

to update everything except `linux-aarch64-rk3588-collabora-git` package without any confirmation

```shell
agr update --sync --noconfirm --np-pkg linux-aarch64-rk3588-collabora-git
agr update --noconfirm --no-pkg linux-aarch64-rk3588-collabora-git
```

### to self update the agr tool

```shell
agr update --agr
```

## Advanced Usage and containers

To use a container you have to set it first and create it. To get the list of available containers:

```shell
agr container list
```

To get the active container

```shell
agr container get
```

To set to another container, in below example `alarm-aarch64`

```shell
agr container set alarm-aarch64
```

After the container is set, you have to create it. (unless the set container is not `native`)

```shell
agr container create
```

After this point, all the build commands will now run for the set target container.

You can delete all of the container image with


```shell
agr container wipe
```

### Working with containers

1. You can find the generated build artifacts (packages) under `~/.agr/tarballs/[container-name]/[repo-name]/`

2. The `update` command updates the built packages when a container is in use, updates the installed packages when `native` is in use.

3. The containers are immutable, meaning that the changes done during the package build process is not permanent, and will be deleted after the building process is finished.

4. However the containers do a generic maintannceof `pacman -Syu` theirselves on each agr execution. So you dont have to maintain them,

5. You can run a mutable command in the constainer with `agr container maintain command-to-run-in-container`. Ie: `agr container maintain sudo pacman -Syu` will update the container in a mutable way, meaning that, next time agr runs the `maintain` commands will be permamnent.

6. You can run immutable commands in a container with `agr container exec command-to-run-in-container`. The changes that the command has done will not be permanent. Ie: `agr container exec bash` will fall you back to the containers terminal.

7. Your current working directory and logged in users home directory will be mapped to container automatically. That means you can run `agr container exec makepkg` in any external `PKGBUILD` directory in your hard drive and compile your package in the container.

## Under the hood.

The cross compiling containers are very fast. The reason for this is, the GCC and toolchain in the foreign artchitecture container runs in native architecture without any emulation, the rest like build tools like make, cmake, ninja, shell etc are running with qemu. Since the bottleneck of performance when compiling is actual compiling and linking stage, both of them runs natively.

The native cross compiling only works for `GCC` based compilers. The compilers like `clang`, `rustc`, `java`, `cpython` etc.. will run with emulation, therefore such packets will be slow to compile.

Further improvement on the rest of development tools or extra compilation can theoretically be done, but future management of them would be quite complicated, so i believe current status is the sweet spot.

