# ######## YOUR SETUP #############

PORT=8080 # Flask server port number
GALLERY='/absolute/path/to/my/gallery' # all the gallery photo files are here

#################################


import os
import json
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_httpauth import HTTPBasicAuth # ADDED: Import for authentication
from werkzeug.utils import secure_filename
from PIL import Image, ExifTags, __version__ as pillow_version
import rawpy
import cv2
import numpy as np
try:
    import imageio.v3 as iio
except ImportError as e:
    print(f"Warning: 'imageio.v3' could not be imported ({e}). HEIC/other processing might be limited if pillow_heif fails.")
    iio = None
import io
from pillow_heif import register_heif_opener

register_heif_opener()


app = Flask(__name__)
auth = HTTPBasicAuth() # ADDED: Initialize the authentication handler

# --- User Authentication ---
# ADDED: Credentials for the server
users = {
    "user": "gallery"
}

@auth.verify_password
def verify_password(username, password):
    """Verifies the username and password."""
    if username in users and users[username] == password:
        return username
# --- End of Authentication ---

# --- Configuration ---
image_library_root = os.path.abspath(GALLERY)
TRASH_FOLDER_NAME = '_Trash'
TRASH_ROOT = os.path.join(image_library_root, TRASH_FOLDER_NAME)
COUNT_META_FILENAME = '_count.meta'
THUMBNAIL_SUBFOLDER_NAME = '.thumbnails'
PREVIEW_SUBFOLDER_NAME = '.previews'
THUMBNAIL_MAX_DIMENSION = 480

try:
    if tuple(map(int, pillow_version.split('.'))) >= (9, 1, 0):
        RESAMPLING_FILTER = Image.Resampling.LANCZOS
    else:
        RESAMPLING_FILTER = Image.LANCZOS
except AttributeError:
    RESAMPLING_FILTER = Image.LANCZOS
except Exception as e:
    RESAMPLING_FILTER = Image.LANCZOS
    print(f"Warning: Error determining resampling filter ({e}), falling back to Image.LANCZOS.")

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.avif'}
ALLOWED_RAW_EXTENSIONS = {'.nef', '.nrw', '.cr2', '.cr3', '.crw', '.arw', '.srf', '.sr2',
                          '.orf', '.raf', '.rw2', '.raw', '.dng', '.kdc', '.dcr', '.erf',
                          '.3fr', '.mef', '.pef', '.x3f'}
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.webm', '.ogg', '.avi', '.mkv'}
ALL_MEDIA_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_RAW_EXTENSIONS).union(ALLOWED_VIDEO_EXTENSIONS)

os.makedirs(image_library_root, exist_ok=True)
os.makedirs(TRASH_ROOT, exist_ok=True)


# --- Helper Functions (from gallery-server, adapted) ---
# NOTE: All helper functions remain unchanged.
def allowed_file(filename):
    """Checks if a file has an allowed extension."""
    return '.' in filename and \
           os.path.splitext(filename)[1].lower() in ALL_MEDIA_EXTENSIONS

def is_image_file(filename):
    """Checks if a file is an allowed image extension (including HEIC/AVIF)."""
    return '.' in filename and \
           os.path.splitext(filename)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def is_raw_file(filename):
    """Checks if a file is an allowed RAW extension."""
    return '.' in filename and \
           os.path.splitext(filename)[1].lower() in ALLOWED_RAW_EXTENSIONS

def is_video_file(filename):
    """Checks if a file is an allowed video extension."""
    return '.' in filename and \
           os.path.splitext(filename)[1].lower() in ALLOWED_VIDEO_EXTENSIONS

def get_media_type(filename):
    """Determines the media type (image, raw, video)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return 'image'
    elif ext in ALLOWED_RAW_EXTENSIONS:
        return 'raw'
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        return 'video'
    return 'unknown'

def _get_recursive_media_count(path):
    """
    Recursively counts all media files (images and videos) in a given path and its subdirectories.
    Excludes trash, thumbnails, and previews.
    """
    count = 0
    if not os.path.isdir(path):
        return 0

    for root, dirs, files in os.walk(path):
        # Exclude hidden directories like .thumbnails, .previews from traversal
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        # Exclude trash folder content from recursive counts for regular folders
        # This ensures counts for years/months/days don't include trashed items
        if TRASH_FOLDER_NAME in os.path.relpath(root, image_library_root).split(os.sep) and root != TRASH_ROOT:
            continue

        for file in files:
            if allowed_file(file) and not file.startswith('.') and not file.endswith('.meta'):
                count += 1
    return count

def _read_folder_item_count(folder_path):
    """Reads item count from a folder's meta file."""
    meta_file_path = os.path.join(folder_path, COUNT_META_FILENAME)
    if os.path.exists(meta_file_path):
        with open(meta_file_path, 'r') as f:
            try:
                return json.load(f).get("item_count", 0)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode {COUNT_META_FILENAME} in {folder_path}. Recalculating.")
                return None # Indicate corruption, trigger recalculation
    return None

def _update_folder_item_count_meta(folder_path):
    """Writes/updates item count to a folder's meta file."""
    if not os.path.isdir(folder_path):
        return # Cannot update count for non-existent folder

    count = _get_recursive_media_count(folder_path)
    meta_file_path = os.path.join(folder_path, COUNT_META_FILENAME)
    try:
        with open(meta_file_path, 'w') as f:
            json.dump({"item_count": count}, f)
    except Exception as e:
        print(f"Error writing {COUNT_META_FILENAME} for {folder_path}: {e}")

