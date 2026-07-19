"""
FLIR Thermal Analyzer - Flask Application
==========================================
Web application for processing FLIR thermal imaging data.
Supports image upload, alignment, ROI selection, background removal,
temperature sampling, and data export.
"""
import os
import io
import csv
import json
import uuid
from datetime import datetime

from flask import (Flask, render_template, request, jsonify, send_file,
                   send_from_directory, Response)
from flask_cors import CORS

import numpy as np
import cv2

from database import init_db, save_experiment, save_roi_analysis, save_temperature_samples, \
    get_experiments_list, query_data
from image_processing import (
    extract_thermal_data_exiftool, create_sobel_edge_image,
    create_thermal_colormap, align_images, create_overlay,
    remove_background_roi, sample_temperature_points,
    save_processed_image, draw_sample_points_on_roi,
    process_full_pipeline, UPLOAD_DIR, PROCESSED_DIR
)

# Initialize database tables
init_db()

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# In-memory cache for current session processing data
# In production, use Redis or session storage
_session_cache = {}


@app.before_request
def ensure_dirs():
    """Ensure upload/processed directories exist."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)


@app.route('/')
def index():
    """Serve the main application page."""
    return render_template('index.html')


@app.route('/api/process', methods=['POST'])
def process_images():
    """
    Process uploaded RGB and thermal images.
    Runs the full pipeline: extract thermal data, edge detection,
    alignment, and overlay creation.
    
    Expects multipart form data with:
    - rgb_image: RGB image file
    - thermal_image: FLIR thermal image file
    """
    if 'rgb_image' not in request.files or 'thermal_image' not in request.files:
        return jsonify({'error': '請上傳 RGB 和熱影像檔案'}), 400

    rgb_file = request.files['rgb_image']
    thermal_file = request.files['thermal_image']

    if rgb_file.filename == '' or thermal_file.filename == '':
        return jsonify({'error': '請選擇檔案'}), 400

    try:
        # Generate unique session ID
        session_id = uuid.uuid4().hex[:12]

        # Save uploaded files
        rgb_ext = os.path.splitext(rgb_file.filename)[1] or '.jpg'
        thermal_ext = os.path.splitext(thermal_file.filename)[1] or '.jpg'

        rgb_filename = f"rgb_{session_id}{rgb_ext}"
        thermal_filename = f"thermal_{session_id}{thermal_ext}"

        rgb_path = os.path.join(UPLOAD_DIR, rgb_filename)
        thermal_path = os.path.join(UPLOAD_DIR, thermal_filename)

        rgb_file.save(rgb_path)
        thermal_file.save(thermal_path)

        # Run full processing pipeline
        result = process_full_pipeline(rgb_path, thermal_path)

        # Cache session data for ROI analysis
        thermal_data = extract_thermal_data_exiftool(thermal_path)
        thermal_colored = create_thermal_colormap(thermal_data)

        # Generate aligned RGB image for later ROI analysis
        edge_image = create_sobel_edge_image(thermal_data)
        aligned_rgb, _ = align_images(rgb_path, thermal_data, edge_image)

        _session_cache[session_id] = {
            'rgb_path': rgb_path,
            'thermal_path': thermal_path,
            'thermal_data': thermal_data,
            'thermal_colored': thermal_colored,
            'aligned_rgb': aligned_rgb,
            'rgb_filename': rgb_file.filename,
            'thermal_filename': thermal_file.filename,
        }

        result['session_id'] = session_id
        result['message'] = '影像處理完成！請在右側圖片上框選 ROI 區域。'

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'影像處理失敗: {str(e)}'}), 500


@app.route('/api/analyze_roi', methods=['POST'])
def analyze_roi():
    """
    Analyze a selected ROI region.
    Performs background removal and random temperature sampling.
    
    Expects JSON body:
    {
        "session_id": str,
        "roi": {"x": int, "y": int, "width": int, "height": int},
        "k": int,
        "annotation_name": str,
        "experiment_name": str,
        "experiment_time": str
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': '缺少請求資料'}), 400

    required = ['session_id', 'roi', 'k', 'annotation_name']
    for field in required:
        if field not in data:
            return jsonify({'error': f'缺少必要欄位: {field}'}), 400

    session_id = data['session_id']

    if session_id not in _session_cache:
        return jsonify({'error': '處理階段已過期，請重新上傳影像'}), 400

    try:
        cache = _session_cache[session_id]
        thermal_data = cache['thermal_data']
        thermal_colored = cache['thermal_colored']
        aligned_rgb = cache.get('aligned_rgb')

        roi = data['roi']
        k = int(data['k'])
        annotation_name = data['annotation_name']

        # Remove background from ROI (also applies mask to aligned RGB)
        roi_fg, mask, thermal_roi, roi_rgb_fg = remove_background_roi(
            thermal_data, roi, thermal_colored, aligned_rgb=aligned_rgb
        )

        # Sample k random temperature points
        samples, stats = sample_temperature_points(
            thermal_roi, mask, k, annotation_name,
            roi_offset={'x': roi['x'], 'y': roi['y']}
        )

        # Draw sample points on ROI image
        roi_annotated = draw_sample_points_on_roi(roi_fg, samples,
                                                   roi_offset={'x': roi['x'], 'y': roi['y']})

        # Save result images
        roi_url = save_processed_image(roi_annotated, 'roi_annotated')
        mask_url = save_processed_image(mask, 'roi_mask')
        roi_fg_url = save_processed_image(roi_fg, 'roi_fg')

        # Save aligned RGB foreground image if available
        roi_rgb_fg_url = None
        if roi_rgb_fg is not None:
            roi_rgb_fg_url = save_processed_image(roi_rgb_fg, 'roi_rgb_fg')

        # Cache analysis results for saving
        _session_cache[session_id]['last_analysis'] = {
            'roi': roi,
            'k': k,
            'annotation_name': annotation_name,
            'experiment_name': data.get('experiment_name', ''),
            'experiment_time': data.get('experiment_time', ''),
            'samples': samples,
            'stats': stats
        }

        response_data = {
            'roi_image_url': roi_url,
            'roi_fg_url': roi_fg_url,
            'mask_image_url': mask_url,
            'samples': samples,
            'stats': stats,
            'message': f'成功從 ROI 中取樣 {len(samples)} 個溫度點'
        }
        if roi_rgb_fg_url:
            response_data['roi_rgb_fg_url'] = roi_rgb_fg_url

        return jsonify(response_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'ROI 分析失敗: {str(e)}'}), 500


