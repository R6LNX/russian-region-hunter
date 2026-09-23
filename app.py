# app.py - Веб-сервер Russian Region Hunter (RRH)
import os
import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request

from config import NEEDED_REGIONS_FILE, POLL_INTERVAL, TARGET_BANDS, TARGET_MODE
from psk_source import get_stations, process_stations
from srr_regions import get_region_name

app = Flask(__name__)

# --- Пути ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKED_SPOTS_FILE = os.path.join(BASE_DIR, 'worked_spots.json')

# --- Глобальное состояние ---
needed_set = set()
needed_regions_list = []
all_spots = []
worked_spots = set()
spots_lock = threading.Lock()
worked_lock = threading.Lock()
session_start = datetime.now()
next_poll_time = time.time() + 5


def load_needed():
    global needed_set, needed_regions_list
    if os.path.exists(NEEDED_REGIONS_FILE):
        with open(NEEDED_REGIONS_FILE, 'r', encoding='utf-8') as f:
            needed_regions_list = json.load(f)
        for item in needed_regions_list:
            needed_set.add(f"{item['region']}_{item['band']}_{item['mode']}")
        print(f"✅ Загружено {len(needed_set)} нужных слотов")
    else:
        print("❌ Файл needed_regions.json не найден!")


def load_worked_spots():
    global worked_spots
    if os.path.exists(WORKED_SPOTS_FILE):
        try:
            with open(WORKED_SPOTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                worked_spots = set(data)
            print(f"✅ Загружено {len(worked_spots)} отработанных спотов")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки worked_spots.json: {e}")
            worked_spots = set()


def save_worked_spots():
    try:
        with worked_lock:
            data = list(worked_spots)
        with open(WORKED_SPOTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения: {e}")


def poller_loop():
    global next_poll_time, all_spots
    while True:
        now = time.time()
        if now >= next_poll_time:
            print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] Опрашиваю PSKReporter...")
            stations = get_stations()
            next_poll_time = time.time() + POLL_INTERVAL

            if stations:
                interesting = process_stations(
                    stations, needed_set,
                    bands=TARGET_BANDS, mode=TARGET_MODE
                )

                with spots_lock:
                    # Ключ дедупликации для таблицы включает тип (RECEIVER/SENDER),
                    # чтобы одна и та же станция могла быть в списке дважды (как RX и как TX)
                    existing_keys = {f"{s['callsign']}_{s['band']}_{s['mode']}_{s.get('type', 'UNKNOWN')}" for s in all_spots}
                    new_count = 0
                    for spot in interesting:
                        key = f"{spot['callsign']}_{spot['band']}_{spot['mode']}_{spot.get('type', 'UNKNOWN')}"
                        if key not in existing_keys:
                            region_name = get_region_name(spot['region'])
                            for nr in needed_regions_list:
                                if nr['region'] == spot['region'] and nr['band'] == spot['band']:
                                    region_name = nr.get('name', region_name)
                                    break
                            spot['region_name'] = region_name

                            all_spots.insert(0, spot)
                            existing_keys.add(key)
                            new_count += 1

                    if len(all_spots) > 500:
                        all_spots = all_spots[:500]

                    if new_count > 0:
                        receivers = sum(1 for s in all_spots if s['type'] == 'RECEIVER')
                        senders = sum(1 for s in all_spots if s['type'] == 'SENDER')
                        print(f"🎯 Новых: {new_count} | Всего: {len(all_spots)} "
                              f"(👂 {receivers}, 📡 {senders})")
            else:
                print("⚠️ Данные не получены")

        time.sleep(1)


@app.route('/')
def index():
    return render_template('index.html', bands=TARGET_BANDS)


@app.route('/api/data')
def api_data():
    with spots_lock:
        spots_copy = list(all_spots)

    with worked_lock:
        worked_copy = set(worked_spots)

    band_counts = {}
    region_counts = {}
    type_counts = {'RECEIVER': 0, 'SENDER': 0}
    active_spots = []

    for s in spots_copy:
        # Ключ для проверки "сработано" НЕ включает тип.
        # Если мы сработали станцию, мы скрываем её полностью (и RX, и TX).
        worked_key = f"{s['callsign']}_{s['band']}_{s['mode']}"
        if worked_key not in worked_copy:
            active_spots.append(s)
            band_counts[s['band']] = band_counts.get(s['band'], 0) + 1
            region_counts[s['region']] = region_counts.get(s['region'], 0) + 1
            type_counts[s['type']] = type_counts.get(s['type'], 0) + 1

    elapsed = datetime.now() - session_start
    seconds_left = max(0, int(next_poll_time - time.time()))

    return jsonify({
        'spots': active_spots,
        'stats': {
            'total': len(active_spots),
            'worked': len(worked_copy),
            'bands': band_counts,
            'types': type_counts,
            'unique_regions': len(region_counts),
            'session_time': str(elapsed).split('.')[0],
            'next_poll_in': seconds_left
        }
    })


@app.route('/api/mark_worked', methods=['POST'])
def api_mark_worked():
    data = request.get_json()
    key = data.get('key', '')

    if not key:
        return jsonify({'success': False, 'error': 'No key'}), 400

    with worked_lock:
        worked_spots.add(key)

    save_worked_spots()
    return jsonify({'success': True, 'key': key})


@app.route('/api/unmark_worked', methods=['POST'])
def api_unmark_worked():
    data = request.get_json()
    key = data.get('key', '')

    if not key:
        return jsonify({'success': False, 'error': 'No key'}), 400

    with worked_lock:
        if key in worked_spots:
            worked_spots.remove(key)

    save_worked_spots()
    return jsonify({'success': True, 'key': key})


if __name__ == '__main__':
    load_needed()
    load_worked_spots()

    thread = threading.Thread(target=poller_loop, daemon=True)
    thread.start()

    print("\n" + "=" * 50)
    print("🌐 Веб-интерфейс запущен!")
    print("👉 Открой в браузере: http://127.0.0.1:5000")
    print("=" * 50 + "\n")

    app.run(host='127.0.0.1', port=5000, debug=False)