def _initial_scan_and_populate_counts():
    """Performs initial scan and populates all _count.meta files for all subdirectories."""
    print("Performing initial scan and populating folder item counts...")

    # Walk through the entire library root
    for root, dirs, files in os.walk(image_library_root, topdown=True):
        # Exclude the trash folder and hidden folders from the scan
        # By modifying dirs in-place, os.walk will not descend into them
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != TRASH_FOLDER_NAME]

        # Update the count for the current directory being walked
        _update_folder_item_count_meta(root)

    # Also ensure the trash folder itself has an up-to-date count
    _update_folder_item_count_meta(TRASH_ROOT)
    print("Initial scan complete.")

def _get_thumbnail_full_path(original_full_path):
    """Generates the expected full path for a thumbnail."""
    original_dir = os.path.dirname(original_full_path)
    base_filename = os.path.basename(original_full_path)
    thumbnail_dir = os.path.join(original_dir, THUMBNAIL_SUBFOLDER_NAME)
    # Use original filename base but change extension to .webp for consistency
    thumbnail_filename = f"{os.path.splitext(base_filename)[0]}.webp"
    return os.path.join(thumbnail_dir, thumbnail_filename)

def _generate_thumbnail(original_full_path):
    """Generates a thumbnail for an image, RAW, or video file and saves it."""
    thumbnail_path = _get_thumbnail_full_path(original_full_path)

    # Check if thumbnail already exists and is up-to-date
    if os.path.exists(thumbnail_path) and os.path.getmtime(thumbnail_path) >= os.path.getmtime(original_full_path):
        return thumbnail_path # Thumbnail is current, no need to regenerate

    os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True) # Ensure thumbnail dir exists

    try:
        file_extension = os.path.splitext(original_full_path)[1].lower()
        img = None

        if is_video_file(original_full_path):
            cap = cv2.VideoCapture(original_full_path)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    # Convert the frame (which is BGR) to RGB for Pillow
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb_frame)
                else:
                    print(f"ERROR: Could not read frame from video {original_full_path}")
                cap.release()
            else:
                print(f"ERROR: Could not open video {original_full_path}")

        elif file_extension in ALLOWED_RAW_EXTENSIONS:
            try:
                with rawpy.imread(original_full_path) as raw:
                    rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
                    if not isinstance(rgb, np.ndarray):
                        print(f"ERROR: rawpy.postprocess did not return a numpy array for {original_full_path}. Type: {type(rgb)}")
                        img = None
                    else:
                        img = Image.fromarray(rgb)
            except rawpy.LibRawError as raw_e:
                print(f"ERROR: rawpy.LibRawError processing RAW thumbnail for {original_full_path}: {raw_e}")
                img = None # Ensure img is None if rawpy fails
            except Exception as raw_e:
                print(f"ERROR: General error processing RAW thumbnail for {original_full_path} with rawpy: {type(raw_e).__name__}: {raw_e}")
                img = None # Ensure img is None if rawpy fails
        elif file_extension in ALLOWED_IMAGE_EXTENSIONS: # Covers HEIC, JPG, PNG, etc.
            try:
                img = Image.open(original_full_path)
            except Exception as pillow_e:
                print(f"ERROR: Pillow failed to open standard image {original_full_path}: {type(pillow_e).__name__}: {pillow_e}")
                img = None # Ensure img is None if Pillow fails
        else:
            return None

        if img is None:
            print(f"ERROR: Image object is None after all processing attempts for {original_full_path}. Thumbnail generation aborted.")
            return None

        # Apply EXIF orientation
        try:
            if hasattr(img, '_getexif'):
                exif = img._getexif()
                if exif:
                    for orientation_tag in ExifTags.TAGS.keys():
                        if ExifTags.TAGS[orientation_tag] == 'Orientation':
                            break
                    else: orientation_tag = None # Ensure orientation_tag is defined even if not found

                    if orientation_tag in exif:
                        orientation = exif[orientation_tag]
                        if orientation == 3: img = img.transpose(Image.ROTATE_180)
                        elif orientation == 6: img = img.transpose(Image.ROTATE_270)
                        elif orientation == 8: img = img.transpose(Image.ROTATE_90)
        except Exception as e:
            print(f"ERROR: Error applying EXIF orientation for {original_full_path}: {e}")

        if img.mode in ('RGBA', 'LA', 'P') or img.mode == 'L':
            img = img.convert('RGB')

        img.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION), RESAMPLING_FILTER)

        img.save(thumbnail_path, "WEBP", quality=85)
        return thumbnail_path

    except Exception as e:
        print(f"ERROR: Error generating thumbnail for {original_full_path}: {type(e).__name__}: {e}")
        return None

def _get_preview_full_path(original_full_path):
    """Generates the expected full path for a preview."""
    original_dir = os.path.dirname(original_full_path)
    base_filename = os.path.basename(original_full_path)
    preview_dir = os.path.join(original_dir, PREVIEW_SUBFOLDER_NAME)
    preview_filename = f"{os.path.splitext(base_filename)[0]}.webp"
    return os.path.join(preview_dir, preview_filename)

