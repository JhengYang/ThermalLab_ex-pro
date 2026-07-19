"""
Database models and operations for FLIR Thermal Analyzer.
Uses SQLite for simplicity and portability.
"""
import sqlite3
import os
import json
from datetime import datetime

DB_DIR = os.environ.get('FLIR_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DB_DIR, 'flir_data.db')


def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_name TEXT NOT NULL,
            experiment_time TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            rgb_filename TEXT,
            thermal_filename TEXT,
            notes TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roi_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            annotation_name TEXT NOT NULL,
            roi_x INTEGER NOT NULL,
            roi_y INTEGER NOT NULL,
            roi_width INTEGER NOT NULL,
            roi_height INTEGER NOT NULL,
            k_points INTEGER NOT NULL,
            temp_min REAL,
            temp_max REAL,
            temp_mean REAL,
            temp_std REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temperature_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roi_analysis_id INTEGER NOT NULL,
            point_label TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            temperature REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (roi_analysis_id) REFERENCES roi_analyses(id) ON DELETE CASCADE
        )
    ''')

    # Create indexes for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_experiment_name 
        ON experiments(experiment_name)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_experiment_time 
        ON experiments(experiment_time)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_roi_annotation 
        ON roi_analyses(annotation_name)
    ''')

    conn.commit()
    conn.close()


def save_experiment(experiment_name, experiment_time, rgb_filename=None,
                    thermal_filename=None, notes=None):
    """Save a new experiment record."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO experiments (experiment_name, experiment_time, 
                                 rgb_filename, thermal_filename, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (experiment_name, experiment_time, rgb_filename, thermal_filename, notes))
    experiment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return experiment_id


def save_roi_analysis(experiment_id, annotation_name, roi, k_points, stats):
    """Save ROI analysis results."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO roi_analyses (experiment_id, annotation_name,
                                   roi_x, roi_y, roi_width, roi_height,
                                   k_points, temp_min, temp_max, temp_mean, temp_std)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (experiment_id, annotation_name,
          roi['x'], roi['y'], roi['width'], roi['height'],
          k_points, stats['min'], stats['max'], stats['mean'], stats['std']))
    roi_analysis_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return roi_analysis_id


def save_temperature_samples(roi_analysis_id, samples):
    """Save temperature sample points."""
    conn = get_db()
    cursor = conn.cursor()
    for sample in samples:
        cursor.execute('''
            INSERT INTO temperature_samples (roi_analysis_id, point_label,
                                              x, y, temperature)
            VALUES (?, ?, ?, ?, ?)
        ''', (roi_analysis_id, sample['label'],
              sample['x'], sample['y'], sample['temperature']))
    conn.commit()
    conn.close()


def get_experiments_list():
    """Get unique experiment names for autocomplete."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT experiment_name FROM experiments ORDER BY experiment_name
    ''')
    result = [row['experiment_name'] for row in cursor.fetchall()]
    conn.close()
    return result


def query_data(experiment_name=None, date_from=None, date_to=None):
    """Query temperature data with optional filters."""
    conn = get_db()
    cursor = conn.cursor()

    query = '''
        SELECT 
            ts.id,
            e.experiment_name,
            e.experiment_time,
            ra.annotation_name,
            ts.point_label,
            ts.x,
            ts.y,
            ts.temperature,
            ra.roi_x,
            ra.roi_y,
            ra.roi_width,
            ra.roi_height,
            ra.k_points,
            ra.temp_min,
            ra.temp_max,
            ra.temp_mean,
            ra.temp_std,
            e.rgb_filename,
            e.thermal_filename
        FROM temperature_samples ts
        JOIN roi_analyses ra ON ts.roi_analysis_id = ra.id
        JOIN experiments e ON ra.experiment_id = e.id
        WHERE 1=1
    '''
    params = []

    if experiment_name:
        query += ' AND e.experiment_name LIKE ?'
        params.append(f'%{experiment_name}%')

    if date_from:
        query += ' AND e.experiment_time >= ?'
        params.append(date_from)

    if date_to:
        query += ' AND e.experiment_time <= ?'
        params.append(date_to + ' 23:59:59')

    query += ' ORDER BY e.experiment_time DESC, ra.annotation_name, ts.point_label'

    cursor.execute(query, params)
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result


def delete_experiment(experiment_id):
    """Delete an experiment and all associated data."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM experiments WHERE id = ?', (experiment_id,))
    conn.commit()
    conn.close()
