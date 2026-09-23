# monitor.py - основной скрипт мониторинга регионов
# Опрос PSKReporter каждые 5 минуты, фильтрация несработанных регионов
import os
import sys
import json
import time
from datetime import datetime, timedelta

# Импортируем локальные модули
from config import (
    NEEDED_REGIONS_FILE, POLL_INTERVAL, SPOT_MAX_AGE_MINUTES,
    MAX_DISPLAY_SPOTS, TARGET_BANDS, TARGET_MODE, COLORS
)
from psk_source import get_stations, process_stations
from srr_regions import get_region_name


class RDAMonitor:
    """Основной класс монитора"""

    def __init__(self):
        self.needed_regions = []
        self.needed_set = set()
        self.seen_spots = {}           # Ключ → спот (для дедупликации)
        self.session_start = datetime.now()
        self.total_found = 0           # Всего найдено за сессию
        self.query_count = 0           # Количество опросов

    def load_needed_regions(self):
        """Загружает список несработанных регионов из JSON"""
        if not os.path.exists(NEEDED_REGIONS_FILE):
            print(f"{COLORS['RED']}❌ Файл {NEEDED_REGIONS_FILE} не найден{COLORS['RESET']}")
            print(f"   Сначала запустите: python hamlog_parser.py")
            return False

        try:
            with open(NEEDED_REGIONS_FILE, 'r', encoding='utf-8') as f:
                self.needed_regions = json.load(f)

            # Создаём множество ключей для быстрого поиска
            for item in self.needed_regions:
                key = f"{item['region']}_{item['band']}_{item['mode']}"
                self.needed_set.add(key)

            return True
        except Exception as e:
            print(f"{COLORS['RED']}❌ Ошибка загрузки: {e}{COLORS['RESET']}")
            return False

    def print_header(self):
        """Печатает заголовок сессии"""
        print()
        print(f"{COLORS['CYAN']}{'=' * 70}{COLORS['RESET']}")
        print(f"{COLORS['BOLD']}{COLORS['CYAN']} RDA MONITOR - Трекер несработанных регионов {COLORS['RESET']}")
        print(f"{COLORS['CYAN']}{'=' * 70}{COLORS['RESET']}")
        print(f"  Старт сессии:    {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Интервал опроса: {POLL_INTERVAL} сек ({POLL_INTERVAL // 60} мин)")
        print(f"  Несработанных:   {len(self.needed_set)} слотов")
        print(f"  Диапазоны:       {', '.join(TARGET_BANDS)}")
        print(f"  Мода:            {TARGET_MODE}")
        print(f"{COLORS['CYAN']}{'=' * 70}{COLORS['RESET']}")
        print(f"  Нажмите {COLORS['YELLOW']}Ctrl+C{COLORS['RESET']} для остановки")
        print()

    def update_seen_spots(self, new_spots):
        """
        Обновляет список увиденных спотов с дедупликацией.
        Возвращает список НОВЫХ спотов (которых не было раньше).
        """
        new_only = []

        for spot in new_spots:
            # Ключ для дедупликации: позывной + диапазон + мода
            key = f"{spot['callsign']}_{spot['band']}_{spot['mode']}"

            if key not in self.seen_spots:
                self.seen_spots[key] = spot
                new_only.append(spot)
                self.total_found += 1
            else:
                # Обновляем время, если спот свежее
                if spot['time'] > self.seen_spots[key]['time']:
                    self.seen_spots[key]['time'] = spot['time']

        return new_only

    def get_region_full_name(self, region_code):
        """Получает полное название региона по коду"""
        # Сначала ищем в needed_regions (там есть поле name)
        for item in self.needed_regions:
            if item['region'] == region_code and item.get('name'):
                return item['name']

        # Если не нашли — пробуем через справочник SRR
        name = get_region_name(region_code)
        return name if name else region_code

    def display_spot(self, spot, is_new=True):
        """Красиво отображает один спот"""
        callsign = spot['callsign']
        band = spot['band']
        mode = spot['mode']
        region = spot['region']
        freq = spot['frequency'] / 1000  # в кГц
        spot_time = spot['time']
        spot_type = spot.get('type', 'RECEIVER')

        # Определяем иконку и цвет по типу станции
        if spot_type == 'RECEIVER':
            icon = "👂"
            type_name = "СЛУШАЕТ"
            color = COLORS['GREEN']
        else:
            icon = "📡"
            type_name = "ПЕРЕДАЁТ"
            color = COLORS['MAGENTA']

        # Маркер новизны
        new_marker = f"{COLORS['YELLOW']}★ НОВЫЙ{COLORS['RESET']} " if is_new else ""

        # Название региона
        region_name = self.get_region_full_name(region)
        if len(region_name) > 25:
            region_name = region_name[:22] + "..."

        # Выводим
        print(f"  {new_marker}{icon} {color}{spot_time}{COLORS['RESET']} | "
              f"{COLORS['BOLD']}{callsign:10}{COLORS['RESET']} | "
              f"{type_name:8} | "
              f"{COLORS['CYAN']}{region:5}{COLORS['RESET']} | "
              f"{COLORS['BLUE']}{band:4}{COLORS['RESET']} | "
              f"{mode:4} | "
              f"{freq:7.1f} kHz | "
              f"{COLORS['WHITE']}{region_name}{COLORS['RESET']}")

    def print_status_bar(self):
        """Печатает строку статуса"""
        elapsed = datetime.now() - self.session_start
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)
        seconds = int(elapsed.total_seconds() % 60)

        # Подсчёт по диапазонам
        band_counts = {}
        for spot in self.seen_spots.values():
            band = spot['band']
            band_counts[band] = band_counts.get(band, 0) + 1

        # Формируем строку по диапазонам
        band_str = " | ".join([
            f"{band}: {count}" for band, count in
            sorted(band_counts.items(), key=lambda x: TARGET_BANDS.index(x[0]) if x[0] in TARGET_BANDS else 99)
        ])

        print()
        print(f"{COLORS['CYAN']}{'─' * 70}{COLORS['RESET']}")
        print(f"  ⏱️  Время сессии: {hours:02d}:{minutes:02d}:{seconds:02d} | "
              f"🔍 Опросов: {self.query_count} | "
              f"🎯 Найдено: {self.total_found} | "
              f"📊 Уникальных: {len(self.seen_spots)}")
        if band_str:
            print(f"  📡 По диапазонам: {band_str}")
        print(f"{COLORS['CYAN']}{'─' * 70}{COLORS['RESET']}")

    def do_poll(self):
        """Выполняет один цикл опроса"""
        self.query_count += 1

        # Запрашиваем данные
        stations = get_stations()

        if not stations:
            print(f"  {COLORS['YELLOW']}⚠️ Данные не получены (возможно, rate limit){COLORS['RESET']}")
            return

        # Обрабатываем
        interesting = process_stations(
            stations,
            self.needed_set,
            bands=TARGET_BANDS,
            mode=TARGET_MODE
        )

        # Дедупликация
        new_spots = self.update_seen_spots(interesting)

        # Выводим
        current_time = datetime.now().strftime('%H:%M:%S')

        if new_spots:
            print(f"\n{COLORS['GREEN']}{'─' * 70}{COLORS['RESET']}")
            print(f"{COLORS['GREEN']}{COLORS['BOLD']}  🎉 НАЙДЕНО {len(new_spots)} НОВЫХ СТАНЦИЙ в {current_time}{COLORS['RESET']}")
            print(f"{COLORS['GREEN']}{'─' * 70}{COLORS['RESET']}")

            for spot in new_spots[:MAX_DISPLAY_SPOTS]:
                self.display_spot(spot, is_new=True)

            if len(new_spots) > MAX_DISPLAY_SPOTS:
                print(f"  ... и ещё {len(new_spots) - MAX_DISPLAY_SPOTS} станций")
        else:
            print(f"  {COLORS['YELLOW']}[{current_time}] Новых станций не найдено. "
                  f"Получено приёмников: {len(stations['receivers'])}, "
                  f"обработано подходящих: {len(interesting)}{COLORS['RESET']}")

    def run(self):
        """Основной цикл мониторинга"""
        # Загружаем данные
        if not self.load_needed_regions():
            return 1

        self.print_header()

        try:
            while True:
                # Опрашиваем
                self.do_poll()

                # Статус
                self.print_status_bar()

                # Ждём следующий опрос
                next_poll = datetime.now() + timedelta(seconds=POLL_INTERVAL)
                print(f"\n  💤 Следующий опрос: {next_poll.strftime('%H:%M:%S')}")

                # Обратный отсчёт с возможностью прерывания
                for remaining in range(POLL_INTERVAL, 0, -1):
                    sys.stdout.write(f"\r  ⏳ До опроса: {remaining:3d} сек   ")
                    sys.stdout.flush()
                    time.sleep(1)

                print()  # Новая строка после таймера

        except KeyboardInterrupt:
            self.print_final_stats()
            return 0

    def print_final_stats(self):
        """Печатает итоговую статистику при остановке"""
        print()
        print(f"\n{COLORS['CYAN']}{'=' * 70}{COLORS['RESET']}")
        print(f"{COLORS['BOLD']}{COLORS['CYAN']} ИТОГОВАЯ СТАТИСТИКА СЕССИИ {COLORS['RESET']}")
        print(f"{COLORS['CYAN']}{'=' * 70}{COLORS['RESET']}")

        elapsed = datetime.now() - self.session_start
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)
        seconds = int(elapsed.total_seconds() % 60)

        print(f"  Начало:           {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Окончание:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Длительность:     {hours:02d}:{minutes:02d}:{seconds:02d}")
        print(f"  Опросов PSK:      {self.query_count}")
        print(f"  Найдено спотов:   {self.total_found}")
        print(f"  Уникальных:       {len(self.seen_spots)}")

        # По диапазонам
        if self.seen_spots:
            print(f"\n  📊 Распределение по диапазонам:")
            band_counts = {}
            for spot in self.seen_spots.values():
                band = spot['band']
                band_counts[band] = band_counts.get(band, 0) + 1

            for band in TARGET_BANDS:
                count = band_counts.get(band, 0)
                if count > 0:
                    print(f"     {band:5}: {count:3d} станций")

            # По регионам
            print(f"\n  🗺️  Найдено уникальных регионов: {len(set(s['region'] for s in self.seen_spots.values()))}")

            # Топ-5 регионов
            region_counts = {}
            for spot in self.seen_spots.values():
                region = spot['region']
                region_counts[region] = region_counts.get(region, 0) + 1

            top_regions = sorted(region_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            if top_regions:
                print(f"\n  🏆 Топ-5 регионов:")
                for region, count in top_regions:
                    name = self.get_region_full_name(region)
                    print(f"     {region:5} ({name[:25]:25}): {count} станций")

        print(f"\n{COLORS['CYAN']}{'=' * 70}{COLORS['RESET']}")
        print(f"  👋 До свидания! Хороших QSO!\n")


def main():
    monitor = RDAMonitor()
    return monitor.run()


if __name__ == '__main__':
    sys.exit(main() or 0)