@app.route('/api/save', methods=['POST'])
def save_to_database():
    """
    Save the current analysis results to the database.
    
    Expects JSON body:
    {
        "session_id": str,
        "experiment_name": str,
        "experiment_time": str,
        "annotation_name": str,
        "samples": [...],
        "stats": {...},
        "roi": {...},
        "k": int
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': '缺少請求資料'}), 400

    session_id = data.get('session_id', '')

    try:
        # Get filenames from cache if available
        rgb_filename = None
        thermal_filename = None
        if session_id in _session_cache:
            cache = _session_cache[session_id]
            rgb_filename = cache.get('rgb_filename')
            thermal_filename = cache.get('thermal_filename')

        experiment_name = data.get('experiment_name', 'unnamed')
        experiment_time = data.get('experiment_time', datetime.now().isoformat())

        # Save experiment
        experiment_id = save_experiment(
            experiment_name=experiment_name,
            experiment_time=experiment_time,
            rgb_filename=rgb_filename,
            thermal_filename=thermal_filename
        )

        # Save ROI analysis
        roi = data.get('roi', {})
        k = data.get('k', 0)
        stats = data.get('stats', {})
        annotation_name = data.get('annotation_name', 'unnamed')

        roi_analysis_id = save_roi_analysis(
            experiment_id=experiment_id,
            annotation_name=annotation_name,
            roi=roi,
            k_points=k,
            stats=stats
        )

        # Save temperature samples
        samples = data.get('samples', [])
        save_temperature_samples(roi_analysis_id, samples)

        return jsonify({
            'message': f'成功儲存 {len(samples)} 筆溫度數據到資料庫',
            'experiment_id': experiment_id,
            'roi_analysis_id': roi_analysis_id
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'儲存失敗: {str(e)}'}), 500


@app.route('/api/experiments', methods=['GET'])
def list_experiments():
    """Get list of unique experiment names for autocomplete."""
    try:
        experiments = get_experiments_list()
        return jsonify({'experiments': experiments})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export', methods=['GET'])
def export_data():
    """
    Export temperature data with optional filters.
    
    Query parameters:
    - experiment_name: filter by experiment name (partial match)
    - date_from: filter by start date (YYYY-MM-DD)
    - date_to: filter by end date (YYYY-MM-DD)
    - format: 'json' (default) or 'csv'
    """
    experiment_name = request.args.get('experiment_name', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    export_format = request.args.get('format', 'json').strip()

    try:
        results = query_data(
            experiment_name=experiment_name if experiment_name else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None
        )

        if export_format == 'csv':
            # Generate CSV file
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow([
                'ID', 'Experiment Name', 'Experiment Time',
                'Annotation Name', 'Point Label',
                'X', 'Y', 'Temperature (°C)',
                'ROI X', 'ROI Y', 'ROI Width', 'ROI Height',
                'K Points', 'Min Temp', 'Max Temp', 'Mean Temp', 'Std Temp',
                'RGB File', 'Thermal File'
            ])

            for row in results:
                writer.writerow([
                    row['id'], row['experiment_name'], row['experiment_time'],
                    row['annotation_name'], row['point_label'],
                    row['x'], row['y'], row['temperature'],
                    row['roi_x'], row['roi_y'], row['roi_width'], row['roi_height'],
                    row['k_points'], row['temp_min'], row['temp_max'],
                    row['temp_mean'], row['temp_std'],
                    row.get('rgb_filename', ''), row.get('thermal_filename', '')
                ])

            output.seek(0)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"flir_export_{timestamp}.csv"

            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename={filename}',
                    'Content-Type': 'text/csv; charset=utf-8-sig'
                }
            )

        elif export_format == 'json':
            if request.args.get('download') == '1':
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"flir_export_{timestamp}.json"

                return Response(
                    json.dumps(results, ensure_ascii=False, indent=2),
                    mimetype='application/json',
                    headers={
                        'Content-Disposition': f'attachment; filename={filename}'
                    }
                )
            return jsonify({'data': results, 'count': len(results)})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'匯出失敗: {str(e)}'}), 500


@app.route('/static/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded files."""
    return send_from_directory(UPLOAD_DIR, filename)


@app.route('/static/processed/<path:filename>')
def serve_processed(filename):
    """Serve processed files."""
    return send_from_directory(PROCESSED_DIR, filename)


if __name__ == '__main__':
    # Initialize database
    init_db()
    print("=" * 60)
    print("  FLIR Thermal Analyzer")
    print("  Open http://localhost:5050 in your browser")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5050, debug=True)
