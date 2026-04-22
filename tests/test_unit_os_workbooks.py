import pytest

from bullstrangle_mcp.os_workbooks import round_to_increment


@pytest.mark.unit
def test_round_to_increment_handles_positive_and_negative_values():
    assert round_to_increment(3.9337, 0.5) == 4.0
    assert round_to_increment(-3.626, 0.5) == -3.5
    assert round_to_increment(-13.2803, 0.5) == -13.5


@pytest.mark.unit
def test_round_to_increment_rejects_non_positive_increment():
    with pytest.raises(ValueError, match="greater than zero"):
        round_to_increment(3.2, 0)
