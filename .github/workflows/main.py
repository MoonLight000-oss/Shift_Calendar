from __future__ import annotations

import json
from pathlib import Path

from dataclasses import dataclass
from datetime import date, timedelta
import calendar
from typing import Dict, List, Sequence, Tuple

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput


BASE_PATTERN: Tuple[str, ...] = ("День", "Ночь", "Отсыпной", "Выходной")
SHIFT_COLORS = {
    "День": (0.95, 0.82, 0.35, 1),
    "Ночь": (0.35, 0.45, 0.80, 1),
    "Отсыпной": (0.55, 0.80, 0.55, 1),
    "Выходной": (0.80, 0.80, 0.80, 1),
    "Пусто": (0.95, 0.95, 0.95, 1),
}
WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def date_range(start_date: date, end_date: date):
    if start_date > end_date:
        raise ValueError("start_date не может быть позже end_date")
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def build_schedule(
    start_date: date,
    end_date: date,
    base_pattern: Sequence[str] = BASE_PATTERN,
    base_start_index: int = 0,
    manual_shifts: Dict[date, str] | None = None,
) -> Dict[date, dict]:
    """
    Возвращает словарь:
    {
        date: {
            'date': date,
            'shift': итоговая смена,
            'base_shift': базовая смена,
            'manual': есть ли ручная замена,
        }
    }
    """
    if not base_pattern:
        raise ValueError("base_pattern не может быть пустым")

    if manual_shifts is None:
        manual_shifts = {}

    result: Dict[date, dict] = {}
    pattern_len = len(base_pattern)

    for day_index, day in enumerate(date_range(start_date, end_date)):
        base_shift = base_pattern[(base_start_index + day_index) % pattern_len]
        final_shift = manual_shifts.get(day, base_shift)
        result[day] = {
            "date": day,
            "shift": final_shift,
            "base_shift": base_shift,
            "manual": day in manual_shifts,
        }

    return result


def parse_date_ddmmyyyy(text: str) -> date:
    return date.fromisoformat("-".join(reversed(text.strip().split("."))))


@dataclass
class MonthState:
    year: int
    month: int


class ShiftDayButton(Button):
    def __init__(self, day_date: date | None = None, **kwargs):
        super().__init__(**kwargs)
        self.day_date = day_date
        self.background_normal = ""
        self.background_down = ""
        self.font_size = dp(13)
        self.halign = "center"
        self.valign = "middle"
        self.text_size = self.size
        self.bind(size=self._update_text_size)

    def _update_text_size(self, *args):
        self.text_size = self.size


