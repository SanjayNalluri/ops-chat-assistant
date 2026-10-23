"""The grader must accept equivalent answers and reject wrong ones."""
from app.evaluate import results_match

GOLD = [("SP", 4.5), ("RJ", 12.2)]


def test_same_rows_any_order():
    assert results_match(GOLD, [("RJ", 12.2), ("SP", 4.5)])


def test_columns_swapped_and_extra_column():
    assert results_match(GOLD, [(4.5, "SP", 40334), (12.2, "RJ", 12291)])


def test_rounding_tolerance():
    assert results_match([(6.8,)], [(6.7987,)])


def test_wrong_value():
    assert not results_match([(6.8,)], [(0.068,)])            # fraction instead of percent


def test_wrong_row_count():
    assert not results_match(GOLD, [("SP", 4.5)])


def test_case_and_spaces_ignored():
    assert results_match([("sao paulo", 10)], [(" Sao Paulo", 10)])


def test_relabelled_groups_need_lenient_mode():
    gold = [(0, 4.29), (1, 2.27)]
    pred = [("On-time", 4.29), ("Late", 2.27)]
    assert not results_match(gold, pred)
    assert results_match(gold, pred, relabel=True)


def test_lenient_mode_still_checks_values():
    assert not results_match([(0, 4.29), (1, 2.27)], [("On-time", 4.0), ("Late", 2.27)], relabel=True)


def test_lenient_mode_not_used_for_single_row_answers():
    assert not results_match([("sao paulo", 14989)], [("rio de janeiro", 14989)], relabel=True)
