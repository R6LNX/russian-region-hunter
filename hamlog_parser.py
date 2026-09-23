# hamlog_parser.py - парсинг таблицы несработанных регионов с Hamlog
# Работает со всеми диапазонами: 160, 80, 40, 30, 20, 17, 15, 12, 10
import os
import json
from bs4 import BeautifulSoup

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'needed_regions.json')

# Описание структуры таблицы:
# Колонка 0 — регион
# Колонки 1-3: 160M (CW, PH, DIG)
# Колонки 4-6: 80M (CW, PH, DIG)
# Колонки 7-9: 40M (CW, PH, DIG)
# Колонки 10-11: 30M (CW, DIG) — только 2 колонки, нет PH!
# Колонки 12-14: 20M (CW, PH, DIG)
# Колонки 15-17: 17M (CW, PH, DIG)
# Колонки 18-20: 15M (CW, PH, DIG)
# Колонки 21-23: 12M (CW, PH, DIG)
# Колонки 24-26: 10M (CW, PH, DIG)

BAND_COLUMNS = [
    # (название диапазона, список индексов колонок и соответствующих мод)
    ('160M', [(1, 'CW'), (2, 'PH'), (3, 'DIG')]),
    ('80M',  [(4, 'CW'), (5, 'PH'), (6, 'DIG')]),
    ('40M',  [(7, 'CW'), (8, 'PH'), (9, 'DIG')]),
    ('30M',  [(10, 'CW'), (11, 'DIG')]),  # Нет PH на 30м!
    ('20M',  [(12, 'CW'), (13, 'PH'), (14, 'DIG')]),
    ('17M',  [(15, 'CW'), (16, 'PH'), (17, 'DIG')]),
    ('15M',  [(18, 'CW'), (19, 'PH'), (20, 'DIG')]),
    ('12M',  [(21, 'CW'), (22, 'PH'), (23, 'DIG')]),
    ('10M',  [(24, 'CW'), (25, 'PH'), (26, 'DIG')]),
]

# Все диапазоны, которые мы хотим отслеживать
ALL_BANDS = ['160M', '80M', '40M', '30M', '20M', '17M', '15M', '12M', '10M']

# Целевая мода для мониторинга
TARGET_MODE = 'DIG'


def parse_hamlog_html(html_content):
    """
    Парсит HTML-страницу статистики регионов с Hamlog.
    
    Возвращает список несработанных слотов в формате:
    [{'region': 'R0C', 'band': '20M', 'mode': 'DIG', 'name': 'Хабаровский край'}, ...]
    """
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Находим основную таблицу с регионами
    tables = soup.find_all('table', class_='table-bordered')
    if not tables:
        print("❌ Таблица регионов не найдена")
        return None
    
    table = tables[0]
    rows = table.find_all('tr')
    
    needed_regions = []
    
    # Пропускаем первые 2 строки (заголовки)
    for row in rows[2:]:
        cells = row.find_all('td')
        if not cells or len(cells) < 2:
            continue
        
        # Первая ячейка — регион
        region_cell = cells[0]
        region_text = region_cell.get_text(strip=True)
        
        # Извлекаем код региона и название
        region_code = None
        region_name = None
        
        # Код региона в начале, название после <br> или <small>
        small_tag = region_cell.find('small')
        if small_tag:
            region_name = small_tag.get_text(strip=True)
            # Код региона — текст до <small>
            full_text = region_cell.get_text(strip=True)
            region_code = full_text.replace(region_name, '').strip()
        else:
            # Если нет <small>, берём первую строку
            parts = region_text.split('\n')
            region_code = parts[0].strip()
            region_name = parts[1].strip() if len(parts) > 1 else ''
        
        if not region_code or region_code == '':
            continue
        
        # Проверяем каждую колонку каждого диапазона
        for band, columns in BAND_COLUMNS:
            for col_idx, mode in columns:
                if col_idx >= len(cells):
                    continue
                
                cell = cells[col_idx]
                
                # Проверяем наличие иконки (сработано)
                icon = cell.find('i', class_='fa-plus')
                worked = icon is not None
                
                # Если не сработано — добавляем в список нужных
                if not worked:
                    needed_regions.append({
                        'region': region_code,
                        'band': band,
                        'mode': mode,
                        'name': region_name,
                    })
    
    return needed_regions


def filter_target_regions(needed_regions, bands=ALL_BANDS, mode=TARGET_MODE):
    """
    Фильтрует список нужных регионов по целевым диапазонам и моде.
    """
    filtered = []
    for item in needed_regions:
        if item['band'] in bands and item['mode'] == mode:
            filtered.append(item)
    return filtered


def save_needed_regions(regions, filename=OUTPUT_FILE):
    """Сохраняет список нужных регионов в JSON файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(regions, f, ensure_ascii=False, indent=2)
    print(f"💾 Сохранено {len(regions)} записей в файл: {filename}")


def load_needed_regions(filename=OUTPUT_FILE):
    """Загружает список нужных регионов из JSON файла"""
    if not os.path.exists(filename):
        return None
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_statistics(needed_regions):
    """Возвращает статистику по нужным регионам"""
    stats = {
        'total': len(needed_regions),
        'by_band': {},
        'unique_regions': set(),
    }
    
    for item in needed_regions:
        band = item['band']
        region = item['region']
        
        stats['unique_regions'].add(region)
        
        if band not in stats['by_band']:
            stats['by_band'][band] = 0
        stats['by_band'][band] += 1
    
    stats['unique_regions_count'] = len(stats['unique_regions'])
    del stats['unique_regions']
    
    return stats


if __name__ == '__main__':
    print("=" * 60)
    print("Парсер таблицы регионов Hamlog")
    print("=" * 60)
    
    # Загружаем сохраненный HTML файл
    html_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hamlog_page.html')
    
    if not os.path.exists(html_file):
        print(f"❌ Файл {html_file} не найден")
        print("Сначала сохраните страницу статистики регионов в этот файл")
        exit(1)
    
    print(f"Загружаю файл: {html_file}")
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Парсим
    needed_regions = parse_hamlog_html(html_content)
    
    if needed_regions is None:
        print("❌ Не удалось распарсить таблицу")
        exit(1)
    
    print(f"✅ Найдено несработанных слотов: {len(needed_regions)}")
    
    # Фильтруем по целевой моде
    target_regions = filter_target_regions(needed_regions)
    print(f"✅ После фильтрации по {TARGET_MODE}: {len(target_regions)}")
    
    # Сохраняем
    save_needed_regions(target_regions)
    
    # Статистика
    stats = get_statistics(target_regions)
    print(f"\n📊 Статистика:")
    print(f"   Всего несработанных слотов: {stats['total']}")
    print(f"   Уникальных регионов: {stats['unique_regions_count']}")
    print(f"\n   По диапазонам:")
    for band in ALL_BANDS:
        count = stats['by_band'].get(band, 0)
        print(f"   {band:5}: {count} слотов")