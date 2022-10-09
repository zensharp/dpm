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
    def Copy(self, source, destination, symlink):
        source = os.path.abspath(source)
        destination = os.path.abspath(destination)
        destinationRoot = os.path.dirname(destination)
        if symlink:
            command = f"ln -s '{source}' '{destination}'"
        else:
            if os.path.isdir(source):
                command = f"cp -r '{source}' '{destination}'"
            else:
                command = f"cp '{source}' '{destination}'"
        ### Transfer
        if not os.path.exists(destinationRoot):
            tryRun(f"mkdir --parents '{destinationRoot}'")
        if os.path.exists(destination):
            tryRun(f"rm -r '{destination}'");
        tryRun(command)

class WslShell:
    def expandEnvironmentVariables(self, x):
        x = re.sub('~', '%userprofile%', x)
        x = re.sub('%([\w]+)%', lambda match: wslExpand(match.group(1)), x)
        return x
    def Copy(self, source, destination, symlink):
        source = os.path.abspath(source)
        destination = os.path.abspath(destination)
        destinationRoot = os.path.dirname(destination)
        if symlink:
            source = winPath(source)
            if os.path.isdir(destination):
                destination = winPath(destinationRoot)
            else:
                destination = os.path.join(winPath(destinationRoot), os.path.basename(destination))
            if os.path.isdir(source):
                command = f"cmd.exe /C mklink /D"
            else:
                command = f"cmd.exe /C mklink"
            source = source.replace(os.sep, '\\')
            destination = destination.replace(os.sep, '\\')
            command = f"{command} '{destination}' '{source}'"
        else:
            if os.path.isdir(source):
                command = f"cp -r '{source}' '{destination}'"
            else:
                command = f"cp '{source}' '{destination}'"
        ### Transfer
        if (os.path.islink(source)):
            if session.verbose:
                print(f"Source '{source}' is a link. Skipping...")
            return
        if not os.path.exists(destinationRoot):
            tryRun(f"mkdir --parents '{destinationRoot}'")
        if os.path.exists(destination):
            tryRun(f"rm -r '{destination}'");
        tryRun(command)

def expandGlob(x):
    if not x:
        return []
    temp = glob.glob(x)
    if temp:
        return temp
    if os.path.exists(x):
        return [x]
    return [x]

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
    def __init__(self, source, destination, symlink):
        self.source = source
        self.destination = destination
        self.symlink = symlink

# Helper functions
def tryRun(x):
    if session.dryRun:
        print(f"[DRY RUN] {x}")
    else:
        os.system(x)

def listOrSingle(x):
    if type(x) is list:
        return x
    return [x]

def dictGet(dict, key, fallback):
    if key in dict:
        return dict[key]
    return fallback

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

def transferExpandGlobs(transfer):
    temp = []
    for source in expandGlob(transfer.source):
        for destination in expandGlob(transfer.destination):
            sourcePath = source;
            destinationPath = destination
            symlink = transfer.symlink and not config["force_no_symlinks"] or config["force_symlinks"]
            temp.append(Transfer(sourcePath, destinationPath, symlink))
    return temp

def transferProcessDests(transfer):
    source = transfer.source
    destination = transfer.destination
    if destination.endswith("/") or destination.endswith("\\"):
        destination = os.path.join(destination, os.path.basename(source))
    else:
        if os.path.isdir(destination):
            destination = os.path.join(destination, os.path.basename(source))
        else:
            destination = destination
    return Transfer(source, destination, transfer.symlink)

def execute(rawTransfer):
    transfers = transferExpandGlobs(rawTransfer)
    transfers = map(transferProcessDests, transfers)
    transfers = list(transfers)
    if session.verb == "load":
        for transfer in transfers:
            shell.Copy(transfer.source, transfer.destination, transfer.symlink);
            if session.verbose and not session.dryRun:
                print(f"Package item '{os.path.relpath(rawTransfer.source, packageRoot)}' loaded to '{transfer.destination}'...")
    elif session.verb == "pack":
        for transfer in transfers:
            shell.Copy(transfer.destination, transfer.source, False);
            if session.verbose and not session.dryRun:
                print(f"Packaed item '{transfer.destination}' as '{os.path.relpath(rawTransfer.source, packageRoot)}'...")
    elif session.verb == "lint":
        print(f"{os.path.relpath(rawTransfer.source, packageRoot)}")
        for transfer in transfers:
            print(f"- source:  {transfer.source}")
            print(f"  dest:    {transfer.destination}")
            print(f"  symlink: {transfer.symlink}")
        print()
    else:
        print(f"Invalid verb '{session.verb}'...")
        exit(1)

## Cross source (glob) paths with destination paths
for include in manifest.include:
    sourcePath = os.path.join(packageRoot, include["path"])
    sourcePath = shell.expandEnvironmentVariables(sourcePath)
    if "destination" in include:
        destinationOverride= include["destination"]
    else:
        destinationOverride = ""
    destinationOverride = shell.expandEnvironmentVariables(destinationOverride)
    if os.path.isabs(destinationOverride):
        destinationPath = destinationOverride
        transfer = Transfer(sourcePath, destinationPath, dictGet(include, "symlink", False))
        execute(transfer)
    else:
        for destination in destinations:
            destinationPath = os.path.join(destination, destinationOverride)
            transfer = Transfer(sourcePath, destinationPath, dictGet(include, "symlink", False))
            execute(transfer)

# Hack for console_scripts
def main():
    pass
