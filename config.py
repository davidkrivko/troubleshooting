import os

TROUBLE_SHOOTING_DATA = {
    "heating_time": 120,
    "heating_time_2": 240,
    "heat_amplitude": 110,
    # Новые параметры для режима обучения:
    "learning_start_temp": 90,
    "learning_target_temp": 110
}

TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT")
CHAT_ID = os.environ.get("CHAT_ID")
