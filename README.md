# AGR (Archlinux Git Repositories)

## What is AGR?

`agr` is a tool that acts like a package manager with a twist. The user sets the remote git addresses where there are bunch of different `PKGBUILD` files in it. Then the user can build and install the package maintained in this repo. So in this sense, it is more like an `AUR` with git backend.

## Why AGR?

When the developers work on a very niche project and that niche project and its dependencies or other projects depend on this projects might not adapt it properly or in time due to individual release cycles. At that point of time you will end up with a mess of forks and this prevents users to give actual feedback about your project.

## Why not AUR?

Because such niche projects might have constraints that AUR maintainers might not be a big fan of. ie: arm packages. And whenever the changes in this repo are mainlined to the individual projects, having this particular work on the repo would not make sense, and then it can be switched to individual AUR package. And in the meanwhile AUR can be kept cleaner.

## Cool stuff how to use=

To install or update the tool, just install with pip as below.

### install of update the agr


```shell
python -m pip install https://github.com/hbiyik/agr/archive/master.zip --break-system-packages --force-reinstall
```

or if pip is already in your path, simply:

```shell
pip install https://github.com/hbiyik/agr/archive/master.zip --break-system-packages --force-reinstall
``` 

Dont worry, you wont break the system packages because there is no agr system package as of yet, instead we are using python pip installer.
Pip installer by default installs the scripts under `~/.local/bin/` if this path is already in your system path, you can directly run `agr` command form shell

if not, you can either add `~/.local/bin/` to your `PATH` or, your can create a symbolic link of agr to `~/.local/bin/agr` as below  

```shell
sudo ln -s ~/.local/bin/agr /usr/local/bin/agr
``` 

or you can run `agr` inside the python interpreter as below

```shell
python -m agr
```

### set the remote repo

To add an example repo of https://github.com/hbiyik/agrrepo.git with an alias/name of of "boogie"

```shell
agr rem set boogie https://github.com/hbiyik/agrrepo.git
```

verify the remote repo is added

```shell
>> agr rem list
boogie https://github.com/hbiyik/agrrepo.git master
``` 

list the packages in the active repos added

```shell
>> agr
2024-02-04 15:15:19,535 - log - RESULT - Repository: blocal
2024-02-04 15:15:19,535 - log - RESULT - dri2to3-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT - linux-radxa-rkbsp5-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT -   +- linux-radxa-rkbsp5-git-headers, installed: False
2024-02-04 15:15:19,535 - log - RESULT - kodi-matrix-addon-pvr-iptvsimple-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT - kodi-nexus-mpp-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT -   +- kodi-nexus-binary-addons-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT - r8125-dkms-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT - mesa-panfork-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT - mpp-git, installed: True
2024-02-04 15:15:19,535 - log - RESULT - libmali-valhall-g610, installed: False
2024-02-04 15:15:19,535 - log - RESULT -   +- libmali-valhall-g610-base, installed: False
2024-02-04 15:15:19,535 - log - RESULT -   +- libmali-valhall-g610-dummy, installed: False
2024-02-04 15:15:19,535 - log - RESULT -   +- libmali-valhall-g610-gbm, installed: False
2024-02-04 15:15:19,535 - log - RESULT -   +- libmali-valhall-g610-wayland-gbm, installed: False
2024-02-04 15:15:19,535 - log - RESULT -   +- libmali-valhall-g610-x11-gbm, installed: False
2024-02-04 15:15:19,535 - log - RESULT -   +- libmali-valhall-g610-x11-wayland-gbm, installed: False
2024-02-04 15:15:19,535 - log - RESULT - 8852be-dkms-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT - 8852bu-dkms-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT - ffmpeg-rockchip-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT - gl4es-git, installed: False
2024-02-04 15:15:19,535 - log - RESULT - librga-multi, installed: False
```

### install a package from the remote repo
to install `ffmpeg-rockchip-git` from the `boogie` repo

```shell
agr install ffmpeg-rockchip-git
```

to automatically say "yes" to each question asked

```shell
agr install ffmpeg-rockchip-git --noconfirm
```



### update the system 

to update the installed packages with their newest versions

```shell
agr update
```

to update everything except linux-radxa-rkbsp5-git package without any confirmation

```shell
agr update --noconfirm --ignore linux-radxa-rkbsp5-git
```

### to self update the agr tool

```shell
agr update --agr
```
