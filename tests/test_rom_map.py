"""tools/rom_map.py: the listing's layout and the code's citations, on a made-up bank."""

from tools.rom_map import Bank, Unit, citations, parse_bank

ASM = """\
\torg 0x08000
l9000h:\tequ 0x09000
DATA_tabla:
\tdefb 001h,002h,003h,004h\t; 8000
arranca:\t\t; empieza
\tld a,001h\t\t;8004
\tld (0e300h),a\t\t;8006   ; un comentario
sigue:
\tret\t\t;8009
\tdefb 0ffh,0ffh\t; 800a
"""

NOTES = """\
# notas
D 0x8000 0x8004 tabla  Cuatro bytes.
D 0x800A 0xA000 relleno  Relleno 0xFF.
"""


def _bank() -> Bank:
    return parse_bank(2, ASM, NOTES)


def test_routines_run_from_label_to_label_over_their_code():
    bank = _bank()
    code = [(u.name, u.start, u.end, u.size) for u in bank.units if u.kind == "code"]
    assert code == [("arranca", 0x8004, 0x8009, 5), ("sigue", 0x8009, 0x800A, 1)]
    assert len(bank.code_bytes) == 6


def test_data_ranges_come_from_the_notes_and_filler_is_named():
    data = [u for u in _bank().units if u.kind == "data"]
    assert [(u.name, u.size, u.filler) for u in data] == [
        ("tabla", 4, False), ("relleno", 0x2000 - 0xA, True)]


def test_a_bank_named_before_an_address_goes_first():
    [c] = citations("the walls (bank 5, 0x8004)", "x.py")
    assert c.candidates[0] == 5
    [c] = citations("0x8004 with nothing said", "x.py")
    assert c.candidates[0] == 2


def test_a_files_bank_map_gives_the_bank():
    text = "BANKS_X_BANKS = {0x8000: 11, 0xA000: 12}\nTABLE = 0x97DE\n"
    tables = [c for c in citations(text, "x.py") if c.address == 0x97DE]
    assert tables[0].candidates[:2] == [11, 2]


def test_ram_and_low_addresses_are_not_rom_citations():
    assert citations("0xE300 and 0x1800 and 0x20", "x.py") == []


def test_fits_is_an_instruction_a_label_or_inside_data():
    bank = _bank()
    assert bank.fits(0x8006) and bank.fits(0x8002)
    assert not bank.fits(0x8005)          # inside an instruction
    unit = bank.unit_at(0x8007)
    assert isinstance(unit, Unit) and unit.name == "arranca"


def test_routines_run_from_one_entry_to_the_next():
    asm = ("uno:\n\tcall tres\t\t;8000\ndos:\n\tret\t\t;8003\n"
           "tres:\n\tnop\t\t;8004\n\tret\t\t;8005\n\tdefb 0ffh\t; 8006\n")
    bank = parse_bank(2, asm, "", "0x8000   # p00:4000 call\n")
    assert [(r.name, r.start, r.size) for r in bank.routines] == [
        ("uno", 0x8000, 4), ("tres", 0x8004, 2)]
