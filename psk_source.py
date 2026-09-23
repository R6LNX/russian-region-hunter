# psk_source.py - получение станций с PSKReporter
# Работает со всеми диапазонами: 160, 80, 40, 30, 20, 17, 15, 12, 10
import requests
import xml.etree.ElementTree as ET
import time
from datetime import datetime
from srr_regions import get_region_hamlog, normalize_mode
from config import EXCLUDED_DECODER_SOFTWARE

# Настройки
PSK_URL = "https://pskreporter.info/query"
MIN_REQUEST_INTERVAL = 120  # Интервал между запросами: 2 минуты

# Все диапазоны, которые мы хотим отслеживать
ALL_BANDS = ['160M', '80M', '40M', '30M', '20M', '17M', '15M', '12M', '10M']

# Целевая мода для мониторинга (совместимо с Hamlog)
TARGET_MODE = 'DIG'

# Максимальный возраст спота для передатчиков (минуты)
SENDER_MAX_AGE_MINUTES = 60

# Время последнего запроса
_last_request_time = 0


def get_stations():
    """
    Получает станции с PSKReporter: и приёмников, и передатчиков.
    """
    global _last_request_time

    current_time = time.time()
    time_since_last = current_time - _last_request_time

    if time_since_last < MIN_REQUEST_INTERVAL:
        wait_time = MIN_REQUEST_INTERVAL - time_since_last
        print(f"⏳ Слишком рано. Подождите {wait_time:.0f} сек...")
        return None

    print("📡 Запрашиваю данные с PSKReporter...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/xml, application/xml",
    }

    try:
        response = requests.get(PSK_URL, headers=headers, timeout=30)
        _last_request_time = time.time()

        if response.status_code == 429:
            print("❌ Слишком много запросов. Подождите.")
            return None

        if response.status_code != 200:
            print(f"❌ Ошибка HTTP: {response.status_code}")
            return None

        stations = parse_xml_response(response.text)
        return stations

    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return None


def parse_xml_response(xml_text):
    """
    Парсит XML-ответ от PSKReporter и извлекает приёмников и передатчиков.
    """
    receivers = []
    senders = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"❌ Ошибка парсинга XML: {e}")
        return {'receivers': receivers, 'senders': senders}

    # === Извлекаем активных приёмников ===
    for element in root.iter('activeReceiver'):
        callsign = element.get('callsign', '')
        if callsign:
            receiver = {
                'type': 'RECEIVER',
                'callsign': callsign,
                'frequency': int(element.get('frequency', 0)),
                'mode': element.get('mode', ''),
                'locator': element.get('locator', ''),
                'region_name': element.get('region', ''),
                'dxcc': element.get('DXCC', ''),
                'decoder_software': element.get('decoderSoftware', ''),
            }
            receivers.append(receiver)

    # === Извлекаем передатчиков из receptionReport ===
    for element in root.iter('receptionReport'):
        callsign = element.get('senderCallsign', '')
        if not callsign:
            continue

        freq = int(element.get('frequency', 0))
        mode = element.get('mode', '')
        flow_start = float(element.get('flowStartSeconds', 0))

        snr = element.get('sNR', None)
        if snr:
            try:
                snr = float(snr)
            except:
                snr = None

        receiver = element.get('receiverCallsign', '')

        sender = {
            'type': 'SENDER',
            'callsign': callsign,
            'frequency': freq,
            'mode': mode,
            'flowStartSeconds': flow_start,
            'snr': snr,
            'receiver': receiver,
        }
        senders.append(sender)

    print(f"   📥 Получено: {len(receivers)} приёмников, {len(senders)} передатчиков")

    return {'receivers': receivers, 'senders': senders}


def freq_to_band(freq_hz):
    """Определяет диапазон по частоте в герцах"""
    freq_khz = freq_hz / 1000

    if 1810 <= freq_khz <= 2000: return '160M'
    elif 3500 <= freq_khz <= 3800: return '80M'
    elif 7000 <= freq_khz <= 7300: return '40M'
    elif 10100 <= freq_khz <= 10150: return '30M'
    elif 14000 <= freq_khz <= 14350: return '20M'
    elif 18068 <= freq_khz <= 18168: return '17M'
    elif 21000 <= freq_khz <= 21450: return '15M'
    elif 24890 <= freq_khz <= 24990: return '12M'
    elif 28000 <= freq_khz <= 29700: return '10M'
    return None


def is_excluded_software(decoder_software):
    """
    Проверяет, является ли decoderSoftware скимером/SDR из чёрного списка.
    Возвращает True, если нужно отсеять.
    """
    if not decoder_software:
        return False

    decoder_lower = decoder_software.lower()

    for excluded in EXCLUDED_DECODER_SOFTWARE:
        if excluded.lower() in decoder_lower:
            return True

    return False


