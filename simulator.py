"""Discrete-event Subaru company model. No third-party dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import heapq
import math
import random
from typing import Callable


@dataclass
class Config:
    days: int = 365
    visitors_min: int = 1              # independent daily draw for each showroom
    visitors_max: int = 10
    seed: int = 2025
    models: tuple[str, ...] = ("Модель 1",)
    prices: tuple[float | None, ...] = (2_500_000,)
    inventory_mode: bool = False
    initial: int = 0                   # per model, per showroom
    reorder: int = 0
    target: int = 0
    replenish: bool = False
    stock_source: str = "Москва"
    prepay: float | None = None        # None = minimum 900,000 RUB
    own_share: float = 1.0             # among the baseline showroom's 60%
    moscow_days: float = 0.0
    hanko_days: float = 0.0
    moscow_cost: float = 90_000.0      # illustrative fee per full transporter trip
    hanko_cost: float = 150_000.0
    batch: int = 5
    small_trucks: int = 1
    rail: bool = False                 # Moscow -> showroom only
    rail_days: float = 0.0
    rail_cost: float = 180_000.0
    work_hours: float | None = None
    omitted: tuple[str, ...] = ()

    def validate(self):
        if self.days < 1 or not 1 <= self.visitors_min <= self.visitors_max <= 10:
            raise ValueError("Горизонт должен быть положительным; покупателей — от 1 до 10 в день.")
        if not self.models or len(self.models) != len(self.prices):
            raise ValueError("Укажите хотя бы одну модель.")
        if any(p is not None and (not math.isfinite(p) or p < 900_000) for p in self.prices):
            raise ValueError("Цена должна быть не меньше минимальной предоплаты 900 000 ₽.")
        if self.prepay is not None and not 0 < self.prepay <= 1:
            raise ValueError("Доля предоплаты должна быть от 0 до 100%.")
        if self.prepay is not None and any(p is not None and p * self.prepay < 900_000 for p in self.prices):
            raise ValueError("Выбранная доля даёт предоплату меньше 900 000 ₽. Увеличьте долю или цену.")
        if self.target < self.reorder or min(self.initial, self.target, self.reorder) < 0:
            raise ValueError("Запасы неотрицательны; целевой запас должен быть не ниже порога заказа.")
        if self.batch not in (5, 6) or self.small_trucks < 1:
            raise ValueError("Автовоз из Москвы: 5 или 6 машин; малых автовозов — не меньше одного.")
        if not 0 <= self.own_share <= 1:
            raise ValueError("Доля своего салона должна быть от 0 до 100%.")
        if any(x < 0 or not math.isfinite(x) for x in (self.moscow_days, self.hanko_days, self.moscow_cost, self.hanko_cost, self.rail_days, self.rail_cost)):
            raise ValueError("Сроки и расходы должны быть конечными неотрицательными числами.")
        if self.work_hours is not None and not 0 < self.work_hours <= 24:
            raise ValueError("Рабочий день: больше 0 и не больше 24 часов.")


@dataclass
class Order:
    number: int
    city: int
    model: int
    created: float
    source: str = ""
    deadline: float = 0
    delivered: float | None = None
    discount: float = 0
    payment: float = 0


@dataclass
class Car:
    number: int
    city: int
    model: int
    ratio: float
    order: Order | None = None
    entered: float = 0
    stocked: bool = False


class Simulation:
    def __init__(self, config: Config):
        config.validate()
        self.c = config
        self.rng = random.Random(config.seed)
        self.now = 0.0
        self.events: list[tuple[float, int, Callable, tuple]] = []
        self.seq = 0
        self.car_seq = 0
        self.orders: list[Order] = []
        self.stock = [[[] for _ in config.models] for _ in range(2)]
        self.pipeline = [[0 for _ in config.models] for _ in range(2)]
        self.moscow: list[list[Car]] = [[], []]
        self.hanko: list[list[Car]] = [[], []]
        self.transit: list[dict] = []
        self.truck_free = [0.0] * config.small_trucks
        self.manager_free = [0.0, 0.0]
        self.visitors = [0, 0]
        self.daily_visitors = [[0, 0] for _ in range(config.days)]
        self.work_minutes = [0.0, 0.0]
        self.routes = {"Свой салон": 0, "Другой салон": 0, "Москва": 0, "Ханко": 0}
        self.revenue = self.cogs = self.storage_cost = self.transport_cost = 0.0
        self.supplier_payments = {"Москва": 0.0, "Ханко": 0.0}
        self.initial_value = self.cash = self.capital_peak = 0.0
        self.cash_in = self.cash_out = 0.0
        self.stock_peak = [0, 0]
        self.occupancy = [0, 0]
        self.history: list[dict] = []
        self.log: list[dict] = []
        self.money_available = all(p is not None for p in config.prices)
        self.finished = False
        if config.inventory_mode:
            for city in range(2):
                for model, price in enumerate(config.prices):
                    for _ in range(config.initial):
                        ratio = .9 if config.stock_source == "Москва" else .8
                        car = self.new_car(city, model, ratio)
                        self.put_stock(car)
                        value = (price or 0) * ratio
                        self.initial_value += value
                        self.pay(value)
        for day in range(config.days):
            for city in range(2):
                # Paired demand streams stay identical between experimental policies.
                count = self.rng.randint(config.visitors_min, config.visitors_max)
                for _ in range(count):
                    arrival = day + self.rng.random()
                    duration = self.rng.uniform(30, 60)
                    buys = self.rng.random() < .1
                    model = self.rng.randrange(len(config.models))
                    source_draw = self.rng.random()
                    own_draw = self.rng.random()
                    self.schedule(arrival, self.visit, city, duration, buys, model, source_draw, own_draw)
            if config.inventory_mode and config.replenish:
                self.schedule(day, self.review_stock)
        self.snapshot()

    def schedule(self, at, fn, *args):
        self.seq += 1
        heapq.heappush(self.events, (at, self.seq, fn, args))

    def new_car(self, city, model, ratio, order=None):
        self.car_seq += 1
        return Car(self.car_seq, city, model, ratio, order)

    def add_log(self, event, detail):
        self.log.append({"day": round(self.now, 4), "event": event, "detail": detail})

    def pay(self, amount):
        self.cash -= amount
        self.cash_out += amount
        self.capital_peak = max(self.capital_peak, -self.cash)

    def receive(self, amount):
        self.cash += amount
        self.cash_in += amount

    def visit(self, city, duration, buys, model, draw, own_draw):
        self.visitors[city] += 1
        self.daily_visitors[int(self.now)][city] += 1
        self.work_minutes[city] += duration
        hours = self.c.work_hours
        # Calendar-day service if working schedule is unspecified. With hours,
        # time is in successive daily working windows (no weekends specified).
        start = max(self.now, self.manager_free[city])
        if hours is None:
            end = start + duration / 1440
        else:
            end = start + duration / (60 * hours)
        self.manager_free[city] = end
        if buys:
            self.schedule(end, self.contract, city, model, draw, own_draw)

    def contract(self, city, model, draw, own_draw):
        o = Order(len(self.orders) + 1, city, model, self.now)
        self.orders.append(o)
        price = self.c.prices[model]
        if price is not None:
            o.payment = 900_000 if self.c.prepay is None else price * self.c.prepay
            self.receive(o.payment)
        if not self.c.inventory_mode:
            # Statistical baseline: given source probabilities, without a physical stock.
            if draw < .6:
                o.source = "Свой салон" if own_draw < self.c.own_share else "Другой салон"
                o.deadline = self.now + 10
                ratio = .9 if self.c.stock_source == "Москва" else .8
                car = self.new_car(city, model, ratio, o)
                self.pay((price or 0) * ratio)
                if o.source == "Свой салон":
                    self.deliver(car)
                else:
                    self.transfer(car)
            else:
                self.purchase(city, model, "Москва" if draw < .7 else "Ханко", o)
        else:
            if self.stock[city][model]:
                car = self.take_stock(city, model)
                car.order = o
                o.source, o.deadline = "Свой салон", self.now + 10
                self.deliver(car)
            elif self.stock[1 - city][model]:
                car = self.take_stock(1 - city, model)
                car.order, car.city = o, city
                o.source, o.deadline = "Другой салон", self.now + 10
                self.transfer(car)
            else:
                # P(Moscow | no car in showrooms) = 10 / (10 + 30).
                self.purchase(city, model, "Москва" if draw < .25 else "Ханко", o)
        self.routes[o.source] += 1
        self.add_log("Договор", f"№{o.number}, салон {city + 1}, {self.c.models[model]}, {o.source}")

    def purchase(self, city, model, source, order=None):
        ratio = .9 if source == "Москва" else .8
        car = self.new_car(city, model, ratio, order)
        cost = (self.c.prices[model] or 0) * ratio
        self.pay(cost)
        self.supplier_payments[source] += cost
        if order is not None:
            order.source = source
            order.deadline = self.now + (30 if source == "Москва" else 90)
        else:
            self.pipeline[city][model] += 1
        queue = self.moscow if source == "Москва" else self.hanko
        queue[city].append(car)
        self.add_log("Закупка", f"{source}, салон {city + 1}, {self.c.models[model]}, " + (f"заказ №{order.number}" if order else "на склад"))
        if source == "Москва":
            self.dispatch_moscow(city)
        else:
            self.dispatch_hanko(city)

    def shipment(self, cars, origin, destination, days, fee, arrive):
        self.transport_cost += fee
        self.pay(fee)
        trip = {"origin": origin, "destination": destination, "start": self.now, "end": self.now + days, "count": len(cars)}
        self.transit.append(trip)
        def finish():
            self.transit.remove(trip)
            arrive(cars)
        self.schedule(self.now + days, finish)
        self.add_log("Отправка", f"{origin} → {destination}: {len(cars)} авто")

    def dispatch_hanko(self, city):
        while len(self.hanko[city]) >= 5:
            cars, self.hanko[city] = self.hanko[city][:5], self.hanko[city][5:]
            def arrived(items, city=city):
                self.moscow[city].extend(items)
                self.dispatch_moscow(city)
            self.shipment(cars, "Ханко", "Москва", self.c.hanko_days, self.c.hanko_cost, arrived)

    def dispatch_moscow(self, city):
        size = 12 if self.c.rail else self.c.batch
        while len(self.moscow[city]) >= size:
            cars, self.moscow[city] = self.moscow[city][:size], self.moscow[city][size:]
            self.shipment(cars, "Москва", f"Салон {city + 1}", self.c.rail_days if self.c.rail else self.c.moscow_days,
                          self.c.rail_cost if self.c.rail else self.c.moscow_cost, self.arrival)

    def transfer(self, car):
        index = min(range(len(self.truck_free)), key=self.truck_free.__getitem__)
        start = max(self.now, self.truck_free[index])
        self.truck_free[index] = start + 2
        origin_city = 1 - car.city
        def depart():
            self.leave_stock(car, origin_city)
            self.shipment([car], f"Салон {origin_city + 1}", f"Салон {car.city + 1}", 2, 15_000, self.arrival)
        self.schedule(start, depart)

    def arrival(self, cars):
        for car in cars:
            if car.order:
                self.deliver(car)
            else:
                self.pipeline[car.city][car.model] -= 1
                self.put_stock(car)

    def put_stock(self, car):
        car.entered, car.stocked = self.now, True
        self.stock[car.city][car.model].append(car)
        self.occupancy[car.city] += 1
        self.stock_peak[car.city] = max(self.stock_peak[car.city], self.occupancy[car.city])
        self.schedule(self.now + 30, self.storage_bill, car)

    def take_stock(self, city, model):
        car = self.stock[city][model].pop(0)
        return car

    def leave_stock(self, car, city=None):
        if car.stocked:
            self.occupancy[car.city if city is None else city] -= 1
            car.stocked = False

    def storage_bill(self, car):
        if car.stocked:
            self.storage_cost += 6_000
            self.pay(6_000)
            self.schedule(self.now + 30, self.storage_bill, car)

    def deliver(self, car):
        self.leave_stock(car)
        o = car.order
        o.delivered = self.now
        price = self.c.prices[o.model]
        # Continuous simulation: delay is counted in fractional days.
        if price is not None:
            o.discount = price * .001 * max(0, self.now - o.deadline)
            sale = price - o.discount
            self.revenue += sale
            self.cogs += price * car.ratio
            self.receive(sale - o.payment)
        self.add_log("Выдан", f"Заказ №{o.number}, срок {self.now - o.created:.2f} дн.")

    def review_stock(self):
        for city in range(2):
            for model in range(len(self.c.models)):
                position = len(self.stock[city][model]) + self.pipeline[city][model]
                if position <= self.c.reorder:
                    for _ in range(max(0, self.c.target - position)):
                        self.purchase(city, model, self.c.stock_source)

    def snapshot(self):
        summary = self.summary()
        day = max(0, min(self.c.days - 1, math.ceil(self.now) - 1))
        self.history.append({"day": self.now, "stock1": self.occupancy[0], "stock2": self.occupancy[1],
                             "visitors1": self.daily_visitors[day][0], "visitors2": self.daily_visitors[day][1],
                             "completed": summary["completed"], "pending": summary["pending"], "cash": self.cash,
                             "profit": self.revenue - self.cogs - self.storage_cost - self.transport_cost})

    def advance(self, until):
        until = min(until, self.c.days)
        while self.events and self.events[0][0] <= until:
            at, _, fn, args = heapq.heappop(self.events)
            self.now = at
            fn(*args)
        self.now = until
        self.finished = until >= self.c.days
        self.snapshot()

    def run(self):
        while not self.finished:
            self.advance(min(self.c.days, self.now + 1))
        return self

    def summary(self):
        done = [o for o in self.orders if o.delivered is not None]
        external = [o for o in done if o.source in ("Москва", "Ханко", "Другой салон")]
        pending = [o for o in self.orders if o.delivered is None]
        late = [o for o in self.orders if (o.delivered if o.delivered is not None else self.now) > o.deadline]
        def time_avg(items):
            return sum(o.delivered - o.created for o in items) / len(items) if items else None
        return {"day": self.now, "visitors": sum(self.visitors), "orders": len(self.orders), "completed": len(done),
                "pending": len(pending), "late": len(late), "completion_rate": len(done) / len(self.orders) if self.orders else None,
                "mean_delivery": time_avg(done), "mean_external": time_avg(external),
                "oldest_pending": max((self.now - o.created for o in pending), default=0),
                "revenue": self.revenue if self.money_available else None,
                "cogs": self.cogs if self.money_available else None,
                "profit": self.revenue - self.cogs - self.storage_cost - self.transport_cost if self.money_available else None,
                "storage": self.storage_cost if self.c.inventory_mode else None, "transport": self.transport_cost,
                "discount": sum(o.discount for o in done) if self.money_available else None,
                "capital": self.capital_peak if self.money_available else None,
                "cash": self.cash if self.money_available else None,
                "supplier_moscow": self.supplier_payments["Москва"] if self.money_available else None,
                "supplier_hanko": self.supplier_payments["Ханко"] if self.money_available else None,
                "initial_value": self.initial_value if self.money_available else None,
                "stock_peak1": self.stock_peak[0] if self.c.inventory_mode else None,
                "stock_peak2": self.stock_peak[1] if self.c.inventory_mode else None,
                "stock1": self.occupancy[0] if self.c.inventory_mode else None,
                "stock2": self.occupancy[1] if self.c.inventory_mode else None,
                "moscow_queue": sum(map(len, self.moscow)), "hanko_queue": sum(map(len, self.hanko)),
                "routes": dict(self.routes), "manager_minutes": list(self.work_minutes)}

    def limitations(self):
        notes = list(self.c.omitted)
        notes.append(f"Поток клиентов: каждый день отдельно для каждого салона равномерно выбирается целое число от {self.c.visitors_min} до {self.c.visitors_max}.")
        if not self.money_available:
            notes.append("Цены не заданы: выручка, прибыль, штрафы в рублях и оборотные средства не рассчитываются.")
        if not self.c.inventory_mode:
            notes.append("Базовый режим: источники выбираются с вероятностями 60/10/30. Физический склад не моделируется; размеры складов недоступны. Стоимость получаемой из салона машины учитывается при договоре по выбранному источнику закупки, история её хранения исключена.")
        else:
            notes.append("Режим запасов: наличие определяется реальным остатком. 60% — ориентир условия, а не принудительная вероятность; при отсутствии машины в обоих салонах вероятность Москвы = 10/(10+30) = 25%.")
        notes.extend([
            "Моменты прихода внутри дня и обслуживание 30–60 минут равномерны. Модели равновероятны, покупка с вероятностью 10%.",
            "Салоны формируют отдельные партии. Ханко → Москва: ровно 5; Москва → салон: выбранные 5 или 6. Ж/д заменяет только участок Москва → салон, отправка партиями по 12.",
            "Принятые правила реализации: немедленная выдача своей машины после договора; FIFO склада; осмотр запасов ежедневно; месяц хранения = 30 дней, 6 000 ₽ за каждый начавшийся платный месяц; штраф начисляется за дробные дни просрочки, для всех источников.",
            "Один менеджер в каждом салоне. Без рабочего дня обслуживание переводится в календарные дни (минуты/1440), ограничения расписания исключены. При указанном рабочем дне каждый календарный день считается рабочим.",
            "Малые автовозы — общий ресурс компании, каждый везёт одну машину за 2 дня. Обратный порожний рейс не задан и исключён. Число автовозов — параметр эксперимента. Ограничения парка остальных перевозчиков исключены.",
            "Прибыль = продажи после штрафов − себестоимость выданных автомобилей − хранение − заданные перевозки. Зарплаты, налоги, стоимость капитала и другие неуказанные статьи исключены. Непроданные машины остаются активом.",
            "Оборотные средства: максимум накопленного дефицита денежных средств, с начальной закупкой запасов и предоплатами. Выплаты поставщикам показаны отдельно. Общая касса компании; стартовый остаток денег = 0 для измерения потребности.",
            "Средний срок учитывает только выданные заказы; незавершённые и их максимальный возраст показаны отдельно. На конце горизонта симуляция останавливается, незаполненные партии остаются в очереди.",
        ])
        return notes


def experiment_configs(c: Config, kind: str, targets: list[int]):
    if kind == "stock":
        return [(f"Запас {n} / модель / салон", replace(c, inventory_mode=True, initial=n, target=n,
                                                       reorder=max(0, n - 1), replenish=n > 0)) for n in targets]
    if kind == "prepay":
        return [("Минимум 900 тыс. ₽", replace(c, prepay=None)), ("50% цены", replace(c, prepay=.5))]
    return [("Автовоз", replace(c, rail=False)), ("Железная дорога", replace(c, rail=True))]
