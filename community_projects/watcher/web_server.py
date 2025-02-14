from flask import Flask, send_from_directory, jsonify, request
import os
import datetime
import re
import json
import subprocess  # Import the subprocess module
import tempfile  # Import the tempfile module

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
    today = datetime.datetime.now().strftime("%Y%m%d")
    directory = os.path.join(OUTPUT_DIRECTORY, today)
    
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
        
    today = datetime.datetime.now().strftime("%Y%m%d")
    directory = os.path.join(OUTPUT_DIRECTORY, today)
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
    today = datetime.datetime.now().strftime("%Y%m%d")
    directory = os.path.join(OUTPUT_DIRECTORY, today)
    
    if not os.path.exists(directory):
        return jsonify({'error': 'Directory not found'}), 404

    # Find and delete all files with the same base filename
    files_to_delete = [f for f in os.listdir(directory) if f.startswith(base_filename)]
    for file in files_to_delete:
        os.remove(os.path.join(directory, file))
    
    return jsonify({'success': True, 'deleted_files': files_to_delete})

@app.route('/media/<filename>')
def serve_media(filename):
    today = datetime.datetime.now().strftime("%Y%m%d")
    directory = os.path.join(OUTPUT_DIRECTORY, today)
    filepath = os.path.join(directory, filename)

    if filename.endswith('.jpg'):
        return send_from_directory(directory, filename)
    elif filename.endswith('.json'):
        return send_from_directory(directory, filename)
    elif filename.endswith('.mp4'):
        # Check if the file exists
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404

        # Check if the video is already H264
        try:
            result = subprocess.run([
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'default=nokey=1:noprint_wrappers=1',
                filepath
            ], capture_output=True, text=True, check=True)
            codec_name = result.stdout.strip()

            if codec_name == 'h264':
                print(f"Video {filename} is already H264.")
                return send_from_directory(directory, filename)
            else:
                print(f"Video {filename} is not H264, converting...")
                try:
                    # Create a temporary file in the same directory
                    with tempfile.NamedTemporaryFile(suffix=".mp4", dir=directory, delete=False) as tmpfile:
                        temp_filepath = tmpfile.name

                    subprocess.run([
                        'ffmpeg',
                        '-y',  # Add -y to overwrite existing files
                        '-i', filepath,
                        '-codec:v', 'libx264',  # Use H264 codec
                        '-preset', 'fast',  # Use a fast preset
                        '-movflags', 'faststart',  # Optimize for streaming
                        temp_filepath  # Output to temporary file
                    ], check=True)

                    # Replace the original file with the temporary file
                    os.replace(temp_filepath, filepath)
                    print(f"Video {filename} successfully converted to H264 and overwritten.")
                    return send_from_directory(directory, filename)
                except subprocess.CalledProcessError as e:
                    print(f"Video conversion failed: {e}")
                    return jsonify({'error': 'Video conversion failed'}), 500
                finally:
                    # Ensure the temporary file is deleted if conversion fails
                    if os.path.exists(temp_filepath):
                        os.remove(temp_filepath)

        except subprocess.CalledProcessError as e:
            print(f"ffprobe failed: {e}")
            return jsonify({'error': 'ffprobe failed'}), 500
    return '', 404

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
