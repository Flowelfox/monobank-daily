
from src.lib.helpers import format_money, group_buttons


class TestFormatMoney:
    def test_positive_amount(self):
        assert format_money(150000) == "1 500.00"

    def test_negative_amount(self):
        assert format_money(-150000) == "-1 500.00"

    def test_zero_amount(self):
        assert format_money(0) == "0.00"

    def test_small_amount(self):
        assert format_money(50) == "0.50"

    def test_large_amount(self):
        assert format_money(1000000000) == "10 000 000.00"


class TestGroupButtons:
    def test_group_by_two(self):
        buttons = [1, 2, 3, 4, 5]
        result = group_buttons(buttons, 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_group_by_three(self):
        buttons = [1, 2, 3, 4, 5, 6]
        result = group_buttons(buttons, 3)
        assert result == [[1, 2, 3], [4, 5, 6]]

    def test_group_by_one(self):
        buttons = [1, 2, 3]
        result = group_buttons(buttons, 1)
        assert result == [[1], [2], [3]]

    def test_empty_buttons(self):
        result = group_buttons([], 2)
        assert result == []

    def test_exact_division(self):
        buttons = [1, 2, 3, 4]
        result = group_buttons(buttons, 2)
        assert result == [[1, 2], [3, 4]]
