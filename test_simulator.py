"""Invariant checks: python -m unittest -v."""
import unittest
from dataclasses import replace

from simulator import Config, Simulation, Order


class ModelTests(unittest.TestCase):
    def empty(self, **kwargs):
        sim = Simulation(Config(days=200, **kwargs))
        sim.events.clear()
        return sim

    def test_batch_not_sent_before_five(self):
        sim = self.empty(moscow_days=3)
        for _ in range(4):
            sim.purchase(0, 0, "Москва")
        self.assertEqual(len(sim.transit), 0)
        sim.purchase(0, 0, "Москва")
        self.assertEqual(len(sim.transit), 1)
        self.assertEqual(sim.transit[0]["count"], 5)
        sim.advance(2)
        self.assertEqual(len(sim.stock[0][0]), 0)
        sim.advance(3)
        self.assertEqual(len(sim.stock[0][0]), 5)

    def test_hanko_two_legs_and_reservation(self):
        sim = self.empty(hanko_days=4, moscow_days=3)
        for i in range(5):
            order = Order(i + 1, 0, 0, 0)
            sim.orders.append(order)
            sim.purchase(0, 0, "Ханко", order)
        sim.advance(4)
        self.assertTrue(all(o.delivered is None for o in sim.orders))
        sim.advance(7)
        self.assertTrue(all(o.delivered == 7 for o in sim.orders))
        self.assertEqual(len(sim.stock[0][0]), 0)

    def test_small_truck_serializes_single_car(self):
        sim = self.empty()
        for i in range(2):
            order = Order(i + 1, 1, 0, 0, "Другой салон", 10)
            sim.orders.append(order)
            sim.transfer(sim.new_car(1, 0, .9, order))
        sim.advance(2)
        self.assertEqual(sim.orders[0].delivered, 2)
        self.assertIsNone(sim.orders[1].delivered)
        sim.advance(4)
        self.assertEqual(sim.orders[1].delivered, 4)
        self.assertEqual(sim.transport_cost, 30_000)

    def test_stock_monthly_bill_and_fifo_reservation(self):
        sim = Simulation(Config(days=100, inventory_mode=True, initial=1))
        sim.events = [e for e in sim.events if e[2] == sim.storage_bill]
        import heapq
        heapq.heapify(sim.events)
        sim.advance(29)
        self.assertEqual(sim.storage_cost, 0)
        sim.advance(30)
        self.assertEqual(sim.storage_cost, 12_000)
        sim.contract(0, 0, .1, .1)
        sim.advance(60)
        self.assertEqual(sim.storage_cost, 18_000)
        self.assertEqual(sim.orders[0].source, "Свой салон")

    def test_rail_waits_for_twelve(self):
        sim = self.empty(rail=True, rail_days=2)
        for _ in range(11):
            sim.purchase(0, 0, "Москва")
        self.assertFalse(sim.transit)
        sim.purchase(0, 0, "Москва")
        self.assertEqual(sim.transit[0]["count"], 12)

    def test_prepayment_does_not_change_profit_or_demand(self):
        c = Config(days=365, prices=(3_000_000,), own_share=.5)
        a = Simulation(c).run()
        b = Simulation(replace(c, prepay=.5)).run()
        self.assertEqual(a.summary()["profit"], b.summary()["profit"])
        self.assertEqual([(o.created, o.source, o.delivered) for o in a.orders], [(o.created, o.source, o.delivered) for o in b.orders])
        self.assertLessEqual(b.capital_peak, a.capital_peak)

    def test_overdue_discount_and_unknown_prices(self):
        sim = self.empty(prices=(3_000_000,))
        order = Order(1, 0, 0, 0, "Москва", 30)
        sim.orders.append(order)
        sim.now = 35
        sim.deliver(sim.new_car(0, 0, .9, order))
        self.assertEqual(order.discount, 15_000)
        self.assertEqual(sim.revenue, 2_985_000)
        unknown = Simulation(Config(days=30, prices=(None,))).run().summary()
        self.assertIsNone(unknown["revenue"])
        self.assertIsNone(unknown["profit"])
        self.assertIsNone(unknown["capital"])

    def test_reproducibility_and_working_day(self):
        c = Config(days=40, work_hours=8)
        a, b = Simulation(c).run(), Simulation(c).run()
        self.assertEqual(a.summary(), b.summary())
        self.assertGreater(a.summary()["orders"], 0)
        self.assertLess(max(o.created for o in a.orders), c.days)

    def test_daily_visitors_random_in_each_showroom(self):
        sim = Simulation(Config(days=100)).run()
        self.assertTrue(all(1 <= count <= 10 for day in sim.daily_visitors for count in day))
        self.assertGreater(len({day[0] for day in sim.daily_visitors}), 1)
        self.assertTrue(any(a != b for a, b in sim.daily_visitors))
        self.assertEqual(sum(map(sum, sim.daily_visitors)), sim.summary()["visitors"])
        self.assertEqual(sim.c.prices, (2_500_000,))

    def test_fixed_range_and_invalid_bounds(self):
        sim = Simulation(Config(days=10, visitors_min=3, visitors_max=3)).run()
        self.assertEqual(sim.daily_visitors, [[3, 3]] * 10)
        with self.assertRaises(ValueError):
            Config(visitors_min=8, visitors_max=2).validate()

    def test_stock_pipeline_prevents_duplicate_replenishment(self):
        sim = self.empty(inventory_mode=True, replenish=True, reorder=0, target=3)
        sim.review_stock()
        self.assertEqual(sim.pipeline, [[3], [3]])
        sim.review_stock()
        self.assertEqual(sim.pipeline, [[3], [3]])

    def test_reserved_car_occupies_stock_until_dispatch(self):
        sim = self.empty(inventory_mode=True, initial=1)
        sim.truck_free[0] = 32
        sim.now = 29
        # Consume own stock first, then reserve the other showroom's car.
        sim.contract(0, 0, .1, .1)
        sim.contract(0, 0, .1, .1)
        self.assertEqual(sim.occupancy, [0, 1])
        self.assertFalse(sim.stock[1][0])
        self.assertEqual(sim.orders[1].source, "Другой салон")
        sim.advance(32)
        self.assertEqual(sim.occupancy, [0, 0])
        sim.advance(34)
        self.assertEqual(sim.orders[1].delivered, 34)


if __name__ == "__main__":
    unittest.main()
