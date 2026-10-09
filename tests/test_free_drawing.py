"""The free assets' drawing helpers (tools/free_assets/draw.py): what keeps
a character's rows in the TMS9918's two colours, and the facets."""

from game.free.png import Picture
from tools.free_assets.draw import (
    CLEAR, CYAN, DARK_BLUE, LIGHT_BLUE, RED, WHITE, Canvas, Chars, cube, shade, shared_edges, two_a_row,
)


def test_a_third_colour_in_a_row_becomes_the_nearer_of_the_two():
    picture = Picture(8, 1)
    for x, colour in enumerate([DARK_BLUE] * 4 + [WHITE] * 3 + [LIGHT_BLUE]):
        picture[x, 0] = colour
    two_a_row(Canvas(picture, 0, 0, 8, 1))
    assert [picture[x, 0] for x in range(8)] == [DARK_BLUE] * 4 + [WHITE] * 3 + [DARK_BLUE]


def test_a_character_drawn_keeps_two_colours_a_row():
    chars = Chars()
    chars.draw(0x80, "three", lambda c: (c.rect(0, 0, 3, 8, RED), c.rect(3, 0, 3, 8, CYAN)))
    canvas = chars.canvas(0x80, 0)
    for y in range(8):
        assert len({canvas.p[canvas.x0 + x, canvas.y0 + y] for x in range(8)}) <= 2


def test_faces_towards_the_light_take_the_lightest():
    ramp = (DARK_BLUE, LIGHT_BLUE, CYAN)
    upper_left = [(0, 0), (4, 0), (0, 4)]
    lower_right = [(16, 16), (12, 16), (16, 12)]
    assert shade(upper_left, ramp, (8, 8)) == CYAN
    assert shade(lower_right, ramp, (8, 8)) == DARK_BLUE


def test_a_cube_is_three_faces_that_meet_in_its_middle():
    faces = cube(8, 8, 6)
    assert len(faces) == 3
    assert all(face[0] == (8, 8) for face in faces)
    # Each face shares an edge with each other one: three cuts from the middle.
    assert len(shared_edges(faces)) == 3


def test_a_mesh_cuts_between_its_faces_but_not_its_outline():
    picture = Picture(16, 16)
    Canvas(picture, 0, 0, 16, 16).mesh([[(0, 0), (16, 0), (16, 16)], [(0, 0), (16, 16), (0, 16)]], WHITE)
    assert picture[8, 8] == CLEAR
    assert picture[1, 14] == WHITE and picture[14, 1] == WHITE