def _generate_preview(original_full_path):
    """Generates a full-size preview for an image (including HEIC) or RAW file and saves it."""
    preview_path = _get_preview_full_path(original_full_path)
    os.makedirs(os.path.dirname(preview_path), exist_ok=True) # Ensure preview dir exists

    if os.path.exists(preview_path) and os.path.getmtime(preview_path) >= os.path.getmtime(original_full_path):
        return preview_path

    try:
        file_extension = os.path.splitext(original_full_path)[1].lower()
        img = None

        if file_extension in ALLOWED_RAW_EXTENSIONS:
            try:
                with rawpy.imread(original_full_path) as raw:
                    rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8, gamma=(2.222, 4.5))
                    if not isinstance(rgb, np.ndarray):
                        print(f"ERROR: rawpy.postprocess did not return a numpy array for {original_full_path}. Type: {type(rgb)}")
                        img = None
                    else:
                        img = Image.fromarray(rgb)
            except rawpy.LibRawError as raw_e:
                print(f"ERROR: rawpy.LibRawError processing RAW preview for {original_full_path}: {raw_e}")
                img = None # Ensure img is None if rawpy fails
            except Exception as raw_e:
                print(f"ERROR: General error processing RAW preview for {original_full_path} with rawpy: {type(raw_e).__name__}: {raw_e}")
                img = None # Ensure img is None if rawpy fails
        elif file_extension in ALLOWED_IMAGE_EXTENSIONS: # Covers HEIC, JPG, PNG, etc.
            try:
                img = Image.open(original_full_path)
            except Exception as pillow_e:
                print(f"ERROR: Pillow failed to open standard image {original_full_path}: {type(pillow_e).__name__}: {pillow_e}")
                img = None # Ensure img is None if Pillow fails
        else:
            return None # Not a supported image format for preview generation

        if img is None:
            print(f"ERROR: Image object is None after all processing attempts for {original_full_path} for preview. Preview generation aborted.")
            return None

        # Apply EXIF orientation
        try:
            if hasattr(img, '_getexif'):
                exif = img._getexif()
                if exif:
                    for orientation_tag in ExifTags.TAGS.keys():
                        if ExifTags.TAGS[orientation_tag] == 'Orientation':
                            break
                    else: orientation_tag = None # Ensure orientation_tag is defined even if not found

                    if orientation_tag in exif:
                        orientation = exif[orientation_tag]
                        if orientation == 3: img = img.transpose(Image.ROTATE_180)
                        elif orientation == 6: img = img.transpose(Image.ROTATE_270)
                        elif orientation == 8: img = img.transpose(Image.ROTATE_90)
        except Exception as e:
            print(f"ERROR: Error applying EXIF orientation for preview {original_full_path}: {e}")

        if img.mode in ('RGBA', 'LA', 'P') or img.mode == 'L':
            img = img.convert('RGB')

        img.save(preview_path, "WEBP", quality=85)
        return preview_path

    except Exception as e:
        print(f"ERROR: Error generating preview for {original_full_path}: {type(e).__name__}: {e}")
        return None

def _get_media_files_in_directory(path, include_subfolders=False):
    """
    Gets media files directly in a directory or recursively in subdirectories.
    Returns list of dictionaries with 'filename', 'original_path', 'thumbnail_path', 'type'.
    """
    media_files = []
    if not os.path.isdir(path):
        return []

    walk_iterator = os.walk(path) if include_subfolders else [(path, [], os.listdir(path))]

    for root, dirs, files in walk_iterator:
        if include_subfolders:
            dirs[:] = [d for d in dirs if not d.startswith('.')]

        current_relative_root_part = os.path.relpath(root, image_library_root)

        if TRASH_FOLDER_NAME in current_relative_root_part.split(os.sep) and root != TRASH_ROOT:
            continue

        for file in files:
            if allowed_file(file) and not file.startswith('.') and not file.endswith('.meta'):
                full_file_path = os.path.join(root, file)
                relative_file_path = os.path.relpath(full_file_path, image_library_root).replace('\\', '/')

                file_info = {
                    'filename': file,
                    'original_path': relative_file_path,
                    'type': get_media_type(file)
                }

                thumbnail_full_path = _get_thumbnail_full_path(full_file_path)
                thumbnail_relative_path = os.path.relpath(thumbnail_full_path, image_library_root).replace('\\', '/')
                file_info['thumbnail_path'] = thumbnail_relative_path

                media_files.append(file_info)

    # UPDATED SORTING LOGIC: Sort by path depth first, then by path name.
    # This ensures root files appear before files in subdirectories.
    return sorted(media_files, key=lambda x: (x['original_path'].count('/'), x['original_path'].lower()))


# --- API Endpoints ---

@app.route('/')
def index():
    """Serves the main HTML page. This is NOT password protected."""
    return send_from_directory('static', 'index.html')

@app.route('/api/folders', defaults={'path': ''})
@app.route('/api/folders/<path:path>')
@auth.login_required # MODIFIED: Add authentication decorator
def get_folders(path):
    """Returns a list of subfolders and files for a given path."""

    current_path = os.path.join(image_library_root, path)
    if not os.path.isdir(current_path):
        return jsonify({"error": "Folder not found"}), 404

    folders_data = []
    files_in_folder = _get_media_files_in_directory(current_path, include_subfolders=False)

    for item in os.listdir(current_path):
        full_path = os.path.join(current_path, item)
        if os.path.isdir(full_path) and not item.startswith('.') and item != TRASH_FOLDER_NAME:
            count = _read_folder_item_count(full_path)
            if count is None:
                _update_folder_item_count_meta(full_path)
                count = _read_folder_item_count(full_path) or 0
            folders_data.append({"name": item, "count": count})

    month_map = {name: i for i, name in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])}
    folders_data.sort(key=lambda x: month_map.get(x['name'], x['name']))

    return jsonify({"folders": folders_data, "files": files_in_folder})


@app.route('/api/media/<path:relative_path>')
@auth.login_required # MODIFIED: Add authentication decorator
def get_media(relative_path):
    """Serves media files (images, videos, converted RAW/HEIC for display)."""
    full_path = os.path.abspath(os.path.join(image_library_root, relative_path))

    if not full_path.startswith(image_library_root):
        return jsonify({"error": "Forbidden"}), 403

    if not os.path.exists(full_path):
        return jsonify({"error": "Media not found"}), 404

    filename = os.path.basename(full_path)
    ext = os.path.splitext(filename)[1].lower()

    if ext in ALLOWED_RAW_EXTENSIONS or ext == '.heic':
        try:
            preview_path = _generate_preview(full_path)
            if preview_path and os.path.exists(preview_path):
                return send_from_directory(os.path.dirname(preview_path), os.path.basename(preview_path), mimetype='image/webp')
            else:
                print(f"ERROR: get_media - Failed to generate preview for {full_path}")
                return jsonify({"error": "Failed to generate preview"}), 500
        except Exception as e:
            print(f"ERROR: get_media - Error processing file {full_path}: {type(e).__name__}: {e}")
            return jsonify({"error": "Failed to process file for display"}), 500
    else:
        directory = os.path.dirname(full_path)
        return send_from_directory(directory, filename)

