import os
import json
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response # Import Response for direct image serving
from werkzeug.utils import secure_filename
from PIL import Image, ExifTags, __version__ as pillow_version # Import Pillow for image processing, and get its version
import rawpy # For RAW image processing
import cv2 # MODIFIED: Added OpenCV for video processing
import numpy as np # For rawpy output and OpenCV frame handling
try:
    # While pillow_heif handles HEIC via Image.open(), imageio.v3 might be useful for other video/image formats
    # or if pillow_heif encounters issues. Keeping it as an optional import.
    import imageio.v3 as iio 
    print("DEBUG: imageio.v3 imported successfully.")
except ImportError as e:
    print(f"Warning: 'imageio.v3' could not be imported ({e}). HEIC/other processing might be limited if pillow_heif fails.")
    iio = None # Set iio to None if import fails
import io # For in-memory image handling
from pillow_heif import register_heif_opener # Import register_heif_opener for HEIC support

# Register the HEIF opener for Pillow. This allows Pillow's Image.open() to handle HEIC files.
register_heif_opener()
print("DEBUG: pillow_heif.register_heif_opener() called.")


app = Flask(__name__)

# --- Configuration ---
# IMPORTANT: Set this to the ABSOLUTE path of your main photo library folder.
# Example: If your photos are in '/Users/YourUser/Pictures/MyGallery', set BASE_DIR to that.
image_library_root = os.path.abspath('/Volumes/aa3025_bkp/Photos_Backup') # User should update this!

TRASH_FOLDER_NAME = '_Trash' # Must match frontend
TRASH_ROOT = os.path.join(image_library_root, TRASH_FOLDER_NAME) # Absolute path to trash

COUNT_META_FILENAME = '_count.meta' # Stores item counts for folders

# Thumbnail and Preview configuration
THUMBNAIL_SUBFOLDER_NAME = '.thumbnails' # Hidden directory for thumbnails within media folders
PREVIEW_SUBFOLDER_NAME = '.previews' # Hidden directory for full-size previews within media folders
THUMBNAIL_MAX_DIMENSION = 480 # Max width or height for thumbnails
# PREVIEW_MAX_DIMENSION = 1920 # Removed as per previous request to serve full-size previews, but good to keep in mind for future scaling

# Determine the resampling filter based on Pillow version
try:
    if tuple(map(int, pillow_version.split('.'))) >= (9, 1, 0):
        RESAMPLING_FILTER = Image.Resampling.LANCZOS
        print(f"DEBUG: Using Image.Resampling.LANCZOS (Pillow >= 9.1.0)")
    else:
        RESAMPLING_FILTER = Image.LANCZOS
        print(f"DEBUG: Using Image.LANCZOS (Pillow < 9.1.0)")
except AttributeError:
    RESAMPLING_FILTER = Image.LANCZOS
    print(f"DEBUG: AttributeError for Image.Resampling, falling back to Image.LANCZOS.")
except Exception as e:
    RESAMPLING_FILTER = Image.LANCZOS
    print(f"DEBUG: Error determining resampling filter ({e}), falling back to Image.LANCZOS.")


# Allowed extensions for upload and processing - CORRECTED TO INCLUDE LEADING DOTS
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.avif'}
ALLOWED_RAW_EXTENSIONS = {'.nef', '.nrw', '.cr2', '.cr3', '.crw', '.arw', '.srf', '.sr2',
                          '.orf', '.raf', '.rw2', '.raw', '.dng', '.kdc', '.dcr', '.erf',
                          '.3fr', '.mef', '.pef', '.x3f'}
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.webm', '.ogg', '.avi', '.mkv'}
ALL_MEDIA_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_RAW_EXTENSIONS).union(ALLOWED_VIDEO_EXTENSIONS)

# Ensure directories exist
os.makedirs(image_library_root, exist_ok=True)
os.makedirs(TRASH_ROOT, exist_ok=True)


# --- Helper Functions (from gallery-server, adapted) ---

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
        # print(f"Updated count for '{os.path.basename(folder_path)}': {count}")
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
        print(f"Scanning and updating count for: {root}")
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
    print(f"DEBUG: _get_thumbnail_full_path for '{original_full_path}' -> '{os.path.join(thumbnail_dir, thumbnail_filename)}'")
    return os.path.join(thumbnail_dir, thumbnail_filename)

