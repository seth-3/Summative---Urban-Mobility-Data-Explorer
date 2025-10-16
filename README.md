# NYC Mobility (Minimal Fullstack)

- Backend: Flask + SQLite
- Frontend: HTML/CSS/JS (no frameworks)
- Data: place the dataset zip inside `nyc-mobility/data/` (e.g., `train.zip` or `train (1).zip`).

## Setup (Windows)

1. Python 3.10+ installed.
2. In PowerShell:
```
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install flask
```

## Load data

1. Put your dataset zip in `nyc-mobility/data/`.
2. Run ETL:
```
python nyc-mobility/backend/etl.py
```
This creates `nyc-mobility/app.db` and `nyc-mobility/backend/log_excluded.csv`.

## Run server
```
python nyc-mobility/backend/app.py
```
Open http://localhost:5000

## API
All endpoints accept date range and optional custom filters.

- `GET /api/summary?start=YYYY-MM-DD HH:MM:SS&end=...&min_distance=&max_distance=&min_speed=&max_speed=&min_fare=&max_fare=&cell=&hod_start=&hod_end=`
  - Returns: `trips`, `avg_speed`, `avg_fpk`, `min_ts`, `max_ts`
- `GET /api/monthly_counts?start=&end=&min_distance=&max_distance=&min_speed=&max_speed=&min_fare=&max_fare=&cell=&hod_start=&hod_end=`
- `GET /api/top_cells?k=10&start=&end=&min_distance=&max_distance=&min_speed=&max_speed=&min_fare=&max_fare=&cell=&hod_start=&hod_end=`
- `GET /api/trips?limit=50&offset=0&start=&end=&min_distance=&max_distance=&min_speed=&max_speed=&min_fare=&max_fare=&cell=&hod_start=&hod_end=`

## Custom Algorithm
Manual Quickselect for Top‑K busiest pickup cells is implemented in `backend/etl.py` (`topk_by_count`).

## Notes
- Minimal schema in SQLite table `trips` with indices on `pickup_ts` and `pickup_cell`.
- Charts are custom Canvas (no libs).

## Database Schema Export

Export the SQLite schema (include in submission):

```
sqlite3 nyc-mobility/app.db .schema > nyc-mobility/schema.sql
```

## Video Walkthroughs

 - https://youtu.be/elunMCRWhcs
