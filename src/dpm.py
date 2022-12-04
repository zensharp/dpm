#!/usr/bin/python3

import argparse
import glob
import os
import platform
import re
import subprocess
import yaml

# OS Wrappers
class PosixShell:
    def expandEnvironmentVariables(self, x):
        x = re.sub('~', '$HOME', x)
        return os.path.expandvars(x)
    def Copy(self, src, dest, symlink):
        src = os.path.abspath(src)
        dest = os.path.abspath(dest)
        destinationRoot = os.path.dirname(dest)
        if symlink:
            command = f"ln -s '{src}' '{dest}'"
        else:
            if os.path.isdir(src):
                command = f"cp -r '{src}' '{dest}'"
            else:
                command = f"cp '{src}' '{dest}'"
        ### Transfer
        if (os.path.islink(src)):
            print(f"Source '{src}' is a link. Skipping...")
            return False
        if not os.path.exists(destinationRoot):
            tryRun(f"mkdir --parents '{destinationRoot}'")
        if os.path.exists(dest):
            tryRun(f"rm -r '{dest}'");
        return tryRun(command)

class WslShell:
    def expandEnvironmentVariables(self, x):
        x = re.sub('~', '%userprofile%', x)
        x = re.sub('%([\w]+)%', lambda match: wslExpand(match.group(1)), x)
        return x
    def Copy(self, src, dest, symlink):
        src = os.path.abspath(src)
        dest = os.path.abspath(dest)
        destinationRoot = os.path.dirname(dest)
        if symlink:
            src = winPath(src)
            if os.path.isdir(dest):
                winDestination = winPath(destinationRoot)
            else:
                winDestination = os.path.join(winPath(destinationRoot), os.path.basename(dest))
            if os.path.isdir(src):
                command = f"cmd.exe /C mklink /D"
            else:
                command = f"cmd.exe /C mklink"
            src = src.replace(os.sep, '\\')
            winDestination = winDestination.replace(os.sep, '\\')
            command = f"{command} '{winDestination}' '{src}'"
        else:
            if os.path.isdir(src):
                command = f"cp -r '{src}' '{dest}'"
            else:
                command = f"cp '{src}' '{dest}'"
        ### Transfer
        if (os.path.islink(src)):
            print(f"Source '{src}' is a link. Skipping...")
            return False
        if not os.path.exists(destinationRoot):
            tryRun(f"mkdir --parents '{destinationRoot}'")
        if os.path.exists(dest):
            tryRun(f"rm -r '{dest}'");
        oldpwd = os.getcwd()
        os.chdir(os.path.dirname(destinationRoot))
        status = tryRun(command)
        os.chdir(oldpwd)
        return status

def wslPath(x):
    return subprocess.check_output(f"wslpath '{x}'", shell=True).decode('ascii').strip()
def winPath(x):
    return subprocess.check_output(f"wslpath -w '{x}'", shell=True).decode('ascii').strip()
def wslExpand(x):
    path = subprocess.check_output(f"wslvar '{x}'", shell=True).decode('ascii').strip()
    return wslPath(path)

# Helper
## Auxilary Classes
class Session:
    def __init__(self):
        if config["windows"]:
            self.platform = "windows"
        elif config["macos"]:
            self.platform = "macos"
        elif config["linux"]:
            self.platform = "linux"
        elif config["wsl"]:
            self.platform = "wsl"
        else:
            if platform.system() == "Windows":
                self.platform = "windows"
            elif platform.system() == "Darwin":
                self.platform = "macos"
            elif platform.system() == "Linux":
                self.platform = "linux"
        self.verb = config["verb"]
        self.verbose = config["verbose"]
        self.dryRun = config["dry_run"]

class Manifest:
    def __init__(self, path):
        with open(packagePath) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            self.include = data["include"]
            self.targets = {}
            if "destination" in data:
                self.targets["global"] = data;
            if "windows" in data:
                self.targets["windows"] = data["windows"]
            if "linux" in data:
                self.targets["linux"] = data["linux"]
            if "macos" in data:
                self.targets["macos"] = data["macos"]
    def getDestinationList(self, platform):
        if platform and platform in self.targets:
            return listOrSingle(self.targets[platform]["destination"])
        if "global" in self.targets:
            return listOrSingle(self.targets["global"]["destination"])
        print(f"Platform '{platform}' not supported")
        exit(1)

