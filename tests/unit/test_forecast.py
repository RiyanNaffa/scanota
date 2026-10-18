"""tests/unit/test_forecast.py – Unit tests for forecast policy and metrics."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.forecast.metrics import bias, rmse, wape
from app.forecast.policy import (
    action,
    cap_order_for_shelf_life,
    days_until_stockout,
    lead_time_weeks,
    order_quantity,
    reorder_point,
    safety_stock,
    shelf_life_risk,
)


class TestWAPE:
    def test_perfect_forecast(self):
        assert wape([10, 20, 30], [10, 20, 30]) == 0.0

    def test_zero_actual(self):
        assert wape([0, 0, 0], [1, 2, 3]) == 0.0

    def test_basic_wape(self):
        # |10-8| + |20-25| + |30-27| = 2 + 5 + 3 = 10; sum(actual) = 60
        assert wape([10, 20, 30], [8, 25, 27]) == pytest.approx(10 / 60)

    def test_empty(self):
        assert wape([], []) == 0.0


class TestBias:
    def test_positive_bias(self):
        assert bias([10], [15]) == pytest.approx(5.0)

    def test_zero_bias(self):
        assert bias([10, 20], [10, 20]) == pytest.approx(0.0)


class TestLeadTimeWeeks:
    def test_seven_days(self):
        assert lead_time_weeks(7) == pytest.approx(1.0)

    def test_three_days(self):
        assert lead_time_weeks(3) == pytest.approx(3 / 7)


class TestSafetyStock:
    def test_zero_sigma(self):
        assert safety_stock(0.0, 1.0) == 0.0

    def test_zero_lt(self):
        assert safety_stock(5.0, 0.0) == 0.0

    def test_formula(self):
        # z=1.65, sigma=10, lt=1 week → 1.65 * 10 * sqrt(1) = 16.5
        assert safety_stock(10.0, 1.0, z=1.65) == pytest.approx(16.5)

    def test_fractional_lt(self):
        lt = 3 / 7  # 3 days
        result = safety_stock(10.0, lt, z=1.65)
        expected = 1.65 * 10 * math.sqrt(lt)
        assert result == pytest.approx(expected)


class TestReorderPoint:
    def test_basic(self):
        assert reorder_point(30.0, 15.0) == pytest.approx(45.0)


class TestOrderQuantity:
    def test_no_order_needed(self):
        # Lots of stock relative to demand
        qty = order_quantity(weekly_forecast=10, lt_weeks=1, ss=5, current_stock=100)
        assert qty == 0

    def test_order_needed(self):
        # weekly=10, lt=1, review=1, ss=5 → target = 10*(1+1)+5 = 25; current=0 → 25
        qty = order_quantity(weekly_forecast=10, lt_weeks=1, ss=5, current_stock=0)
        assert qty == 25

    def test_rounds_up(self):
        # qty = 25.3 → ceil = 26
        qty = order_quantity(weekly_forecast=10, lt_weeks=1, ss=5.3, current_stock=0)
        assert qty == math.ceil(10 * 2 + 5.3)

    def test_zero_demand(self):
        qty = order_quantity(weekly_forecast=0, lt_weeks=1, ss=0, current_stock=10)
        assert qty == 0


class TestDaysUntilStockout:
    def test_zero_forecast(self):
        assert days_until_stockout(100, 0) == float("inf")

    def test_basic(self):
        # 70 units / (10 units/week / 7 days/week) = 49 days
        assert days_until_stockout(70, 10) == pytest.approx(49.0)

    def test_zero_stock(self):
        assert days_until_stockout(0, 10) == pytest.approx(0.0)


class TestAction:
    def test_order_now(self):
        assert action(current_stock=5, rop=10) == "order_now"

    def test_watch(self):
        # stock = 12, rop = 10, 1.5*rop = 15 → 10 < 12 < 15 → watch
        assert action(current_stock=12, rop=10) == "watch"

    def test_ok(self):
        assert action(current_stock=100, rop=10) == "ok"

    def test_exactly_at_rop(self):
        assert action(current_stock=10, rop=10) == "order_now"


class TestRMSE:
    def test_perfect_forecast_is_zero(self):
        assert rmse([1, 2, 3], [1, 2, 3]) == 0.0

    def test_alternating_errors_keep_their_size(self):
        """Errors of +3, -3, +3, -3: the spread of |error| is 0, the typical error is 3."""
        actual = [10, 10, 10, 10]
        forecast = [13, 7, 13, 7]
        assert float(np.std(np.abs(np.subtract(forecast, actual)))) == 0.0  # the old sigma
        assert rmse(actual, forecast) == pytest.approx(3.0)

    def test_constant_bias_counts(self):
        """A forecast that is always 2 too high is a 2-unit error, not a 0-unit one."""
        assert rmse([5, 5, 5], [7, 7, 7]) == pytest.approx(2.0)

    def test_matches_definition(self):
        errors = np.array([1.0, -2.0, 3.0, 0.0])
        assert rmse(errors + 10, np.full(4, 10.0) + 0) == pytest.approx(
            math.sqrt(np.mean(errors**2))
        )

    def test_empty_is_zero(self):
        assert rmse([], []) == 0.0

    def test_accepts_arrays_and_lists(self):
        assert rmse(np.array([0.0, 4.0]), [2.0, 2.0]) == pytest.approx(2.0)


class TestShelfLifeRisk:
    def test_no_shelf_life_means_no_risk(self):
        assert shelf_life_risk(1000, 1, None) is None

    def test_stock_that_outlasts_the_shelf_life_is_high_risk(self):
        # 70 units at 7 per week = 10 weeks = 70 days of cover, against a 60-day shelf life
        assert shelf_life_risk(70, 7, 60) == "high"

    def test_stock_close_to_the_shelf_life_is_watch(self):
        # 49 days of cover against 60 days: above 70 % (42 days), below 100 %
        assert shelf_life_risk(49, 7, 60) == "watch"

    def test_stock_that_sells_well_inside_the_shelf_life_is_fine(self):
        assert shelf_life_risk(21, 7, 60) is None  # 21 days of cover

    def test_stock_with_no_demand_never_sells(self):
        assert shelf_life_risk(5, 0, 90) == "high"

    def test_empty_shelf_has_nothing_to_spoil(self):
        assert shelf_life_risk(0, 5, 90) is None


class TestCapOrderForShelfLife:
    def test_unchanged_without_shelf_life(self):
        assert cap_order_for_shelf_life(500, 10, 7, None) == 500

    def test_capped_to_what_can_sell_before_it_spoils(self):
        # 7 per week for 90 days sells 90 units; 30 are already on hand
        assert cap_order_for_shelf_life(500, 30, 7, 90) == 60

    def test_small_orders_pass_through(self):
        assert cap_order_for_shelf_life(20, 30, 7, 90) == 20

    def test_never_negative_when_stock_already_exceeds_the_sellable_amount(self):
        assert cap_order_for_shelf_life(50, 200, 7, 90) == 0


class TestRestockTextLanguage:
    def test_reason_in_indonesian_by_default(self):
        from app.forecast.policy import restock_reason

        text = restock_reason("Semen", 50, "sak", 7.0, 49.0, 3)
        assert (
            text
            == "Stok 50 sak, perkiraan laku 7.0 sak/minggu, habis sekitar 49 hari. Lead time 3 hari."
        )

    def test_reason_in_english(self):
        from app.forecast.policy import restock_reason

        text = restock_reason("Semen", 50, "sak", 7.0, 49.0, 3, lang="en")
        assert (
            text
            == "Stock 50 sak, expected to sell 7.0 sak/week, runs out in about 49 days. Lead time 3 days."
        )

    def test_reason_with_no_demand_in_both_languages(self):
        from app.forecast.policy import restock_reason

        inf = float("inf")
        assert "tidak terhitung" in restock_reason("x", 5, "pcs", 0.0, inf, 2)
        assert "not computable" in restock_reason("x", 5, "pcs", 0.0, inf, 2, lang="en")

    def test_shelf_life_note_in_english(self):
        from app.forecast.service import shelf_life_note

        high = shelf_life_note("high", 120.0, 90, "en")
        assert high == (
            "Stock covers about 120 days, longer than the 90-day shelf life: expiry risk. "
            "Hold purchases and sell the old stock first."
        )
        assert "never sells" in shelf_life_note("high", float("inf"), 90, "en")
        assert "close to the 90-day shelf life" in shelf_life_note("watch", 70.0, 90, "en")
