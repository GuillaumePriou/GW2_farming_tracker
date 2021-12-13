from string import printable

from hypothesis import strategies as st

from gw2_tracker import models


@st.composite
def inventories(draw, min_size=0, max_size=None):
    content = draw(
        st.dictionaries(
            keys=st.text(printable),
            values=st.integers(),
            min_size=min_size,
            max_size=max_size,
        )
    )
    return models.Inventory(content)
