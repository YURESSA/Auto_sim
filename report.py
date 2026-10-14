"""Portable HTML report with embedded SVG plots; no network or libraries."""
from dataclasses import asdict
import html
import json


def esc(value):
    return html.escape(str(value))


def fmt(value, digits=2):
    if value is None:
        return "нет данных"
    if isinstance(value, (int, float)):
        return f"{value:,.{digits}f}".replace(",", " ")
    return esc(value)


def table(headers, rows):
    return "<table><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in rows) + "</tbody></table>"


def plot(history, series, title):
    if len(history) < 2:
        return ""
    w, h, left, top = 900, 270, 70, 40
    right, bottom = 870, 230
    values = [row[key] for row in history for key, _, _ in series]
    lo, hi = min(0, min(values)), max(1, max(values))
    duration = max(1, history[-1]["day"])
    result = f'<h3>{esc(title)}</h3><svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
    for i in range(5):
        y = bottom - (bottom - top) * i / 4
        value = lo + (hi - lo) * i / 4
        result += f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="#dde3ec"/><text x="{left - 8}" y="{y + 4}" text-anchor="end">{fmt(value, 0)}</text>'
    for i, (key, label, color) in enumerate(series):
        points = " ".join(f'{left + (right-left)*row["day"]/duration:.2f},{bottom-(bottom-top)*(row[key]-lo)/(hi-lo):.2f}' for row in history)
        result += f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/><text x="{left + i * 220}" y="20" fill="{color}">{esc(label)}</text>'
    result += f'<text x="{left}" y="255">0</text><text x="{right}" y="255" text-anchor="end">{fmt(duration, 0)} дней</text></svg>'
    return result


