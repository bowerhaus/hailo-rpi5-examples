from flask import Flask, send_from_directory, jsonify, request
import os
import sys
import logging
import re

# Add watcher directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from web_server_common import (token_required, handle_login, handle_register, handle_login_page,
                   handle_list_dates, handle_media, handle_delete_files, handle_update_json,
                   handle_cpu_temperature, get_date_param, OUTPUT_DIRECTORY, handle_metadata_request,
                   handle_logout, SECRET_KEY, handle_user_status)

# Configure logging to only show errors
# logging.getLogger('werkzeug').setLevel(logging.ERROR)
# logging.getLogger('flask').setLevel(logging.ERROR)

app = Flask(__name__, static_url_path='/static', static_folder='static')

@app.route('/api/metadata')
@token_required
def get_metadata():
    return handle_metadata_request()

@app.route('/api/update/<filename>', methods=['POST'])
@token_required
def update_json(filename):
    return handle_update_json(filename)

@app.route('/api/delete/<base_filename>', methods=['DELETE'])
@token_required
def delete_files(base_filename):
    return handle_delete_files(base_filename)

@app.route('/media/<filename>')
@token_required
def serve_media(filename):
    return handle_media(filename)

@app.route('/api/dates')
@token_required
def list_dates():
    return handle_list_dates()

@app.route('/api/cpu_temperature')
@token_required
def get_cpu_temperature():
    return handle_cpu_temperature()
    
@app.route('/api/login', methods=['POST'])
def login():
    return handle_login()

@app.route('/logout')
def logout():
    return handle_logout()

@app.route('/api/register', methods=['POST'])
def register():
    return handle_register()

@app.route('/api/user')
@token_required
def user_status():
    return handle_user_status()

@app.route('/login')
def login_page():
    return handle_login_page(app.static_folder)

# Removed debug route

@app.route('/')
@token_required
def index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, ssl_context=('certificate/helen-o-matic.pem', 'certificate/helen-o-matic-privkey.pem'))
