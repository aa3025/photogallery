# filename: server.py
import os
import shutil # Import shutil for moving files
import json   # Import json for reading/writing metadata
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS # Import CORS for cross-origin requests
from datetime import datetime # For timestamping restored files if needed
from PIL import Image, ExifTags # Import Pillow for image processing
import rawpy # For RAW image processing
from pillow_heif import register_heif_opener # For HEIC support

# Register HEIF opener for Pillow
register_heif_opener()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing your HTML to fetch data

# --- Configuration for your Image Library ---
# Set this to the ABSOLUTE path of the directory that contains your YYYY (year) folders.
# Example: If your images are in /Users/YourUser/Pictures/MyPhotos/2023/01/01
# then image_library_root should be '/Users/YourUser/Pictures/MyPhotoLibrary'
# IMPORTANT: This should be the absolute path to your media folder.
# For example: '/Users/youruser/Pictures/MyPhotoLibrary' or 'C:\\Users\\youruser\\Pictures\\MyPhotoLibrary'
# Ensure this path is correct for your environment.
image_library_root = os.path.abspath('/Volumes/aa3025_bkp/Photos_Backup') # Hardcoded path as requested

# Define the trash folder name and its absolute path
TRASH_FOLDER_NAME = '_Trash'
TRASH_ROOT = os.path.join(image_library_root, TRASH_FOLDER_NAME)

# Define the metadata file name for counts
COUNT_META_FILENAME = '_count.meta'

# Thumbnail configuration
THUMBNAIL_DIR_NAME = '.thumbnails' # Hidden directory for thumbnails
THUMBNAIL_MAX_DIMENSION = 480 # Max width or height for thumbnails

# Ensure the image_library_root exists
if not os.path.isdir(image_library_root):
    print(f"Warning: Image library root '{image_library_root}' does not exist or is not a directory.")
    print("Please update the 'image_library_root' variable in server.py to your actual image folder path.")
    # You might want to exit or handle this more gracefully in a production app
    # For now, we'll let it run but it won't find any images.

# Ensure the trash directory exists
if not os.path.exists(TRASH_ROOT):
    os.makedirs(TRASH_ROOT)
    print(f"Created TRASH_ROOT directory: {TRASH_ROOT}")


# Define allowed image and video extensions globally for consistency
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.avif')
RAW_EXTENSIONS = ('.nef', '.nrw', '.cr2', '.cr3', '.crw', '.arw', '.srf', '.sr2',
                  '.orf', '.raf', '.rw2', '.raw', '.dng', '.kdc', '.dcr', '.erf',
                  '.3fr', '.mef', '.pef', '.x3f')
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.webm', '.ogg', '.avi', '.mkv')
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + RAW_EXTENSIONS + VIDEO_EXTENSIONS


# Helper function to get directories and files in a given path
def get_contents_structured(path):
    """
    Lists directories and files in a given path.
    Returns a dictionary: {"directories": [...], "files": [...]}.
    Files are returned as dictionaries with 'filename' and 'original_path'.
    """
    if not os.path.isdir(path):
        return {"directories": [], "files": []}
    
    directories = []
    files = []
    
    for item in os.listdir(path):
        full_path = os.path.join(path, item)
        # Exclude hidden files/directories (starting with '.')
        # Also exclude metadata files (ending with .meta) and thumbnail directories
        if item.startswith('.') or item.endswith('.meta') or item == THUMBNAIL_DIR_NAME:
            continue
        if os.path.isdir(full_path):
            directories.append(item)
        elif os.path.isfile(full_path):
            # Only include files with allowed media extensions
            if item.lower().endswith(MEDIA_EXTENSIONS):
                # Construct the relative path from image_library_root
                relative_path = os.path.relpath(full_path, image_library_root)
                files.append({"filename": item, "original_path": relative_path})
    
    return {"directories": sorted(directories), "files": sorted(files, key=lambda x: x['filename'])}

# Helper function to get files (images/videos)
# This function is defined globally and used by list_trash_content
def get_files(path):
    # This function uses the globally defined MEDIA_EXTENSIONS
    # Exclude metadata files here too
    return sorted([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.lower().endswith(MEDIA_EXTENSIONS) and not f.endswith('.meta')])

