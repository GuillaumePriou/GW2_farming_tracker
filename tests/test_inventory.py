from gw2_tracker import inventory
import tempfile
from string import printable

from hypothesis import given, strategies as st

@given(st.dictionaries(keys=st.text(printable), values=st.integers()))
def test_inventory_serialization(content):
    inv = inventory.Inventory(items=content)
    with tempfile.NamedTemporaryFile(mode="wt+") as f:
        inv.save_to_file(f.name, "")
        f.seek(0)
        assert inv == inventory.Inventory.load_from_file(f.name, "")