class Transfer:
    def __init__(self, src, dest, symlink):
        self.src = src
        self.dest = dest
        self.symlink = symlink

# Helper functions
def expandGlob(x):
    if not x:
        return []
    temp = glob.glob(x)
    if temp:
        return temp
    if os.path.exists(x):
        return [x]
    return [x]

def tryRun(x):
    if session.dryRun:
        print(f"[DRY RUN] {x}")
        return False
    os.system(x)
    return True

def listOrSingle(x):
    if type(x) is list:
        return x
    return [x]

def dictGet(dict, key, fallback):
    if key in dict:
        return dict[key]
    return fallback

def prefixDest(src, dest):
    if dest.endswith("/") or dest.endswith("\\"):
        dest = os.path.join(dest, os.path.relpath(src, packageRoot))
    else:
        if os.path.isdir(dest):
            dest = os.path.join(dest, os.path.relpath(src, packageRoot))
        else:
            dest = dest
    return dest

def execute(transfer):
    if session.verb == "load":
        symlink = transfer.symlink and not config["force_no_symlinks"] or config["force_symlinks"]
        if shell.Copy(transfer.src, transfer.dest, symlink):
            print(f"Loaded '{os.path.relpath(transfer.src, packageRoot)}' to '{transfer.dest}'...")
    elif session.verb == "pack":
        if shell.Copy(transfer.dest, transfer.src, False):
            print(f"Packed '{transfer.dest}' as '{os.path.relpath(transfer.src, packageRoot)}'...")
    elif session.verb == "lint":
        suffix = "/" if os.path.isdir(transfer.src) else "";
        print(f"- source: {transfer.src}{suffix}")
        print(f"    dest: {transfer.dest}{suffix}")
        if transfer.symlink:
            print(f" symlink: {transfer.symlink}")
    else:
        print(f"Invalid verb '{session.verb}'...")
        exit(1)

# Begin code
## Parse configuration
parser = argparse.ArgumentParser(description="Dotfiles Package Manager", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("verb", help="The dotfile operation", nargs='?', default="load")
parser.add_argument("id", help="The id of the package")
parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
parser.add_argument("-n", "--dry-run", action="store_true", help="Dry run mode")
parser.add_argument("--windows", action="store_true", help="Install in 'windows' mode")
parser.add_argument("--macos", action="store_true", help="Install in 'macOS' mode")
parser.add_argument("--linux", action="store_true", help="Install in 'linux' mode")
parser.add_argument("--wsl", action="store_true", help="Install in 'wsl' mode")
parser.add_argument("-s", "--force-symlinks", action="store_true", help="Force all contents to be installed as symlinks")
parser.add_argument("--force-no-symlinks", action="store_true", help="Force all contents to be installed as copies")
config = vars(parser.parse_args())

## Parse environment
session = Session()
if session.platform == "wsl":
    shell = WslShell()
    virtualPlatform = "windows"
elif session.platform == "macos":
    shell = PosixShell()
    virtualPlatform = "macos"
else:
    shell = PosixShell()
    virtualPlatform = "linux"
packageRoot = os.path.join(os.path.expandvars('$HOME/.dotfiles'), config["id"])
packagePath = os.path.join(packageRoot, "package.yml")
manifest = Manifest(packagePath)

## Compute destinations
destinations = []
for destinationGlob in manifest.getDestinationList(virtualPlatform):
    destinationGlob = shell.expandEnvironmentVariables(destinationGlob)
    destinations.append(destinationGlob)

## Cross source (glob) paths with destination paths
for include in manifest.include:
    srcGlob = os.path.join(packageRoot, include["path"])
    srcGlob = shell.expandEnvironmentVariables(srcGlob)
    if "destination" in include:
        destinationOverride = include["destination"]
        destinationOverride = shell.expandEnvironmentVariables(destinationOverride)
        if os.path.isabs(destinationOverride):
            destGlobs = [ destinationOverride ]
        else:
            destGlobs = map(lambda d : os.path.join(d, destinationOverride), destinations)
    else:
        destGlobs = destinations
    for src in expandGlob(srcGlob):
        for destGlob in destGlobs:
            for dest in expandGlob(destGlob):
                dest = prefixDest(src, dest)
                transfer = Transfer(src, dest, dictGet(include, "symlink", False))
                execute(transfer)

# Hack for console_scripts
def main():
    pass
