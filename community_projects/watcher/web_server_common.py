import os
import datetime
import re
import json
import subprocess
import hashlib
import jwt
from flask import request, redirect, url_for, jsonify, send_from_directory

# Constants
# Load secret key from secrets.json in the current folder
secrets_path = os.path.join(os.path.dirname(__file__), 'secrets.json')
with open(secrets_path, 'r') as f:
    secrets = json.load(f)
    SECRET_KEY = secrets['secret_key']
USERS_FILE = 'users.json'
OUTPUT_DIRECTORY = 'output'

# User authentication functions
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users_data = json.load(f)
            # Convert legacy format to new format if needed
            converted_users = {}
            for username, value in users_data.items():
                if isinstance(value, str):
                    # Legacy format with just password hash
                    converted_users[username] = {
                        'password': value,
                        'is_admin': True  # Default existing users to admin
                    }
                else:
                    # Already in new format
                    converted_users[username] = value
            return converted_users
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

def get_user_from_token():
    """Extract user information from token"""
    token = request.cookies.get('token')
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return {
            'username': payload.get('username'),
            'is_admin': payload.get('is_admin', False)
        }
    except:
        return None

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

def verify_admin_token():
    """Verify the admin authorization token from the request headers"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return False, "Missing or invalid authorization header"
    
    token = auth_header.split(' ')[1]
    try:
        # Decode and verify the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        # Check if the user is an admin
        if not payload.get('is_admin', False):
            return False, "Administrator privileges required"
        return True, ""
    except jwt.ExpiredSignatureError:
        return False, "Authorization token has expired"
    except jwt.InvalidTokenError:
        return False, "Invalid authorization token"

# Common API handlers
def handle_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    users = load_users()
    
    # Check if the user exists
    if username not in users:
        return jsonify({'error': 'Invalid credentials'}), 401
        
    user_data = users[username]
    
    # Handle both legacy format and new format
    if isinstance(user_data, str):
        # Legacy format - just password hash
        password_hash = user_data
        is_admin = True  # Default to admin for legacy users
    else:
        # New format - dictionary with password and admin status
        password_hash = user_data['password']
        is_admin = user_data.get('is_admin', False)
    
    # Compare stored hash with hash of provided password
    if password_hash == hash_password(password):
        # Set token to expire after 12 hours (changed from 60 minutes)
        token = jwt.encode({
            'username': username,
            'is_admin': is_admin,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)
        }, SECRET_KEY, algorithm='HS256')
        response = jsonify({'token': token, 'is_admin': is_admin})
        response.set_cookie('token', token)
        return response
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

def handle_register():
    # First verify that the request comes from an authenticated admin
    is_valid, error_msg = verify_admin_token()
    if not is_valid:
        return jsonify({'error': error_msg or 'Admin authentication required'}), 401
    
    # Now process the registration
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin', False)
    
    # Validate input
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    # Check if username contains only allowed characters
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return jsonify({'error': 'Username can only contain letters, numbers, underscores, and hyphens'}), 400
    
    # Check password length
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400
    
    users = load_users()
    if username in users:
        return jsonify({'error': 'User already exists'}), 400
    
    # Store the user data with password hash and admin status
    users[username] = {
        'password': hash_password(password),
        'is_admin': bool(is_admin)
    }
    save_users(users)
    return jsonify({'success': True})

def handle_user_status():
    """Get the current user's status including admin privileges"""
    user = get_user_from_token()
    if user:
        return jsonify({
            'authenticated': True,
            'username': user['username'],
            'is_admin': user['is_admin']
        })
    else:
        return jsonify({'authenticated': False}), 401

def handle_login_page(static_folder):
    response = send_from_directory(static_folder, 'login.html')
    response.delete_cookie('token')  # Logout: remove authentication cookie when navigating to login page
    return response

# Add explicit logout handler
def handle_logout():
    response = redirect(url_for('login_page'))
    response.delete_cookie('token')
    return response

def handle_list_dates():
    if not os.path.exists(OUTPUT_DIRECTORY):
        return jsonify([])

    dates = [d for d in os.listdir(OUTPUT_DIRECTORY) if os.path.isdir(os.path.join(OUTPUT_DIRECTORY, d))]
    dates.sort(reverse=True)  # Newest first
    return jsonify(dates)

def handle_media(filename):
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

def handle_delete_files(base_filename):
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

def handle_update_json(filename):
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

def handle_cpu_temperature():
    try:
        # Get CPU temperature using vcgencmd
        temp = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        temp = float(temp.replace("temp=", "").replace("'C\n", ""))
        
        # Return multiple temperature formats to ensure compatibility with frontend
        return jsonify({
            "cpu_temp": temp,
            "temperature": temp,
            "temp": temp,
            "value": temp,
            "formatted": f"{temp}°C"
        })
    except Exception as e:
        # Try alternative method if vcgencmd fails
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read().strip()) / 1000
            return jsonify({
                "cpu_temp": temp,
                "temperature": temp,
                "temp": temp,
                "value": temp,
                "formatted": f"{temp}°C"
            })
        except Exception as alt_e:
            return jsonify({"error": f"Failed to get temperature"}), 500

def handle_metadata_request():
    """
    Common handler for metadata API endpoint.
    Returns a list of JSON files for a given date, filtered by 'since' timestamp if provided.
    """
    date = get_date_param()
    directory = os.path.join(OUTPUT_DIRECTORY, date)
    
    # Debug info
    print(f"Metadata requested for date: {date}")
    print(f"Looking in directory: {directory}")
    
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return jsonify([])
    
    files = os.listdir(directory)
    json_files = [f for f in files if f.endswith('.json')]
    
    print(f"Found {len(json_files)} JSON files before filtering")

    since = request.args.get('since', type=str)
    print(f"Since parameter: {since}")

    if since:
        filtered_files = []
        for file in json_files:
            try:
                # Use regex for more robust timestamp extraction
                match = re.match(r'^\d{8}_(\d{6})_', file)
                if match:
                    time_str = match.group(1)  # Extract HHMMSS from filename
                    if time_str > since:
                        filtered_files.append(file)
                else:
                    # Try splitting method as fallback
                    time_str = file.split('_')[1]  # Extract HHMMSS from filename
                    if time_str > since:
                        filtered_files.append(file)
            except (IndexError, ValueError):
                # Handle files with unexpected naming format
                print(f"Warning: Could not parse timestamp from filename: {file}")
                continue
        json_files = filtered_files
        print(f"After filtering: {len(json_files)} files")

    json_files.sort(reverse=True)
    return jsonify(json_files)