def _generate_thumbnail(original_full_path):
    """Generates a thumbnail for an image, RAW, or video file and saves it."""
    thumbnail_path = _get_thumbnail_full_path(original_full_path)
    print(f"DEBUG: _generate_thumbnail called for '{original_full_path}'. Target: '{thumbnail_path}'")

    # Check if thumbnail already exists and is up-to-date
    if os.path.exists(thumbnail_path) and os.path.getmtime(thumbnail_path) >= os.path.getmtime(original_full_path):
        print(f"DEBUG: Thumbnail for '{original_full_path}' already exists and is up-to-date.")
        return thumbnail_path # Thumbnail is current, no need to regenerate

    os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True) # Ensure thumbnail dir exists

    try:
        file_extension = os.path.splitext(original_full_path)[1].lower()
        print(f"DEBUG: Inside _generate_thumbnail. File: '{original_full_path}', Ext: '{file_extension}'")
        img = None

        if is_video_file(original_full_path):
            print(f"DEBUG: Processing VIDEO thumbnail for {original_full_path} using OpenCV.")
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
            print(f"DEBUG: Processing RAW thumbnail for {original_full_path} using rawpy.")
            try:
                print(f"DEBUG: Attempting rawpy.imread for {original_full_path}")
                with rawpy.imread(original_full_path) as raw:
                    print(f"DEBUG: rawpy.imread successful. Attempting raw.postprocess for {original_full_path}")
                    rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
                    if not isinstance(rgb, np.ndarray):
                        print(f"ERROR: rawpy.postprocess did not return a numpy array for {original_full_path}. Type: {type(rgb)}")
                        img = None
                    else:
                        print(f"DEBUG: rawpy.postprocess successful. Converting rawpy output to Pillow Image for {original_full_path}")
                        img = Image.fromarray(rgb)
            except rawpy.LibRawError as raw_e:
                print(f"ERROR: rawpy.LibRawError processing RAW thumbnail for {original_full_path}: {raw_e}")
                img = None # Ensure img is None if rawpy fails
            except Exception as raw_e:
                print(f"ERROR: General error processing RAW thumbnail for {original_full_path} with rawpy: {type(raw_e).__name__}: {raw_e}")
                img = None # Ensure img is None if rawpy fails
        elif file_extension in ALLOWED_IMAGE_EXTENSIONS: # Covers HEIC, JPG, PNG, etc.
            print(f"DEBUG: Processing standard image (including HEIC) thumbnail for {original_full_path} using Pillow.Image.open().")
            try:
                img = Image.open(original_full_path)
            except Exception as pillow_e:
                print(f"ERROR: Pillow failed to open standard image {original_full_path}: {type(pillow_e).__name__}: {pillow_e}")
                img = None # Ensure img is None if Pillow fails
        else:
            print(f"DEBUG: Not a supported image format for thumbnail generation: {original_full_path}")
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
                        print(f"DEBUG: EXIF Orientation found: {orientation} for {original_full_path}")
                        if orientation == 3: img = img.transpose(Image.ROTATE_180)
                        elif orientation == 6: img = img.transpose(Image.ROTATE_270)
                        elif orientation == 8: img = img.transpose(Image.ROTATE_90)
        except Exception as e:
            print(f"ERROR: Error applying EXIF orientation for {original_full_path}: {e}")

        if img.mode in ('RGBA', 'LA', 'P') or img.mode == 'L':
            print(f"DEBUG: Converting image mode from {img.mode} to RGB for {original_full_path}")
            img = img.convert('RGB')
        
        print(f"DEBUG: Resizing image to thumbnail dimensions ({THUMBNAIL_MAX_DIMENSION}x{THUMBNAIL_MAX_DIMENSION}) for {original_full_path}")
        img.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION), RESAMPLING_FILTER)
        
        print(f"DEBUG: Saving thumbnail to {thumbnail_path} (WEBP format) for {original_full_path}")
        img.save(thumbnail_path, "WEBP", quality=85)
        print(f"DEBUG: Thumbnail successfully saved to: {thumbnail_path}")
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
    print(f"DEBUG: _get_preview_full_path for '{original_full_path}' -> '{os.path.join(preview_dir, preview_filename)}'")
    return os.path.join(preview_dir, preview_filename)

def _generate_preview(original_full_path):
    """Generates a full-size preview for an image (including HEIC) or RAW file and saves it."""
    preview_path = _get_preview_full_path(original_full_path)
    print(f"DEBUG: _generate_preview called for '{original_full_path}'. Target: '{preview_path}'")
    os.makedirs(os.path.dirname(preview_path), exist_ok=True) # Ensure preview dir exists

    if os.path.exists(preview_path) and os.path.getmtime(preview_path) >= os.path.getmtime(original_full_path):
        print(f"DEBUG: Preview for '{original_full_path}' already exists and is up-to-date.")
        return preview_path

    try:
        file_extension = os.path.splitext(original_full_path)[1].lower()
        print(f"DEBUG: Inside _generate_preview. File: '{original_full_path}', Ext: '{file_extension}'")
        print(f"DEBUG: Is RAW? {file_extension in ALLOWED_RAW_EXTENSIONS}. Is HEIC? {file_extension == '.heic'}")
        img = None

        if file_extension in ALLOWED_RAW_EXTENSIONS:
            print(f"DEBUG: Processing RAW preview for {original_full_path} using rawpy.")
            try:
                print(f"DEBUG: Attempting rawpy.imread for {original_full_path}")
                with rawpy.imread(original_full_path) as raw:
                    print(f"DEBUG: rawpy.imread successful. Attempting raw.postprocess for {original_full_path}")
                    rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8, gamma=(2.222, 4.5))
                    if not isinstance(rgb, np.ndarray):
                        print(f"ERROR: rawpy.postprocess did not return a numpy array for {original_full_path}. Type: {type(rgb)}")
                        img = None
                    else:
                        print(f"DEBUG: rawpy.postprocess successful. Converting rawpy output to Pillow Image for {original_full_path}")
                        img = Image.fromarray(rgb)
            except rawpy.LibRawError as raw_e:
                print(f"ERROR: rawpy.LibRawError processing RAW preview for {original_full_path}: {raw_e}")
                img = None # Ensure img is None if rawpy fails
            except Exception as raw_e:
                print(f"ERROR: General error processing RAW preview for {original_full_path} with rawpy: {type(raw_e).__name__}: {raw_e}")
                img = None # Ensure img is None if rawpy fails
        elif file_extension in ALLOWED_IMAGE_EXTENSIONS: # Covers HEIC, JPG, PNG, etc.
            print(f"DEBUG: Processing standard image (including HEIC) preview for {original_full_path} using Pillow.Image.open().")
            try:
                img = Image.open(original_full_path)
            except Exception as pillow_e:
                print(f"ERROR: Pillow failed to open standard image {original_full_path}: {type(pillow_e).__name__}: {pillow_e}")
                img = None # Ensure img is None if Pillow fails
        else:
            print(f"DEBUG: Not a supported image format for preview generation: {original_full_path}")
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
                        print(f"DEBUG: EXIF Orientation found for preview: {orientation} for {original_full_path}")
                        if orientation == 3: img = img.transpose(Image.ROTATE_180)
                        elif orientation == 6: img = img.transpose(Image.ROTATE_270)
                        elif orientation == 8: img = img.transpose(Image.ROTATE_90)
        except Exception as e:
            print(f"ERROR: Error applying EXIF orientation for preview {original_full_path}: {e}")

        if img.mode in ('RGBA', 'LA', 'P') or img.mode == 'L':
            print(f"DEBUG: Converting image mode from {img.mode} to RGB for preview {original_full_path}")
            img = img.convert('RGB')
        
        print(f"DEBUG: Saving preview to {preview_path} (WEBP format) for {original_full_path}")
        img.save(preview_path, "WEBP", quality=85)
        print(f"DEBUG: Preview successfully saved to: {preview_path}")
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
        print(f"DEBUG: _get_media_files_in_directory: Path '{path}' is not a directory.")
        return []

    # Determine the base path for relative paths
    base_relative_path_for_root = os.path.relpath(path, image_library_root)
    if base_relative_path_for_root == '.':
        base_relative_path_for_root = ''
    print(f"DEBUG: _get_media_files_in_directory: base_relative_path_for_root='{base_relative_path_for_root}'")

    walk_iterator = os.walk(path) if include_subfolders else [(path, [], os.listdir(path))]

    for root, dirs, files in walk_iterator:
        # Exclude hidden directories from traversal if walking
        if include_subfolders:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            print(f"DEBUG: _get_media_files_in_directory: Filtered dirs: {dirs}")

        current_relative_root_part = os.path.relpath(root, image_library_root)
        if current_relative_root_part == '.':
            current_relative_root_part = ''
        print(f"DEBUG: _get_media_files_in_directory: current_relative_root_part='{current_relative_root_part}'")
        
        # Skip trash content if not explicitly in trash root
        if TRASH_FOLDER_NAME in current_relative_root_part.split(os.sep) and root != TRASH_ROOT:
            print(f"DEBUG: _get_media_files_in_directory: Skipping trash content in '{root}'")
            continue

        for file in files:
            if allowed_file(file) and not file.startswith('.') and not file.endswith('.meta'):
                full_file_path = os.path.join(root, file)
                relative_file_path = os.path.relpath(full_file_path, image_library_root).replace('\\', '/')
                print(f"DEBUG: _get_media_files_in_directory: Found file '{file}', relative_path='{relative_file_path}'")
                
                file_info = {
                    'filename': file,
                    'original_path': relative_file_path,
                    'type': get_media_type(file)
                }

                if is_video_file(file):
                    file_info['thumbnail_path'] = relative_file_path # Use video itself as thumbnail
                    print(f"DEBUG: _get_media_files_in_directory: Video thumbnail path set to original path.")
                else: # Image or RAW
                    thumbnail_full_path = _get_thumbnail_full_path(full_file_path)
                    thumbnail_relative_path = os.path.relpath(thumbnail_full_path, image_library_root).replace('\\', '/')
                    file_info['thumbnail_path'] = thumbnail_relative_path
                    print(f"DEBUG: _get_media_files_in_directory: Image/RAW thumbnail path set to '{thumbnail_relative_path}'.")
                
                media_files.append(file_info)
    print(f"DEBUG: _get_media_files_in_directory: Returning {len(media_files)} media files.")
    return sorted(media_files, key=lambda x: x['original_path'].lower())


