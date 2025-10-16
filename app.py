from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import os
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(APP_DIR, '..'))
DB_PATH = os.path.join(ROOT_DIR, 'app.db')
FRONTEND_DIR = os.path.join(ROOT_DIR, 'frontend')

app = Flask(__name__, static_folder=None)

# --- DB helpers ---

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- Routes: Frontend ---

@app.get('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.get('/assets/<path:fname>')
def assets(fname):
    return send_from_directory(FRONTEND_DIR, fname)

# --- Routes: API ---

def _parse_dt(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def _validated_range():
    start = request.args.get('start')
    end = request.args.get('end')
    if start:
        if not _parse_dt(start):
            return None, None, (jsonify({"error":"invalid start datetime; expected YYYY-MM-DD HH:MM:SS"}), 400)
    if end:
        if not _parse_dt(end):
            return None, None, (jsonify({"error":"invalid end datetime; expected YYYY-MM-DD HH:MM:SS"}), 400)
    return start, end, None

def _apply_custom_filters(where, params):
    md = request.args.get('min_distance'); xd = request.args.get('max_distance')
    ms = request.args.get('min_speed'); xs = request.args.get('max_speed')
    mf = request.args.get('min_fare'); xf = request.args.get('max_fare')
    cell = request.args.get('cell')
    hod_start = request.args.get('hod_start'); hod_end = request.args.get('hod_end')
    def _num(v):
        try:
            return float(v) if v is not None and v != '' else None
        except:
            return None
    md, xd = _num(md), _num(xd)
    ms, xs = _num(ms), _num(xs)
    mf, xf = _num(mf), _num(xf)
    if md is not None:
        where.append("distance_km >= ?"); params.append(md)
    if xd is not None:
        where.append("distance_km <= ?"); params.append(xd)
    if ms is not None:
        where.append("speed_kmh >= ?"); params.append(ms)
    if xs is not None:
        where.append("speed_kmh <= ?"); params.append(xs)
    if mf is not None:
        where.append("fare_amount >= ?"); params.append(mf)
    if xf is not None:
        where.append("fare_amount <= ?"); params.append(xf)
    if cell:
        where.append("pickup_cell = ?"); params.append(cell)
    if hod_start is not None or hod_end is not None:
        try:
            hs = int(hod_start) if hod_start is not None and hod_start != '' else None
            he = int(hod_end) if hod_end is not None and hod_end != '' else None
            if hs is not None:
                where.append("CAST(substr(pickup_ts,12,2) AS INTEGER) >= ?"); params.append(hs)
            if he is not None:
                where.append("CAST(substr(pickup_ts,12,2) AS INTEGER) <= ?"); params.append(he)
        except:
            pass
    return where, params

def _clamp_int(name, default, min_v, max_v):
    v = request.args.get(name)
    if v is None:
        return default
    try:
        iv = int(v)
    except Exception:
        raise ValueError(f"invalid {name}")
    if iv < min_v or iv > max_v:
        raise ValueError(f"{name} out of range")
    return iv

@app.get('/api/summary')
def api_summary():
    start, end, err = _validated_range()
    if err:
        return err
    q = [
        "SELECT COUNT(*) as trips, AVG(speed_kmh) as avg_speed,",
        "       COALESCE(AVG(fare_per_km), AVG(fare_amount / NULLIF(distance_km,0))) as avg_fpk,",
        "       MIN(pickup_ts) as min_ts, MAX(pickup_ts) as max_ts",
        "FROM trips WHERE 1=1"
    ]
    params = []
    if start:
        q.append("AND pickup_ts >= ?")
        params.append(start)
    if end:
        q.append("AND pickup_ts <= ?")
        params.append(end)
    where = []
    where, params_extra = _apply_custom_filters(where, [])
    if where:
        q.append("AND "+' AND '.join(where))
        params.extend(params_extra)
    sql = ' '.join(q)
    with get_db() as db:
        row = db.execute(sql, params).fetchone()
    if row:
        return jsonify(dict(row))
    else:
        return jsonify({"trips":0, "avg_speed":0, "avg_fpk":0, "min_ts": None, "max_ts": None})

@app.get('/api/monthly_counts')
def api_monthly_counts():
    start, end, err = _validated_range()
    if err:
        return err
    where = ["1=1"]
    params = []
    if start:
        where.append("pickup_ts >= ?")
        params.append(start)
    if end:
        where.append("pickup_ts <= ?")
        params.append(end)
    where, params = _apply_custom_filters(where, params)
    sql = f"""
            SELECT substr(pickup_ts,1,7) as ym, COUNT(*) as c
            FROM trips
            WHERE {' AND '.join(where)}
            GROUP BY ym
            ORDER BY ym
          """
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return jsonify([{"month": r[0], "count": r[1]} for r in rows])

@app.get('/api/top_cells')
def api_top_cells():
    try:
        k = _clamp_int('k', 10, 1, 100)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    start, end, err = _validated_range()
    if err:
        return err
    where = ["pickup_cell IS NOT NULL"]
    params = []
    if start:
        where.append("pickup_ts >= ?")
        params.append(start)
    if end:
        where.append("pickup_ts <= ?")
        params.append(end)
    where, params = _apply_custom_filters(where, params)
    params.append(k)
    sql = f"""
            SELECT pickup_cell as cell, COUNT(*) as c
            FROM trips
            WHERE {' AND '.join(where)}
            GROUP BY pickup_cell
            ORDER BY c DESC
            LIMIT ?
          """
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return jsonify([{"cell": r[0], "count": r[1]} for r in rows])

@app.get('/api/trips')
def api_trips():
    try:
        limit = _clamp_int('limit', 50, 1, 1000)
        offset = _clamp_int('offset', 0, 0, 10_000_000)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    start, end, err = _validated_range()
    if err:
        return err
    where = ["1=1"]
    params = []
    if start:
        where.append("pickup_ts >= ?")
        params.append(start)
    if end:
        where.append("pickup_ts <= ?")
        params.append(end)
    where, params = _apply_custom_filters(where, params)
    with get_db() as db:
        sql = f"""
            SELECT pickup_ts, dropoff_ts, distance_km, duration_min, speed_kmh, fare_amount, fare_per_km
            FROM trips
            WHERE {' AND '.join(where)}
            ORDER BY pickup_ts
            LIMIT ? OFFSET ?
        """
        rows = db.execute(sql, (*params, limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
