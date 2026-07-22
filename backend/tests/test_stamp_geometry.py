"""Stamp geometry, and the contract that keeps two implementations in step.

``wallets/stamp_grid.py`` draws what Apple and Google actually render.
``frontend/dashboard/src/components/passGeometry.js`` reimplements the same
arithmetic so the merchant's design preview shows the real thing. Nothing in
the language stops those drifting, and a silent drift is the worst kind here —
the preview keeps looking right while the pass in the customer's phone does not.

So both sides assert against one generated fixture. This module is the
generator's source of truth; ``WalletPreview.test.jsx`` reads the same file.
Changing the geometry means regenerating the fixture, which shows up as a diff
in review rather than as a surprise on someone's lock screen.

Regenerate with::

    python -c "import json,pathlib,sys; sys.path.insert(0,'.'); \
from wallets.stamp_grid import stamp_geometry; ..."

or simply run this module's ``test_fixture_is_current`` and follow the failure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wallets.stamp_grid import (
    STAMP_FILL,
    STAMP_ICON_FILL,
    _pad_y_factor,
    stamp_geometry,
)

FIXTURE = Path(__file__).parent / "fixtures" / "stamp_geometry.json"
APPLE_STRIP = (1125, 369)
GOOGLE_HERO = (1032, 336)


def load_cases() -> list[dict]:
    return json.loads(FIXTURE.read_text())["cases"]


class TestFixtureContract:
    def test_fixture_matches_the_implementation(self):
        """The fixture is generated from this module — if they disagree, either
        the geometry changed without regenerating, or the fixture was hand-edited.
        Both are bugs, and both would let the preview drift from the pass."""
        for case in load_cases():
            actual = stamp_geometry(case["n"], case["layout"], tuple(case["size"]))
            expected = {k: case[k] for k in ("pitch", "radius", "ring", "icon_size")}
            assert {k: actual[k] for k in expected} == expected, (
                f"{case['size_name']} {case['layout']} n={case['n']}"
            )
            assert actual["centers"] == case["centers"]

    def test_fixture_covers_both_canvases_and_every_layout(self):
        cases = load_cases()
        assert {c["size_name"] for c in cases} == {"apple", "google"}
        assert {c["layout"] for c in cases} == {"grid", "columns", "stagger"}
        # Both sides of the one-row/two-row split, and the 15-stamp cap.
        assert {1, 5, 6, 15} <= {c["n"] for c in cases}


class TestSizing:
    def test_stamps_never_collide(self):
        """The invariant the fill factor exists to protect: a stamp's diameter
        must stay inside the pitch, or neighbouring circles overlap."""
        for case in load_cases():
            assert 2 * case["radius"] < case["pitch"], (
                f"{case['layout']} n={case['n']}: Ø{2 * case['radius']} ≥ pitch {case['pitch']}"
            )

    def test_stamps_stay_inside_the_canvas(self):
        for case in load_cases():
            w, h = case["size"]
            r = case["radius"]
            for point in case["centers"]:
                assert r <= point["x"] <= w - r
                assert r <= point["y"] <= h - r

    def test_fewer_stamps_are_never_smaller(self):
        """Monotonicity: adding a stamp may shrink the glyphs, never grow them.

        Not strict — a one-stamp and a three-stamp card are both limited by the
        strip height, so they legitimately draw the same size. Equal is fine;
        going *up* would mean the layout is fighting itself.
        """
        for layout in ("grid", "columns", "stagger"):
            radii = [
                stamp_geometry(n, layout, APPLE_STRIP)["radius"] for n in range(1, 16)
            ]
            assert radii == sorted(radii, reverse=True), f"{layout}: {radii}"

    @pytest.mark.parametrize(
        ("n", "minimum_fraction"),
        [(1, 0.60), (3, 0.60), (5, 0.40), (8, 0.30), (12, 0.30)],
    )
    def test_stamps_fill_a_useful_share_of_the_strip(self, n, minimum_fraction):
        """Guards the change these numbers were chosen for. The old geometry put
        a one-stamp card at 49% of strip height and every card from 6 to 12 at
        24% — small enough that a merchant's card read as mostly empty panel."""
        radius = stamp_geometry(n, "grid", APPLE_STRIP)["radius"]
        assert 2 * radius / APPLE_STRIP[1] >= minimum_fraction

    def test_single_row_gets_less_vertical_padding_than_two(self):
        """A single row has nothing above or below it; two rows need the gap."""
        assert _pad_y_factor(1) < _pad_y_factor(2)

    def test_fill_factor_cannot_overlap_by_construction(self):
        """Diameter is 2 × STAMP_FILL of the available space, so ≥ 0.5 would
        guarantee collisions regardless of layout."""
        assert STAMP_FILL < 0.5
        # Icons are square and read smaller than a disc, so they get slightly
        # more than the circle's diameter — but not unboundedly more.
        assert 2 * STAMP_FILL <= STAMP_ICON_FILL <= 1.0


class TestGeometryShape:
    def test_one_row_up_to_five_then_two(self):
        assert len({p["y"] for p in stamp_geometry(5, "grid", APPLE_STRIP)["centers"]}) == 1
        assert len({p["y"] for p in stamp_geometry(6, "grid", APPLE_STRIP)["centers"]}) == 2

    def test_grid_is_symmetric_about_the_centreline(self):
        centers = stamp_geometry(3, "grid", APPLE_STRIP)["centers"]
        assert centers[1]["x"] == pytest.approx(APPLE_STRIP[0] / 2, abs=1)

    def test_alternating_layouts_pack_tighter_so_stamps_shrink(self):
        grid = stamp_geometry(10, "grid", APPLE_STRIP)
        stagger = stamp_geometry(10, "stagger", APPLE_STRIP)
        assert stagger["pitch"] < grid["pitch"]
        assert stagger["radius"] <= grid["radius"]

    def test_count_is_capped_so_a_huge_card_does_not_render_dust(self):
        assert len(stamp_geometry(40, "grid", APPLE_STRIP)["centers"]) == 15

    def test_google_hero_is_computed_in_its_own_canvas(self):
        apple = stamp_geometry(8, "grid", APPLE_STRIP)
        google = stamp_geometry(8, "grid", GOOGLE_HERO)
        assert apple["radius"] != google["radius"]
