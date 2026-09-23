# srr_regions.py - определение регионов на основе данных SRR API
# Данные берутся из локального файла srr_info.json

import json
import os
import re

SRR_INFO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'srr_info.json')

# Кэш загруженных данных
_srr_data = None
_prefix_to_region = None
_hamlog_to_srr = None
_srr_to_hamlog = None
_band_modes_cache = None


def _load_data():
    """Загружает данные из srr_info.json (один раз, с кэшированием)"""
    global _srr_data
    if _srr_data is not None:
        return _srr_data

    if not os.path.exists(SRR_INFO_FILE):
        raise FileNotFoundError(
            f"Файл {SRR_INFO_FILE} не найден!\n"
            "Скачайте справочник с: https://award.srr.ru/api/v1/info\n"
            "и сохраните как srr_info.json в папке проекта."
        )

    with open(SRR_INFO_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    _srr_data = raw.get('data', raw)
    return _srr_data


def _build_maps():
    """Строит все словари соответствия (вызывается один раз)"""
    global _prefix_to_region, _hamlog_to_srr, _srr_to_hamlog

    if _prefix_to_region is not None:
        return

    data = _load_data()
    regions = data.get('regions', [])

    _prefix_to_region = {}
    _hamlog_to_srr = {}
    _srr_to_hamlog = {}

    for region in regions:
        code = region.get('code', '').strip()
        prefix_str = region.get('prefix', '').strip()
        name = region.get('name', '').strip()
        date_end = region.get('date_actual_end')

        # Пропускаем упразднённые регионы
        if date_end:
            continue
        # Пропускаем регионы с пометкой «упразднён» (имя начинается с «x»)
        if name.startswith('x'):
            continue

        if not code or not prefix_str:
            continue

        # Разбиваем префиксы по запятой
        prefixes = [p.strip() for p in prefix_str.split(',')]
        first_prefix = None

        for pfx in prefixes:
            if not pfx:
                continue

            # Сохраняем первый префикс как код Hamlog
            if first_prefix is None:
                first_prefix = pfx

            # Из префикса (например, "R0C") извлекаем "цифра+буква" (например, "0C")
            match = re.search(r'(\d[A-Z])', pfx.upper())
            if match:
                short_pfx = match.group(1)
                _prefix_to_region[short_pfx] = code

            # Маппинг полный префикс → код региона
            _hamlog_to_srr[pfx.upper()] = code

        # Маппинг код региона → первый префикс
        if first_prefix:
            _srr_to_hamlog[code] = first_prefix.upper()


def get_region(callsign):
    """
    Определяет код региона (например, 'HK', 'MA', 'RO') по позывному.
    """
    if not callsign:
        return 'Не определён'

    callsign = callsign.upper().strip()
    base_call = callsign.split('/')[0]

    # Проверяем, что позывной российский
    if not re.match(r'^(R[A-Z0-9]?|U[A-I])', base_call):
        return 'Не РФ'

    # Извлекаем "цифра + первая буква после цифры"
    match = re.search(r'\d([A-Z])', base_call)
    if not match:
        return 'Не определён'

    prefix = match.group(0)

    _build_maps()

    if prefix in _prefix_to_region:
        return _prefix_to_region[prefix]

    return 'Не определён'


def get_region_hamlog(callsign):
    """
    Определяет регион в формате Hamlog (например, 'R0C', 'R3A', 'R9X').
    """
    srr_code = get_region(callsign)

    if srr_code in ('Не РФ', 'Не определён'):
        return srr_code

    return srr_code_to_hamlog(srr_code)


def srr_code_to_hamlog(srr_code):
    """Конвертирует код региона в формат, совместимый с Hamlog."""
    _build_maps()
    return _srr_to_hamlog.get(srr_code, srr_code)


def hamlog_to_srr_code(hamlog_code):
    """Конвертирует код из формата, совместимого с Hamlog, в формат."""
    _build_maps()
    return _hamlog_to_srr.get(hamlog_code.upper(), hamlog_code)


def get_band_by_freq(frequency_khz):
    """Определяет диапазон по частоте в кГц."""
    band_modes = _get_band_modes()

    for bm in band_modes:
        if bm['freq_from'] <= frequency_khz <= bm['freq_to']:
            return bm['band']

    return None


def get_band_mode_by_freq(frequency_khz):
    """Определяет диапазон и моду по частоте в кГц."""
    band_modes = _get_band_modes()

    for bm in band_modes:
        if bm['freq_from'] <= frequency_khz <= bm['freq_to']:
            return bm['band'], bm['mode']

    return None, None


def _get_band_modes():
    """Загружает и кэширует справочник диапазонов с частотами"""
    global _band_modes_cache
    if _band_modes_cache is not None:
        return _band_modes_cache

    data = _load_data()

    bands = {b['id']: b['name'].strip() for b in data.get('bands', [])}
    modes = {m['id']: m['name'].strip() for m in data.get('modes', [])}

    result = []
    for bm in data.get('band_modes', []):
        band_name = bands.get(bm['id_band'], '')
        mode_name = modes.get(bm['id_mode'], '')
        result.append({
            'band': band_name,
            'mode': mode_name,
            'freq_from': bm.get('freqFrom', 0),
            'freq_to': bm.get('freqTo', 0),
        })

    _band_modes_cache = result
    return _band_modes_cache


def normalize_mode(mode):
    """
    Нормализует моду в стандартный формат, совместимый с Hamlog.
    FT8, FT4, JT65 и т.д. → DIG
    CW → CW
    SSB, USB, LSB → PH
    """
    if not mode:
        return None

    mode = mode.upper().strip()

    digi_modes = [
        'FT8', 'FT4', 'FT2', 'JT65', 'JT9', 'JT4', 'JT6M', 'JT44',
        'PSK31', 'PSK63', 'PSK125', 'PSK250', 'PSK500', 'PSK1000',
        'QPSK31', 'QPSK63', 'QPSK125', 'QPSK250', 'QPSK500',
        'RTTY', 'RTTYM', 'OLIVIA', 'CONTESTI', 'HELL', 'THOR',
        'MT63', 'MFSK16', 'MFSK31', 'DOMINO', 'FST4', 'FST4W',
        'JS8', 'Q65', 'MSK144', 'FSK441', 'ISCAT', 'WSPR',
        'DATA', 'PKT', 'PAC', 'PAX', 'TOR', 'AMTOR',
        'SSTV', 'FAX', 'DIGI',
    ]

    cw_modes = ['CW', 'PCW']
    ph_modes = ['SSB', 'USB', 'LSB', 'AM', 'FM', 'PH', 'PHONE']

    if mode in digi_modes:
        return 'DIG'
    elif mode in cw_modes:
        return 'CW'
    elif mode in ph_modes:
        return 'PH'

    # Дополнительная проверка по подстрокам
    if 'PSK' in mode or 'FT' in mode or 'JT' in mode:
        return 'DIG'

    return mode


def get_region_name(region_code):
    """Возвращает название региона по коду"""
    data = _load_data()

    for region in data.get('regions', []):
        if region.get('code', '').strip() == region_code:
            return region.get('name', '').strip()

    return ''


def get_all_regions():
    """Возвращает список всех активных регионов"""
    _build_maps()
    data = _load_data()
    result = []

    for region in data.get('regions', []):
        if region.get('date_actual_end'):
            continue
        if region.get('name', '').startswith('x'):
            continue

        result.append({
            'code': region.get('code', '').strip(),
            'name': region.get('name', '').strip(),
            'prefix': region.get('prefix', '').strip(),
        })

    return result


# =====================================================================
# ТЕСТОВЫЙ БЛОК
# =====================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("Тест модуля srr_regions.py")
    print("=" * 60)

    # Тест определения региона по позывному
    print("\nТЕСТ 1: Определение регионов")
    test_calls = [
        ("R0CBS", "HK", "R0C"),
        ("R3ABC", "MA", "R2A"),
        ("R9XYZ", "KO", "R1I"),
        ("UA3DEF", "MO", "R2D"),
        ("R6LNX", "RO", "R6L"),
        ("K1USA", "Не РФ", "Не РФ"),
        ("DL1ABC", "Не РФ", "Не РФ"),
    ]

    all_pass = True
    for callsign, exp_srr, exp_hamlog in test_calls:
        result_srr = get_region(callsign)
        result_hamlog = get_region_hamlog(callsign)
        ok = (result_srr == exp_srr and result_hamlog == exp_hamlog)
        status = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {status} {callsign:10} → SRR: {result_srr:6} | Hamlog: {result_hamlog}")

    # Тест нормализации моды
    print("\nТЕСТ 2: Нормализация моды")
    mode_tests = [
        ("FT8", "DIG"),
        ("FT4", "DIG"),
        ("CW", "CW"),
        ("SSB", "PH"),
        ("USB", "PH"),
        ("RTTY", "DIG"),
        ("PSK31", "DIG"),
        ("JT65", "DIG"),
        ("FM", "PH"),
    ]

    for mode, expected in mode_tests:
        result = normalize_mode(mode)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {status} {mode:8} → {result}")

    # Тест определения диапазона
    print("\nТЕСТ 3: Определение диапазона по частоте")
    freq_tests = [
        (14074, "20M"),
        (7074, "40M"),
        (3573, "80M"),
        (21074, "15M"),
        (28074, "10M"),
        (1840, "160M"),
        (10136, "30M"),
        (18100, "17M"),
        (24915, "12M"),
    ]

    for freq, expected_band in freq_tests:
        result = get_band_by_freq(freq)
        ok = result == expected_band
        status = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {status} {freq:6} кГц → {result}")

    # Итог
    print("\n" + "=" * 60)
    if all_pass:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print("⚠️ ЕСТЬ ПРОБЛЕМЫ!")
    print("=" * 60)