# motd-app: запуск в Docker и оптимизация образа

## Задание

1. Собрать и запустить приложение `motd-app` (Flask) в контейнере.
2. Замерить размер образа и время сборки исходной («наивной») версии.
3. Поэтапно оптимизировать `Dockerfile` по размеру образа и скорости сборки, замеряя результат после каждого этапа.
4. Подготовить образ к работе «как в проде»: продакшен-сервер вместо dev-сервера Flask, запуск не от root, лимиты ресурсов.
5. Заполнить таблицу результатов и ответить на контрольные вопросы.

## Приложение

```
motd-app/
├── requirements.txt   flask (без версии)
├── settings.py        константы SERVICE_NAME, ENVIRONMENT, OWNER
└── app.py             Flask, порт 6080; маршруты / и /health
```

Ожидаемые ответы:

```
GET /        → Status Board [staging] — владелец: platform-team
GET /health  → ok
```

## Окружение

- Сервер: `ip-172-31-16-169` (Ubuntu 26.04), команда `docker` = обёртка над Podman (`podman-docker`).
- Порт на хосте: **6081** (6080 может быть занят прошлым `motd-app-1`).
- Имена образов: `motd-app:v1`, `motd-app:v2`, … — по одному тегу на этап, чтобы сравнивать версии между собой.

---

## 0. Подготовка

### Код на сервер

С Mac:

```bash
scp motd-app-optimization.zip ubuntu@<IP_app-server>:/home/devops-practice/
```

На сервере:

```bash
cd /home/devops-practice
unzip motd-app-optimization.zip && cd motd-app
ls -la
```

### Базовые образы заранее

Скачивание базового образа не должно попадать в замер времени сборки, поэтому все базовые образы скачиваются до начала:

```bash
docker pull docker.io/library/python:3.12
docker pull docker.io/library/python:3.12-slim
docker pull docker.io/library/python:3.12-alpine

docker images python --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"
df -h /
```

### Как замерять

Используются одни и те же команды на каждом этапе.

**Размер образа:**

```bash
docker images motd-app --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"
docker history motd-app:<тег>            # размер каждого слоя
```

**Холодная сборка** (без кэша слоёв):

```bash
time docker build --no-cache -t motd-app:<тег> .
```

**Пересборка после изменения кода** (кэш есть, поменялся только `app.py`):

```bash
sed -i 's/return "ok"/return "ok!"/' app.py
time docker build -t motd-app:<тег> .
sed -i 's/return "ok!"/return "ok"/' app.py    # вернуть как было
```

В таблицу результатов записывается значение `real` из вывода `time`.

---

## 1. Базовая версия (v1)

Написать `Dockerfile` по требованиям:

1. Базовый образ `python:3.12` (полный, не slim).
2. `WORKDIR /app`.
3. Скопировать **весь** каталог проекта одной инструкцией `COPY . .`.
4. Установить зависимости из `requirements.txt`.
5. `CMD` — запуск `app.py`.

Сборка, замеры, запуск:

```bash
time docker build --no-cache -t motd-app:v1 .
docker run -d --name motd-v1 -p 6081:6080 motd-app:v1

curl --retry 10 --retry-delay 1 --retry-all-errors -w '\n' http://127.0.0.1:6081/
curl -w '\n' http://127.0.0.1:6081/health
docker logs motd-v1
```

Выполнить замер «пересборка после изменения кода».

Записать в таблицу: размер, холодную сборку, пересборку.

Перед следующим этапом:

```bash
docker rm -f motd-v1
```

---

## 2. Размер образа и кэш слоёв (v2)

Изменения относительно v1:

