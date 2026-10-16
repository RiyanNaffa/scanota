"""tests/unit/test_forecast.py – Unit tests for forecast policy and metrics."""
from __future__ import annotations

import math

import pytest

from app.forecast.metrics import bias, wape
from app.forecast.policy import (
    action,
    days_until_stockout,
    lead_time_weeks,
    order_quantity,
    reorder_point,
    safety_stock,
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