# --- API Endpoints ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    print("DEBUG: '/' endpoint called.")
    return send_from_directory('.', 'index.html')

# MODIFIED: Unified endpoint for browsing folders
@app.route('/api/folders', defaults={'path': ''})
@app.route('/api/folders/<path:path>')
def get_folders(path):
    """Returns a list of subfolders and files for a given path."""
    print(f"DEBUG: '/api/folders/{path}' endpoint called.")
    
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

    # Custom sorting for months
    month_map = {name: i for i, name in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])}
    folders_data.sort(key=lambda x: month_map.get(x['name'], x['name']))

    return jsonify({"folders": folders_data, "files": files_in_folder})


@app.route('/api/media/<path:relative_path>')
def get_media(relative_path):
    """Serves media files (images, videos, converted RAW/HEIC for display)."""
    print(f"DEBUG: '/api/media/{relative_path}' endpoint called.")
    full_path = os.path.abspath(os.path.join(image_library_root, relative_path))
    print(f"DEBUG: get_media - full_path: '{full_path}'")
    
    if not full_path.startswith(image_library_root):
        print(f"DEBUG: Forbidden media access attempt: {full_path}")
        return jsonify({"error": "Forbidden"}), 403

    if not os.path.exists(full_path):
        print(f"DEBUG: Media not found: {full_path}")
        return jsonify({"error": "Media not found"}), 404

    filename = os.path.basename(full_path)
    ext = os.path.splitext(filename)[1].lower() # Get extension with leading dot

    if ext in ALLOWED_RAW_EXTENSIONS:
        print(f"DEBUG: get_media - Serving RAW file: {filename}")
        try:
            preview_path = _generate_preview(full_path)
            if preview_path and os.path.exists(preview_path):
                print(f"DEBUG: get_media - Serving generated RAW preview: {preview_path}")
                return send_from_directory(os.path.dirname(preview_path), os.path.basename(preview_path), mimetype='image/webp')
            else:
                print(f"ERROR: get_media - Failed to generate RAW preview for {full_path}")
                return jsonify({"error": "Failed to generate RAW preview"}), 500
        except Exception as e:
            print(f"ERROR: get_media - Error processing RAW file {full_path}: {type(e).__name__}: {e}")
            return jsonify({"error": "Failed to process RAW file for display"}), 500
    elif ext == '.heic': # Explicitly check for .heic
        print(f"DEBUG: get_media - Serving HEIC file: {filename}")
        try:
            preview_path = _generate_preview(full_path) # _generate_preview now uses Image.open() for HEIC
            if preview_path and os.path.exists(preview_path):
                print(f"DEBUG: get_media - Serving generated HEIC preview: {preview_path}")
                return send_from_directory(os.path.dirname(preview_path), os.path.basename(preview_path), mimetype='image/webp')
            else:
                print(f"ERROR: get_media - Failed to generate HEIC preview for {full_path}")
                return jsonify({"error": "Failed to generate HEIC preview"}), 500
        except Exception as e:
            print(f"ERROR: get_media - Error processing HEIC file {full_path}: {type(e).__name__}: {e}")
            return jsonify({"error": "Failed to process HEIC file for display"}), 500
    else: # Serve original image/video directly (JPG, PNG, GIF, WEBP, MP4, etc.)
        print(f"DEBUG: get_media - Serving original file directly: {full_path}")
        directory = os.path.dirname(full_path)
        return send_from_directory(directory, filename)

