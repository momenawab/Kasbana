"""Tests for stamp layouts — how the stamps are arranged in the strip/hero.

``grid`` is the historical row-major arrangement (6 stamps → 0,1,2 on top, 3,4,5
below). ``columns`` alternates down the rows instead (0,2,4 on top, 1,3,5 below),
and ``stagger`` does the same but offsets the lower row half a cell into a zigzag.

Covers the pure geometry, that the arrangement survives into real pixels, that an
unset design still renders exactly what it always did, the API round-trip, and the
Google hero cache key (a layout change MUST produce a new filename).
"""

from __future__ import annotations

import pytest

from wallets import stamp_grid
from wallets.models import WalletCardDesign
from wallets.stamp_grid import (
    LAYOUT_COLUMNS,
    LAYOUT_GRID,
    LAYOUT_STAGGER,
    render_stamp_grid,
)

BG, FG = (20, 20, 30), (250, 200, 90)
SIZE = (1125, 369)


def _centers(n: int, layout: str):
    """The pure geometry for an n-stamp card at the Apple strip size."""
    w, h = SIZE
    rows = 1 if n <= 5 else 2
    cols = (n + rows - 1) // rows
    pad_x, pad_y = int(w * 0.06), int(h * 0.14)
    cell_w = (w - 2 * pad_x) / cols
    cell_h = (h - 2 * pad_y) / rows
    pts, _pitch = stamp_grid._centers(n, rows, cols, w, pad_x, pad_y, cell_w, cell_h, layout)
    return pts


def _rows_of(pts):
    """Group stamp indices by their y (row), top row first."""
    ys = sorted({round(y, 3) for _x, y in pts})
    return [[i for i, (_x, y) in enumerate(pts) if round(y, 3) == y_val] for y_val in ys]


# ── Geometry ──────────────────────────────────────────────────────────────────
def test_grid_is_row_major():
    """The default: 6 stamps fill across the top row, then across the bottom."""
    assert _rows_of(_centers(6, LAYOUT_GRID)) == [[0, 1, 2], [3, 4, 5]]


@pytest.mark.parametrize("layout", [LAYOUT_COLUMNS, LAYOUT_STAGGER])
def test_alternating_layouts_put_even_stamps_on_top(layout):
    """The thing that was actually asked for: 0,2,4 on top and 1,3,5 below."""
    assert _rows_of(_centers(6, layout)) == [[0, 2, 4], [1, 3, 5]]


@pytest.mark.parametrize("layout", [LAYOUT_COLUMNS, LAYOUT_STAGGER])
def test_an_odd_count_puts_the_extra_stamp_on_top(layout):
    """Mirrored by stampRows() in the dashboard preview — keep the two in step."""
    assert _rows_of(_centers(7, layout)) == [[0, 2, 4, 6], [1, 3, 5]]


def test_columns_keeps_the_rows_aligned():
    """``columns`` re-numbers the grid but does not move it — columns stay square."""
    pts = _centers(6, LAYOUT_COLUMNS)
    # stamps 0/1, 2/3, 4/5 are column pairs and must share an x
    for top, bottom in ((0, 1), (2, 3), (4, 5)):
        assert pts[top][0] == pytest.approx(pts[bottom][0])


def test_stagger_offsets_the_lower_row_by_half_a_cell():
    """``stagger`` is ``columns`` plus the horizontal shift — that IS the zigzag."""
    pts = _centers(6, LAYOUT_STAGGER)
    pitch = pts[2][0] - pts[0][0]  # same-row neighbours are one pitch apart
    for top, bottom in ((0, 1), (2, 3), (4, 5)):
        assert pts[bottom][0] - pts[top][0] == pytest.approx(pitch / 2)


def test_stagger_stays_inside_the_panel():
    """The offset row sticks out furthest right; it must not fall off the strip."""
    pts = _centers(6, LAYOUT_STAGGER)
    xs = [x for x, _y in pts]
    left, right = min(xs), SIZE[0] - max(xs)
    assert left > 0 and right > 0
    assert left == pytest.approx(right, abs=2)  # and the whole set is centred


