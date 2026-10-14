"""Run with: python main.py"""
from __future__ import annotations

from dataclasses import asdict
import csv
import html
import json
from pathlib import Path
import statistics
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser

from simulator import Config, Simulation, experiment_configs

from ui_components import BG, PANEL, TEXT, MUTED, ACCENT, BLUE, ORANGE, BORDER, Button, MetricCard, ProgressStrip, rounded


def num(value, suffix="", digits=0):
    if value is None:
        return "нет данных"
    return f"{value:,.{digits}f}".replace(",", " ") + suffix


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Subaru · Имитационная модель компании · 2025_А5")
        self.geometry("1450x930")
        self.minsize(1100, 850)
        self.configure(bg=BG)
        self.sim = None
        self.running = False
        self.generation = 0
        self.experiment_rows = []
        self.experiment_meta = None
        self.results_queue = queue.Queue()
        self.vars = {}
        self.style_setup()
        self.build()
        self.after(100, self.poll)
        self.draw_empty()

    def style_setup(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=PANEL, foreground=TEXT, font=("Segoe UI", 10), borderwidth=0)
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("TLabel", background=PANEL)
        s.configure("TButton", padding=(12, 8), background="#1c2940", relief="flat", borderwidth=0)
        s.map("TButton", background=[("active", "#273650")])
        s.configure("TEntry", fieldbackground="#0e1728", foreground=TEXT, insertcolor=TEXT,
                    padding=(10, 7), bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        s.map("TEntry", bordercolor=[("focus", BLUE)], lightcolor=[("focus", BLUE)], darkcolor=[("focus", BLUE)])
        s.configure("TCombobox", fieldbackground="#0e1728", foreground=TEXT,
                    padding=(10, 7), arrowcolor=MUTED, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        s.map("TCombobox", fieldbackground=[("readonly", "#0e1728")], foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", "#0e1728")], selectforeground=[("readonly", TEXT)])
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", "#30496e")
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                    rowheight=34, borderwidth=0, font=("Segoe UI", 10))
        s.map("Treeview", background=[("selected", "#29466b")], foreground=[("selected", TEXT)])
        s.configure("Treeview.Heading", background="#1b2940", foreground=MUTED,
                    relief="flat", padding=(10, 10), font=("Segoe UI", 9, "bold"))
        s.configure("TNotebook", background=BG, borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG, tabmargins=(0, 0, 0, 10))
        s.configure("TNotebook.Tab", padding=(18, 10), background=BG, foreground=MUTED, borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        s.map("TNotebook.Tab", background=[("selected", "#23334f"), ("active", PANEL)],
              foreground=[("selected", TEXT), ("active", TEXT)],
              lightcolor=[("selected", "#23334f")], darkcolor=[("selected", "#23334f")])
        s.configure("TCheckbutton", background=PANEL, padding=(0, 5))
        s.map("TCheckbutton", background=[("active", PANEL)])
        s.configure("TProgressbar", background=ACCENT, troughcolor="#1d2b43", borderwidth=0, thickness=4)
        s.configure("Vertical.TScrollbar", background="#31425e", troughcolor=PANEL,
                    arrowcolor=MUTED, borderwidth=0, arrowsize=10, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)

    def build(self):
        self.settings_groups = {}
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=22, pady=(11, 12))
        badge = tk.Canvas(header, width=45, height=45, bg=BG, highlightthickness=0)
        badge.pack(side="left", padx=(0, 12))
        rounded(badge, 1, 1, 44, 44, 12, fill="#2e4c87", outline="")
        badge.create_text(22, 22, text="S", fill=TEXT, font=("Segoe UI", 23, "bold"))
        title = tk.Frame(header, bg=BG)
        title.pack(side="left")
        tk.Label(title, text="Subaru", fg=TEXT, bg=BG, font=("Segoe UI", 23, "bold")).pack(anchor="w")
        tk.Label(title, text="Симуляция автосалонов", fg=MUTED, bg=BG, font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(header, text="2025_А5  /  Модель компании", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="right")
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        sidebar = tk.Frame(body, bg=PANEL, width=305)
        body.add(sidebar, weight=0)
        tk.Label(sidebar, text="Настройки", bg=PANEL, fg=TEXT, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(17, 2))
        tk.Label(sidebar, text="Параметры следующего запуска", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 12))
        footer = tk.Frame(sidebar, bg=PANEL, padx=13, pady=12)
        footer.pack(side="bottom", fill="x")
        Button(footer, "Применить и сбросить", self.reset, primary=True, bg=PANEL).pack(fill="x")
        sc = tk.Canvas(sidebar, bg=PANEL, width=305, highlightthickness=0)
        scroll = ttk.Scrollbar(sidebar, orient="vertical", command=sc.yview)
        sc.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        sc.pack(side="left", fill="both", expand=True)
        inputs = tk.Frame(sc, bg=PANEL, padx=13, pady=2)
        win = sc.create_window(0, 0, window=inputs, anchor="nw")
        inputs.bind("<Configure>", lambda _: sc.configure(scrollregion=sc.bbox("all")))
        sc.bind("<Configure>", lambda e: sc.itemconfigure(win, width=e.width))
        sc.bind("<Enter>", lambda _: sc.bind_all("<MouseWheel>", lambda e: sc.yview_scroll(-int(e.delta / 120), "units")))
        sc.bind("<Leave>", lambda _: sc.unbind_all("<MouseWheel>"))
        self.section(inputs, "ЭКСПЕРИМЕНТ")
        self.field(inputs, "days", "Горизонт, дней", "365")
        self.field(inputs, "visitors_min", "Случайный поток: минимум / день", "1")
        self.field(inputs, "visitors_max", "Случайный поток: максимум / день", "10")
        self.hint(inputs, "Каждый день в каждом салоне независимо выбирается случайное целое число посетителей в этом диапазоне.")
        self.field(inputs, "seed", "Начальное число генератора", "2025")
        self.field(inputs, "speed", "Дней за кадр", "1")
        self.field(inputs, "mode", "Режим наличия автомобилей", "Фактические запасы", ["Вероятности 60/10/30", "Фактические запасы"])
        self.hint(inputs, "Базовый режим воспроизводит доли условия. Для оценки складов включите фактические запасы.")
        self.section(inputs, "МОДЕЛИ И ПРЕДОПЛАТА")
        ttk.Label(self.field_target(inputs), text="Модели: по одной строке, название; цена").pack(anchor="w")
        self.models_box = tk.Text(self.field_target(inputs), height=3, padx=10, pady=8, bg="#0e1728", fg=TEXT, insertbackground=TEXT, font=("Segoe UI", 10), relief="flat", wrap="none")
        self.models_box.pack(fill="x", pady=(4, 5))
        self.models_box.insert("1.0", "Модель 1; 2500000")
        self.hint(inputs, "Условное имя можно заменить. Цена необязательна; без цен денежные итоги недоступны. Спрос равновероятный.")
        self.field(inputs, "prepay_mode", "Предоплата", "900 тыс. ₽", ["900 тыс. ₽", "% от цены"])
        self.field(inputs, "prepay_percent", "Доля, % (если выбран процент)", "50")
        self.section(inputs, "СКЛАД И ПОПОЛНЕНИЕ")
        self.field(inputs, "initial", "Начальный запас / модель / салон", "8")
        self.check(inputs, "replenish", "Заказывать автомобили на склад", True)
        self.field(inputs, "reorder", "Порог заказа / модель / салон", "7")
        self.field(inputs, "target", "Целевой запас / модель / салон", "8")
        self.field(inputs, "stock_source", "Источник закупки на склад", "Ханко", ["Москва", "Ханко"])
        self.field(inputs, "own_share", "Из салонных 60%: в своём салоне, %", "100")
        self.hint(inputs, "Доля своего салона — настройка базового режима. В режиме запасов сначала проверяется свой склад, затем другой.")
        self.section(inputs, "ПЕРЕВОЗКИ")
        self.field(inputs, "batch", "Партия Москва → салон", "5", ["5", "6"])
        self.field(inputs, "small_trucks", "Малых автовозов в эксперименте", "1")
        self.hint(inputs, "Перегон: 1 авто, 2 дня, 15 000 ₽. Ханко → Москва: партии по 5. Партии каждого салона отдельные.")
        self.field(inputs, "moscow_days", "Москва → салон, дней (необяз.)", "")
        self.field(inputs, "moscow_cost", "Цена рейса Москва → салон, ₽", "90000")
        self.field(inputs, "hanko_days", "Ханко → Москва, дней (необяз.)", "")
        self.field(inputs, "hanko_cost", "Цена рейса Ханко → Москва, ₽", "150000")
        self.check(inputs, "rail", "Ж/д Москва → салон (партия 12)", False)
        self.field(inputs, "rail_days", "Ж/д: время рейса, дней (необяз.)", "")
        self.field(inputs, "rail_cost", "Ж/д: цена рейса, ₽", "180000")
        self.hint(inputs, "Цены рейсов примерные: 90 / 150 / 180 тыс. ₽. Их можно изменить для своего эксперимента.")
        self.field(inputs, "work_hours", "Рабочий день, часов (необяз.)", "")
        self.hint(inputs, "Пустые поля исключают соответствующие сроки, расходы или ограничения расписания. Ожидание набора партии учитывается всегда.")
        self.section(inputs, "СРАВНЕНИЕ СЦЕНАРИЕВ")
        self.field(inputs, "replications", "Повторов на сценарий", "1")
        self.field(inputs, "targets", "Проверяемые запасы (через запятую)", "0, 5, 8, 10")
        for text, kind in [("Сравнить стратегии склада", "stock"), ("Предоплата: минимум / 50%", "prepay"), ("Автовоз / железная дорога", "rail")]:
            Button(self.field_target(inputs), text=text, bg=PANEL, small=True, command=lambda k=kind: self.start_experiment(k)).pack(fill="x", pady=3)
        Button(self.field_target(inputs), text="Сохранить настройки", bg=PANEL, small=True, command=self.save_config).pack(fill="x", pady=(12, 3))
        Button(self.field_target(inputs), text="Загрузить настройки", bg=PANEL, small=True, command=self.load_config).pack(fill="x", pady=3)
        right = tk.Frame(body, bg=BG, padx=16)
        body.add(right, weight=1)
        toolbar_title = tk.Frame(right, bg=BG)
        toolbar_title.pack(fill="x", pady=(0, 8))
        tk.Label(toolbar_title, text="Обзор компании", bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(side="left")
        Button(toolbar_title, "Отчёт HTML  ↗", self.export_report, small=True).pack(side="right")
        Button(toolbar_title, "Экспорт CSV", self.export_csv, small=True).pack(side="right", padx=(0, 8))
        controls = tk.Frame(right, bg=BG)
        controls.pack(fill="x", pady=(0, 11))
        for text, command, primary in [("▶  Запустить", self.start, True), ("Ⅱ  Пауза", self.pause, False),
                                       ("+ День", self.step, False), ("До конца  →", self.finish, False), ("↻  Сброс", self.reset, False)]:
            Button(controls, text, command, primary=primary).pack(side="left", padx=(0, 7))
        self.day_label = tk.StringVar(value="День 0 / 365")
        tk.Label(controls, textvariable=self.day_label, bg=BG, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(side="right")
        self.status = tk.StringVar(value="Готово к запуску · цена автомобиля 2,5 млн ₽ · случайный поток 1–10 клиентов")
        tk.Label(right, textvariable=self.status, bg=BG, fg=MUTED, anchor="w", font=("Segoe UI", 9), wraplength=950).pack(fill="x", pady=(0, 9))
        self.progress = ProgressStrip(right)
        self.progress.pack(fill="x", pady=(0, 15))
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.visual_tab = ttk.Frame(self.tabs)
        self.orders_tab = ttk.Frame(self.tabs)
        self.exp_tab = ttk.Frame(self.tabs)
        self.notes_tab = ttk.Frame(self.tabs)
        for panel, title in [(self.visual_tab, "Обзор"), (self.orders_tab, "Заказы"), (self.exp_tab, "Эксперименты"), (self.notes_tab, "О модели")]:
            self.tabs.add(panel, text=title)
        metrics = tk.Frame(self.visual_tab, bg=BG)
        metrics.pack(fill="x", pady=(0, 8))
        self.metric_labels = {}
        cards = [("completed", "Выданные заказы", "Выдано / заключено договоров", ACCENT, "✓"),
                 ("pending", "Ожидание и просрочка", "Ожидают / просрочены", ORANGE, "clock"),
                 ("mean_external", "Среднее время заказа", "Без наличия в своём салоне, дни", BLUE, "→"),
                 ("profit", "Прибыль", "По учтённым статьям, ₽", ACCENT, "₽"),
                 ("capital", "Оборотные средства", "Максимальный дефицит денег, ₽", BLUE, "↗"),
                 ("storage", "Хранение", "Накопленные расходы, ₽", ORANGE, "▤")]
        for i, (key, title, detail, color, symbol) in enumerate(cards):
            card = MetricCard(metrics, title, detail, color, symbol)
            card.grid(row=i // 3, column=i % 3, sticky="nsew", padx=(0, 8) if i % 3 < 2 else 0, pady=(0, 6))
            metrics.columnconfigure(i % 3, weight=1, uniform="metrics")
            self.metric_labels[key] = card
        self.map = tk.Canvas(self.visual_tab, bg=BG, highlightthickness=0, height=215)
        self.map.pack(fill="x", pady=(0, 10))
        self.map.bind("<Configure>", lambda _: self.draw_map())
        self.charts = tk.Canvas(self.visual_tab, bg=BG, highlightthickness=0, height=215)
        self.charts.pack(fill="both", expand=True)
        self.charts.bind("<Configure>", lambda _: self.draw_charts())
        self.summary_line = tk.StringVar(value="Показатели появятся после запуска модели")
        summary_widget = tk.Label(self.visual_tab, textvariable=self.summary_line, bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=1000, justify="left", anchor="w")
        summary_widget.pack(side="bottom", before=self.map, fill="x", padx=2, pady=(9, 0))
        self.order_tree = self.tree(self.orders_tab, ["№", "Салон", "Модель", "Источник", "Договор, дн.", "Дедлайн", "Выдан", "Срок, дн.", "Статус"])
        self.order_tree.column("№", width=45, minwidth=35)
        self.order_tree.column("Статус", width=175, minwidth=150)
        self.exp_text = tk.StringVar(value="Сравните стратегии склада, предоплату или транспорт в панели настроек. Результаты — средние по независимым повторениям.")
        tk.Label(self.exp_tab, textvariable=self.exp_text, bg=BG, fg=MUTED, wraplength=950, justify="left").pack(fill="x", padx=10, pady=12)
        self.exp_tree = self.tree(self.exp_tab, ["Сценарий", "Выдано, %", "Срок, дн.", "Ожидают", "Прибыль, ₽", "Капитал, ₽", "Хранение, ₽", "Пик складов"])
        self.notes = tk.Text(self.notes_tab, bg=PANEL, fg=TEXT, wrap="word", font=("Segoe UI", 11), padx=24, pady=24, relief="flat", spacing3=8)
        self.notes.pack(fill="both", expand=True)

    def field_target(self, frame):
        return self.settings_groups.get(frame, frame)

    def section(self, frame, text):
        group = tk.Frame(frame, bg=PANEL)
        group.pack(fill="x", pady=(0, 9))
        tk.Frame(group, bg=BORDER, height=1).pack(fill="x", pady=(0, 7))
        title = text.capitalize()
        button = tk.Label(group, text="▸  " + title, bg=PANEL, fg=TEXT,
                          cursor="hand2", font=("Segoe UI", 10, "bold"), anchor="w", pady=7)
        button.pack(fill="x")
        content = tk.Frame(group, bg=PANEL)
        opened = [not self.settings_groups]
        if opened[0]:
            content.pack(fill="x", pady=(0, 7))
            button.configure(text="▾  " + title)
        def toggle(_=None):
            opened[0] = not opened[0]
            button.configure(text=("▾  " if opened[0] else "▸  ") + title)
            if opened[0]:
                content.pack(fill="x", pady=(0, 7))
            else:
                content.pack_forget()
        button.bind("<Button-1>", toggle)
        button.bind("<Enter>", lambda _: button.configure(fg=BLUE))
        button.bind("<Leave>", lambda _: button.configure(fg=TEXT))
        self.settings_groups[frame] = content

    def hint(self, frame, text):
        tk.Label(self.field_target(frame), text=text, bg=PANEL, fg=MUTED, wraplength=260,
                 justify="left", font=("Segoe UI", 9)).pack(fill="x", pady=(3, 9))

    def field(self, frame, key, title, default, options=None):
        parent = self.field_target(frame)
        ttk.Label(parent, text=title, foreground=MUTED, wraplength=265, font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 4))
        var = tk.StringVar(value=default)
        self.vars[key] = var
        entry = ttk.Combobox(parent, textvariable=var, values=options, state="readonly") if options else ttk.Entry(parent, textvariable=var)
        entry.pack(fill="x", pady=(0, 5))

    def check(self, frame, key, title, default):
        var = tk.BooleanVar(value=default)
        self.vars[key] = var
        ttk.Checkbutton(self.field_target(frame), text=title, variable=var).pack(anchor="w", pady=6)

    def tree(self, frame, columns):
        holder = ttk.Frame(frame)
        holder.pack(fill="both", expand=True)
        tree = ttk.Treeview(holder, columns=columns, show="headings")
        for i, col in enumerate(columns):
            tree.heading(col, text=col)
            tree.column(col, width=185 if i == 0 and len(columns) == 8 else 110, minwidth=70, stretch=True)
        vs = ttk.Scrollbar(holder, command=tree.yview)
        hs = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)
        tree.tag_configure("late", foreground=ORANGE)
        tree.tag_configure("done", foreground=ACCENT)
        tree.tag_configure("pending", foreground=TEXT)
        return tree

    def config(self):
        get = lambda key: self.vars[key].get()
        def integer(key):
            try:
                return int(get(key))
            except ValueError:
                raise ValueError(f"Поле {key}: требуется целое число.")
        def real(key):
            return float(str(get(key)).replace(" ", "").replace(",", "."))
        omitted = []
        def optional(key, title):
            if str(get(key)).strip():
                return real(key)
            omitted.append(title + ": не задано, исключено из расчёта.")
            return 0.0
        models, prices = [], []
        for row in self.models_box.get("1.0", "end").strip().splitlines():
            if not row.strip():
                continue
            parts = row.split(";")
            if len(parts) > 2 or not parts[0].strip():
                raise ValueError("Формат моделей: название; цена (цену можно оставить пустой).")
            models.append(parts[0].strip())
            prices.append(float(parts[1].replace(" ", "").replace(",", ".")) if len(parts) > 1 and parts[1].strip() else None)
        if len(set(models)) != len(models):
            raise ValueError("Названия моделей должны быть уникальными.")
        hours = optional("work_hours", "Рабочее расписание")
        c = Config(days=integer("days"), visitors_min=integer("visitors_min"), visitors_max=integer("visitors_max"), seed=integer("seed"), models=tuple(models), prices=tuple(prices),
                   inventory_mode=get("mode") == "Фактические запасы", initial=integer("initial"), reorder=integer("reorder"), target=integer("target"),
                   replenish=get("replenish"), stock_source=get("stock_source"), own_share=real("own_share") / 100,
                   prepay=None if get("prepay_mode") == "900 тыс. ₽" else real("prepay_percent") / 100,
                   batch=integer("batch"), small_trucks=integer("small_trucks"), rail=get("rail"),
                   moscow_days=optional("moscow_days", "Время Москва → салон"), moscow_cost=optional("moscow_cost", "Стоимость рейса Москва → салон"),
                   hanko_days=optional("hanko_days", "Время Ханко → Москва"), hanko_cost=optional("hanko_cost", "Стоимость рейса Ханко → Москва"),
                   rail_days=optional("rail_days", "Время ж/д рейса"), rail_cost=optional("rail_cost", "Стоимость ж/д рейса"),
                   work_hours=hours if str(get("work_hours")).strip() else None, omitted=tuple(omitted))
        c.validate()
        return c

    def new_sim(self):
        self.sim = Simulation(self.config())
        self.progress.configure(maximum=self.sim.c.days, value=0)
        self.update_view()

    def start(self):
        try:
            if self.running:
                return
            if self.sim is None or self.sim.finished:
                self.new_sim()
            self.running = True
            self.generation += 1
            self.tick(self.generation)
        except (ValueError, OverflowError) as e:
            messagebox.showerror("Параметры", str(e))

    def tick(self, generation):
        if not self.running or generation != self.generation:
            return
        try:
            speed = max(1, int(self.vars["speed"].get()))
            self.sim.advance(self.sim.now + speed)
            self.update_view()
            if self.sim.finished:
                self.running = False
            else:
                self.after(140, lambda: self.tick(generation))
        except Exception as e:
            self.pause()
            messagebox.showerror("Ошибка", str(e))

    def pause(self):
        self.running = False
        self.generation += 1
        if self.sim and not self.sim.finished:
            self.status.set(f"Пауза · день {self.sim.now:.0f}. Изменённые параметры применяются после сброса.")

    def step(self):
        self.pause()
        try:
            if self.sim is None:
                self.new_sim()
            self.sim.advance(self.sim.now + 1)
            self.update_view()
        except (ValueError, OverflowError) as e:
            messagebox.showerror("Параметры", str(e))

    def finish(self):
        self.vars["speed"].set("10")
        self.start()

    def reset(self):
        self.pause()
        try:
            self.new_sim()
        except (ValueError, OverflowError) as e:
            messagebox.showerror("Параметры", str(e))

    def draw_empty(self):
        self.notes.insert("1.0", "Нажмите «Запустить». Цена автомобиля по выбору пользователя — 2 500 000 ₽. Каждый день отдельно для каждого салона случайно выбирается от 1 до 10 посетителей.\n\nНеуказанные время и стоимость перевозок исключены. Численные результаты с такими настройками описывают сокращённую модель.\n\nДля складских экспериментов используется отдельный режим фактических запасов: наличие автомобилей меняется в зависимости от выбранной политики. Нельзя одновременно принудительно сохранять 60% наличия и оценивать влияние произвольного размера склада.\n\nПоказатели: выручка, прибыль по учтённым статьям, потребность в деньгах, средние сроки только выданных заказов, незавершённые заказы, фактические пики остатков, расходы на хранение.\n\nВы можете изменить модели, начальные остатки, политику заказа, долю предоплаты и транспорт, затем сохранить HTML-отчёт.")
        self.notes.configure(state="disabled")
        self.draw_map()
        self.draw_charts()

    def update_view(self):
        s = self.sim.summary()
        self.metric_labels["completed"].configure(text=f'{s["completed"]} / {s["orders"]}')
        self.metric_labels["pending"].configure(text=f'{s["pending"]} / {s["late"]}')
        self.metric_labels["mean_external"].configure(text=num(s["mean_external"], digits=1) if s["mean_external"] is not None else "Не было выдач")
        for key in ("profit", "capital", "storage"):
            self.metric_labels[key].configure(text=num(s[key]))
        self.progress.configure(value=self.sim.now)
        self.day_label.set(f"День {self.sim.now:.0f} / {self.sim.c.days}")
        self.status.set(f'{"Завершено" if self.sim.finished else "Моделирование"} · поток {self.sim.c.visitors_min}–{self.sim.c.visitors_max} посетителей / день · ' + ("денежный расчёт по заданным статьям" if self.sim.money_available else "для расчёта денег нужны цены"))
        flow = self.sim.history[-1]
        self.summary_line.set(f'Посетителей за текущий день: {flow["visitors1"]} / {flow["visitors2"]} · Всего: {s["visitors"]}   |   Выручка: {num(s["revenue"], " ₽")}\nПик склада: {num(s["stock_peak1"])} / {num(s["stock_peak2"])} авто · Старейший незавершённый: {s["oldest_pending"]:.1f} дн. · Неуказанное время перевозок исключено.')
        self.order_tree.delete(*self.order_tree.get_children())
        for o in self.sim.orders:
            overdue = (o.delivered if o.delivered is not None else self.sim.now) > o.deadline
            status = ("Выдан, просрочен" if overdue else "Выдан") if o.delivered is not None else ("Просрочен" if overdue else "Ожидание")
            self.order_tree.insert("", "end", tags=("late" if overdue else ("done" if o.delivered is not None else "pending"),), values=(o.number, o.city + 1, self.sim.c.models[o.model], o.source, f"{o.created:.2f}", f"{o.deadline:.2f}", num(o.delivered, digits=2) if o.delivered is not None else "—", num(o.delivered - o.created, digits=2) if o.delivered is not None else "—", status))
        self.notes.configure(state="normal")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", "ПРАВИЛА ТЕКУЩЕГО ЗАПУСКА\n\n" + "\n\n".join(self.sim.limitations()))
        self.notes.configure(state="disabled")
        self.draw_map()
        self.draw_charts()

    def draw_map(self):
        cv = self.map
        cv.delete("all")
        w, h = max(cv.winfo_width(), 650), max(cv.winfo_height(), 215)
        rounded(cv, 1, 1, w - 1, h - 1, 16, fill=PANEL, outline=BORDER)
        cv.create_text(20, 24, anchor="w", text="Сеть поставок", fill=TEXT, font=("Segoe UI", 12, "bold"))
        cv.create_text(20, 45, anchor="w", text="Два салона · Москва · завод Ханко", fill=MUTED, font=("Segoe UI", 9))
        trips = len(self.sim.transit) if self.sim else 0
        rounded(cv, w - 142, 15, w - 18, 42, 12, fill="#203349", outline="")
        cv.create_oval(w - 129, 25, w - 123, 31, fill=ACCENT, outline="")
        cv.create_text(w - 116, 28, anchor="w", text=f"В пути: {trips} рейсов", fill=ACCENT, font=("Segoe UI", 9))
        xy = {"Ханко": (w * .14, h * .58), "Москва": (w * .43, h * .58),
              "Салон 1": (w * .78, h * .37), "Салон 2": (w * .78, h * .73)}
        half = min(86, w * .105)
        node_h = 30
        rail = self.sim.c.rail if self.sim else self.vars["rail"].get()
        batch = self.sim.c.batch if self.sim else self.vars["batch"].get()
        connections = [("Ханко", "Москва", "5 автомобилей"),
                       ("Москва", "Салон 1", "12 · ж/д" if rail else f"{batch} · автовоз"),
                       ("Москва", "Салон 2", "12 · ж/д" if rail else f"{batch} · автовоз")]
        for a, b, label in connections:
            x1, y1 = xy[a]
            x2, y2 = xy[b]
            left, right = x1 + half, x2 - half
            mid = (left + right) / 2
            cv.create_line(left, y1, mid, y1, mid, y2, right - 3, y2,
                           smooth=True, splinesteps=24, fill="#3b506f", width=2,
                           arrow="last", arrowshape=(7, 8, 3))
            tx, ty = mid, (y1 + y2) / 2 - 15
            label_width = 104 if a == "Ханко" else 93
            rounded(cv, tx - label_width / 2, ty - 11, tx + label_width / 2, ty + 11, 8, fill=PANEL, outline="")
            cv.create_text(tx, ty, text=label, fill=MUTED, font=("Segoe UI", 8))
        x = xy["Салон 1"][0] + half + 22
        y1, y2 = xy["Салон 1"][1], xy["Салон 2"][1]
        cv.create_line(x - 20, y1, x, y1, x, y2, x - 20, y2,
                       smooth=True, fill="#456458", width=2, dash=(4, 4), arrow="both")
        cv.create_text(x + 7, (y1 + y2) / 2, text="2 дня", anchor="w", fill=ACCENT, font=("Segoe UI", 8))
        for title, (x, y) in xy.items():
            color = ACCENT if title.startswith("Салон") else BLUE
            rounded(cv, x - half, y - node_h + 2, x + half, y + node_h + 2, 12, fill="#0d1525", outline="")
            rounded(cv, x - half, y - node_h, x + half, y + node_h, 12, fill="#1b2940", outline="#314360")
            icon_x = x - half + 24
            rounded(cv, icon_x - 13, y - 19, icon_x + 13, y + 7, 8, fill="#2b3d59", outline="")
            if title == "Ханко":
                cv.create_line(icon_x - 7, y + 1, icon_x - 7, y - 8, icon_x - 1, y - 5,
                               icon_x + 4, y - 10, icon_x + 8, y - 6, icon_x + 8, y + 1,
                               icon_x - 7, y + 1, fill=color, width=1.5)
                cv.create_line(icon_x - 5, y - 9, icon_x - 5, y - 14, fill=color, width=2)
            else:
                cv.create_line(icon_x - 8, y - 3, icon_x - 4, y - 9, icon_x + 4, y - 9,
                               icon_x + 8, y - 3, fill=color, width=1.5)
                cv.create_rectangle(icon_x - 8, y - 3, icon_x + 8, y + 1, outline=color, width=1.5)
                for wheel in (icon_x - 5, icon_x + 5):
                    cv.create_oval(wheel - 2, y, wheel + 2, y + 4, fill=color, outline="")
            cv.create_text(x - half + 45, y - 9, anchor="w", text=title, fill=TEXT, font=("Segoe UI", 11, "bold"))
            label = "Автомобили в наличии" if title == "Ханко" else "Пункт поставки"
            if self.sim:
                if title == "Ханко":
                    label = f"Ожидают партии: {sum(map(len, self.sim.hanko))}"
                elif title == "Москва":
                    label = f"Ожидают партии: {sum(map(len, self.sim.moscow))}"
                else:
                    city = int(title[-1]) - 1
                    label = f"На складе: {self.sim.occupancy[city]} авто" if self.sim.c.inventory_mode else "Базовый режим наличия"
            cv.create_text(x - half + 15, y + 19, anchor="w", text=label, fill=MUTED, font=("Segoe UI", 8))
        if self.sim:
            for trip in self.sim.transit:
                a, b = xy[trip["origin"]], xy[trip["destination"]]
                frac = max(0, min(1, (self.sim.now - trip["start"]) / max(.001, trip["end"] - trip["start"])))
                if trip["origin"].startswith("Салон"):
                    x = a[0] + half + 22
                    y = a[1] + (b[1] - a[1]) * frac
                else:
                    x = a[0] + half + (b[0] - a[0] - 2 * half) * frac
                    mid = (a[0] + b[0]) / 2
                    # Position follows the visible route, including its bend.
                    if frac < .25:
                        y = a[1]
                    elif frac > .75:
                        y = b[1]
                    else:
                        y = a[1] + (b[1] - a[1]) * ((frac - .25) * 2)
                rounded(cv, x - 15, y - 10, x + 15, y + 10, 6, fill=ORANGE, outline=BG)
                cv.create_text(x, y, text=str(trip["count"]), fill=BG, font=("Segoe UI", 8, "bold"))
        cv.create_oval(21, h - 25, 27, h - 19, fill=ORANGE, outline="")
        cv.create_text(35, h - 22, anchor="w", text="Автомобили в пути", fill=MUTED, font=("Segoe UI", 8))
        cv.create_text(w - 20, h - 22, anchor="e", text="Незаполненные партии ожидают отправки", fill=MUTED, font=("Segoe UI", 8))

    def draw_charts(self):
        cv = self.charts
        cv.delete("all")
        w, h = max(cv.winfo_width(), 650), max(cv.winfo_height(), 100)
        left_series = [("stock1", "Салон 1", BLUE), ("stock2", "Салон 2", ACCENT)] if self.sim and self.sim.c.inventory_mode else [("visitors1", "Салон 1", BLUE), ("visitors2", "Салон 2", ORANGE)]
        right_series = [("profit", "Прибыль", ACCENT), ("cash", "Касса", BLUE)] if not self.sim or self.sim.money_available else [("completed", "Выдано", ACCENT), ("pending", "Ожидают", ORANGE)]
        for j, series in enumerate((left_series, right_series)):
            card0, card1 = j * (w + 10) / 2, (j + 1) * (w + 10) / 2 - 10
            rounded(cv, card0 + 1, 1, card1 - 1, h - 1, 14, fill=PANEL, outline=BORDER)
            title = ("Остатки автомобилей" if self.sim and self.sim.c.inventory_mode else "Поток посетителей") if j == 0 else ("Денежный поток" if not self.sim or self.sim.money_available else "Выполнение заказов")
            cv.create_text(card0 + 17, 21, text=title, anchor="w", fill=TEXT, font=("Segoe UI", 11, "bold"))
            for k, (_, label, color) in enumerate(series):
                lx = card0 + 20 + k * 95
                cv.create_oval(lx - 3, 39, lx + 3, 45, fill=color, outline="")
                cv.create_text(lx + 10, 42, text=label, anchor="w", fill=MUTED, font=("Segoe UI", 8))
            if not self.sim or len(self.sim.history) < 2:
                cv.create_text((card0 + card1) / 2, (h + 50) / 2, text="Данные появятся после запуска", fill=MUTED, font=("Segoe UI", 10))
                continue
            x0, x1, y0, y1 = card0 + 51, card1 - 22, 66, h - 27
            values = [row[key] for row in self.sim.history for key, _, _ in series]
            lo, hi = min(0, min(values)), max(1, max(values))
            span = hi - lo
            hi += span * .10
            for tick in range(4):
                value = lo + (hi - lo) * tick / 3
                y = y1 - (y1 - y0) * tick / 3
                cv.create_line(x0, y, x1, y, fill="#27354b", dash=(2, 5))
                label = f"{value / 1e6:.1f}м" if max(abs(lo), abs(hi)) >= 1e6 else f"{value:.0f}"
                cv.create_text(x0 - 9, y, text=label, anchor="e", fill=MUTED, font=("Segoe UI", 8))
            for k, (key, _, color) in enumerate(series):
                points = []
                for row in self.sim.history:
                    points.extend((x0 + (x1 - x0) * row["day"] / max(1, self.sim.now),
                                   y1 - (y1 - y0) * (row[key] - lo) / (hi - lo)))
                if k == 0 and j == 1:
                    cv.create_polygon(x0, y1, *points, x1, y1, fill="#192f37", outline="")
                cv.create_line(*points, fill=color, width=2)
                cv.create_oval(points[-2] - 3, points[-1] - 3, points[-2] + 3, points[-1] + 3, fill=color, outline=PANEL)
            cv.create_text(x0, y1 + 16, text="0", fill=MUTED, font=("Segoe UI", 8))
            cv.create_text((x0 + x1) / 2, y1 + 16, text=f"{self.sim.now / 2:.0f}", fill=MUTED, font=("Segoe UI", 8))
            cv.create_text(x1, y1 + 16, text=f"{self.sim.now:.0f} дней", fill=MUTED, font=("Segoe UI", 8))

    def start_experiment(self, kind):
        if getattr(self, "experiment_busy", False):
            return
        try:
            c = self.config()
            count = int(self.vars["replications"].get())
            if not 1 <= count <= 1000:
                raise ValueError("Повторов должно быть от 1 до 1000.")
            targets = sorted(set(int(x.strip()) for x in self.vars["targets"].get().split(",")))
            if any(n < 0 for n in targets):
                raise ValueError("Запасы должны быть неотрицательными.")
            scenarios = experiment_configs(c, kind, targets)
            if kind == "prepay" and not all(p is not None for p in c.prices):
                raise ValueError("Для сравнения предоплаты нужны цены автомобилей. Введите их в поле моделей.")
            for _, config in scenarios:
                config.validate()
            self.experiment_busy = True
            self.exp_tree.delete(*self.exp_tree.get_children())
            self.experiment_rows = []
            self.experiment_meta = {"kind": kind, "repetitions": count, "config": asdict(c), "targets": targets, "scenarios": [{"name": name, "config": asdict(cfg)} for name, cfg in scenarios]}
            self.tabs.select(self.exp_tab)
            self.exp_text.set(f"Выполняется сравнение: {len(scenarios)} сценариев × {count} повторов. Можно продолжать работать с интерфейсом.")
            def worker():
                try:
                    for name, cfg in scenarios:
                        summaries = []
                        for i in range(count):
                            from dataclasses import replace
                            summaries.append(Simulation(replace(cfg, seed=c.seed + i)).run().summary())
                        result = {"scenario": name}
                        for key in ("completion_rate", "mean_external", "pending", "profit", "capital", "storage", "stock_peak1", "stock_peak2"):
                            values = [s[key] for s in summaries if s[key] is not None]
                            result[key] = statistics.mean(values) if values else None
                            result[key + "_sd"] = statistics.stdev(values) if len(values) > 1 else None
                            result[key + "_n"] = len(values)
                        self.results_queue.put(("row", result))
                    self.results_queue.put(("done", None))
                except Exception as e:
                    self.results_queue.put(("error", str(e)))
            threading.Thread(target=worker, daemon=True).start()
        except (ValueError, OverflowError) as e:
            messagebox.showerror("Эксперимент", str(e))

    def poll(self):
        try:
            while True:
                kind, data = self.results_queue.get_nowait()
                if kind == "row":
                    self.experiment_rows.append(data)
                    self.exp_tree.insert("", "end", values=(data["scenario"], num(data["completion_rate"] * 100 if data["completion_rate"] is not None else None, digits=1), num(data["mean_external"], digits=1), num(data["pending"], digits=1), num(data["profit"]), num(data["capital"]), num(data["storage"]), num(data["stock_peak1"], digits=1) + " / " + num(data["stock_peak2"], digits=1)))
                else:
                    self.experiment_busy = False
                    if kind == "error":
                        messagebox.showerror("Эксперимент", data)
                    else:
                        message = "Сравнение завершено. Значения — средние по повторениям. "
                        if self.experiment_meta["kind"] == "stock":
                            rows = self.experiment_rows
                            frontier = []
                            def dominates(a, b):
                                # Max completion, min funding/storage. No invented service target.
                                keys = ["completion_rate", "storage"] + (["capital"] if a["capital"] is not None else [])
                                pairs = [(a[k] if k != "completion_rate" else -a[k], b[k] if k != "completion_rate" else -b[k]) for k in keys if a[k] is not None and b[k] is not None]
                                return bool(pairs) and all(x <= y for x, y in pairs) and any(x < y for x, y in pairs)
                            for row in rows:
                                if not any(dominates(other, row) for other in rows if other is not row):
                                    frontier.append(row["scenario"])
                            message += "Компромиссные стратегии (выдано ↑, хранение и капитал ↓): " + "; ".join(frontier) + ". Пики — наблюдаемые остатки, не гарантия вместимости."
                        elif self.experiment_meta["kind"] == "prepay":
                            message += "Цена капитала не задана: предоплата влияет на денежный дефицит, а прибыль при одинаковых заказах не меняется."
                        else:
                            message += "Сравниваются партии и заданные перевозки. Без стоимости и времени ж/д оценить экономическую выгодность нельзя."
                        self.exp_text.set(message)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def save_config(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile="settings.json")
        if path:
            Path(path).write_text(json.dumps({"fields": {k: v.get() for k, v in self.vars.items()}, "models": self.models_box.get("1.0", "end").strip()}, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_config(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                for key, value in data["fields"].items():
                    if key in self.vars:
                        self.vars[key].set(value)
                self.models_box.delete("1.0", "end")
                self.models_box.insert("1.0", data["models"])
                self.status.set("Настройки загружены. Нажмите «Сброс», чтобы применить их к модели.")
            except (ValueError, KeyError, OSError) as e:
                messagebox.showerror("Настройки", str(e))

    def export_csv(self):
        if not self.sim and not self.experiment_rows:
            messagebox.showinfo("CSV", "Сначала запустите модель или сравнение.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="experiments.csv" if self.tabs.select() == str(self.exp_tab) and self.experiment_rows else "orders.csv")
        if path:
            if self.tabs.select() == str(self.exp_tab) and self.experiment_rows:
                rows = self.experiment_rows
            elif self.sim:
                rows = [dict(asdict(o), model_name=self.sim.c.models[o.model]) for o in self.sim.orders]
            else:
                rows = self.experiment_rows
            if not rows:
                messagebox.showinfo("CSV", "Пока нет строк для выгрузки.")
                return
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
                writer.writeheader()
                writer.writerows(rows)

    def export_report(self):
        if not self.sim and not self.experiment_rows:
            messagebox.showinfo("Отчёт", "Сначала запустите модель или сравнение.")
            return
        if getattr(self, "experiment_busy", False):
            messagebox.showinfo("Отчёт", "Дождитесь окончания сравнения для полного отчёта.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML", "*.html")], initialfile="report_simulation.html")
        if path:
            from report import make_report
            Path(path).write_text(make_report(self.sim, self.experiment_rows, self.experiment_meta, self.exp_text.get()), encoding="utf-8")
            webbrowser.open(Path(path).resolve().as_uri())


if __name__ == "__main__":
    App().mainloop()
