"""A built executable starts with no `--rom`: `cartridge.find` looks for the dump
beside it, by SHA-1 and under any name. No cartridge ships here, so the blank
cartridge-shaped file stands in for it, with the SHA-1 it is known by pointed
at the blank's own."""

import hashlib

from game.rom import cartridge
from tests.cartridge_shape import Blank


def test_the_dump_is_found_by_its_bytes_not_its_name(tmp_path, monkeypatch):
    data = bytes(Blank().data)
    monkeypatch.setattr(cartridge, "SHA1", hashlib.sha1(data).hexdigest())
    (tmp_path / "a readme.txt").write_text("not a cartridge")
    (tmp_path / "another.rom").write_bytes(b"AB" + bytes(cartridge.SIZE - 2))
    (tmp_path / "Nemesis (Japan, Europe).mx1").write_bytes(data)
    assert cartridge.find([str(tmp_path / "missing"), str(tmp_path)]) == \
        str(tmp_path / "Nemesis (Japan, Europe).mx1")


def test_nothing_that_is_not_the_dump_is_taken(tmp_path):
    (tmp_path / "nemesis.rom").write_bytes(bytes(Blank().data))
    assert cartridge.find([str(tmp_path)]) is None
