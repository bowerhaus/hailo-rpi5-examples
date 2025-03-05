from flask import Flask, send_from_directory, jsonify, request, send_file
import os
import datetime
import re
import json
import subprocess  # Import the subprocess module
import tempfile  # Import the tempfile module
from io import BytesIO
from clock import Clock  # Import the Clock class

app = Flask(__name__, static_url_path='/static', static_folder='static')
OUTPUT_DIRECTORY = 'output'

def get_date_param():
    date = request.args.get('date')
    if not date or date == 'undefined':
        date = datetime.datetime.now().strftime("%Y%m%d")
    return date

@app.route('/api/files')
def list_files():
    date = get_date_param()
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    if not os.path.exists(directory):
        return jsonify([])
    files = os.listdir(directory)
    image_files = [f for f in files if f.endswith('.jpg')]
    image_files.sort(reverse=True)
    return jsonify(image_files)

@app.route('/api/metadata')
def list_metadata():
    date = get_date_param()
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    if not os.path.exists(directory):
        return jsonify([])
    files = os.listdir(directory)
    json_files = [f for f in files if f.endswith('.json')]
    json_files.sort(reverse=True)
    return jsonify(json_files)

@app.route('/api/images/<root_filename>')
def list_sequence_images(root_filename):
    date = get_date_param()
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    base_name = re.sub(r'_x\d+_\d+$', '', root_filename)
    all_files = os.listdir(directory)
    sequence_images = [f for f in all_files if f.startswith(base_name) and '[' in f and f.endswith('.jpg')]
    sequence_images.sort()
    return jsonify(sequence_images)

@app.route('/api/update/<filename>', methods=['POST'])
def update_json(filename):
    date = get_date_param()
    if not filename.endswith('.json'):
        return jsonify({'error': 'Invalid file type'}), 400
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
    date = get_date_param()
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    if not os.path.exists(directory):
        return jsonify({'error': 'Directory not found'}), 404
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

# NEW: Add an API endpoint to generate and return a clock image
@app.route('/api/clock_image')
def get_clock_image():
    clock = Clock()
    # Read days query parameter; default to all days if not provided
    days = request.args.get('days', "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday")
    pil_img = clock.create_clock_image(days=days)
    pil_img = clock.draw_current_hour_hand(pil_img)
    
    img_io = BytesIO()
    pil_img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

@app.route('/api/cpu_temperature')
def get_cpu_temp():
    try:
        temp = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        temp = float(temp.replace("temp=", "").replace("'C\n", ""))
        return jsonify({"cpu_temp": temp})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return send_from_directory('static', 'home.html')

@app.route('/review')
def review():
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