# NEW: Helper function to recursively get all media files (used for slideshows)
def get_all_media_recursive(path):
    """
    Recursively lists all media files (images and videos) in a given path and its subdirectories.
    Returns a list of dictionaries: [{"filename": "...", "original_path": "..."}, ...].
    """
    all_files = []
    if not os.path.isdir(path):
        return []

    for root, _, files in os.walk(path):
        current_relative_root = os.path.relpath(root, image_library_root)
        if current_relative_root == '.': # If root is the image_library_root itself
            current_relative_root = ''
        
        # Exclude trash folder content from recursive scans for regular views
        # This prevents accidental inclusion of trash items in regular slideshows
        if TRASH_FOLDER_NAME in current_relative_root.split(os.sep):
            continue

        # Exclude thumbnail directories from recursive scan
        if THUMBNAIL_DIR_NAME in current_relative_root.split(os.sep):
            continue

        for file in files:
            if file.lower().endswith(MEDIA_EXTENSIONS) and not file.endswith('.meta'):
                # Construct the relative path from image_library_root
                full_relative_path = os.path.join(current_relative_root, file) if current_relative_root else file
                all_files.append({"filename": file, "original_path": full_relative_path})
    return sorted(all_files, key=lambda x: x['original_path']) # Sort by original_path

# NEW: Function to recursively count media files
def _get_recursive_media_count(path):
    """
    Recursively counts all media files (images and videos) in a given path and its subdirectories.
    """
    count = 0
    if not os.path.isdir(path):
        return 0
    
    for root, _, files in os.walk(path):
        # Exclude trash folder content from recursive counts for regular folders
        # This ensures counts for years/months/days don't include trashed items
        if TRASH_FOLDER_NAME in os.path.relpath(root, image_library_root).split(os.sep) and root != TRASH_ROOT:
            continue
        
        # Exclude thumbnail directories from recursive count
        if THUMBNAIL_DIR_NAME in os.path.relpath(root, image_library_root).split(os.sep):
            continue

        for file in files:
            if file.lower().endswith(MEDIA_EXTENSIONS) and not file.endswith('.meta') and not file.startswith('.'):
                count += 1
    return count

# NEW: Function to read item count from a folder's meta file
def _read_folder_item_count(folder_path):
    meta_file_path = os.path.join(folder_path, COUNT_META_FILENAME)
    if os.path.exists(meta_file_path):
        try:
            with open(meta_file_path, 'r') as f:
                metadata = json.load(f)
                return metadata.get("item_count", 0)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode {COUNT_META_FILENAME} in {folder_path}. Recalculating.")
            return None # Indicate corruption, trigger recalculation
    return None

# NEW: Function to write/update item count to a folder's meta file
def _update_folder_item_count_meta(folder_path):
    if not os.path.isdir(folder_path):
        return # Cannot update count for non-existent folder

    count = _get_recursive_media_count(folder_path)
    meta_file_path = os.path.join(folder_path, COUNT_META_FILENAME)
    try:
        with open(meta_file_path, 'w') as f:
            json.dump({"item_count": count}, f)
        print(f"Updated count for '{os.path.basename(folder_path)}': {count}")
    except Exception as e:
        print(f"Error writing {COUNT_META_FILENAME} for {folder_path}: {e}")

# NEW: Function to perform initial scan and populate all _count.meta files
def _initial_scan_and_populate_counts():
    print("Performing initial scan and populating folder item counts...")
    
    # Update count for the trash folder first
    _update_folder_item_count_meta(TRASH_ROOT)

    # Update counts for years, months, and days
    if os.path.isdir(image_library_root):
        for year_dir in os.listdir(image_library_root):
            year_path = os.path.join(image_library_root, year_dir)
            if os.path.isdir(year_path) and year_dir.isdigit() and len(year_dir) == 4 and year_dir != TRASH_FOLDER_NAME:
                _update_folder_item_count_meta(year_path) # Update year's count
                for month_dir in os.listdir(year_path):
                    month_path = os.path.join(year_path, month_dir)
                    if os.path.isdir(month_path) and month_dir.isdigit() and len(month_dir) == 2:
                        _update_folder_item_count_meta(month_path) # Update month's count
                        for day_dir in os.listdir(month_path):
                            day_path = os.path.join(month_path, day_dir)
                            if os.path.isdir(day_path) and day_dir.isdigit() and len(day_dir) == 2:
                                _update_folder_item_count_meta(day_path) # Update day's count
    print("Initial scan complete.")

# Helper function to ensure thumbnail directory exists for a given original file path
def _ensure_thumbnail_dir_exists(original_file_path):
    """Ensures the .thumbnails directory exists for a given original file path."""
    thumbnail_dir = os.path.join(os.path.dirname(original_file_path), THUMBNAIL_DIR_NAME)
    os.makedirs(thumbnail_dir, exist_ok=True)
    return thumbnail_dir