@app.route('/api/thumbnail/<path:relative_path>')
def get_thumbnail(relative_path):
    """Serves thumbnails for images and RAW files."""
    print(f"DEBUG: '/api/thumbnail/{relative_path}' endpoint called.")
    full_media_path = os.path.abspath(os.path.join(image_library_root, relative_path))
    print(f"DEBUG: get_thumbnail - full_media_path: '{full_media_path}'")
    
    if not full_media_path.startswith(image_library_root):
        print(f"DEBUG: Forbidden thumbnail access attempt: {full_media_path}")
        return jsonify({"error": "Forbidden"}), 403

    if not os.path.exists(full_media_path):
        print(f"DEBUG: Media file for thumbnail not found: {full_media_path}")
        return jsonify({"error": "Media file for thumbnail not found"}), 404

    # MODIFIED: Always generate a thumbnail, even for videos
    thumbnail_full_path = _generate_thumbnail(full_media_path) # Generate or get existing
    print(f"DEBUG: get_thumbnail - _generate_thumbnail returned: {thumbnail_full_path}")

    if thumbnail_full_path and os.path.exists(thumbnail_full_path):
        print(f"DEBUG: get_thumbnail - Serving thumbnail from: {thumbnail_full_path}")
        return send_from_directory(os.path.dirname(thumbnail_full_path), os.path.basename(thumbnail_full_path))
    else:
        print(f"ERROR: get_thumbnail - Thumbnail generation failed or unsupported type for {full_media_path}")
        return jsonify({"error": "Thumbnail generation failed or unsupported type"}), 500

@app.route('/api/recursive_media/<path:path_segments>')
def get_recursive_media(path_segments):
    """Returns all media files recursively from a given path."""
    print(f"DEBUG: '/api/recursive_media/{path_segments}' endpoint called.")
    full_path_segments = path_segments.split('/')
    base_dir = os.path.abspath(os.path.join(image_library_root, *full_path_segments))
    print(f"DEBUG: get_recursive_media - base_dir: '{base_dir}'")

    if not base_dir.startswith(image_library_root):
        print(f"DEBUG: Forbidden recursive media access attempt: {base_dir}")
        return jsonify({"error": "Forbidden"}), 403

    if not os.path.isdir(base_dir):
        print(f"DEBUG: Recursive media base directory not found: {base_dir}")
        return jsonify([])

    media_files = _get_media_files_in_directory(base_dir, include_subfolders=True)
    print(f"DEBUG: '/api/recursive_media' returning {len(media_files)} files.")
    return jsonify(media_files)

@app.route('/api/download_original_raw/<path:relative_path>')
def download_original_raw(relative_path):
    """Allows downloading of original RAW/HEIC files."""
    print(f"DEBUG: '/api/download_original_raw/{relative_path}' endpoint called.")
    full_path = os.path.abspath(os.path.join(image_library_root, relative_path))
    print(f"DEBUG: download_original_raw - full_path: '{full_path}'")
    
    if not full_path.startswith(image_library_root):
        print(f"DEBUG: Forbidden download attempt: {full_path}")
        return jsonify({"error": "Forbidden"}), 403

    if not os.path.exists(full_path):
        print(f"DEBUG: File not found for download: {full_path}")
        return jsonify({"error": "File not found"}), 404

    filename = os.path.basename(full_path)
    ext = os.path.splitext(filename)[1].lower()

    # Allow download for RAW and HEIC
    if ext in ALLOWED_RAW_EXTENSIONS or ext == '.heic':
        print(f"DEBUG: Serving original RAW/HEIC for download: {full_path}")
        directory = os.path.dirname(full_path)
        return send_from_directory(directory, filename, as_attachment=True)
    else:
        print(f"DEBUG: File is not RAW/HEIC for download: {full_path}")
        return jsonify({"error": "File is not a RAW/HEIC format or not allowed for direct download"}), 400

@app.route('/api/trash_content')
def get_trash_content():
    """
    Returns a list of all files in the trash directory, including subfolders.
    """
    trash_files = []
    # MODIFIED: Added dirs[:] to prevent walking into hidden subdirectories
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
                    'thumbnail_path': os.path.join(TRASH_FOLDER_NAME, relative_path_in_trash).replace('\\', '/') # Thumbnail is the file itself in trash
                }
                # Get original path from metadata
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
    
    # Sort by filename
    trash_files.sort(key=lambda x: x['filename'].lower())
    
    count = _read_folder_item_count(TRASH_ROOT)
    if count is None: # Fallback if read fails
        count = len(trash_files)
        print(f"DEBUG: Trash count recalculated based on files found: {count}")
    else:
        print(f"DEBUG: Trash count from meta file: {count}")


    print(f"DEBUG: '/api/trash_content' returning {len(trash_files)} files, count: {count}.")
    return jsonify({'files': trash_files, 'count': count})


