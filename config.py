# config.py - конфигурация приложения
import os

# Пути к файлам
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEEDED_REGIONS_FILE = os.path.join(BASE_DIR, 'needed_regions.json')
SRR_INFO_FILE = os.path.join(BASE_DIR, 'srr_info.json')
HAMLOG_PAGE_FILE = os.path.join(BASE_DIR, 'hamlog_page.html')

# Настройки мониторинга
POLL_INTERVAL = 120              # Интервал опроса PSKReporter (секунды) = 2 минуты
SPOT_MAX_AGE_MINUTES = 30        # Показывать споты не старше этого времени
MAX_DISPLAY_SPOTS = 50           # Максимум спотов в консоли

# Целевые диапазоны и моды
TARGET_BANDS = ['160M', '80M', '40M', '30M', '20M', '17M', '15M', '12M', '10M']
TARGET_MODE = 'DIG'

# Настройки PSKReporter
PSK_URL = "https://pskreporter.info/query"
MIN_REQUEST_INTERVAL = 120       # Минимальный интервал между запросами (секунды)
REQUEST_TIMEOUT = 30             # Таймаут HTTP запроса (секунды)

# Чёрный список decoderSoftware для приёмников
# Если decoderSoftware содержит любую из этих подстрок (без учёта регистра) - приёмник отсеивается
# НЕ включены: MSHV, JS8Call, Subspace Edition (реальные операторы)
EXCLUDED_DECODER_SOFTWARE = [
    'kiwisdr',
    'web-888',
    'openwebrx',
    'websdr',
    'digi-skimmer',
    'jtskimmer',
    'cwskimmer',
    'cwsl_digi',
    'n1dq-ka9q-radio',
    'n1dq-importer',
    'wsjt-cb',
    'wd_',
    'skimmer',
    'decodium',
    'ft8tw',
    'spark-sdr',
    'sdroxide',
    'qft8',
    'ft8af',
    'ft8-hochgericht',
    'ft8web',
    'ft8_web',
    'psk-recorder',
    'radio-reporter',
    'wsprdaemon',
    'mykolassdr',
    'eradiosdr',
    'phantomsdr',
    'granolasdr',
    'nereussdr',
    'novasdr',
    'my-sdr',
    'rptr v1',
]

# Цвета для консоли (ANSI escape codes)
COLORS = {
    'RESET': '\033[0m',
    'RED': '\033[91m',
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'BLUE': '\033[94m',
    'MAGENTA': '\033[95m',
    'CYAN': '\033[96m',
    'WHITE': '\033[97m',
    'BOLD': '\033[1m',
}