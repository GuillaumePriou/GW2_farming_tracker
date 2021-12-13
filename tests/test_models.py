import tempfile
from string import printable

from hypothesis import given
from hypothesis import strategies as st

from gw2_tracker import models

from . import strategies as more_st


@given(more_st.inventories())
def test_inventory_serialization(content):
    inv = models.Inventory(content)

    assert inv == models.Inventory.from_json(inv.to_json())

    with tempfile.TemporaryFile(mode="wt+") as f:
        inv.to_file(f)
        f.seek(0)
        assert inv == models.Inventory.from_file(f)


@given(st.text(printable), more_st.inventories(), more_st.inventories())
def test_snapshot_serialization(key, inventory, wallet):
    snap = models.Snapshot(key, inventory, wallet)

    assert snap == models.Snapshot.from_json(snap.to_json())

    with tempfile.TemporaryFile(mode="wt+") as f:
        snap.to_file(f)
        f.seek(0)
        assert snap == models.Snapshot.from_file(f)
