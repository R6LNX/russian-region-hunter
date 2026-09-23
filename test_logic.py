# test_logic.py - тесты логики приложения
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from srr_regions import (
    get_region, get_region_hamlog, get_band_by_freq, normalize_mode
)


def test_region_determination():
    """Тест определения регионов по позывным"""
    print("-" * 60)
    print("ТЕСТ 1: Определение регионов")

    test_cases = [
        ("R0CBS", "HK", "R0C"),
        ("R3ABC", "MA", "R2A"),
        ("R9XYZ", "KO", "R1I"),
        ("UA3DEF", "MO", "R2D"),
        ("R6LNX", "RO", "R6L"),
        ("RA0CCK", "HK", "R0C"),
        ("R9ON", "NS", "R8O"),
        ("UA9YJM", "AL", "R8Y"),
        ("R9W", "BA", "R8W"),
        ("R0D", "EA", "R0D"),
        ("R0K", "CK", "R0K"),
        ("R0Y", "TU", "R0Y"),
        ("R1P", "NO", "R1P"),
        ("R6I", "KM", "R6I"),
        ("R6Q", "IN", "R6Q"),
        ("R6U", "AO", "R6U"),
        ("R9Z", "GA", "R8Z"),
        ("K1USA", "Не РФ", "Не РФ"),
        ("DL1ABC", "Не РФ", "Не РФ"),
    ]

    passed = 0
    failed = 0

    for callsign, exp_srr, exp_hamlog in test_cases:
        result_srr = get_region(callsign)
        result_hamlog = get_region_hamlog(callsign)

        if result_srr == exp_srr and result_hamlog == exp_hamlog:
            passed += 1
            print(f"  ✅ {callsign:10} → SRR: {result_srr:6} | Hamlog: {result_hamlog}")
        else:
            failed += 1
            print(f"  ❌ {callsign:10} → SRR: {result_srr:6} | Hamlog: {result_hamlog} "
                  f"(ожидалось: {exp_srr} / {exp_hamlog})")

    print(f"\nРезультат: {passed} пройдено, {failed} провалено")
    return failed == 0


def test_band_determination():
    """Тест определения диапазонов по частоте"""
    print("-" * 60)
    print("ТЕСТ 2: Определение диапазонов по частоте")

    freq_tests = [
        (1840, "160M"),
        (1845, "160M"),
        (3573, "80M"),
        (3510, "80M"),
        (7074, "40M"),
        (7020, "40M"),
        (10136, "30M"),
        (10120, "30M"),
        (14074, "20M"),
        (14250, "20M"),
        (14050, "20M"),
        (18100, "17M"),
        (21074, "15M"),
        (21300, "15M"),
        (24915, "12M"),
        (28074, "10M"),
        (28500, "10M"),
        (28050, "10M"),
    ]

    passed = 0
    failed = 0

    for freq, expected_band in freq_tests:
        result = get_band_by_freq(freq)

        if result == expected_band:
            passed += 1
            print(f"  ✅ {freq:6} кГц → {result}")
        else:
            failed += 1
            print(f"  ❌ {freq:6} кГц → {result} (ожидалось: {expected_band})")

    print(f"\nРезультат: {passed} пройдено, {failed} провалено")
    return failed == 0


def test_mode_normalization():
    """Тест нормализации моды"""
    print("-" * 60)
    print("ТЕСТ 3: Нормализация моды")

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
        ("PCW", "CW"),
    ]

    passed = 0
    failed = 0

    for mode, expected in mode_tests:
        result = normalize_mode(mode)

        if result == expected:
            passed += 1
            print(f"  ✅ {mode:8} → {result}")
        else:
            failed += 1
            print(f"  ❌ {mode:8} → {result} (ожидалось: {expected})")

    print(f"\nРезультат: {passed} пройдено, {failed} провалено")
    return failed == 0


def test_needed_regions():
    """Тест загрузки списка нужных регионов"""
    print("-" * 60)
    print("ТЕСТ 4: Список нужных регионов")

    needed_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'needed_regions.json')

    if not os.path.exists(needed_file):
        print("  ⚠️ Файл needed_regions.json не найден")
        print("  Запустите сначала hamlog_parser.py")
        return False

    with open(needed_file, 'r', encoding='utf-8') as f:
        needed_list = json.load(f)

    print(f"  Загружено несработанных слотов: {len(needed_list)}")

    all_bands = ['160M', '80M', '40M', '30M', '20M', '17M', '15M', '12M', '10M']

    for band in all_bands:
        count = sum(1 for item in needed_list if item['band'] == band)
        if count > 0:
            print(f"  ✅ {band:5}: {count} несработанных слотов")
        else:
            print(f"  ⚠️ {band:5}: нет несработанных слотов")

    unique_regions = set(item['region'] for item in needed_list)
    print(f"\n  Уникальных несработанных регионов: {len(unique_regions)}")

    return True


def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print("ТЕСТЫ ЛОГИКИ ПРИЛОЖЕНИЯ")
    print("=" * 60 + "\n")

    results = []

    results.append(("Определение регионов", test_region_determination()))
    print()

    results.append(("Определение диапазонов", test_band_determination()))
    print()

    results.append(("Нормализация моды", test_mode_normalization()))
    print()

    results.append(("Список нужных регионов", test_needed_regions()))
    print()

    # Итоги
    print("=" * 60)
    print("ИТОГИ ТЕСТОВ")
    print("=" * 60)

    all_passed = True
    for name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"  {status}: {name}")
        if not result:
            all_passed = False

    print()
    if all_passed:
        print("🎉 Все тесты пройдены!")
    else:
        print("⚠️ Есть проваленные тесты")

    return all_passed


if __name__ == '__main__':
    main()