def test_a_single_row_ignores_the_layout():
    """<=5 stamps is one row — there is nothing to alternate or offset."""
    for layout in (LAYOUT_GRID, LAYOUT_COLUMNS, LAYOUT_STAGGER):
        assert _rows_of(_centers(5, layout)) == [[0, 1, 2, 3, 4]]


def test_unknown_layout_falls_back_to_grid():
    """Blank/garbage must not blow up — it renders today's grid."""
    for value in ("", "nonsense"):
        assert _centers(6, value) == _centers(6, LAYOUT_GRID)


# ── Pixels — the arrangement has to survive into the actual image ─────────────
def _filled_indices(img, pts):
    """Which stamps rendered SOLID. A filled stamp has fg at its centre; a
    remaining one is an outline ring, so its centre is still background."""
    px = img.convert("RGB").load()
    return [i for i, (x, y) in enumerate(pts) if px[int(x), int(y)] == FG]


@pytest.mark.parametrize(
    ("layout", "expected_top"),
    [(LAYOUT_GRID, [0, 1, 2]), (LAYOUT_COLUMNS, [0, 2, 4]), (LAYOUT_STAGGER, [0, 2, 4])],
)
def test_earned_stamps_render_solid_in_the_right_cells(layout, expected_top):
    """3 of 6 earned → stamps 0,1,2 are solid, wherever the layout puts them."""
    img = render_stamp_grid(3, 6, BG, FG, SIZE, layout=layout)
    pts = _centers(6, layout)
    assert _filled_indices(img, pts) == [0, 1, 2]
    assert _rows_of(pts)[0] == expected_top


def test_default_render_is_unchanged():
    """An unset design must render pixel-for-pixel what it did before layouts."""
    explicit = render_stamp_grid(3, 6, BG, FG, SIZE, layout=LAYOUT_GRID)
    implicit = render_stamp_grid(3, 6, BG, FG, SIZE)  # no layout arg at all
    assert explicit.tobytes() == implicit.tobytes()


def test_the_layouts_actually_differ():
    """Guard against a no-op: the three must not collapse to the same image."""
    imgs = {
        layout: render_stamp_grid(3, 6, BG, FG, SIZE, layout=layout).tobytes()
        for layout in (LAYOUT_GRID, LAYOUT_COLUMNS, LAYOUT_STAGGER)
    }
    assert len(set(imgs.values())) == 3


# ── Model / hero cache ────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_design_persists_a_layout(card, merchant):
    design = WalletCardDesign.objects.create(
        card=card, merchant=merchant, stamp_layout=LAYOUT_STAGGER
    )
    design.refresh_from_db()
    assert design.stamp_layout == LAYOUT_STAGGER


@pytest.mark.django_db
def test_layout_defaults_to_blank_meaning_grid(card, merchant):
    """Blank = default: an existing design keeps today's behavior untouched."""
    design = WalletCardDesign.objects.create(card=card, merchant=merchant)
    assert design.stamp_layout == ""


@pytest.mark.django_db
def test_changing_the_layout_busts_the_google_hero_cache(card, merchant, customer_card):
    """The hero PNG is content-addressed. If the layout were left out of that
    fingerprint the new arrangement would hash to the SAME filename and Google
    would keep serving the stale image — the edit would look like a no-op."""
    from core.enums import CardType
    from wallets.google import hero

    card.type = CardType.STAMP
    card.stamps_required = 6
    card.save()
    design = WalletCardDesign.objects.create(card=card, merchant=merchant, google_stamp_hero=True)

    first = hero.stamp_hero_url(customer_card)
    design.stamp_layout = LAYOUT_STAGGER
    design.save()
    second = hero.stamp_hero_url(customer_card)

    assert first and second
    assert first != second
