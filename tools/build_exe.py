"""Freeze the game into one executable, check it, and zip it.

    python tools/build_exe.py                        # this system, version off git
    python tools/build_exe.py --version 0.1.0        # ...or say it
    python tools/build_exe.py --with-rom <rom>       # + a private zip with the ROM
    python tools/build_exe.py --add-rom <zip> --rom <rom>   # the same, to a zip
                                                            # built elsewhere (CI)

Out comes `dist/nemesio-<version>-<system>-x64.zip`: one binary, the README and
the licence, **and no ROM**: that is the zip that can be published. The player drops their
own dump beside the binary under any name and `cartridge.find` knows it by its
SHA-1.

`--with-rom` / `--add-rom` make a second zip, `...-x64-with-rom.zip`, with the
ROM beside the binary: unzip and play, for handing to one person. It is never
built by the workflow and never leaves this machine except by hand -- the ROM
is not in the repo and is not given to GitHub (rule 3). A Windows binary can
only be built on Windows, so for that one: run the `release` workflow, download
its zip, and `--add-rom` it here.

**PyInstaller directly, and not `pyxel package` / `pyxel app2exe`**: Pyxel's
packager zips the whole app directory (`.venv/` included) and ships the
modules as data behind an import list scanned off the startup script alone. PyInstaller pointed at
`main.py` follows the real import graph.

With no cartridge the game plays the free assets (`assets/free`, none of it
the cartridge's): they go inside the binary, and beside it in the zip, where
a player can edit them -- the ones beside the binary win.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

NAME = "nemesio"
DIST = os.path.join(ROOT, "dist")

# Held out of the bundle. None of them is imported from `main.py`, so this is a
# guard: the tests and the harness's drawing libraries have no business in a
# player's download.
EXCLUDE = ("tests", "tools", "pytest", "numpy", "PIL")

# What the zip carries beside the binary.
EXTRAS = ("README.md", "LICENSE")
#: The free assets, in the binary and in the zip.
FREE_ASSETS = os.path.join("assets", "free")

FALLBACK_VERSION = "0.1.0-alpha"


def version() -> str:
    """The tag we are on, or the commit, or a stated fallback."""
    try:
        out = subprocess.run(["git", "describe", "--tags", "--always", "--dirty"],
                             cwd=ROOT, capture_output=True, text=True)
    except OSError:
        return FALLBACK_VERSION
    described = out.stdout.strip()
    if out.returncode != 0 or not described:
        return FALLBACK_VERSION
    return described.lstrip("v")


def system() -> str:
    """`windows` or `linux`. macOS is not built and is not refused -- untested."""
    return {"Windows": "windows", "Linux": "linux"}.get(
        platform.system(), platform.system().lower())


def binary() -> str:
    return os.path.join(DIST, NAME + (".exe" if system() == "windows" else ""))


def build() -> None:
    """Run PyInstaller. Raises `CalledProcessError` if it fails."""
    command = [sys.executable, "-m", "PyInstaller", "--onefile", "--clean",
               "--noconfirm", "--name", NAME, "--distpath", DIST,
               "--workpath", os.path.join(ROOT, "build"),
               "--specpath", os.path.join(ROOT, "build")]
    for module in EXCLUDE:
        command += ["--exclude-module", module]
    command += ["--add-data", "%s%s%s" % (os.path.join(ROOT, FREE_ASSETS), os.pathsep, FREE_ASSETS)]
    if system() == "windows":
        # No console window behind the game: Pyxel opens its own. With no ROM
        # found, `main.no_rom` says so in that window instead.
        command.append("--windowed")
    command.append(os.path.join(ROOT, "main.py"))
    print(" ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def selftest(rom: str | None) -> bool:
    """Ask the binary whether its bundle is whole: a play from the title to
    GAME OVER, of the ROM's or, without one (a build machine), of the free
    assets inside it."""
    command = [binary(), "--selftest"] + (["--rom", rom] if rom else [])
    print("---", " ".join(command))
    return subprocess.run(command, cwd=DIST).returncode == 0


def package(tag: str) -> str:
    """Zip the binary with the README and the licence. Returns the path."""
    path = os.path.join(DIST, "%s-%s-%s-x64.zip" % (NAME, tag, system()))
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(binary(), os.path.basename(binary()))
        for extra in EXTRAS:
            zf.write(os.path.join(ROOT, extra), extra)
        folder = os.path.join(ROOT, FREE_ASSETS)
        for name in sorted(os.listdir(folder)):
            zf.write(os.path.join(folder, name), os.path.join(FREE_ASSETS, name))
    return path


def add_rom(zip_path: str, rom: str) -> str:
    """A copy of `zip_path` with the ROM beside the binary. Returns its path.

    The ROM is checked first: a private zip with the wrong dump in it would be
    handed over and fail on somebody else's machine."""
    from game.rom.cartridge import Cartridge
    Cartridge.from_file(rom)
    stem = zip_path[:-len(".zip")] if zip_path.endswith(".zip") else zip_path
    path = stem + "-with-rom.zip"
    with zipfile.ZipFile(zip_path) as src, \
            zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            # `writestr` with the ZipInfo keeps the permission bits, so the
            # Linux binary stays executable once unzipped.
            dst.writestr(item, src.read(item.filename))
        dst.write(rom, "nemesis.rom")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--version", dest="tag", default=None,
                        help="version for the zip's name (default: git describe)")
    parser.add_argument("--with-rom", metavar="ROM", default=None,
                        help="also make a private zip with this ROM in it")
    parser.add_argument("--add-rom", metavar="ZIP", default=None,
                        help="only add --rom to an already built zip")
    parser.add_argument("--rom", default=None, help="the ROM, for --add-rom")
    parser.add_argument("--no-selftest", action="store_true",
                        help="skip running the built binary (don't)")
    args = parser.parse_args(argv)

    if args.add_rom:
        if not args.rom:
            parser.error("--add-rom needs --rom")
        print(add_rom(args.add_rom, args.rom))
        return 0

    tag = args.tag or version()
    shutil.rmtree(DIST, ignore_errors=True)
    build()
    if not args.no_selftest and not selftest(args.with_rom and os.path.abspath(args.with_rom)):
        print("selftest failed: the bundle is missing something. Not packaging.")
        return 1
    paths = [package(tag)]
    if args.with_rom:
        paths.append(add_rom(paths[0], args.with_rom))
    for path in paths:
        print("%s  (%.1f MB)" % (path, os.path.getsize(path) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
