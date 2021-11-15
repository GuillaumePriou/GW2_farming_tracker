from gw2_tracker import inventory
import tempfile
from string import printable

from hypothesis import given, strategies as st

@given(st.dictionaries(keys=st.text(printable), values=st.integers()))
def test_inventory_serialization(content):
    inv = inventory.Inventory(content)
    
    assert inv == inventory.Inventory(inv.to_json())

    with tempfile.TemporaryFile(mode="wt+") as f:
        inv.to_file(f)
        f.seek(0)
        assert inv == inventory.Inventory.from_file(f)
