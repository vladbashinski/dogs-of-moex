# 🐕 Собаки MOEX — Бэктестер

Streamlit-приложение для тестирования стратегии **Dogs of the Dow** на MOEX.

## Структура проекта

```
dogs_of_moex/
├── app.py            # Streamlit UI
├── backtester.py     # Логика стратегии + метрики
├── data_loader.py    # Загрузка Excel + MOEX ISS API
├── requirements.txt
└── data/
    └── Дивиденды_с_2019_MOEX.xlsx
```

## Локальный запуск

```bash
pip install -r requirements.txt
streamlit run app.py
```

Откроется http://localhost:8501

---

## Деплой на Timeweb VPS (Ubuntu)

### 1. Установка зависимостей

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
```

### 2. Загрузка проекта

```bash
cd ~
git clone <ваш_репозиторий> dogs_of_moex
# ИЛИ просто скопируйте файлы через scp:
# scp -r ./dogs_of_moex user@your-server-ip:~/
cd dogs_of_moex
```

### 3. Виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Тест запуска

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Проверьте: http://ВАШ_IP:8501

### 5. Systemd-сервис (автозапуск)

Создайте файл `/etc/systemd/system/dogs-moex.service`:

```ini
[Unit]
Description=Dogs of MOEX Streamlit App
After=network.target

[Service]
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/dogs_of_moex
ExecStart=/home/YOUR_USER/dogs_of_moex/venv/bin/streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable dogs-moex
sudo systemctl start dogs-moex
sudo systemctl status dogs-moex
```

### 6. Nginx reverse proxy (опционально, для домена)

```nginx
server {
    listen 80;
    server_name dogs.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

---

## Методология бэктеста

### Правило отбора (Dogs of the Dow)
1. На начало года Y взять все акции из состава MOEX с ненулевой дивдоходностью.
2. Отсортировать по убыванию дивидендной доходности.
3. Выбрать топ-N (по умолчанию 10).

### Расчёт доходности
```
R_портфель = mean(R_i) - 2 × комиссия
R_i = (Цена_{Y+1} / Цена_Y - 1) + ДивДоходность_Y
```

### Фильтры (расширенные стратегии)
| Фильтр               | Описание                                              |
|----------------------|-------------------------------------------------------|
| Мин. дивдоходность   | Исключить бумаги без дивидендов                       |
| Макс. дивдоходность  | Исключить аномальные выплаты (разовые/ошибочные)      |
| Мин. вес в индексе   | Ограничить по ликвидности                             |
| «Щенки Доу» (Low-5) | Из топ-10 по доходности — 5 с наименьшей ценой акции  |

### Метрики
- **CAGR** — среднегеометрическая годовая доходность
- **Sharpe** — (R - Rf) / σ, Rf = ключевая ставка ЦБ по году
- **Sortino** — учитывает только нисходящую волатильность
- **Альфа / Бета** — относительно IMOEX (через MOEX ISS API)

---

## Источники данных
- **Дивиденды и состав индекса**: файл `Дивиденды_с_2019_MOEX.xlsx`
- **Бенчмарк IMOEX**: [MOEX ISS API](https://iss.moex.com) (кэшируется в `data/benchmark_cache.json`)
- **Безрисковая ставка**: ключевая ставка ЦБ РФ (захардкожена по годам)