class CalendarAppRoot(BoxLayout):

    def get_save_path(self):

        app = App.get_running_app()
        if app is None:
            # На всякий случай (например при запуске вне Kivy)
            return Path("shift_calendar_data.json")

        return Path(app.user_data_dir) / "shift_calendar_data.json"

    def save_state(self):
        save_file = self.get_save_path()
        data = {
            "current_month": {
                "year": self.current_month.year,
                "month": self.current_month.month,
            },
            "base_start_index": self.base_start_index,
            "base_pattern": list(self.base_pattern),
            "manual_shifts": {
                day.isoformat(): shift for day, shift in self.manual_shifts.items()
            },
            "start_input": self.start_input.text,
            "end_input": self.end_input.text,
        }

        try:
            save_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    def load_state(self):
        save_file = self.get_save_path()
        if not save_file.exists():
            return

        try:
            data = json.loads(save_file.read_text(encoding="utf-8"))
        except Exception:
            return

        current_month = data.get("current_month", {})
        if isinstance(current_month, dict):
            year = current_month.get("year")
            month = current_month.get("month")
            if isinstance(year, int) and isinstance(month, int):
                self.current_month = MonthState(year, month)

        base_start_index = data.get("base_start_index")
        if isinstance(base_start_index, int):
            self.base_start_index = base_start_index

        base_pattern = data.get("base_pattern")
        if isinstance(base_pattern, list) and base_pattern:
            self.base_pattern = [str(x) for x in base_pattern]

        manual = data.get("manual_shifts", {})
        if isinstance(manual, dict):
            loaded = {}
            for key, value in manual.items():
                try:
                    loaded[date.fromisoformat(key)] = str(value)
                except Exception:
                    continue
            self.manual_shifts = loaded

        start_input = data.get("start_input")
        end_input = data.get("end_input")
        if isinstance(start_input, str):
            self.start_input.text = start_input
        if isinstance(end_input, str):
            self.end_input.text = end_input

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(8), **kwargs)

        today = date.today()
        self.current_month = MonthState(today.year, today.month)
        self.manual_shifts: Dict[date, str] = {}
        self.base_start_index = 0
        self.base_pattern = list(BASE_PATTERN)

        self.month_label = Label(
            text="",
            size_hint_y=None,
            height=dp(36),
            font_size=dp(18),
            bold=True,
        )

        nav_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.prev_btn = Button(text="<- Месяц", on_press=self.go_prev_month)
        self.next_btn = Button(text="Месяц ->", on_press=self.go_next_month)
        nav_row.add_widget(self.prev_btn)
        nav_row.add_widget(self.month_label)
        nav_row.add_widget(self.next_btn)

        controls = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.shift_spinner = Spinner(
            text="День",
            values=BASE_PATTERN,
            size_hint_x=0.35,
        )
        self.apply_btn = Button(text="Применить к выбранному дню", on_press=self.apply_selected_shift)
        self.clear_btn = Button(text="Сбросить выбор", on_press=self.clear_selected_day)
        controls.add_widget(self.shift_spinner)
        controls.add_widget(self.apply_btn)
        controls.add_widget(self.clear_btn)

        self.info_label = Label(
            text="Выбери день, затем смену. Нажатие по дню меняет ручную смену.",
            size_hint_y=None,
            height=dp(30),
            font_size=dp(12),
        )

        range_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.start_input = TextInput(
            hint_text="Старт (дд.мм.гггг)",
            multiline=False,
            text=today.replace(day=1).strftime("%d.%m.%Y"),
        )
        self.end_input = TextInput(
            hint_text="Конец (дд.мм.гггг)",
            multiline=False,
            text=(today.replace(day=28) + timedelta(days=4)).replace(day=1).strftime("%d.%m.%Y"),
        )
        self.rebuild_btn = Button(text="Построить диапазон", on_press=self.rebuild_range)
        range_row.add_widget(self.start_input)
        range_row.add_widget(self.end_input)
        range_row.add_widget(self.rebuild_btn)

        self.calendar_container = BoxLayout()
        self.calendar_scroll = ScrollView(do_scroll_x=False)
        self.week_header = GridLayout(cols=7, size_hint_y=None, height=dp(28), spacing=dp(4))
        self.days_grid = GridLayout(cols=7, size_hint_y=None, spacing=dp(4), padding=dp(2))
        self.days_grid.bind(minimum_height=self.days_grid.setter("height"))

        calendar_box = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        calendar_box.bind(minimum_height=calendar_box.setter("height"))

        calendar_box.add_widget(self.week_header)
        calendar_box.add_widget(self.days_grid)

        self.calendar_scroll.add_widget(calendar_box)
        self.calendar_container.add_widget(self.calendar_scroll)

        self.selected_day: date | None = None
        self.selected_day_label = Label(
            text="Выбранный день: нет",
            size_hint_y=None,
            height=dp(26),
            font_size=dp(12),
        )

        self.add_widget(nav_row)
        self.add_widget(range_row)
        self.add_widget(controls)
        self.add_widget(self.info_label)
        self.add_widget(self.selected_day_label)
        self.add_widget(self.calendar_container)
        self.load_state()
        self.refresh_calendar()

    def go_prev_month(self, *_):
        if self.current_month.month == 1:
            self.current_month = MonthState(self.current_month.year - 1, 12)
        else:
            self.current_month = MonthState(self.current_month.year, self.current_month.month - 1)
        self.refresh_calendar()

    def go_next_month(self, *_):
        if self.current_month.month == 12:
            self.current_month = MonthState(self.current_month.year + 1, 1)
        else:
            self.current_month = MonthState(self.current_month.year, self.current_month.month + 1)
        self.refresh_calendar()

    def clear_selected_day(self, *_):
        if self.selected_day and self.selected_day in self.manual_shifts:
            del self.manual_shifts[self.selected_day]
            self.info_label.text = f"Смена на {self.selected_day.strftime('%d.%m.%Y')} сброшена"
            self.save_state()
            self.refresh_calendar()

    def apply_selected_shift(self, *_):
        if not self.selected_day:
            self.info_label.text = "Сначала выбери день на календаре."
            return
        self.manual_shifts[self.selected_day] = self.shift_spinner.text
        self.info_label.text = (
            f"На {self.selected_day.strftime('%d.%m.%Y')} установлено: {self.shift_spinner.text}"
        )
        self.save_state()
        self.refresh_calendar()

    def rebuild_range(self, *_):
        try:
            start_dt = parse_date_ddmmyyyy(self.start_input.text)
            end_dt = parse_date_ddmmyyyy(self.end_input.text)
        except Exception:
            self.info_label.text = "Неверный формат даты. Нужно дд.мм.гггг"
            return

        if start_dt > end_dt:
            self.info_label.text = "Начальная дата не может быть позже конечной."
            return

        self.current_month = MonthState(start_dt.year, start_dt.month)
        self.selected_day = None
        self.info_label.text = f"Диапазон перестроен: {start_dt.strftime('%d.%m.%Y')} — {end_dt.strftime('%d.%m.%Y')}"
        self.save_state()
        self.refresh_calendar()

    def month_bounds(self) -> tuple[date, date]:
        year = self.current_month.year
        month = self.current_month.month
        first_day = date(year, month, 1)
        last_day_num = calendar.monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)
        return first_day, last_day

    def refresh_calendar(self):
        self.week_header.clear_widgets()
        self.days_grid.clear_widgets()

        first_day, last_day = self.month_bounds()
        self.month_label.text = first_day.strftime("%B %Y")
        # Английские названия месяцев переводим вручную для простоты.
        months_ru = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
        }
        self.month_label.text = f"{months_ru[first_day.month]} {first_day.year}"

        # Дни недели сверху
        for name in WEEKDAY_NAMES:
            lbl = Label(
                text=name,
                size_hint_y=None,
                height=dp(28),
                bold=True,
            )
            self.week_header.add_widget(lbl)

        # Пустые клетки до первого дня месяца
        weekday_index = first_day.weekday()  # Monday = 0
        for _ in range(weekday_index):
            self.days_grid.add_widget(Label(text="", size_hint_y=None, height=dp(56)))

        # Строим полный календарь на месяц
        month_days = list(date_range(first_day, last_day))
        schedule = build_schedule(
            start_date=first_day,
            end_date=last_day,
            base_pattern=self.base_pattern,
            base_start_index=self.base_start_index,
            manual_shifts=self.manual_shifts,
        )

        for day in month_days:
            item = schedule[day]
            shift = item["shift"]
            short_shift = self.shift_short(shift)
            day_color = SHIFT_COLORS.get(shift, SHIFT_COLORS["Пусто"])

            is_selected = self.selected_day == day
            text = f"{day.day}\n{short_shift}"
            btn = ShiftDayButton(
                day_date=day,
                text=text,
                size_hint_y=None,
                height=dp(56),
                background_color=day_color,
                color=(0, 0, 0, 1),
            )

            if is_selected:
                btn.background_color = (0.25, 0.65, 1.0, 1)
                btn.color = (1, 1, 1, 1)

            btn.bind(on_press=self.on_day_press)
            self.days_grid.add_widget(btn)

        # Заполняем пустые клетки в конце месяца, чтобы сетка выглядела ровно
        used_cells = weekday_index + len(month_days)
        remainder = used_cells % 7
        if remainder != 0:
            for _ in range(7 - remainder):
                self.days_grid.add_widget(Label(text="", size_hint_y=None, height=dp(56)))

    def shift_short(self, shift: str) -> str:
        mapping = {
            "День": "День",
            "Ночь": "Ночь",
            "Отсыпной": "Отсыпной",
            "Выходной": "Выходной",
        }
        return mapping.get(shift, shift[:1].upper() if shift else "")

    def on_day_press(self, button: ShiftDayButton):
        self.selected_day = button.day_date
        if self.selected_day in self.manual_shifts:
            self.shift_spinner.text = self.manual_shifts[self.selected_day]
        else:
            self.shift_spinner.text = self.base_shift_for_day(self.selected_day)
        self.selected_day_label.text = f"Выбранный день: {self.selected_day.strftime('%d.%m.%Y')}"
        self.info_label.text = (
            f"День {self.selected_day.strftime('%d.%m.%Y')} выбран. "
            f"Текущая смена: {self.shift_spinner.text}"
        )
        self.save_state()
        self.refresh_calendar()

    def base_shift_for_day(self, day: date) -> str:
        first_day = date(day.year, day.month, 1)
        day_index = (day - first_day).days
        return self.base_pattern[(self.base_start_index + day_index) % len(self.base_pattern)]


class ShiftCalendarApp(App):
    def build(self):
        return CalendarAppRoot()


if __name__ == "__main__":
    ShiftCalendarApp().run()