1. Базовый образ `python:3.12-slim`.
2. Двухшаговое копирование: сначала только `requirements.txt` и установка зависимостей, затем код (`app.py` и `settings.py`) одной инструкцией `COPY`.
3. Установка зависимостей без сохранения кэша pip внутри образа.
4. Файл `.dockerignore`, исключающий из контекста сборки всё, что не нужно образу: `.git`, `__pycache__`, `*.pyc`, `.env`, `README.md`, `Dockerfile`, `.dockerignore`, архивы.
5. Зафиксированная версия Flask в `requirements.txt` (`flask==<версия>`).

Версию взять из уже собранного образа v1:

```bash
docker run --rm motd-app:v1 pip freeze
```

В `requirements.txt` фиксируются Flask и все его зависимости из вывода `pip freeze`.

Сборка, замеры, запуск — как в этапе 1, с тегом `v2` и именем контейнера `motd-v2`.

Проверка содержимого образа:

```bash
docker run --rm motd-app:v2 ls -la /app
```

В `/app` должны быть только `app.py`, `settings.py`, `requirements.txt`.

---

## 3. Готовность к продакшену (v3)

Изменения относительно v2:

1. Продакшен-сервер **gunicorn** вместо встроенного сервера Flask: добавить `gunicorn==<версия>` в `requirements.txt`, в `CMD` запускать gunicorn на `0.0.0.0:6080` с 2 воркерами, объект приложения — `app:app`.
2. Отдельный системный пользователь `app` без пароля и шелла; приложение работает от него (`USER`).
3. Переменные окружения Python:
   - `PYTHONDONTWRITEBYTECODE=1` — не создавать `.pyc`;
   - `PYTHONUNBUFFERED=1` — логи сразу попадают в `docker logs`, без буферизации.
4. `EXPOSE 6080` — документирует порт приложения.
5. `CMD` в exec-форме (JSON-массив).

Запуск с лимитами ресурсов и политикой перезапуска:

```bash
docker run -d --name motd-v3 -p 6081:6080 \
  --memory 128m --pids-limit 100 --restart unless-stopped \
  motd-app:v3
```

Проверки:

```bash
curl --retry 10 --retry-delay 1 --retry-all-errors -w '\n' http://127.0.0.1:6081/
curl -w '\n' http://127.0.0.1:6081/health

docker exec motd-v3 whoami                 # app, не root
docker logs motd-v3                        # строки gunicorn: Listening at..., Booting worker...
docker stats --no-stream motd-v3           # потребление памяти против лимита 128 МБ
docker inspect motd-v3 --format '{{.Config.User}} {{.Config.Cmd}}'
```

В логах не должно быть предупреждения `WARNING: This is a development server`.

---

## 4. Скорость сборки: кэш pip между сборками (v4)

Изменения относительно v3:

1. Установка зависимостей через кэш-монтирование BuildKit/Buildah:
   `RUN --mount=type=cache,target=<каталог кэша pip> pip install ...`
2. Флаг отключения кэша pip из этапа 2 в этой инструкции убрать: кэш хранится вне образа, в слой он не попадает.

Замер пользы кэша — при изменении **зависимостей**, а не кода:

```bash
# 1. сборка, чтобы наполнить кэш
docker build -t motd-app:v4 .

# 2. добавить пакет в requirements.txt, пересобрать
echo "requests==2.32.3" >> requirements.txt
time docker build -t motd-app:v4 .

# 3. то же самое на v3 для сравнения (Dockerfile v3 сохранить как Dockerfile.v3)
time docker build -f Dockerfile.v3 -t motd-app:v3-test .

# 4. вернуть requirements.txt
sed -i '/^requests==/d' requirements.txt
```

Размер v4 сравнить с v3: он не должен вырасти.

---

## 5. Сравнение базовых образов (v5, исследование)

Собрать образ v5 из того же `Dockerfile`, что v4, но на базе `python:3.12-alpine`.

На Alpine нет `useradd` — системный пользователь создаётся командой `adduser -S -D -H app`.

Сборка, запуск, проверка `/` и `/health`, замеры — как на предыдущих этапах, тег `v5`.

Сравнить с v4 размер и время сборки, заполнить строку таблицы.