@app.route('/api/move_to_trash', methods=['POST'])
def move_to_trash():
    """Moves a single file to the trash folder and records its original path."""
    print("DEBUG: '/api/move_to_trash' endpoint called.")
    data = request.get_json()
    file_relative_path = data.get('path')
    print(f"DEBUG: move_to_trash - file_relative_path: '{file_relative_path}'")

    if not file_relative_path:
        print("DEBUG: Path not provided for move_to_trash.")
        return jsonify({"error": "Path not provided"}), 400

    original_full_path = os.path.abspath(os.path.join(image_library_root, file_relative_path))
    print(f"DEBUG: move_to_trash - original_full_path: '{original_full_path}'")
    if not original_full_path.startswith(image_library_root) or TRASH_ROOT in original_full_path:
        print(f"DEBUG: Forbidden move_to_trash attempt: {original_full_path}")
        return jsonify({"error": "Forbidden: Attempted to move file from outside media root or from trash."}), 403 # Forbidden

    if not os.path.exists(original_full_path):
        print(f"DEBUG: File not found for move_to_trash: {original_full_path}")
        return jsonify({"error": "File not found"}), 404

    filename = os.path.basename(original_full_path)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = os.urandom(4).hex()
    name, ext = os.path.splitext(filename)
    trash_filename = f"{name}_{timestamp}_{unique_id}{ext}"
    trash_full_path = os.path.join(TRASH_ROOT, trash_filename)
    print(f"DEBUG: move_to_trash - trash_full_path: '{trash_full_path}'")

    try:
        # MODIFICATION: Create hidden subdirectories in trash
        trash_thumbnail_dir = os.path.join(TRASH_ROOT, THUMBNAIL_SUBFOLDER_NAME)
        trash_preview_dir = os.path.join(TRASH_ROOT, PREVIEW_SUBFOLDER_NAME)
        os.makedirs(trash_thumbnail_dir, exist_ok=True)
        os.makedirs(trash_preview_dir, exist_ok=True)

        shutil.move(original_full_path, trash_full_path)
        print(f"DEBUG: Moved original file from '{original_full_path}' to '{trash_full_path}'")

        # Move associated thumbnail if it exists
        original_thumbnail_full_path = _get_thumbnail_full_path(original_full_path)
        trashed_thumbnail_relative_path = None
        print(f"DEBUG: Checking for associated thumbnail at: '{original_thumbnail_full_path}'")
        if os.path.isfile(original_thumbnail_full_path):
            thumb_name, thumb_ext = os.path.splitext(os.path.basename(original_thumbnail_full_path))
            trashed_thumb_filename = f"{thumb_name}_{timestamp}_{unique_id}{thumb_ext}" # Use same timestamp/unique_id
            # MODIFICATION: Move to hidden thumbnail folder in trash
            trashed_thumb_full_path = os.path.join(trash_thumbnail_dir, trashed_thumb_filename)
            shutil.move(original_thumbnail_full_path, trashed_thumb_full_path)
            trashed_thumbnail_relative_path = os.path.relpath(trashed_thumb_full_path, image_library_root).replace('\\', '/')
            print(f"DEBUG: Moved thumbnail from '{original_thumbnail_full_path}' to '{trashed_thumb_full_path}'")
            
            # Clean up empty thumbnail directory
            thumb_dir = os.path.dirname(original_thumbnail_full_path)
            if os.path.exists(thumb_dir) and not os.listdir(thumb_dir):
                os.rmdir(thumb_dir)
                print(f"DEBUG: Removed empty thumbnail directory: {thumb_dir}")

        # Handle preview: if it exists, move it to trash too
        original_preview_full_path = _get_preview_full_path(original_full_path)
        trashed_preview_relative_path = None
        print(f"DEBUG: move_to_trash - checking for preview at: '{original_preview_full_path}'")
        if os.path.isfile(original_preview_full_path):
            preview_base_name, preview_ext = os.path.splitext(os.path.basename(original_preview_full_path))
            trashed_preview_filename = f"{preview_base_name}_{timestamp}_{unique_id}{preview_ext}"
            # MODIFICATION: Move to hidden preview folder in trash
            trashed_preview_full_path = os.path.join(trash_preview_dir, trashed_preview_filename)
            shutil.move(original_preview_full_path, trashed_preview_full_path)
            trashed_preview_relative_path = os.path.relpath(trashed_preview_full_path, image_library_root).replace('\\', '/')
            print(f"DEBUG: Moved preview from '{original_preview_full_path}' to trash as '{trashed_preview_filename}'")

            preview_dir = os.path.dirname(original_preview_full_path)
            if os.path.exists(preview_dir) and not os.listdir(preview_dir):
                os.rmdir(preview_dir)
                print(f"DEBUG: Removed empty preview directory: {preview_dir}")


        # Create metadata file for the trashed item
        metadata = {
            'original_path': file_relative_path,
            'trashed_at': datetime.now().isoformat(),
            'trashed_as': trash_filename # Store the name it was trashed as
        }
        if trashed_thumbnail_relative_path:
            metadata['trashed_thumbnail_path'] = trashed_thumbnail_relative_path
        if trashed_preview_relative_path:
            metadata['trashed_preview_path'] = trashed_preview_relative_path
        
        metadata_file_path = f"{trash_full_path}.meta"
        with open(metadata_file_path, 'w') as f:
            json.dump(metadata, f, indent=4)
        print(f"DEBUG: Saved metadata to: {metadata_file_path}")

        # Update counts
        _update_folder_item_count_meta(os.path.dirname(original_full_path))
        _update_folder_item_count_meta(TRASH_ROOT)
        print(f"DEBUG: Updated counts for '{os.path.dirname(original_full_path)}' and '{TRASH_ROOT}'")

        return jsonify({"message": "File moved to trash successfully"})
    except Exception as e:
        print(f"ERROR: Error moving file to trash: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete_file_forever', methods=['DELETE'])
def delete_file_forever():
    """Permanently deletes a file from TRASH_ROOT, along with its metadata, thumbnail, and preview."""
    print("DEBUG: '/api/delete_file_forever' endpoint called.")
    data = request.get_json()
    file_relative_path_in_trash = data.get('path')
    print(f"DEBUG: delete_file_forever - file_relative_path_in_trash: '{file_relative_path_in_trash}'")

    if not file_relative_path_in_trash:
        print("DEBUG: Path not provided for delete_file_forever.")
        return jsonify({"error": "Path not provided"}), 400

    # Construct the full absolute path of the main file in trash
    full_path_in_trash = os.path.abspath(os.path.join(image_library_root, file_relative_path_in_trash))
    print(f"DEBUG: delete_file_forever - full_path_in_trash: '{full_path_in_trash}'")

    # Security check: Ensure the file is actually within the TRASH_ROOT
    if not full_path_in_trash.startswith(TRASH_ROOT):
        print(f"DEBUG: Forbidden delete_file_forever attempt: {full_path_in_trash}")
        return jsonify({"error": "Forbidden: Attempted to delete file outside of trash folder."}), 403 # Forbidden

    if not os.path.exists(full_path_in_trash):
        print(f"DEBUG: File not found in trash for delete_file_forever: {full_path_in_trash}")
        return jsonify({"error": "File not found in trash"}), 404

    try:
        # Read metadata to find associated thumbnail and preview path in trash
        metadata_file_path = f"{full_path_in_trash}.meta"
        trashed_thumbnail_path = None
        trashed_preview_path = None
        print(f"DEBUG: Checking metadata for associated files at: '{metadata_file_path}'")
        if os.path.exists(metadata_file_path):
            try:
                with open(metadata_file_path, 'r') as f:
                    metadata = json.load(f)
                trashed_thumbnail_path = metadata.get('trashed_thumbnail_path')
                trashed_preview_path = metadata.get('trashed_preview_path')
                print(f"DEBUG: Found associated thumbnail in metadata: {trashed_thumbnail_path}")
                print(f"DEBUG: Found associated preview in metadata: {trashed_preview_path}")
            except Exception as e:
                print(f"Warning: Could not read metadata for {full_path_in_trash} to find associated files: {e}")

        # Delete the main media file
        os.remove(full_path_in_trash)
        print(f"DEBUG: Deleted main file: {full_path_in_trash}")

        # Delete the metadata file
        if os.path.exists(metadata_file_path):
            os.remove(metadata_file_path)
            print(f"DEBUG: Deleted metadata file: {metadata_file_path}")
        
        # Delete the associated thumbnail if it exists and is in trash
        if trashed_thumbnail_path:
            full_trashed_thumbnail_path = os.path.abspath(os.path.join(image_library_root, trashed_thumbnail_path))
            print(f"DEBUG: Checking associated thumbnail for deletion: {full_trashed_thumbnail_path}")
            if os.path.exists(full_trashed_thumbnail_path) and full_trashed_thumbnail_path.startswith(TRASH_ROOT):
                os.remove(full_trashed_thumbnail_path)
                print(f"DEBUG: Deleted associated thumbnail: {full_trashed_thumbnail_path}")
        
        # Delete the associated preview if it exists and is in trash
        if trashed_preview_path:
            full_trashed_preview_path = os.path.abspath(os.path.join(image_library_root, trashed_preview_path))
            print(f"DEBUG: Checking associated preview for deletion: {full_trashed_preview_path}")
            if os.path.exists(full_trashed_preview_path) and full_trashed_preview_path.startswith(TRASH_ROOT):
                os.remove(full_trashed_preview_path)
                print(f"DEBUG: Deleted associated preview: {full_trashed_preview_path}")

        _update_folder_item_count_meta(TRASH_ROOT)
        print(f"DEBUG: Updated count for '{TRASH_ROOT}'")

        return jsonify({"message": "File permanently deleted"})
    except Exception as e:
        print(f"ERROR: Error permanently deleting file: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

# NEW: Helper function to restore associated files like thumbnails and previews
def _restore_associated_file(final_restore_path, trashed_associated_path, path_generator_func):
    """
    Helper to restore an associated file (thumbnail or preview).
    :param final_restore_path: The full path where the main file was restored.
    :param trashed_associated_path: The relative path of the associated file in the trash.
    :param path_generator_func: The function to generate the new path (_get_thumbnail_full_path or _get_preview_full_path).
    """
    if trashed_associated_path:
        full_trashed_associated_path = os.path.abspath(os.path.join(image_library_root, trashed_associated_path))
        print(f"DEBUG: Checking associated file for restoration: {full_trashed_associated_path}")
        if os.path.exists(full_trashed_associated_path) and full_trashed_associated_path.startswith(TRASH_ROOT):
            expected_new_path = path_generator_func(final_restore_path)
            os.makedirs(os.path.dirname(expected_new_path), exist_ok=True)
            shutil.move(full_trashed_associated_path, expected_new_path)
            print(f"DEBUG: Restored associated file from '{full_trashed_associated_path}' to '{expected_new_path}'")

@app.route('/api/restore_file', methods=['POST'])
def restore_file():
    """Restores a file from TRASH_ROOT to its original location, recreating folders if needed."""
    print("DEBUG: '/api/restore_file' endpoint called.")
    data = request.get_json()
    file_relative_path_in_trash = data.get('path')
    print(f"DEBUG: restore_file - file_relative_path_in_trash: '{file_relative_path_in_trash}'")

    if not file_relative_path_in_trash:
        print("DEBUG: Path not provided for restore_file.")
        return jsonify({"error": "Path not provided"}), 400

    source_full_path_in_trash = os.path.abspath(os.path.join(image_library_root, file_relative_path_in_trash))
    print(f"DEBUG: restore_file - source_full_path_in_trash: '{source_full_path_in_trash}'")
    if not source_full_path_in_trash.startswith(TRASH_ROOT):
        print(f"DEBUG: Forbidden restore_file attempt: {source_full_path_in_trash}")
        return jsonify({"error": "Forbidden: Attempted to restore file outside of trash folder."}), 403 # Forbidden

    if not os.path.exists(source_full_path_in_trash):
        print(f"DEBUG: File not found in trash for restore_file: {source_full_path_in_trash}")
        return jsonify({"error": "File not found in trash"}), 404

    metadata_file_path = f"{source_full_path_in_trash}.meta"
    if not os.path.exists(metadata_file_path):
        print(f"DEBUG: Metadata for file not found in trash for restore_file: {metadata_file_path}")
        return jsonify({"error": "Metadata for file not found in trash"}), 404

    with open(metadata_file_path, 'r') as f:
        metadata = json.load(f)
    original_relative_path = metadata.get('original_path')
    trashed_thumbnail_path = metadata.get('trashed_thumbnail_path') # Get the path of the thumbnail *in trash*
    trashed_preview_path = metadata.get('trashed_preview_path') # Get the path of the preview *in trash*
    print(f"DEBUG: restore_file - original_relative_path from metadata: '{original_relative_path}'")
    print(f"DEBUG: restore_file - trashed_thumbnail_path from metadata: '{trashed_thumbnail_path}'")
    print(f"DEBUG: restore_file - trashed_preview_path from metadata: '{trashed_preview_path}'")


    if not original_relative_path:
        print("DEBUG: Original path not found in metadata for restore_file. Cannot restore.")
        return jsonify({"error": "Original path not found in metadata. Cannot restore."}), 500

    original_full_path = os.path.abspath(os.path.join(image_library_root, original_relative_path))
    original_directory = os.path.dirname(original_full_path)
    print(f"DEBUG: restore_file - original_full_path: '{original_full_path}', original_directory: '{original_directory}'")

    try:
        os.makedirs(original_directory, exist_ok=True)
        print(f"DEBUG: Ensured original directory exists: {original_directory}")
        
        # Handle potential filename conflict at destination
        final_restore_path = original_full_path
        if os.path.exists(original_full_path):
            base_name, ext = os.path.splitext(original_relative_path)
            timestamp = datetime.now().strftime("_%Y%m%d%H%M%S")
            dir_name = os.path.dirname(original_relative_path)
            new_filename = f"{os.path.basename(base_name)}{timestamp}{ext}"
            final_restore_path = os.path.abspath(os.path.join(image_library_root, dir_name, new_filename))
            print(f"DEBUG: Conflict at original path. Restoring to: {os.path.relpath(final_restore_path, image_library_root)}")

        # MODIFIED: Restore associated files FIRST to make the operation more robust.
        # If moving these fails, the main file remains safely in the trash.
        _restore_associated_file(final_restore_path, trashed_thumbnail_path, _get_thumbnail_full_path)
        _restore_associated_file(final_restore_path, trashed_preview_path, _get_preview_full_path)

        # Now, move the main file
        shutil.move(source_full_path_in_trash, final_restore_path)
        print(f"DEBUG: Restored main file from '{source_full_path_in_trash}' to '{final_restore_path}'")

        os.remove(metadata_file_path)
        print(f"DEBUG: Deleted metadata file: {metadata_file_path}")

        _update_folder_item_count_meta(TRASH_ROOT)
        _update_folder_item_count_meta(os.path.dirname(final_restore_path))
        print(f"DEBUG: Updated counts for '{TRASH_ROOT}' and '{os.path.dirname(final_restore_path)}'")


        return jsonify({"message": "File restored successfully"})
    except Exception as e:
        print(f"ERROR: Error restoring file: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create_folder', methods=['POST'])
def create_folder():
    """Creates a new folder at the specified parent path."""
    print("DEBUG: '/api/create_folder' endpoint called.")
    data = request.get_json()
    parent_path_segments = data.get('parent_path', [])
    folder_name = data.get('folder_name')
    print(f"DEBUG: create_folder - parent_path_segments: {parent_path_segments}, folder_name: '{folder_name}'")

    if not folder_name:
        print("DEBUG: Folder name not provided for create_folder.")
        return jsonify({"error": "Folder name not provided"}), 400

    safe_folder_name = secure_filename(folder_name)
    if not safe_folder_name:
        print("DEBUG: Invalid folder name after secure_filename.")
        return jsonify({"error": "Invalid folder name"}), 400

    full_parent_path = os.path.abspath(os.path.join(image_library_root, *parent_path_segments))
    new_folder_full_path = os.path.join(full_parent_path, safe_folder_name)
    print(f"DEBUG: create_folder - full_parent_path: '{full_parent_path}', new_folder_full_path: '{new_folder_full_path}'")

    if not new_folder_full_path.startswith(image_library_root) or TRASH_ROOT in new_folder_full_path:
        print(f"DEBUG: Forbidden create_folder attempt: {new_folder_full_path}")
        return jsonify({"error": "Forbidden: Cannot create folders outside media root or inside trash."}), 403

    if os.path.exists(new_folder_full_path):
        print(f"DEBUG: Folder already exists: {new_folder_full_path}")
        return jsonify({"error": f"Folder '{safe_folder_name}' already exists."}), 409

    try:
        os.makedirs(new_folder_full_path)
        print(f"DEBUG: Folder created: {new_folder_full_path}")
        # Update count of parent folder (if applicable)
        if parent_path_segments:
            _update_folder_item_count_meta(full_parent_path)
            print(f"DEBUG: Updated count for parent folder: {full_parent_path}")

        # MODIFIED: Correctly format the location message to prevent error on empty path
        location_message = os.path.join(*parent_path_segments) if parent_path_segments else 'root'
        return jsonify({"message": f"Folder '{safe_folder_name}' created successfully at '{location_message}'."}), 201
    except Exception as e:
        print(f"ERROR: Error creating folder: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    """Handles file uploads to the appropriate dated folder."""
    print("DEBUG: '/api/upload_file' endpoint called.")
    if 'file' not in request.files:
        print("DEBUG: No file part in request for upload_file.")
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        print("DEBUG: No selected file for upload_file.")
        return jsonify({"error": "No selected file"}), 400

    current_path_json = request.form.get('current_path', '[]')
    try:
        current_path_segments = json.loads(current_path_json)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid current_path format"}), 400

    # Determine destination path
    destination_dir = os.path.join(image_library_root, *current_path_segments)

    os.makedirs(destination_dir, exist_ok=True)
    file_full_path = os.path.join(destination_dir, file.filename)

    # Prevent overwriting existing files with the same name
    counter = 1
    original_name, ext = os.path.splitext(file.filename)
    while os.path.exists(file_full_path):
        file_full_path = os.path.join(destination_dir, f"{original_name}_{counter}{ext}")
        counter += 1

    try:
        file.save(file_full_path)
        print(f"DEBUG: File saved to: {file_full_path}")
        # Check against extensions with leading dots
        if os.path.splitext(file.filename)[1].lower() in ALLOWED_IMAGE_EXTENSIONS or \
           os.path.splitext(file.filename)[1].lower() in ALLOWED_RAW_EXTENSIONS:
            print(f"DEBUG: Triggering thumbnail generation for uploaded file: {file_full_path}")
            _generate_thumbnail(file_full_path) # Call helper function
        
        _update_folder_item_count_meta(destination_dir)
        print(f"DEBUG: Updated count for upload directory: {destination_dir}")

        # MODIFIED: Correctly format the success message to be more accurate and avoid TypeError
        final_destination_relative_path = os.path.relpath(os.path.dirname(file_full_path), image_library_root)
        return jsonify({"message": f"File '{os.path.basename(file_full_path)}' uploaded successfully to '{final_destination_relative_path}'"}), 200
    except Exception as e:
        print(f"ERROR: Error saving file during upload: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete_folder', methods=['POST'])
def delete_folder():
    """Moves an entire folder and its contents to the trash folder."""
    print("DEBUG: '/api/delete_folder' endpoint called.")
    data = request.get_json()
    path_data = data.get('path') # Can be a string or a list
    print(f"DEBUG: delete_folder - path_data: {path_data}, type: {type(path_data)}")

    if not path_data:
        print("DEBUG: Folder path not provided for delete_folder.")
        return jsonify({"error": "Folder path not provided"}), 400

    # Ensure path_segments is a list
    if isinstance(path_data, str):
        folder_path_segments = path_data.split('/')
    elif isinstance(path_data, list):
        folder_path_segments = path_data
    else:
        print(f"ERROR: Invalid path data type for delete_folder: {type(path_data)}")
        return jsonify({"error": "Invalid path format provided"}), 400
    
    folder_full_path = os.path.abspath(os.path.join(image_library_root, *folder_path_segments))
    print(f"DEBUG: delete_folder - folder_full_path: '{folder_full_path}'")

    if not folder_full_path.startswith(image_library_root) or TRASH_ROOT in folder_full_path:
        print(f"DEBUG: Forbidden delete_folder attempt: {folder_full_path}")
        return jsonify({"error": "Forbidden: Cannot delete root media directory, trash folder, or outside media root."}), 403

    if not os.path.isdir(folder_full_path):
        print(f"DEBUG: Folder not found for delete_folder: {folder_full_path}")
        return jsonify({"error": "Folder not found"}), 404

    try:
        # Get all media files recursively within the folder to be deleted
        files_to_trash = _get_media_files_in_directory(folder_full_path, include_subfolders=True)
        print(f"DEBUG: delete_folder - Found {len(files_to_trash)} files to trash.")

        for file_info in files_to_trash:
            original_relative_path = file_info['original_path']
            original_file_full_path = os.path.abspath(os.path.join(image_library_root, original_relative_path))
            print(f"DEBUG: delete_folder - Processing file to trash: '{original_file_full_path}'")
            
            filename = os.path.basename(original_file_full_path)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_id = os.urandom(4).hex()
            name, ext = os.path.splitext(filename)
            trash_filename = f"{name}_{timestamp}_{unique_id}{ext}"
            trash_full_path = os.path.join(TRASH_ROOT, trash_filename)
            print(f"DEBUG: delete_folder - Trash destination: '{trash_full_path}'")

            # Move main file
            shutil.move(original_file_full_path, trash_full_path)
            print(f"DEBUG: Moved original file: '{original_file_full_path}' to '{trash_full_path}'")

            # Move associated thumbnail if it exists
            original_thumbnail_full_path = _get_thumbnail_full_path(original_file_full_path)
            trashed_thumbnail_relative_path = None
            print(f"DEBUG: Checking for thumbnail to move: '{original_thumbnail_full_path}'")
            if os.path.isfile(original_thumbnail_full_path):
                thumb_name, thumb_ext = os.path.splitext(os.path.basename(original_thumbnail_full_path))
                trashed_thumb_filename = f"{thumb_name}_{timestamp}_{unique_id}{thumb_ext}"
                trashed_thumb_full_path = os.path.join(TRASH_ROOT, trashed_thumb_filename)
                shutil.move(original_thumbnail_full_path, trashed_thumb_full_path)
                trashed_thumbnail_relative_path = os.path.relpath(trashed_thumb_full_path, image_library_root).replace('\\', '/')
                print(f"DEBUG: Moved thumbnail: '{original_thumbnail_full_path}' to '{trashed_thumb_full_path}'")
            
            # Move associated preview if it exists
            original_preview_full_path = _get_preview_full_path(original_file_full_path)
            trashed_preview_relative_path = None
            print(f"DEBUG: Checking for preview to move: '{original_preview_full_path}'")
            if os.path.isfile(original_preview_full_path):
                preview_name, preview_ext = os.path.splitext(os.path.basename(original_preview_full_path))
                trashed_preview_filename = f"{preview_name}_{timestamp}_{unique_id}{preview_ext}"
                trashed_preview_full_path = os.path.join(TRASH_ROOT, trashed_preview_filename)
                shutil.move(original_preview_full_path, trashed_preview_full_path)
                trashed_preview_relative_path = os.path.relpath(trashed_preview_full_path, image_library_root).replace('\\', '/')
                print(f"DEBUG: Moved preview: '{original_preview_full_path}' to '{trashed_preview_full_path}'")

            # Create metadata file for the trashed item
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
            print(f"DEBUG: Saved metadata for trashed file: {metadata_file_path}")

        # After moving all files, remove the now empty original folder structure
        shutil.rmtree(folder_full_path)
        print(f"DEBUG: Removed empty original folder structure: {folder_full_path}")
        
        # Update counts for affected folders
        # Update parent folder's count
        parent_folder_full_path = os.path.dirname(folder_full_path)
        if parent_folder_full_path.startswith(image_library_root): # Ensure it's within media root
            _update_folder_item_count_meta(parent_folder_full_path)
            print(f"DEBUG: Updated count for parent folder: {parent_folder_full_path}")
        _update_folder_item_count_meta(TRASH_ROOT)
        print(f"DEBUG: Updated count for trash root: {TRASH_ROOT}")

        return jsonify({"message": f"Folder '{'/'.join(folder_path_segments)}' and its contents moved to trash."})
    except Exception as e:
        print(f"ERROR: Error deleting folder: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    _initial_scan_and_populate_counts() # Run initial scan on startup
    app.run(host='0.0.0.0', debug=True, port=8080)