# Helper function to generate and save a thumbnail
def _generate_thumbnail(original_file_path):
    """
    Generates a thumbnail for an image or RAW file and saves it.
    Returns the path to the generated thumbnail.
    """
    # Determine the thumbnail file path
    thumbnail_dir = _ensure_thumbnail_dir_exists(original_file_path)
    base_filename = os.path.basename(original_file_path)
    thumbnail_filename = f"{os.path.splitext(base_filename)[0]}.webp" # Use webp for efficiency
    thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)

    # Check if thumbnail already exists and is up-to-date
    if os.path.exists(thumbnail_path) and os.path.getmtime(thumbnail_path) >= os.path.getmtime(original_file_path):
        return thumbnail_path # Thumbnail is current, no need to regenerate

    print(f"Generating thumbnail for: {original_file_path}")
    try:
        file_extension = os.path.splitext(original_file_path)[1].lower()

        if file_extension in RAW_EXTENSIONS:
            # Use rawpy for RAW images
            with rawpy.imread(original_file_path) as raw:
                # Get a thumbnail from the raw image (if available) or a small RGB image
                # Using postprocess() to get a renderable image
                rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
                image = Image.fromarray(rgb)
        else:
            # Use Pillow for standard image formats
            image = Image.open(original_file_path)

        # Apply EXIF orientation
        try:
            if hasattr(image, '_getexif'):
                exif = image._getexif()
                if exif:
                    for orientation_tag in ExifTags.TAGS.keys():
                        if ExifTags.TAGS[orientation_tag] == 'Orientation':
                            break
                    
                    orientation = exif.get(orientation_tag)
                    if orientation == 3:
                        image = image.rotate(180, expand=True)
                    elif orientation == 6:
                        image = image.rotate(270, expand=True)
                    elif orientation == 8:
                        image = image.rotate(90, expand=True)
        except Exception as e:
            print(f"Error applying EXIF orientation for {original_file_path}: {e}")

        # Resize the image while maintaining aspect ratio
        image.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION), Image.LANCZOS)
        
        # Save the thumbnail in WEBP format
        image.save(thumbnail_path, "WEBP")
        return thumbnail_path

    except Exception as e:
        print(f"Error generating thumbnail for {original_file_path}: {e}")
        # Return a placeholder or indicate failure
        return None


# API endpoint to list years
@app.route('/api/years')
def list_years():
    """Lists all year directories (e.g., '2023', '2024') in the image_library_root, with item counts."""
    years_data = []
    if os.path.isdir(image_library_root):
        for item in os.listdir(image_library_root):
            full_path = os.path.join(image_library_root, item)
            if os.path.isdir(full_path) and item.isdigit() and len(item) == 4 and item != TRASH_FOLDER_NAME:
                count = _read_folder_item_count(full_path)
                if count is None: # Recalculate if meta file is missing or corrupted
                    _update_folder_item_count_meta(full_path)
                    count = _read_folder_item_count(full_path) # Read again after update
                years_data.append({"year": item, "count": count})
    
    # Sort by year (descending)
    years_data.sort(key=lambda x: int(x['year']), reverse=True)
    return jsonify(years_data)

# API endpoint to list months for a given year, and files within that year folder
@app.route('/api/months/<year>')
def list_months(year):
    """Lists all month directories and media files for a given year, with item counts."""
    year_path = os.path.join(image_library_root, year)
    if not os.path.isdir(year_path):
        return jsonify({"error": "Year not found"}), 404
    
    contents = get_contents_structured(year_path) # Now returns files as dicts
    
    months_data = []
    for month_dir in contents["directories"]:
        if month_dir.isdigit() and len(month_dir) == 2:
            month_path = os.path.join(year_path, month_dir)
            count = _read_folder_item_count(month_path)
            if count is None: # Recalculate if meta file is missing or corrupted
                _update_folder_item_count_meta(month_path)
                count = _read_folder_item_count(month_path) # Read again after update
            months_data.append({"month": month_dir, "count": count})
    
    # contents["files"] already contains dictionaries with "filename" and "original_path"
    # No need to construct full relative paths here, they are already in the dicts
    
    # Sort months numerically
    months_data.sort(key=lambda x: int(x['month']))
    return jsonify({"months": months_data, "files": contents["files"]})