@app.route('/api/thumbnail/<path:relative_path>')
@auth.login_required # MODIFIED: Add authentication decorator
def get_thumbnail(relative_path):
    """Serves thumbnails for images and RAW files."""
    full_media_path = os.path.abspath(os.path.join(image_library_root, relative_path))

    if not full_media_path.startswith(image_library_root):
        return jsonify({"error": "Forbidden"}), 403

    if not os.path.exists(full_media_path):
        return jsonify({"error": "Media file for thumbnail not found"}), 404

    thumbnail_full_path = _generate_thumbnail(full_media_path)

    if thumbnail_full_path and os.path.exists(thumbnail_full_path):
        return send_from_directory(os.path.dirname(thumbnail_full_path), os.path.basename(thumbnail_full_path))
    else:
        print(f"ERROR: get_thumbnail - Thumbnail generation failed or unsupported type for {full_media_path}")
        return jsonify({"error": "Thumbnail generation failed or unsupported type"}), 500

@app.route('/api/recursive_media', defaults={'path_segments': ''})
@app.route('/api/recursive_media/<path:path_segments>')
@auth.login_required # MODIFIED: Add authentication decorator
def get_recursive_media(path_segments):
    """Returns all media files recursively from a given path."""
    full_path_segments = path_segments.split('/') if path_segments else []
    base_dir = os.path.abspath(os.path.join(image_library_root, *full_path_segments))

    if not base_dir.startswith(image_library_root):
        return jsonify({"error": "Forbidden"}), 403

    if not os.path.isdir(base_dir):
        return jsonify([])

    media_files = _get_media_files_in_directory(base_dir, include_subfolders=True)
    return jsonify(media_files)

@app.route('/api/download_original_raw/<path:relative_path>')
@auth.login_required # MODIFIED: Add authentication decorator
def download_original_raw(relative_path):
    """Allows downloading of original RAW/HEIC files."""
    full_path = os.path.abspath(os.path.join(image_library_root, relative_path))

    if not full_path.startswith(image_library_root):
        return jsonify({"error": "Forbidden"}), 403

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    filename = os.path.basename(full_path)
    ext = os.path.splitext(filename)[1].lower()

    if ext in ALLOWED_RAW_EXTENSIONS or ext == '.heic':
        directory = os.path.dirname(full_path)
        return send_from_directory(directory, filename, as_attachment=True)
    else:
        return jsonify({"error": "File is not a RAW/HEIC format or not allowed for direct download"}), 400

