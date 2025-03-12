from flask import Flask, send_from_directory, jsonify, request, send_file, redirect, url_for
import os
import datetime
import re
import json
import subprocess
import tempfile
from io import BytesIO
from clock import Clock
import jwt
import hashlib  # New import for password hashing

app = Flask(__name__, static_url_path='/static', static_folder='static')
OUTPUT_DIRECTORY = 'output'
SECRET_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6InRlc3R1c2VyQGV4YW1wbGUuY29tIiwiaWF0IjoxNzQxMzAzNTE0LCJleHAiOjE3NDEzMDcxMTR9.WSL53OdeTIlC1HT44_ZocGUTZf-nTm-GduDIKh-FEzo'
USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def get_date_param():
    date = request.args.get('date')
    if not date or date == 'undefined':
        date = datetime.datetime.now().strftime("%Y%m%d")
    return date

def token_required(f):
    def wrap(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return redirect(url_for('login_page'))
        try:
            jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        except:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

def get_date_param():
    date = request.args.get('date')
    if not date or date == 'undefined':
        date = datetime.datetime.now().strftime("%Y%m%d")
    return date

@app.route('/api/files')
@token_required
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
@token_required
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
@token_required
def list_sequence_images(root_filename):
    date = get_date_param()
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    base_name = re.sub(r'_x\d+_\d+$', '', root_filename)
    all_files = os.listdir(directory)
    sequence_images = [f for f in all_files if f.startswith(base_name) and '[' in f and f.endswith('.jpg')]
    sequence_images.sort()
    return jsonify(sequence_images)

@app.route('/api/update/<filename>', methods=['POST'])
@token_required
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
@token_required
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
@token_required
def serve_media(filename):
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
@token_required
def list_dates():
    if not os.path.exists(OUTPUT_DIRECTORY):
        return jsonify([])

    dates = [d for d in os.listdir(OUTPUT_DIRECTORY) if os.path.isdir(os.path.join(OUTPUT_DIRECTORY, d))]
    dates.sort(reverse=True)
    return jsonify(dates)

@app.route('/api/clock_image')
@token_required
def get_clock_image():
    clock = Clock()
    days = request.args.get('days', "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday")
    pil_img = clock.create_clock_image(days=days)
    pil_img = clock.draw_current_hour_hand(pil_img)
    
    img_io = BytesIO()
    pil_img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

@app.route('/api/cpu_temperature')
@token_required
def get_cpu_temp():
    try:
        temp = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        temp = float(temp.replace("temp=", "").replace("'C\n", ""))
        return jsonify({"cpu_temp": temp})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    users = load_users()
    # Compare stored hash with hash of provided password
    if username in users and users[username] == hash_password(password):
        # Set token to expire after 1 minute using non-deprecated datetime method
        token = jwt.encode({
            'username': username,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)
        }, SECRET_KEY, algorithm='HS256')
        response = jsonify({'token': token})
        response.set_cookie('token', token)
        return response
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/register', methods=['POST'])
@token_required  # registration endpoint now requires authentication
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    users = load_users()
    if username in users:
        return jsonify({'error': 'User already exists'}), 400
    
    # Store the hashed password instead of plain text
    users[username] = hash_password(password)
    save_users(users)
    return jsonify({'success': True})

@app.route('/login')
def login_page():
    response = send_from_directory('static', 'login.html')
    response.delete_cookie('token')  # Logout: remove authentication cookie when navigating to login page
    return response

@app.route('/')
@token_required
def home():
    return send_from_directory('static', 'home.html')

@app.route('/review')
@token_required
def review():
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', ssl_context=('certificate/helen-o-matic.pem', 'certificate/helen-o-matic-privkey.pem'))