# API endpoint to list days for a given year and month, and files within that month folder
@app.route('/api/days/<year>/<month>')
def list_days(year, month):
    """Lists all day directories and media files for a given year and month, with item counts."""
    month_path = os.path.join(image_library_root, year, month)
    if not os.path.isdir(month_path):
        return jsonify({"error": "Month not found"}), 404
    
    contents = get_contents_structured(month_path) # Now returns files as dicts
    
    days_data = []
    for day_dir in contents["directories"]:
        if day_dir.isdigit() and len(day_dir) == 2:
            day_path = os.path.join(month_path, day_dir)
            count = _read_folder_item_count(day_path)
            if count is None: # Recalculate if meta file is missing or corrupted
                _update_folder_item_count_meta(day_path)
                count = _read_folder_item_count(day_path) # Read again after update
            days_data.append({"day": day_dir, "count": count})

    # contents["files"] already contains dictionaries with "filename" and "original_path"
    # No need to construct full relative paths here, they are already in the dicts

    # Sort days numerically
    days_data.sort(key=lambda x: int(x['day']))
    return jsonify({"days": days_data, "files": contents["files"]})

# API endpoint to list photos for a given year, month, and day
@app.route('/api/photos/<year>/<month>/<day>')
def list_photos(year, month, day):
    """Lists all image and video files for a given year, month, and day."""
    day_path = os.path.join(image_library_root, year, month, day)
    if not os.path.isdir(day_path):
        return jsonify({"error": "Day not found"}), 404
    
    contents = get_contents_structured(day_path) # Now returns files as dicts
    
    # contents["files"] already contains dictionaries with "filename" and "original_path"
    return jsonify(contents["files"]) # Already sorted by filename in get_contents_structured

# NEW: API endpoint to get all media recursively for a given year
@app.route('/api/recursive_media/year/<year>')
def get_recursive_media_for_year(year):
    """Lists all media files recursively for a given year."""
    year_path = os.path.join(image_library_root, year)
    if not os.path.isdir(year_path):
        return jsonify({"error": "Year not found"}), 404
    
    files = get_all_media_recursive(year_path) # Now returns files as dicts
    return jsonify(files)

# NEW: API endpoint to get all media recursively for a given year and month
@app.route('/api/recursive_media/month/<year>/<month>')
def get_recursive_media_for_month(year, month):
    """Lists all media files recursively for a given year and month."""
    month_path = os.path.join(image_library_root, year, month)
    if not os.path.isdir(month_path):
        return jsonify({"error": "Month not found"}), 404
    
    files = get_all_media_recursive(month_path) # Now returns files as dicts
    return jsonify(files)


