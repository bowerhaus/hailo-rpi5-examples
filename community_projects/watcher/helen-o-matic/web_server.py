from flask import Flask, send_from_directory, jsonify, request, send_file
import os
import sys
from io import BytesIO
from clock import Clock

# Add watcher directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from web_server_common import (token_required, handle_login, handle_register, handle_login_page,
                   handle_list_dates, handle_media, handle_delete_files, handle_update_json,
                   handle_cpu_temperature, get_date_param, OUTPUT_DIRECTORY, handle_metadata_request,
                   handle_logout)

app = Flask(__name__, static_url_path='/static', static_folder='static')

@app.route('/api/metadata')
@token_required
def list_metadata():
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
    return handle_cpu_temperature()

@app.route('/api/login', methods=['POST'])
def login():
    return handle_login()

@app.route('/logout')
def logout():
    return handle_logout()

@app.route('/api/register', methods=['POST'])
@token_required
def register():
    return handle_register()

@app.route('/login')
def login_page():
    return handle_login_page(app.static_folder)

@app.route('/')
@token_required
def home():
    return send_from_directory(app.static_folder, 'home.html')

@app.route('/review')
@token_required
def review():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', ssl_context=('certificate/helen-o-matic.pem', 'certificate/helen-o-matic-privkey.pem'))
