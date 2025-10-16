import os, sqlite3, csv, zipfile, io
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(ROOT, 'app.db')
DATA_DIR = os.path.join(ROOT, 'data')
ALT_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
LOG_PATH = os.path.join(os.path.dirname(__file__), 'log_excluded.csv')

# --- minimal helpers ---

def ensure_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY,
            pickup_ts TEXT,
            dropoff_ts TEXT,
            pickup_lon REAL,
            pickup_lat REAL,
            dropoff_lon REAL,
            dropoff_lat REAL,
            distance_km REAL,
            duration_min REAL,
            speed_kmh REAL,
            fare_amount REAL,
            fare_per_km REAL,
            pickup_cell TEXT
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_trips_pickup_ts ON trips(pickup_ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_trips_pickup_cell ON trips(pickup_cell)")

# simple manual grid to cell mapper (no libs)

def grid_cell(lon, lat, size=0.01):  # ~1.1km cells
    if lon is None or lat is None:
        return None
    try:
        x = int((lon + 180.0) / size)
        y = int((lat + 90.0) / size)
        return f"{x}:{y}"
    except Exception:
        return None

# Manual Quickselect (custom algorithm requirement) for top-K frequencies

def topk_by_count(items, k):
    counts = {}
    for it in items:
        if it is None: 
            continue
        counts[it] = counts.get(it, 0) + 1
    arr = list(counts.items())  # (key, count)

    def partition(lo, hi, pivot_idx):
        pivot = arr[pivot_idx][1]
        arr[pivot_idx], arr[hi] = arr[hi], arr[pivot_idx]
        store = lo
        for i in range(lo, hi):
            if arr[i][1] > pivot:  # desc
                arr[store], arr[i] = arr[i], arr[store]
                store += 1
        arr[store], arr[hi] = arr[hi], arr[store]
        return store

    def select(lo, hi, k_smallest):  # kth in desc order
        if lo == hi:
            return
        pivot_idx = (lo + hi) // 2
        p = partition(lo, hi, pivot_idx)
        if k_smallest == p:
            return
        elif k_smallest < p:
            select(lo, p - 1, k_smallest)
        else:
            select(p + 1, hi, k_smallest)

    if arr:
        k_idx = min(k - 1, len(arr) - 1)
        select(0, len(arr) - 1, k_idx)
    return arr[:k]

# --- CSV field access that tolerates variants ---

FIELD_MAPS = {
    'pickup_ts': ['tpep_pickup_datetime','lpep_pickup_datetime','pickup_datetime'],
    'dropoff_ts': ['tpep_dropoff_datetime','lpep_dropoff_datetime','dropoff_datetime'],
    'trip_distance': ['trip_distance','distance','distance_km'],
    'trip_duration': ['trip_duration','duration','duration_sec'],
    'fare_amount': ['fare_amount','total_amount','fare'],
    'pickup_longitude': ['pickup_longitude','PULocationID','pu_lon'],
    'pickup_latitude': ['pickup_latitude','pu_lat'],
    'dropoff_longitude': ['dropoff_longitude','DOLocationID','do_lon'],
    'dropoff_latitude': ['dropoff_latitude','do_lat'],
}

def pick(row, keys):
    for k in keys:
        if k in row and row[k] not in ('', None):
            return row[k]
    return None

# --- ETL ---

def parse_ts(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None

def miles_to_km(x):
    return x * 1.60934

def haversine_km(lon1, lat1, lon2, lat2):
    try:
        from math import radians, sin, cos, asin, sqrt
        lon1, lat1, lon2, lat2 = map(float, (lon1, lat1, lon2, lat2))
        R = 6371.0
        dlon = radians(lon2 - lon1)
        dlat = radians(lat2 - lat1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c
    except Exception:
        return None


def run():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ALT_DATA_DIR, exist_ok=True)
    # prefer CSV in backend/data if present; else first ZIP in root data
    csvs = [os.path.join(ALT_DATA_DIR, f) for f in os.listdir(ALT_DATA_DIR) if f.lower().endswith('.csv')]
    zips = [os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR) if f.lower().endswith('.zip')]
    mode = 'csv' if csvs else 'zip'
    if mode == 'csv':
        input_path = csvs[0]
    elif zips:
        input_path = zips[0]
    else:
        raise SystemExit(f"Place a CSV in {ALT_DATA_DIR} or a ZIP in {DATA_DIR}")

    print(f"ETL source mode: {mode}, input: {input_path}")
    print(f"Target DB: {DB_PATH}")

    excluded_log = open(LOG_PATH, 'w', newline='')
    logw = csv.writer(excluded_log)
    logw.writerow(['reason','row_sample'])

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        ensure_schema(conn)

        def process_reader(reader):
            batch = []
            processed = 0
            inserted_total = 0
            excluded = 0
            for row in reader:
                    processed += 1
                    pu = pick(row, FIELD_MAPS['pickup_ts'])
                    do = pick(row, FIELD_MAPS['dropoff_ts'])
                    if not pu or not do:
                        logw.writerow(['missing_ts', str(row)[:200]])
                        excluded += 1
                        continue
                    pu_dt, do_dt = parse_ts(pu), parse_ts(do)
                    if not pu_dt or not do_dt or do_dt <= pu_dt:
                        logw.writerow(['bad_ts', str(row)[:200]])
                        excluded += 1
                        continue

                    dist_raw = pick(row, FIELD_MAPS['trip_distance'])
                    try:
                        dist = float(dist_raw)
                    except Exception:
                        dist = None

                    fare_raw = pick(row, FIELD_MAPS['fare_amount'])
                    try:
                        fare = float(fare_raw)
                    except Exception:
                        fare = None

                    # coordinates optional
                    def to_float(v):
                        try: return float(v)
                        except: return None
                    pu_lon = to_float(pick(row, FIELD_MAPS['pickup_longitude']))
                    pu_lat = to_float(pick(row, FIELD_MAPS['pickup_latitude']))
                    do_lon = to_float(pick(row, FIELD_MAPS['dropoff_longitude']))
                    do_lat = to_float(pick(row, FIELD_MAPS['dropoff_latitude']))

                    # duration: prefer explicit field if present (e.g., trip_duration seconds)
                    dur_raw = pick(row, FIELD_MAPS['trip_duration'])
                    if dur_raw is not None:
                        try:
                            duration_min = float(dur_raw) / 60.0
                        except Exception:
                            duration_min = (do_dt - pu_dt).total_seconds() / 60.0
                    else:
                        duration_min = (do_dt - pu_dt).total_seconds() / 60.0
                    if duration_min <= 0 or duration_min > 240:  # cap at 4h
                        logw.writerow(['bad_duration', str(row)[:200]])
                        excluded += 1
                        continue

                    # distance: use field when present; else compute from coordinates
                    distance_km = None
                    if dist is not None:
                        distance_km = miles_to_km(dist) if dist < 200 else dist  # heuristic
                    if distance_km is None and pu_lon is not None and pu_lat is not None and do_lon is not None and do_lat is not None:
                        distance_km = haversine_km(pu_lon, pu_lat, do_lon, do_lat)
                    if distance_km is None or distance_km <= 0 or distance_km > 200:
                        logw.writerow(['bad_distance', str(row)[:200]])
                        excluded += 1
                        continue

                    speed_kmh = distance_km / (duration_min / 60.0)
                    if speed_kmh <= 0 or speed_kmh > 150:
                        logw.writerow(['bad_speed', str(row)[:200]])
                        excluded += 1
                        continue

                    # fare: optional; only exclude if explicitly invalid negative or unrealistic
                    fare_amount = None
                    if fare is not None:
                        if fare < 0 or fare > 1000:
                            logw.writerow(['bad_fare', str(row)[:200]])
                            excluded += 1
                            continue
                        fare_amount = fare

                    fare_per_km = (fare_amount / distance_km) if (fare_amount is not None and distance_km > 0) else None

                    pu_cell = None
                    if pu_lon is not None and pu_lat is not None:
                        pu_cell = grid_cell(pu_lon, pu_lat)
                    else:
                        # If only zone IDs are present in lon field (e.g., PULocationID), use as cell
                        try:
                            pu_cell = str(int(pick(row, FIELD_MAPS['pickup_longitude'])))
                        except Exception:
                            pu_cell = None

                    batch.append((
                        pu_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        do_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        pu_lon, pu_lat, do_lon, do_lat,
                        round(distance_km, 3), round(duration_min, 2), round(speed_kmh, 2),
                        (round(fare_amount, 2) if fare_amount is not None else None),
                        (round(fare_per_km, 2) if fare_per_km is not None else None),
                        pu_cell
                    ))

                    if len(batch) >= 2000:
                        conn.executemany(
                            """
                            INSERT INTO trips (
                              pickup_ts, dropoff_ts, pickup_lon, pickup_lat, dropoff_lon, dropoff_lat,
                              distance_km, duration_min, speed_kmh, fare_amount, fare_per_km, pickup_cell
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            batch
                        )
                        conn.commit()
                        inserted_total += 2000
                        batch = []
                        if processed % 50000 == 0:
                            print(f"Processed: {processed}, Inserted: {inserted_total}, Excluded: {excluded}")

            if batch:
                conn.executemany(
                        """
                        INSERT INTO trips (
                          pickup_ts, dropoff_ts, pickup_lon, pickup_lat, dropoff_lon, dropoff_lat,
                          distance_km, duration_min, speed_kmh, fare_amount, fare_per_km, pickup_cell
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        batch
                )
                conn.commit()
                inserted_total += len(batch)
            print(f"ETL done. Processed: {processed}, Inserted: {inserted_total}, Excluded: {excluded}")

        if mode == 'csv':
            with open(input_path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
                reader = csv.DictReader(f)
                process_reader(reader)
        else:
            with zipfile.ZipFile(input_path) as zf:
                for name in zf.namelist():
                    if not name.lower().endswith('.csv'):
                        continue
                    with zf.open(name) as f:
                        text = io.TextIOWrapper(f, encoding='utf-8', errors='ignore')
                        reader = csv.DictReader(text)
                        process_reader(reader)

    excluded_log.close()
    # compute top-k with our custom algorithm (example usage)
    with sqlite3.connect(DB_PATH) as conn:
        cells = [r[0] for r in conn.execute('SELECT pickup_cell FROM trips WHERE pickup_cell IS NOT NULL')]
    top10 = topk_by_count(cells, 10)
    print('Top cells (custom quickselect):', top10)

if __name__ == '__main__':
    run()