@app.route('/api/trash_content', methods=['GET'])
def list_trash_content():
    """
    Lists all files directly within the _Trash folder, including their original paths and the total count.
    Returns a list of dictionaries: [{"filename": "...", "relative_path_in_trash": "...", "original_path": "..."}, ...].
    """
    if not os.path.isdir(TRASH_ROOT):
        return jsonify({"error": "Trash folder not found"}), 404
    try:
        trashed_items = []
        for f in os.listdir(TRASH_ROOT):
            full_path = os.path.join(TRASH_ROOT, f)
            if os.path.isfile(full_path) and f.lower().endswith(MEDIA_EXTENSIONS) and not f.endswith('.meta') and not f.startswith('.'):
                metadata_path = f"{full_path}.meta"
                original_path_from_meta = None # Use a distinct variable name
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r') as meta_f:
                            metadata = json.load(meta_f)
                            original_path_from_meta = metadata.get("original_relative_path")
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode metadata for {f}")
                
                trashed_items.append({
                    "filename": f,
                    "relative_path_in_trash": os.path.join(TRASH_FOLDER_NAME, f), # Path used for deletion/restoration
                    "original_path": original_path_from_meta # Client will now consistently use 'original_path'
                })
        
        # Sort by filename
        trashed_items.sort(key=lambda x: x['filename'])
        
        # Read/update the trash folder's count
        _update_folder_item_count_meta(TRASH_ROOT) # Ensure count is fresh
        trash_count = _read_folder_item_count(TRASH_ROOT)
        if trash_count is None: # Fallback if read fails after update
            trash_count = len(trashed_items)


        return jsonify({"files": trashed_items, "count": trash_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/move_to_trash', methods=['POST'])
def move_to_trash():
    try:
        data = request.get_json(silent=True)

        if data is None:
            return jsonify({"error": "Invalid or empty JSON body"}), 400

        file_relative_path = data.get('path') # e.g., "2023/01/image.jpg"

        if not file_relative_path:
            return jsonify({"error": "File path not provided"}), 400

        # Construct absolute path of the source file
        source_path = os.path.abspath(os.path.join(image_library_root, file_relative_path))
        
        # Security checks:
        # 1. Ensure the source file is within image_library_root (and not already in trash)
        if not source_path.startswith(image_library_root) or TRASH_FOLDER_NAME in file_relative_path.split(os.sep):
            return jsonify({"error": "Attempted to move file from outside media root or from trash to trash"}), 403 # Forbidden

        # 2. Ensure the source is an actual file
        if not os.path.isfile(source_path):
            return jsonify({"error": "File not found or is not a file"}), 404
        
        # Determine destination path in trash, handling potential filename conflicts
        original_filename = os.path.basename(file_relative_path)
        trashed_filename = original_filename
        counter = 1
        destination_path = os.path.abspath(os.path.join(TRASH_ROOT, trashed_filename))
        
        # If a file with the same name exists in trash, append a counter
        while os.path.exists(destination_path) or os.path.exists(f"{destination_path}.meta"):
            base_name, ext = os.path.splitext(original_filename)
            trashed_filename = f"{base_name}_{counter}{ext}"
            destination_path = os.path.abspath(os.path.join(TRASH_ROOT, trashed_filename))
            counter += 1

        # Move the actual media file
        shutil.move(source_path, destination_path)

        # Create metadata file
        metadata = {"original_relative_path": file_relative_path}
        metadata_path = f"{destination_path}.meta"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

        # Update counts for affected folders
        source_folder_path = os.path.dirname(source_path)
        _update_folder_item_count_meta(source_folder_path) # Decrement source folder's count
        _update_folder_item_count_meta(TRASH_ROOT) # Increment trash folder's count

        return jsonify({"message": f"File {file_relative_path} moved to trash as {trashed_filename} successfully"}), 200

    except Exception as e:
        print(f"An unexpected error occurred during file movement to trash: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete_file_forever', methods=['DELETE'])
def delete_file_forever():
    """Permanently deletes a file from the trash folder."""
    try:
        data = request.get_json(silent=True)

        if data is None:
            return jsonify({"error": "Invalid or empty JSON body"}), 400

        file_relative_path = data.get('path') # e.g., "_Trash/trashed_image.jpg"

        if not file_relative_path:
            return jsonify({"error": "File path not provided"}), 400

        # Construct absolute path for the file to be deleted
        file_to_delete_path = os.path.abspath(os.path.join(image_library_root, file_relative_path))
        metadata_path = f"{file_to_delete_path}.meta"

        # IMPORTANT SECURITY CHECK: Ensure the file is actually within the TRASH_ROOT
        if not file_to_delete_path.startswith(TRASH_ROOT):
            return jsonify({"error": "Attempted to permanently delete file from outside trash folder"}), 403 # Forbidden

        if not os.path.isfile(file_to_delete_path):
            return jsonify({"error": "File not found or is not a file"}), 404

        os.remove(file_to_delete_path) # Delete the media file
        if os.path.exists(metadata_path): # Delete the metadata file if it exists
            os.remove(metadata_path)
        
        # Update count for the trash folder
        _update_folder_item_count_meta(TRASH_ROOT) # Decrement trash folder's count

        return jsonify({"message": f"File {file_relative_path} permanently deleted successfully"}), 200

    except Exception as e:
        print(f"An unexpected error occurred during permanent file deletion: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/restore_file', methods=['POST'])
def restore_file():
    """Restores a file from the trash folder to its original location."""
    try:
        data = request.get_json(silent=True)

        if data is None: # Corrected from 'data === None'
            return jsonify({"error": "Invalid or empty JSON body"}), 400

        trashed_file_relative_path = data.get('path') # e.g., "_Trash/trashed_image.jpg"

        if not trashed_file_relative_path:
            return jsonify({"error": "File path not provided"}), 400

        trashed_absolute_path = os.path.abspath(os.path.join(image_library_root, trashed_file_relative_path))
        metadata_path = f"{trashed_absolute_path}.meta"

        # Security check: Ensure the file is actually in the TRASH_ROOT
        if not trashed_absolute_path.startswith(TRASH_ROOT):
            return jsonify({"error": "Attempted to restore file from outside trash folder"}), 403 # Forbidden

        if not os.path.isfile(trashed_absolute_path):
            return jsonify({"error": "Trashed file not found or is not a file"}), 404
        
        if not os.path.exists(metadata_path):
            return jsonify({"error": "Metadata for trashed file not found. Cannot restore original path."}), 404

        # Read original path from metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        original_relative_path = metadata.get("original_relative_path")

        if not original_relative_path:
            return jsonify({"error": "Original path not found in metadata. Cannot restore."}), 500

        restore_destination_path = os.path.abspath(os.path.join(image_library_root, original_relative_path))
        
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(restore_destination_path), exist_ok=True)

        # Handle potential conflicts at the original destination
        final_restore_path = restore_destination_path
        if os.path.exists(restore_destination_path):
            base_name, ext = os.path.splitext(original_relative_path)
            timestamp = datetime.now().strftime("_%Y%m%d%H%M%S")
            # Reconstruct relative path for timestamped file
            dir_name = os.path.dirname(original_relative_path)
            new_filename = f"{os.path.basename(base_name)}{timestamp}{ext}"
            final_restore_relative_path = os.path.join(dir_name, new_filename)
            final_restore_path = os.path.abspath(os.path.join(image_library_root, final_restore_relative_path))
            print(f"Conflict at original path. Restoring to: {final_restore_relative_path}")


        # Move the file back to its original location (or a new timestamped one)
        shutil.move(trashed_absolute_path, final_restore_path)
        os.remove(metadata_path) # Delete the metadata file after successful restoration

        # Update counts for affected folders
        _update_folder_item_count_meta(TRASH_ROOT) # Decrement trash folder's count
        restore_destination_folder_path = os.path.dirname(final_restore_path)
        _update_folder_item_count_meta(restore_destination_folder_path) # Increment destination folder's count

        return jsonify({"message": f"File {trashed_file_relative_path} restored to {original_relative_path} successfully."}), 200

    except Exception as e:
        print(f"An unexpected error occurred during file restoration: {e}")
        return jsonify({"error": str(e)}), 500

# NEW: API endpoint to serve thumbnails
@app.route('/api/thumbnail/<path:filename>')
def serve_thumbnail(filename):
    """
    Generates and serves a thumbnail for the given media file.
    'filename' is the relative path of the original file from image_library_root.
    """
    original_file_path = os.path.abspath(os.path.join(image_library_root, filename))

    # Security check: Ensure the requested file is within the image_library_root
    if not original_file_path.startswith(image_library_root):
        abort(403) # Forbidden

    if not os.path.isfile(original_file_path):
        abort(404) # Not found

    # If it's a video, we don't generate a thumbnail on the server-side for now.
    # The client will use the video itself as a "thumbnail" or show a play icon.
    file_extension = os.path.splitext(original_file_path)[1].lower()
    if file_extension in VIDEO_EXTENSIONS:
        return send_from_directory(image_library_root, filename)

    # For images and RAW files, generate/retrieve thumbnail
    thumbnail_path = _generate_thumbnail(original_file_path)

    if thumbnail_path and os.path.exists(thumbnail_path):
        # Serve the generated thumbnail
        thumbnail_directory = os.path.dirname(thumbnail_path)
        thumbnail_basename = os.path.basename(thumbnail_path)
        return send_from_directory(thumbnail_directory, thumbnail_basename)
    else:
        # If thumbnail generation failed or path is invalid, return 404
        abort(404)


# Serve static files (the HTML and actual images/videos)
# This route serves files from the image_library_root.
# The HTML's imageLibraryBasePath should match how this route is configured.
@app.route('/<path:filename>')
def serve_static_files(filename):
    """Serves static files (images, etc.) directly from the image_library_root."""
    # This route handles requests like /2023/01/01/image.jpg or /_Trash/deleted_image.jpg
    # It sends the file from the image_library_root.
    full_path = os.path.join(image_library_root, filename)
    if os.path.isfile(full_path):
        return send_from_directory(image_library_root, filename)
    else:
        # Fallback for index.html if it's not in the root of image_library_root
        # This is typically for when server.py is in the same dir as index.html
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.isfile(os.path.join(base_dir, filename)):
            return send_from_directory(base_dir, filename)
        return "File not found", 404

# Route to serve the main HTML file
@app.route('/')
def serve_index():
    """Serves the main index.html file."""
    # Assuming index.html is in the same directory as server.py
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')


if __name__ == '__main__':
    # Perform initial scan and populate counts on server startup
    _initial_scan_and_populate_counts()
    # You can change the port if 5000 is in use
    app.run(host='0.0.0.0', debug=True, port=8080)