@app.route('/api/trash_content')
@auth.login_required # MODIFIED: Add authentication decorator
def get_trash_content():
    """
    Returns a list of all files in the trash directory, including subfolders.
    """
    trash_files = []
    for root, dirs, files in os.walk(TRASH_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if os.path.splitext(file)[1].lower() in ALL_MEDIA_EXTENSIONS:
                full_file_path = os.path.join(root, file)
                relative_path_in_trash = os.path.relpath(full_file_path, TRASH_ROOT)

                info = {
                    'filename': file,
                    'relative_path_in_trash': os.path.join(TRASH_FOLDER_NAME, relative_path_in_trash).replace('\\', '/'),
                    'type': get_media_type(file),
                    'thumbnail_path': os.path.join(TRASH_FOLDER_NAME, relative_path_in_trash).replace('\\', '/')
                }
                metadata_file = full_file_path + '.meta'
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r') as f:
                            meta = json.load(f)
                            info['original_path_from_metadata'] = meta.get('original_path', 'Unknown Original Path').replace('\\', '/')
                    except Exception as e:
                        print(f"Error reading metadata for {full_file_path}: {e}")
                        info['original_path_from_metadata'] = 'Error Reading Metadata'
                else:
                    info['original_path_from_metadata'] = 'Metadata Missing'

                trash_files.append(info)

    trash_files.sort(key=lambda x: x['filename'].lower())

    count = _read_folder_item_count(TRASH_ROOT)
    if count is None:
        count = len(trash_files)

    return jsonify({'files': trash_files, 'count': count})


@app.route('/api/move_to_trash', methods=['POST'])
@auth.login_required # MODIFIED: Add authentication decorator
def move_to_trash():
    """Moves a single file to the trash folder and records its original path."""
    data = request.get_json()
    file_relative_path = data.get('path')

    if not file_relative_path:
        return jsonify({"error": "Path not provided"}), 400

    original_full_path = os.path.abspath(os.path.join(image_library_root, file_relative_path))
    if not original_full_path.startswith(image_library_root) or TRASH_ROOT in original_full_path:
        return jsonify({"error": "Forbidden: Attempted to move file from outside media root or from trash."}), 403

    if not os.path.exists(original_full_path):
        return jsonify({"error": "File not found"}), 404

    filename = os.path.basename(original_full_path)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = os.urandom(4).hex()
    name, ext = os.path.splitext(filename)
    trash_filename = f"{name}_{timestamp}_{unique_id}{ext}"
    trash_full_path = os.path.join(TRASH_ROOT, trash_filename)

    try:
        trash_thumbnail_dir = os.path.join(TRASH_ROOT, THUMBNAIL_SUBFOLDER_NAME)
        trash_preview_dir = os.path.join(TRASH_ROOT, PREVIEW_SUBFOLDER_NAME)
        os.makedirs(trash_thumbnail_dir, exist_ok=True)
        os.makedirs(trash_preview_dir, exist_ok=True)

        shutil.move(original_full_path, trash_full_path)

        original_thumbnail_full_path = _get_thumbnail_full_path(original_full_path)
        trashed_thumbnail_relative_path = None
        if os.path.isfile(original_thumbnail_full_path):
            thumb_name, thumb_ext = os.path.splitext(os.path.basename(original_thumbnail_full_path))
            trashed_thumb_filename = f"{thumb_name}_{timestamp}_{unique_id}{thumb_ext}"
            trashed_thumb_full_path = os.path.join(trash_thumbnail_dir, trashed_thumb_filename)
            shutil.move(original_thumbnail_full_path, trashed_thumb_full_path)
            trashed_thumbnail_relative_path = os.path.relpath(trashed_thumb_full_path, image_library_root).replace('\\', '/')
            
            thumb_dir = os.path.dirname(original_thumbnail_full_path)
            if os.path.exists(thumb_dir) and not os.listdir(thumb_dir):
                os.rmdir(thumb_dir)

        original_preview_full_path = _get_preview_full_path(original_full_path)
        trashed_preview_relative_path = None
        if os.path.isfile(original_preview_full_path):
            preview_base_name, preview_ext = os.path.splitext(os.path.basename(original_preview_full_path))
            trashed_preview_filename = f"{preview_base_name}_{timestamp}_{unique_id}{preview_ext}"
            trashed_preview_full_path = os.path.join(trash_preview_dir, trashed_preview_filename)
            shutil.move(original_preview_full_path, trashed_preview_full_path)
            trashed_preview_relative_path = os.path.relpath(trashed_preview_full_path, image_library_root).replace('\\', '/')

            preview_dir = os.path.dirname(original_preview_full_path)
            if os.path.exists(preview_dir) and not os.listdir(preview_dir):
                os.rmdir(preview_dir)

        metadata = {
            'original_path': file_relative_path,
            'trashed_at': datetime.now().isoformat(),
            'trashed_as': trash_filename
        }
        if trashed_thumbnail_relative_path:
            metadata['trashed_thumbnail_path'] = trashed_thumbnail_relative_path
        if trashed_preview_relative_path:
            metadata['trashed_preview_path'] = trashed_preview_relative_path

        metadata_file_path = f"{trash_full_path}.meta"
        with open(metadata_file_path, 'w') as f:
            json.dump(metadata, f, indent=4)

        _update_folder_item_count_meta(os.path.dirname(original_full_path))
        _update_folder_item_count_meta(TRASH_ROOT)

        return jsonify({"message": "File moved to trash successfully"})
    except Exception as e:
        print(f"ERROR: Error moving file to trash: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete_file_forever', methods=['DELETE'])
@auth.login_required # MODIFIED: Add authentication decorator
def delete_file_forever():
    """Permanently deletes a file from TRASH_ROOT, along with its metadata, thumbnail, and preview."""
    data = request.get_json()
    file_relative_path_in_trash = data.get('path')

    if not file_relative_path_in_trash:
        return jsonify({"error": "Path not provided"}), 400

    full_path_in_trash = os.path.abspath(os.path.join(image_library_root, file_relative_path_in_trash))

    if not full_path_in_trash.startswith(TRASH_ROOT):
        return jsonify({"error": "Forbidden: Attempted to delete file outside of trash folder."}), 403

    if not os.path.exists(full_path_in_trash):
        return jsonify({"error": "File not found in trash"}), 404

    try:
        metadata_file_path = f"{full_path_in_trash}.meta"
        trashed_thumbnail_path = None
        trashed_preview_path = None
        if os.path.exists(metadata_file_path):
            try:
                with open(metadata_file_path, 'r') as f:
                    metadata = json.load(f)
                trashed_thumbnail_path = metadata.get('trashed_thumbnail_path')
                trashed_preview_path = metadata.get('trashed_preview_path')
            except Exception as e:
                print(f"Warning: Could not read metadata for {full_path_in_trash} to find associated files: {e}")

        os.remove(full_path_in_trash)

        if os.path.exists(metadata_file_path):
            os.remove(metadata_file_path)

        if trashed_thumbnail_path:
            full_trashed_thumbnail_path = os.path.abspath(os.path.join(image_library_root, trashed_thumbnail_path))
            if os.path.exists(full_trashed_thumbnail_path) and full_trashed_thumbnail_path.startswith(TRASH_ROOT):
                os.remove(full_trashed_thumbnail_path)

        if trashed_preview_path:
            full_trashed_preview_path = os.path.abspath(os.path.join(image_library_root, trashed_preview_path))
            if os.path.exists(full_trashed_preview_path) and full_trashed_preview_path.startswith(TRASH_ROOT):
                os.remove(full_trashed_preview_path)

        _update_folder_item_count_meta(TRASH_ROOT)

        return jsonify({"message": "File permanently deleted"})
    except Exception as e:
        print(f"ERROR: Error permanently deleting file: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

def _restore_associated_file(final_restore_path, trashed_associated_path, path_generator_func):
    """
    Helper to restore an associated file (thumbnail or preview).
    """
    if trashed_associated_path:
        full_trashed_associated_path = os.path.abspath(os.path.join(image_library_root, trashed_associated_path))
        if os.path.exists(full_trashed_associated_path) and full_trashed_associated_path.startswith(TRASH_ROOT):
            expected_new_path = path_generator_func(final_restore_path)
            os.makedirs(os.path.dirname(expected_new_path), exist_ok=True)
            shutil.move(full_trashed_associated_path, expected_new_path)

@app.route('/api/restore_file', methods=['POST'])
@auth.login_required # MODIFIED: Add authentication decorator
def restore_file():
    """Restores a file from TRASH_ROOT to its original location, and updates counts."""
    data = request.get_json()
    file_relative_path_in_trash = data.get('path')

    if not file_relative_path_in_trash:
        return jsonify({"error": "Path not provided"}), 400

    try:
        final_restore_path = restore_file_logic(file_relative_path_in_trash)
        _update_folder_item_count_meta(TRASH_ROOT)
        _update_folder_item_count_meta(os.path.dirname(final_restore_path))
        return jsonify({"message": "File restored successfully"})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"ERROR: Error restoring file: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create_folder', methods=['POST'])
@auth.login_required # MODIFIED: Add authentication decorator
def create_folder():
    """Creates a new folder at the specified parent path."""
    data = request.get_json()
    parent_path_segments = data.get('parent_path', [])
    folder_name = data.get('folder_name')

    if not folder_name:
        return jsonify({"error": "Folder name not provided"}), 400

    safe_folder_name = secure_filename(folder_name)
    if not safe_folder_name:
        return jsonify({"error": "Invalid folder name"}), 400

    full_parent_path = os.path.abspath(os.path.join(image_library_root, *parent_path_segments))
    new_folder_full_path = os.path.join(full_parent_path, safe_folder_name)

    if not new_folder_full_path.startswith(image_library_root) or TRASH_ROOT in new_folder_full_path:
        return jsonify({"error": "Forbidden: Cannot create folders outside media root or inside trash."}), 403

    if os.path.exists(new_folder_full_path):
        return jsonify({"error": f"Folder '{safe_folder_name}' already exists."}), 409

    try:
        os.makedirs(new_folder_full_path)
        if parent_path_segments:
            _update_folder_item_count_meta(full_parent_path)

        location_message = os.path.join(*parent_path_segments) if parent_path_segments else 'root'
        return jsonify({"message": f"Folder '{safe_folder_name}' created successfully at '{location_message}'."}), 201
    except Exception as e:
        print(f"ERROR: Error creating folder: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload_file', methods=['POST'])
@auth.login_required # MODIFIED: Add authentication decorator
def upload_file():
    """Handles file uploads to the appropriate dated folder."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    current_path_json = request.form.get('current_path', '[]')
    try:
        current_path_segments = json.loads(current_path_json)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid current_path format"}), 400

    destination_dir = os.path.join(image_library_root, *current_path_segments)
    os.makedirs(destination_dir, exist_ok=True)
    file_full_path = os.path.join(destination_dir, file.filename)

    counter = 1
    original_name, ext = os.path.splitext(file.filename)
    while os.path.exists(file_full_path):
        file_full_path = os.path.join(destination_dir, f"{original_name}_{counter}{ext}")
        counter += 1

    try:
        file.save(file_full_path)
        if os.path.splitext(file.filename)[1].lower() in ALLOWED_IMAGE_EXTENSIONS or \
           os.path.splitext(file.filename)[1].lower() in ALLOWED_RAW_EXTENSIONS:
            _generate_thumbnail(file_full_path)

        _update_folder_item_count_meta(destination_dir)

        final_destination_relative_path = os.path.relpath(os.path.dirname(file_full_path), image_library_root)
        return jsonify({"message": f"File '{os.path.basename(file_full_path)}' uploaded successfully to '{final_destination_relative_path}'"}), 200
    except Exception as e:
        print(f"ERROR: Error saving file during upload: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete_folder', methods=['POST'])
@auth.login_required # MODIFIED: Add authentication decorator
def delete_folder():
    """Moves an entire folder and its contents to the trash folder."""
    data = request.get_json()
    path_data = data.get('path')

    if not path_data:
        return jsonify({"error": "Folder path not provided"}), 400

    if isinstance(path_data, str):
        folder_path_segments = path_data.split('/')
    elif isinstance(path_data, list):
        folder_path_segments = path_data
    else:
        print(f"ERROR: Invalid path data type for delete_folder: {type(path_data)}")
        return jsonify({"error": "Invalid path format provided"}), 400

    folder_full_path = os.path.abspath(os.path.join(image_library_root, *folder_path_segments))

    if not folder_full_path.startswith(image_library_root) or TRASH_ROOT in folder_full_path:
        return jsonify({"error": "Forbidden: Cannot delete root media directory, trash folder, or outside media root."}), 403

    if not os.path.isdir(folder_full_path):
        return jsonify({"error": "Folder not found"}), 404

    try:
        files_to_trash = _get_media_files_in_directory(folder_full_path, include_subfolders=True)
        for file_info in files_to_trash:
            original_relative_path = file_info['original_path']
            original_file_full_path = os.path.abspath(os.path.join(image_library_root, original_relative_path))

            filename = os.path.basename(original_file_full_path)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_id = os.urandom(4).hex()
            name, ext = os.path.splitext(filename)
            trash_filename = f"{name}_{timestamp}_{unique_id}{ext}"
            trash_full_path = os.path.join(TRASH_ROOT, trash_filename)

            shutil.move(original_file_full_path, trash_full_path)

            original_thumbnail_full_path = _get_thumbnail_full_path(original_file_full_path)
            trashed_thumbnail_relative_path = None
            if os.path.isfile(original_thumbnail_full_path):
                thumb_name, thumb_ext = os.path.splitext(os.path.basename(original_thumbnail_full_path))
                trashed_thumb_filename = f"{thumb_name}_{timestamp}_{unique_id}{thumb_ext}"
                trashed_thumb_full_path = os.path.join(TRASH_ROOT, trashed_thumb_filename)
                shutil.move(original_thumbnail_full_path, trashed_thumb_full_path)
                trashed_thumbnail_relative_path = os.path.relpath(trashed_thumb_full_path, image_library_root).replace('\\', '/')

            original_preview_full_path = _get_preview_full_path(original_file_full_path)
            trashed_preview_relative_path = None
            if os.path.isfile(original_preview_full_path):
                preview_name, preview_ext = os.path.splitext(os.path.basename(original_preview_full_path))
                trashed_preview_filename = f"{preview_name}_{timestamp}_{unique_id}{preview_ext}"
                trashed_preview_full_path = os.path.join(TRASH_ROOT, trashed_preview_filename)
                shutil.move(original_preview_full_path, trashed_preview_full_path)
                trashed_preview_relative_path = os.path.relpath(trashed_preview_full_path, image_library_root).replace('\\', '/')

            metadata = {
                'original_path': original_relative_path,
                'trashed_at': datetime.now().isoformat(),
                'trashed_as': trash_filename
            }
            if trashed_thumbnail_relative_path:
                metadata['trashed_thumbnail_path'] = trashed_thumbnail_relative_path
            if trashed_preview_relative_path:
                metadata['trashed_preview_path'] = trashed_preview_relative_path

            metadata_file_path = f"{trash_full_path}.meta"
            with open(metadata_file_path, 'w') as f:
                json.dump(metadata, f, indent=4)

        shutil.rmtree(folder_full_path)

        parent_folder_full_path = os.path.dirname(folder_full_path)
        if parent_folder_full_path.startswith(image_library_root):
            _update_folder_item_count_meta(parent_folder_full_path)
        _update_folder_item_count_meta(TRASH_ROOT)

        return jsonify({"message": f"Folder '{'/'.join(folder_path_segments)}' and its contents moved to trash."})
    except Exception as e:
        print(f"ERROR: Error deleting folder: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/empty_trash', methods=['POST'])
@auth.login_required # MODIFIED: Add authentication decorator
def empty_trash():
    """Permanently deletes all files and folders within the trash directory."""
    try:
        for item in os.listdir(TRASH_ROOT):
            full_path = os.path.join(TRASH_ROOT, item)
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
        _update_folder_item_count_meta(TRASH_ROOT)
        return jsonify({"message": "Trash emptied successfully."})
    except Exception as e:
        print(f"ERROR: Error emptying trash: {e}")
        return jsonify({"error": "Failed to empty trash."}), 500

@app.route('/api/restore_all', methods=['POST'])
@auth.login_required # MODIFIED: Add authentication decorator
def restore_all():
    """Restores all files from the trash to their original locations."""
    try:
        parent_folders_to_update = set()
        for filename in os.listdir(TRASH_ROOT):
            if filename.endswith('.meta'):
                continue

            source_full_path = os.path.join(TRASH_ROOT, filename)
            if os.path.isfile(source_full_path):
                relative_path_in_trash = os.path.join(TRASH_FOLDER_NAME, filename)
                final_restore_path = restore_file_logic(relative_path_in_trash)
                parent_folders_to_update.add(os.path.dirname(final_restore_path))

        for folder in parent_folders_to_update:
            _update_folder_item_count_meta(folder)
        _update_folder_item_count_meta(TRASH_ROOT)
        return jsonify({"message": "All files have been restored."})
    except Exception as e:
        print(f"ERROR: Error during restore all: {e}")
        return jsonify({"error": "An error occurred during the restore all process."}), 500

@app.route('/api/delete_multiple', methods=['POST'])
@auth.login_required # MODIFIED: Add authentication decorator
def delete_multiple():
    """Moves multiple files to the trash, or deletes them permanently from the trash."""
    data = request.get_json()
    paths = data.get('paths', [])
    is_permanent = data.get('is_permanent', False)

    if not paths:
        return jsonify({"error": "No paths provided"}), 400

    success_count = 0
    fail_count = 0
    parent_folders_to_update = set()

    for path in paths:
        try:
            if is_permanent:
                full_path = os.path.abspath(os.path.join(image_library_root, path))
                if not full_path.startswith(TRASH_ROOT) or not os.path.exists(full_path):
                    raise ValueError("File is not in trash or does not exist.")

                metadata_file_path = f"{full_path}.meta"
                trashed_thumbnail_path = None
                trashed_preview_path = None
                if os.path.exists(metadata_file_path):
                    with open(metadata_file_path, 'r') as f:
                        metadata = json.load(f)
                    trashed_thumbnail_path = metadata.get('trashed_thumbnail_path')
                    trashed_preview_path = metadata.get('trashed_preview_path')
                    if trashed_thumbnail_path:
                        thumb_full_path = os.path.join(image_library_root, trashed_thumbnail_path)
                        if os.path.exists(thumb_full_path): os.remove(thumb_full_path)
                    if trashed_preview_path:
                        preview_full_path = os.path.join(image_library_root, trashed_preview_path)
                        if os.path.exists(preview_full_path): os.remove(preview_full_path)
                    os.remove(metadata_file_path)
                os.remove(full_path)

            else:
                original_full_path = os.path.abspath(os.path.join(image_library_root, path))
                if not original_full_path.startswith(image_library_root) or not os.path.exists(original_full_path):
                    raise ValueError("File is not in media library or does not exist.")

                move_to_trash_logic(path)
                parent_folders_to_update.add(os.path.dirname(original_full_path))
            success_count += 1
        except Exception as e:
            print(f"Failed to process '{path}': {e}")
            fail_count += 1

    for folder in parent_folders_to_update:
        _update_folder_item_count_meta(folder)

    _update_folder_item_count_meta(TRASH_ROOT)

    return jsonify({
        "message": f"Operation complete. Succeeded: {success_count}, Failed: {fail_count}",
        "success_count": success_count,
        "fail_count": fail_count
    })

@app.route('/api/restore_multiple', methods=['POST'])
@auth.login_required # MODIFIED: Add authentication decorator
def restore_multiple():
    """Restores multiple files from the trash."""
    data = request.get_json()
    paths = data.get('paths', [])

    if not paths:
        return jsonify({"error": "No paths provided"}), 400

    success_count = 0
    fail_count = 0
    parent_folders_to_update = set()

    for path in paths:
        try:
            source_full_path = os.path.abspath(os.path.join(image_library_root, path))
            if not source_full_path.startswith(TRASH_ROOT):
                raise ValueError(f"File '{path}' is not in the trash folder.")

            final_restore_path = restore_file_logic(path)
            parent_folders_to_update.add(os.path.dirname(final_restore_path))
            success_count += 1
        except Exception as e:
            print(f"ERROR: Failed to restore '{path}': {e}")
            fail_count += 1

    for folder in parent_folders_to_update:
        _update_folder_item_count_meta(folder)
    _update_folder_item_count_meta(TRASH_ROOT)

    return jsonify({
        "message": f"Operation complete. Restored: {success_count}, Failed: {fail_count}",
        "success_count": success_count,
        "fail_count": fail_count
    })


def move_to_trash_logic(file_relative_path):
    """Refactored logic to move a single file to trash, to be reusable."""
    original_full_path = os.path.abspath(os.path.join(image_library_root, file_relative_path))

    filename = os.path.basename(original_full_path)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = os.urandom(4).hex()
    name, ext = os.path.splitext(filename)
    trash_filename = f"{name}_{timestamp}_{unique_id}{ext}"
    trash_full_path = os.path.join(TRASH_ROOT, trash_filename)

    metadata = {
        'original_path': file_relative_path,
        'trashed_at': datetime.now().isoformat(),
        'trashed_as': trash_filename
    }

    original_thumbnail_full_path = _get_thumbnail_full_path(original_full_path)
    if os.path.isfile(original_thumbnail_full_path):
        thumb_name, thumb_ext = os.path.splitext(os.path.basename(original_thumbnail_full_path))
        trashed_thumb_filename = f"{thumb_name}_{timestamp}_{unique_id}{thumb_ext}"
        trashed_thumb_full_path = os.path.join(TRASH_ROOT, THUMBNAIL_SUBFOLDER_NAME, trashed_thumb_filename)
        os.makedirs(os.path.dirname(trashed_thumb_full_path), exist_ok=True)
        shutil.move(original_thumbnail_full_path, trashed_thumb_full_path)
        metadata['trashed_thumbnail_path'] = os.path.relpath(trashed_thumb_full_path, image_library_root).replace('\\','/')

    original_preview_full_path = _get_preview_full_path(original_full_path)
    if os.path.isfile(original_preview_full_path):
        preview_name, preview_ext = os.path.splitext(os.path.basename(original_preview_full_path))
        trashed_preview_filename = f"{preview_name}_{timestamp}_{unique_id}{preview_ext}"
        trashed_preview_full_path = os.path.join(TRASH_ROOT, PREVIEW_SUBFOLDER_NAME, trashed_preview_filename)
        os.makedirs(os.path.dirname(trashed_preview_full_path), exist_ok=True)
        shutil.move(original_preview_full_path, trashed_preview_full_path)
        metadata['trashed_preview_path'] = os.path.relpath(trashed_preview_full_path, image_library_root).replace('\\','/')

    shutil.move(original_full_path, trash_full_path)
    metadata_file_path = f"{trash_full_path}.meta"
    with open(metadata_file_path, 'w') as f:
        json.dump(metadata, f, indent=4)


def restore_file_logic(file_relative_path_in_trash):
    """
    Logic to restore a single file, refactored to be reusable.
    This function does NOT update folder counts. The caller is responsible.
    Returns the final path of the restored file.
    """
    source_full_path_in_trash = os.path.abspath(os.path.join(image_library_root, file_relative_path_in_trash))
    if not source_full_path_in_trash.startswith(TRASH_ROOT):
        raise ValueError("Forbidden: Attempted to restore file outside of trash folder.")

    if not os.path.exists(source_full_path_in_trash):
        raise FileNotFoundError(f"File not found in trash: {source_full_path_in_trash}")

    metadata_file_path = f"{source_full_path_in_trash}.meta"
    if not os.path.exists(metadata_file_path):
        raise FileNotFoundError(f"Metadata for file not found: {metadata_file_path}. Cannot restore.")

    with open(metadata_file_path, 'r') as f:
        metadata = json.load(f)
    original_relative_path = metadata.get('original_path')
    trashed_thumbnail_path = metadata.get('trashed_thumbnail_path')
    trashed_preview_path = metadata.get('trashed_preview_path')

    if not original_relative_path:
        raise ValueError("Original path not found in metadata.")

    original_full_path = os.path.abspath(os.path.join(image_library_root, original_relative_path))
    original_directory = os.path.dirname(original_full_path)
    os.makedirs(original_directory, exist_ok=True)

    final_restore_path = original_full_path
    if os.path.exists(original_full_path):
        base_name, ext = os.path.splitext(original_relative_path)
        timestamp = datetime.now().strftime("_%Y%m%d%H%M%S")
        dir_name = os.path.dirname(original_relative_path)
        new_filename = f"{os.path.basename(base_name)}{timestamp}{ext}"
        final_restore_path = os.path.abspath(os.path.join(image_library_root, dir_name, new_filename))

    _restore_associated_file(final_restore_path, trashed_thumbnail_path, _get_thumbnail_full_path)
    _restore_associated_file(final_restore_path, trashed_preview_path, _get_preview_full_path)

    shutil.move(source_full_path_in_trash, final_restore_path)
    os.remove(metadata_file_path)

    return final_restore_path


if __name__ == '__main__':
    _initial_scan_and_populate_counts()
    app.run(host='0.0.0.0', debug=True, port=PORT)



# To run with SSL for local dev (you need to generate two pem files in the server.py directory)
    #app.run(host='0.0.0.0', debug=True, port=PORT, ssl_context=('cert.pem', 'key.pem'))
