from flask import Flask, send_from_directory, jsonify, request
import os
import datetime
import re
import json
import subprocess
import tempfile
import logging

# Configure logging to only show errors
# logging.getLogger('werkzeug').setLevel(logging.ERROR)
# logging.getLogger('flask').setLevel(logging.ERROR)

app = Flask(__name__, static_url_path='/static', static_folder='static')
OUTPUT_DIRECTORY = 'output'

def get_date_param():
    date = request.args.get('date')
    if not date or date == 'undefined':
        date = datetime.datetime.now().strftime("%Y%m%d")
    return date

@app.route('/api/files')
def list_files():
    today = datetime.datetime.now().strftime("%Y%m%d")
    directory = os.path.join(OUTPUT_DIRECTORY, today)
    
    if not os.path.exists(directory):
        return jsonify([])

    files = os.listdir(directory)
    image_files = [f for f in files if f.endswith('.jpg')]
    # Sort files by timestamp (newest first)
    image_files.sort(reverse=True)
    return jsonify(image_files)

@app.route('/api/metadata')
def get_metadata():
    # Get date from query parameter, default to today
    date_param = request.args.get('date', datetime.datetime.now().strftime("%Y%m%d"))
    
    # Get 'since' parameter (HHMMSS string)
    since_param = request.args.get('since')
    
    # Find all JSON metadata files for the specified date
    date_dir = os.path.join(OUTPUT_DIRECTORY, date_param)
    if not os.path.exists(date_dir):
        return jsonify([])
    
    json_files = [f for f in os.listdir(date_dir) if f.endswith('.json')]
    
    # Filter files by time if 'since' parameter was provided
    if since_param:
        filtered_files = []
        for filename in json_files:
            # Extract time string from filename (HHMMSS)
            match = re.match(r'^\d{8}_(\d{6})_', filename)
            if match:
                file_time = match.group(1)
                if file_time > since_param:
                    filtered_files.append(filename)
        json_files = filtered_files
    
    # Sort by timestamp (newest first)
    json_files.sort(reverse=True)
    
    return jsonify(json_files)

@app.route('/api/update/<filename>', methods=['POST'])
def update_json(filename):
    if not filename.endswith('.json'):
        return jsonify({'error': 'Invalid file type'}), 400
        
    # Extract date from request parameters
    date = request.args.get('date', datetime.datetime.now().strftime("%Y%m%d"))
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    filepath = os.path.join(directory, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
        
    try:
        json_data = request.get_json()
        with open(filepath, 'w') as f:
            json.dump(json_data, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete/<base_filename>', methods=['DELETE'])
def delete_files(base_filename):
    # Extract date from request parameters
    date = request.args.get('date', datetime.datetime.now().strftime("%Y%m%d"))
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    
    if not os.path.exists(directory):
        return jsonify({'error': 'Directory not found'}), 404

    # Find and delete all files with the same base filename
    files_to_delete = [f for f in os.listdir(directory) if f.startswith(base_filename)]
    for file in files_to_delete:
        os.remove(os.path.join(directory, file))
    
    return jsonify({'success': True, 'deleted_files': files_to_delete})

@app.route('/media/<filename>')
def serve_media(filename):
    # Extract the date from the start of the filename
    match = re.match(r'^(\d{8})_', filename)
    if not match:
        return jsonify({'error': 'Invalid filename format'}), 400

    date = match.group(1)
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    filepath = os.path.join(directory, filename)

    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    if filename.endswith('.jpg') or filename.endswith('.json') or filename.endswith('.mp4'):
        return send_from_directory(directory, filename)
    
    return '', 404

@app.route('/api/dates')
def list_dates():
    if not os.path.exists(OUTPUT_DIRECTORY):
        return jsonify([])

    dates = [d for d in os.listdir(OUTPUT_DIRECTORY) if os.path.isdir(os.path.join(OUTPUT_DIRECTORY, d))]
    dates.sort(reverse=True)  # Newest first
    return jsonify(dates)

@app.route('/api/cpu_temperature')
def get_cpu_temperature():
    try:
        # Try vcgencmd first (Raspberry Pi specific)
        try:
            output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode('utf-8')
            temp_str = output.strip().split('=')[1].replace('\'C', '')
            temperature = float(temp_str)
            return jsonify({"temperature": temperature})
        except (subprocess.SubprocessError, FileNotFoundError):
            # Fall back to reading from thermal zone if vcgencmd fails
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = float(f.read().strip()) / 1000.0  # Convert millicelsius to celsius
                return jsonify({"temperature": round(temp, 1)})
            except (IOError, FileNotFoundError):
                # If no thermal info is available, return a mock value for testing
                return jsonify({"temperature": 42.0, "mock": True})
    except Exception as e:
        app.logger.error(f"Error getting temperature: {str(e)}")
        return jsonify({"error": str(e), "temperature": None}), 500

# Add a simple test endpoint to check if API is working
@app.route('/api/test')
def test_api():
    return jsonify({"status": "API working", "timestamp": datetime.datetime.now().isoformat()})

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
