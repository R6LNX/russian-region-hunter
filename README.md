# Russian Region Hunter (RRH) 📡

**Russian Region Hunter (RRH)** — монитор несработанных регионов России для диплома **«Россия»**. Программа отслеживает станции через [PSKReporter](https://pskreporter.info) и показывает, где сейчас есть станции из нужных тебе регионов.

---

## ✨ Возможности

- 📡 Мониторинг приёмников и передатчиков на 9 диапазонах (160M — 10M)
- 🗺️ Определение региона по позывному (справочник СРР)
- 🚫 Отсев скимеров и веб-SDR (KiwiSDR, OpenWebRX и др.)
- 🖥️ Веб-интерфейс с фильтрами и статистикой
- ✅ Отметка сработанных станций чекбоксом
- 🔊 Звуковое уведомление при новой станции

---

## 🚀 Установка

```bash
# 1. Клонируй репозиторий
git clone https://github.com/ТВОЙ_ЛОГИН/russian-region-hunter.git
cd russian-region-hunter

# 2. Установи зависимости
pip install -r requirements.txt

# 3. Сохрани страницу статистики с Hamlog
#    Зайди на: https://hamlog.online/account/rregions.php
#    Сохрани как: hamlog_page.html (тип: "Веб-страница, только HTML")

# 4. Сгенерируй список несработанных регионов
python hamlog_parser.py

# 5. Запусти веб-интерфейс
python app.py

# 6. Открой в браузере:
#    http://127.0.0.1:5000

📁 Структура проекта
russian-region-hunter/
├── app.py                  # Веб-сервер (Flask)
├── monitor.py              # Консольный монитор
├── config.py               # Конфигурация
├── psk_source.py           # Данные с PSKReporter
├── srr_regions.py          # Определение регионов (СРР)
├── hamlog_parser.py        # Парсинг таблицы с Hamlog
├── test_logic.py           # Тесты
├── srr_info.json           # Справочники СРР
├── templates/
│   └── index.html          # Веб-интерфейс
├── requirements.txt        # Зависимости
└── README.md

В будущем добавятся SSB/CW. Так же планируется добавить диплом RDA
