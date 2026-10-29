# motd-app

Задача 23: Python, Flask + вспомогательный модуль с настройками.

### Структура
```
├── requirements.txt
├── settings.py   # константы SERVICE_NAME, ENVIRONMENT, OWNER
└── app.py        # основной Flask-файл, импортирует settings.py
```

### Задание
Напишите `Dockerfile` для этого приложения:
1. Базовый образ `python:3.12-slim`
2. `WORKDIR`
3. Двухшаговый `COPY` — сначала `requirements.txt`, `RUN pip install -r requirements.txt`
4. Затем **оба** файла кода (`app.py` и `settings.py`) одной строкой `COPY`
5. `CMD` для запуска

### Сборка и запуск
```bash
docker build -t motd-app-image .
docker run -d --name motd-app-1 -p 6080:6080 motd-app-image
```

### Проверка
```bash
curl http://127.0.0.1:6080/
curl http://127.0.0.1:6080/health
```

Ожидаемый ответ:
```
Status Board [staging] — владелец: platform-team
ok
```