def process_stations(stations, needed_set, bands=ALL_BANDS, mode=TARGET_MODE):
    """
    Обрабатывает станции: определяет регион, диапазон, проверяет нужность.
    Дедуплицирует по ключу: позывной + диапазон + мода + тип.
    """
    if not stations:
        return []

    interesting = []
    seen_keys = set()  # Дедупликация на этапе обработки
    current_time = time.time()
    skipped_skimmers = 0

    # Обрабатываем приёмников
    for station in stations['receivers']:
        # Проверяем decoderSoftware на скимеры
        decoder_sw = station.get('decoder_software', '')
        if is_excluded_software(decoder_sw):
            skipped_skimmers += 1
            continue

        processed = _process_one_station(station, needed_set, bands, mode, current_time)
        if processed:
            # Дедупликация: один позывной на одном диапазоне = одна запись
            key = f"{processed['callsign']}_{processed['band']}_{processed['mode']}_{processed['type']}"
            if key not in seen_keys:
                seen_keys.add(key)
                interesting.append(processed)

    # Обрабатываем передатчиков
    for station in stations['senders']:
        # Проверяем свежесть спота
        flow_start = station.get('flowStartSeconds', 0)
        if flow_start > 0:
            age_seconds = current_time - flow_start
            if age_seconds > SENDER_MAX_AGE_MINUTES * 60:
                continue
            if age_seconds < -60:
                continue

        processed = _process_one_station(station, needed_set, bands, mode, current_time)
        if processed:
            # Дедупликация: один позывной на одном диапазоне = одна запись
            key = f"{processed['callsign']}_{processed['band']}_{processed['mode']}_{processed['type']}"
            if key not in seen_keys:
                seen_keys.add(key)
                interesting.append(processed)

    if skipped_skimmers > 0:
        print(f"   🚫 Отсеяно скимеров/SDR: {skipped_skimmers}")

    return interesting


def _process_one_station(station, needed_set, bands, mode, current_time):
    """Обработка одной станции"""
    callsign = station['callsign']
    freq = station['frequency']
    raw_mode = station['mode']
    station_type = station['type']

    # Определяем регион
    region = get_region_hamlog(callsign)
    if region in ('Не РФ', 'Не определён'):
        return None

    # Определяем диапазон по частоте
    band = freq_to_band(freq)
    if not band:
        return None

    # Фильтруем нужные диапазоны
    if band not in bands:
        return None

    # Нормализуем моду
    normalized_mode = normalize_mode(raw_mode)
    if not normalized_mode:
        return None

    # Проверяем целевую моду
    if normalized_mode != mode:
        return None

    # Проверяем, нужен ли этот слот
    key = f"{region}_{band}_{normalized_mode}"
    if key not in needed_set:
        return None

    return {
        'time': datetime.now().strftime('%H:%M:%S'),
        'callsign': callsign,
        'type': station_type,
        'region': region,
        'band': band,
        'mode': normalized_mode,
        'frequency': freq,
    }


if __name__ == '__main__':
    import json
    import os

    print("=" * 60)
    print("Тест получения станций с PSKReporter")
    print(f"Интервал опроса: {MIN_REQUEST_INTERVAL} сек ({MIN_REQUEST_INTERVAL // 60} мин)")
    print(f"Целевая мода: {TARGET_MODE}")
    print(f"Макс. возраст передатчиков: {SENDER_MAX_AGE_MINUTES} мин")
    print(f"Чёрный список: {len(EXCLUDED_DECODER_SOFTWARE)} записей")
    print("=" * 60)
    print()

    # Загружаем список нужных регионов
    needed_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'needed_regions.json')

    if not os.path.exists(needed_file):
        print(f"❌ Файл {needed_file} не найден")
        print("Сначала запустите hamlog_parser.py")
        exit(1)

    with open(needed_file, 'r', encoding='utf-8') as f:
        needed_list = json.load(f)

    # Создаём множество ключей
    needed_set = set()
    for item in needed_list:
        key = f"{item['region']}_{item['band']}_{item['mode']}"
        needed_set.add(key)

    print(f"Загружено несработанных слотов: {len(needed_set)}")
    print()

    # Получаем станции
    stations = get_stations()

    if stations:
        print(f"\n📊 Итого получено:")
        print(f"   Приёмников: {len(stations['receivers'])}")
        print(f"   Передатчиков: {len(stations['senders'])}")
        print()

        # Обрабатываем
        interesting = process_stations(stations, needed_set)

        # Разделяем по типам
        receivers = [s for s in interesting if s['type'] == 'RECEIVER']
        senders = [s for s in interesting if s['type'] == 'SENDER']

        print(f"🎯 Найдено интересных станций: {len(interesting)}")
        print(f"   👂 Приёмников: {len(receivers)}")
        print(f"   📡 Передатчиков: {len(senders)}")
        print()

        # Показываем приёмников
        if receivers:
            print("--- ПРИЁМНИКИ ---")
            for s in receivers[:20]:
                print(f"👂 {s['time']} | {s['callsign']:10} | "
                      f"{s['region']:5} | {s['band']:4} | {s['mode']:4} | "
                      f"{s['frequency']/1000:.1f} kHz")

        # Показываем передатчиков
        if senders:
            print("\n--- ПЕРЕДАТЧИКИ ---")
            for s in senders[:20]:
                print(f"📡 {s['time']} | {s['callsign']:10} | "
                      f"{s['region']:5} | {s['band']:4} | {s['mode']:4} | "
                      f"{s['frequency']/1000:.1f} kHz")
    else:
        print("Не удалось получить станции.")