---

## 6. Результаты

| Версия | База | Размер образа | Холодная сборка | Пересборка после правки кода | Что изменилось |
|---|---|---|---|---|---|
| v1 | python:3.12 | | | | исходная версия |
| v2 | python:3.12-slim | | | | slim, порядок слоёв, `.dockerignore`, без кэша pip, версии зафиксированы |
| v3 | python:3.12-slim | | | | gunicorn, non-root, ENV, лимиты |
| v4 | python:3.12-slim | | | | кэш pip между сборками |
| v5 | python:3.12-alpine | | | | Alpine вместо slim |

Итог одной строкой: «образ уменьшен с ___ до ___ МБ (в ___ раз), пересборка после изменения кода ускорилась с ___ до ___ с».

Итоговые файлы в каталоге проекта:

```
motd-app/
├── Dockerfile            финальная версия
├── Dockerfile.v1         исходная версия для сравнения
├── .dockerignore
├── requirements.txt      с зафиксированными версиями
├── settings.py
└── app.py
```

---

## 7. Контрольные вопросы

1. Почему на этапе 1 изменение одной строки в `app.py` заставляет заново устанавливать зависимости, а на этапе 2 — нет?
2. Какой слой в `docker history motd-app:v1` самый большой и откуда он взялся?
3. Почему удаление кэша отдельной инструкцией `RUN rm -rf ...` после `RUN pip install ...` не уменьшает образ?
4. Что попадёт в образ из каталога проекта без `.dockerignore` при `COPY . .`? Почему файл `.env` в образе — проблема?
5. Чем опасен `flask` без версии в `requirements.txt`?
6. Почему встроенный сервер Flask не используют в продакшене?
7. Что даёт запуск не от root, если контейнер и так изолирован?
8. Что произойдёт с контейнером v3, если приложение превысит лимит памяти 128 МБ? Какой будет код выхода?
9. Почему Alpine не всегда лучший выбор для Python, несмотря на меньший размер?
10. Чем `--mount=type=cache` отличается от обычного кэша слоёв Docker?

---

## 8. Удаление

```bash
docker rm -f motd-v1 motd-v2 motd-v3 motd-v4 motd-v5 2>/dev/null; true
docker images motd-app
docker rmi motd-app:v1 motd-app:v2 motd-app:v3 motd-app:v3-test motd-app:v4 motd-app:v5
docker rmi docker.io/library/python:3.12       # самый тяжёлый базовый образ, если больше не нужен
docker system df
```

---

## Частые проблемы

| Симптом | Причина и решение |
|---|---|
| `curl: (56) Connection reset by peer` сразу после `docker run` | Приложение ещё не открыло порт. Использовать `curl --retry ...` из замеров |
| `bind: address already in use` на 6081 | Порт занят прошлым контейнером: `docker ps -a`, удалить или взять другой порт хоста |
| `ModuleNotFoundError: No module named 'settings'` | `settings.py` не скопирован в образ или `.dockerignore` его исключил |
| gunicorn: `Failed to find attribute 'app'` | Неверный аргумент приложения; формат `<файл без .py>:<переменная Flask>` |
| `Permission denied` после `USER app` | Файлы в `/app` принадлежат root без права чтения для остальных; проверить `docker run --rm --entrypoint ls motd-app:<тег> -la /app` |
| Контейнер `Exited (137)` | Убит по лимиту памяти (OOM): `docker inspect <имя> --format '{{.State.OOMKilled}}'` |
| `Cannot fork` в любом контейнере | Возврат проблемы с `pids.max = 1`: проверить, что `docker version` показывает `Podman Engine`, а не клиент Docker |
| `--mount` не распознаётся | Старый сборщик; проверить `docker version` / `buildah --version` |
| Время холодной сборки сильно «прыгает» | В замер попало скачивание базового образа или пакетов из PyPI. Повторить замер 2–3 раза, записать среднее |
