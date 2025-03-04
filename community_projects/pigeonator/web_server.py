from flask import Flask, send_from_directory, jsonify, request
import os
import datetime
import re
import json
import subprocess
import tempfile
import logging

# Configure logging to only show errors
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('flask').setLevel(logging.ERROR)

app = Flask(__name__, static_url_path='/static', static_folder='static')
OUTPUT_DIRECTORY = 'output'

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
def list_metadata():
    date = request.args.get('date', datetime.datetime.now().strftime("%Y%m%d"))
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    
    if not os.path.exists(directory):
        return jsonify([])

    files = os.listdir(directory)
    json_files = [f for f in files if f.endswith('.json')]
    json_files.sort(reverse=True)  # Newest first
    return jsonify(json_files)

@app.route('/api/images/<root_filename>')
def list_sequence_images(root_filename):
    today = datetime.datetime.now().strftime("%Y%m%d")
    directory = os.path.join(OUTPUT_DIRECTORY, today)
    
    # Remove the _xN_M suffix from filename to get base name
    base_name = re.sub(r'_x\d+_\d+$', '', root_filename)
    
    # Find all sequence images matching the base name
    all_files = os.listdir(directory)
    sequence_images = [f for f in all_files if f.startswith(base_name) and '[' in f and f.endswith('.jpg')]
    sequence_images.sort()  # Sort by sequence number
    
    return jsonify(sequence_images)

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

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