def make_report(sim, experiments=None, meta=None, experiment_text=""):
    experiments = experiments or []
    out = ['<!doctype html><html lang="ru"><meta charset="utf-8"><title>2025_А5 — Автосалон Subaru</title><style>body{font:15px/1.6 Segoe UI,Arial,sans-serif;color:#172337;max-width:1100px;margin:36px auto;padding:0 28px}h1{font-size:30px}h2{margin-top:32px;color:#214d77}table{border-collapse:collapse;width:100%;font-size:13px;margin:14px 0}th,td{border:1px solid #d8e0ea;padding:7px;text-align:left}th{background:#edf3f9}pre{white-space:pre-wrap;background:#f1f5fa;padding:15px}svg{width:100%;font:12px Arial}.note{border-left:4px solid #e49b3c;background:#fff6e7;padding:12px}@media print{body{margin:0;max-width:none}h2{break-after:avoid}tr,svg{break-inside:avoid}}</style><h1>Задание 2025_А5. Автосалон Subaru</h1><p>Имитационная модель компании на Python. Два автономных салона, обмен автомобилями, поставки из Москвы и Ханко.</p>']
    out.append('<h2>Описание модели</h2><p>Дискретно-событийная модель: посещение, обслуживание менеджером, договор и предоплата, резервирование, закупка, накопление партии, отправка, прибытие, выдача и ежемесячное хранение. События выполняются в порядке времени. Автомобиль клиента резервируется и не участвует в свободном запасе.</p><p>В базовом режиме источник задан вероятностями 60/10/30. В режиме запасов сначала проверяется свой салон, затем второй; при отсутствии машины используется условная вероятность Москвы 25%. Политика пополнения (s, S) ежедневно доводит складскую позицию — свободный остаток плюс заказанные на склад машины — до S, если она не превышает s.</p>')
    if sim:
        s = sim.summary()
        out.append(f'<h2>Параметры запуска</h2><p>Состояние на день {fmt(sim.now)} из {sim.c.days}. {"Горизонт завершён." if sim.finished else "Промежуточный результат: горизонт ещё не завершён."}</p><pre>{esc(json.dumps(asdict(sim.c), ensure_ascii=False, indent=2))}</pre>')
        out.append('<div class="note">Неуказанные данные исключены по выбору пользователя. Нулевое время перевозки означает исключённую длительность, а не установленную скорость транспорта. Результаты относятся к указанным параметрам и правилам модели.</div>')
        labels = [("visitors", "Потенциальных покупателей"), ("orders", "Договоров"), ("completed", "Выданных заказов"), ("pending", "Незавершённых заказов"), ("late", "Просроченных заказов (включая выданные)"), ("mean_external", "Средний срок без наличия в своём салоне, дни (выданные)"), ("mean_delivery", "Средний срок всех выданных, дни"), ("oldest_pending", "Максимальный возраст незавершённого заказа, дни"), ("stock_peak1", "Наблюдаемый пик склада 1, авто"), ("stock_peak2", "Наблюдаемый пик склада 2, авто"), ("stock1", "Остаток склада 1, авто"), ("stock2", "Остаток склада 2, авто"), ("revenue", "Выручка после штрафов, ₽"), ("cogs", "Себестоимость проданных машин, ₽"), ("storage", "Расходы на хранение, ₽"), ("transport", "Учтённые транспортные расходы, ₽"), ("discount", "Снижение стоимости за просрочку, ₽"), ("profit", "Прибыль по учтённым статьям, ₽"), ("capital", "Максимальный дефицит денег / оборотные средства, ₽"), ("supplier_moscow", "Выплаты складу в Москве за новые закупки, ₽"), ("supplier_hanko", "Выплаты Ханко за новые закупки, ₽"), ("initial_value", "Стоимость начальных запасов, ₽"), ("cash", "Накопленный денежный баланс, ₽"), ("moscow_queue", "Ожидают партии в Москве, авто"), ("hanko_queue", "Ожидают партии в Ханко, авто")]
        out.append('<h2>Результаты запуска</h2>' + table(["Показатель", "Значение"], [(esc(label), fmt(s[key])) for key, label in labels]))
        out.append('<h3>Источники выполнения заказов</h3>' + table(["Источник", "Заказов", "Доля, %"], [(esc(k), fmt(v, 0), fmt(100 * v / s["orders"] if s["orders"] else None)) for k, v in s["routes"].items()]))
        out.append(plot(sim.history, [("stock1", "Склад 1", "#367ac7"), ("stock2", "Склад 2", "#19a58c")] if sim.c.inventory_mode else [("completed", "Выданные заказы", "#19a58c"), ("pending", "Незавершённые", "#d28530")], "Динамика складов" if sim.c.inventory_mode else "Динамика заказов"))
        out.append(plot(sim.history, [("visitors1", "Посетители: салон 1", "#367ac7"), ("visitors2", "Посетители: салон 2", "#d28530")], "Случайный поток посетителей по дням"))
        if sim.money_available:
            out.append(plot(sim.history, [("profit", "Прибыль, ₽", "#19a58c"), ("cash", "Денежный баланс, ₽", "#367ac7")], "Экономические характеристики"))
        out.append('<h2>Правила и ограничения расчёта</h2><ol>' + ''.join(f'<li>{esc(note)}</li>' for note in sim.limitations()) + '</ol>')
    if experiments:
        out.append('<h2>Сравнение экспериментов</h2><p>' + esc(experiment_text) + '</p>')
        out.append('<p>Среднее ± стандартное отклонение между повторами. Для среднего срока n — число повторов с хотя бы одним выданным внешним заказом. Одинаковое начальное число генератора в соответствующих повторах сценариев даёт одинаковый спрос.</p>')
        def stat(row, key, scale=1):
            mean, sd = row[key], row.get(key + "_sd")
            if mean is None:
                return "нет данных"
            return fmt(mean * scale) + (" ± " + fmt(sd * scale) if sd is not None else "")
        out.append(table(["Сценарий", "Выдано, %", "Внешний срок, дни", "n срока", "Ожидают", "Прибыль, ₽", "Капитал, ₽", "Хранение, ₽", "Пики складов"], [(esc(row["scenario"]), stat(row, "completion_rate", 100), stat(row, "mean_external"), fmt(row["mean_external_n"], 0), stat(row, "pending"), stat(row, "profit"), stat(row, "capital"), stat(row, "storage"), stat(row, "stock_peak1") + " / " + stat(row, "stock_peak2")) for row in experiments]))
        out.append('<h3>Параметры сравнения (отдельно от одиночного запуска)</h3><pre>' + esc(json.dumps(meta, ensure_ascii=False, indent=2)) + '</pre>')
        out.append('<p>Стратегии склада оцениваются по доле выданных заказов, хранению и потребности в деньгах. Наблюдаемый пик запаса описывает требуемую вместимость для конкретного прогона. Единственный эффективный размер без требуемого уровня обслуживания или экономического критерия не определяется.</p><p>Увеличение предоплаты само по себе не меняет признанную прибыль при одинаковых заказах и отсутствии цены привлечённого капитала. Меняется денежный дефицит. Выгодность железной дороги требует заданных тарифов и времени пути; порог в 12 машин позволяет сравнить влияние ожидания партии.</p>')
        if not sim:
            c = meta["config"]
            out.append('<h2>Ограничения экспериментов</h2><p>Сценарии используют те же правила дискретных событий, хранения и расчёта денег, что одиночная модель. Фактические остатки изменяют вероятность наличия машины в салонах. Незавершённые заказы не входят в среднее время.</p><ul>' + ''.join('<li>' + esc(note) + '</li>' for note in c.get("omitted", [])) + '</ul>')
    out.append('<h2>Выводы и воспроизводимость</h2><p>Численные выводы относятся к указанным настройкам, горизонту и повторениям. При отсутствии цен денежные результаты недоступны. Без сроков и тарифов транспорта сравнение касается ожидания партий и известных расходов. Для оценки складов нужен режим фактических запасов. Настройки можно сохранить в JSON, заказы и таблицы экспериментов — в CSV. Дополнительные фактические исходные данные в отчёт не подставляются.</p></html>')
    return "".join(out)
