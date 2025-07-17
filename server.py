# filename: server.py
import os
import shutil # Import shutil for moving files
import json   # Import json for reading/writing metadata
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS # Import CORS for cross-origin requests
from datetime import datetime # For timestamping restored files if needed
from PIL import Image, ExifTags # Import Pillow for image processing and ExifTags
from pillow_heif import register_heif_opener # Import register_heif_opener
import rawpy # NEW: Import rawpy for RAW file processing
import numpy as np # NEW: Import numpy for array manipulation

# Register the HEIF opener for Pillow
register_heif_opener()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing your HTML to fetch data

# --- Configuration for your Image Library ---
# Set this to the ABSOLUTE path of the directory that contains your YYYY (year) folders.
# Example: If your images are in /Users/YourUser/Pictures/MyPhotos/2023/01/01
# then image_library_root should be '/Users/YourUser/Pictures/MyPhotos'
# IMPORTANT: This should be the absolute path to your media folder.
# For example: '/Users/youruser/Pictures/MyPhotoLibrary' or 'C:\\Users\\youruser\\Pictures\\MyPhotoLibrary'
# Ensure this path is correct for your environment.
image_library_root = os.path.abspath('/Volumes/aa3025_bkp/Photos_Backup') # Hardcoded path as requested

# Define the trash folder name and its absolute path
TRASH_FOLDER_NAME = '_Trash'
TRASH_ROOT = os.path.join(image_library_root, TRASH_FOLDER_NAME)

# Define the thumbnail subfolder name (hidden) and max dimension
THUMBNAIL_SUBFOLDER_NAME = '.thumbnails'
THUMBNAIL_MAX_DIMENSION = 480 # Max width/height for thumbnails

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
# Added more common RAW formats for explicit handling
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.avif')
# Separated RAW extensions for specific rawpy handling
RAW_EXTENSIONS = ('.nef', '.nrw', '.cr2', '.cr3', '.crw', '.arw', '.srf', '.sr2',
                  '.orf', '.raf', '.rw2', '.raw', '.dng', '.kdc', '.dcr', '.erf',
                  '.3fr', '.mef', '.pef', '.x3f')

VIDEO_EXTENSIONS = ('.mp4', '.mov', '.webm', '.ogg', '.avi', '.mkv')
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + RAW_EXTENSIONS + VIDEO_EXTENSIONS # Combine all for general media check

# Helper function to get the path for a thumbnail
def get_thumbnail_full_path(original_full_path):
    """
    Generates the expected full path for a thumbnail.
    Thumbnails are stored in a hidden '.thumbnails' subfolder within the original file's directory.
    """
    original_dir = os.path.dirname(original_full_path)
    original_filename = os.path.basename(original_full_path)
    thumbnail_dir = os.path.join(original_dir, THUMBNAIL_SUBFOLDER_NAME)
    thumbnail_filename = original_filename # Keep original filename for thumbnail
    return os.path.join(thumbnail_dir, thumbnail_filename)

# Helper function to generate and save a thumbnail
def generate_and_save_thumbnail(original_full_path, thumbnail_full_path):
    """
    Generates a thumbnail for an image and saves it to the specified path.
    Creates the thumbnail directory if it doesn't exist.
    Corrects orientation based on EXIF data.
    Handles RAW files using rawpy for better quality.
    """
    try:
        # Ensure the thumbnail directory exists
        os.makedirs(os.path.dirname(thumbnail_full_path), exist_ok=True)
        
        file_extension = os.path.splitext(original_full_path)[1].lower()
        img = None # Initialize img to None

        if file_extension in RAW_EXTENSIONS:
            try:
                # Use rawpy to open and postprocess RAW files
                with rawpy.imread(original_full_path) as raw:
                    # Postprocess the RAW image to a renderable format (e.g., sRGB)
                    # use_camera_wb=True applies camera's white balance
                    # no_auto_bright=True prevents rawpy from doing its own auto-brightness
                    # output_bps=8 outputs 8-bit per channel (standard for JPEGs)
                    rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
                    img = Image.fromarray(rgb)
            except rawpy.LibRawError as e:
                print(f"rawpy error processing RAW file {original_full_path}: {e}")
                # Fallback to Pillow's default open if rawpy fails (might still fail, but worth a try)
                try:
                    img = Image.open(original_full_path)
                except Exception as e_pillow:
                    print(f"Pillow fallback also failed for RAW file {original_full_path}: {e_pillow}")
                    return False # Cannot process this file
            except Exception as e:
                print(f"General error processing RAW file {original_full_path} with rawpy: {e}")
                return False # Cannot process this file
        else:
            # For non-RAW image files (JPG, PNG, HEIC, etc.), use Pillow's default open
            try:
                img = Image.open(original_full_path)
            except Exception as e:
                print(f"Pillow error opening image file {original_full_path}: {e}")
                return False # Cannot process this file

        if img is None: # If img is still None, something went wrong
            return False

        # Correct orientation based on EXIF data (Pillow's method)
        try:
            exif = img._getexif()
            if exif:
                for orientation_tag in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation_tag] == 'Orientation':
                        break
                else:
                    orientation_tag = None

                if orientation_tag in exif:
                    orientation = exif[orientation_tag]
                    if orientation == 2:
                        img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 3:
                        img = img.transpose(Image.ROTATE_180)
                    elif orientation == 4:
                        img = img.transpose(Image.FLIP_TOP_BOTTOM)
                    elif orientation == 5:
                        img = img.transpose(Image.TRANSPOSE)
                    elif orientation == 6:
                        img = img.transpose(Image.ROTATE_270)
                    elif orientation == 7:
                        img = img.transpose(Image.TRANSVERSE)
                    elif orientation == 8:
                        img = img.transpose(Image.ROTATE_90)
                    
                    # Note: Removing EXIF orientation tag is complex without a dedicated library.
                    # For now, we rely on the rotation applied above.
        except Exception as e:
            print(f"Warning: Could not read/correct EXIF orientation for {original_full_path}: {e}")

        # Convert to RGB if not already (e.g., for PNGs with alpha channel or grayscale)
        if img.mode in ('RGBA', 'LA', 'P') or img.mode == 'L': # 'L' for grayscale
            img = img.convert('RGB')
        
        # Calculate new size maintaining aspect ratio
        img.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION), Image.Resampling.LANCZOS)
        
        # Save the thumbnail. Use JPEG for consistency and smaller file size,
        # unless original is GIF (which should remain GIF for animation).
        save_format = 'JPEG'
        if original_full_path.lower().endswith('.gif'):
            save_format = 'GIF'
        
        img.save(thumbnail_full_path, format=save_format)
        return True
    except Exception as e:
        print(f"Error generating thumbnail for {original_full_path}: {e}")
        return False

# Helper function to get directories and files in a given path
def get_contents_structured(path, is_trash_folder=False):
    """
    Lists directories and media files in a given path, returning structured data
    including original and thumbnail paths.
    """
    if not os.path.isdir(path):
        return {"directories": [], "files": []}
    
    directories = []
    files_data = [] # Will store dictionaries with original and thumbnail paths
    
    for item in os.listdir(path):
        full_path = os.path.join(path, item)
        # Exclude hidden files/directories (starting with '.') and metadata files
        if item.startswith('.') or item.endswith('.meta'):
            continue
        
        if os.path.isdir(full_path):
            directories.append(item)
        elif os.path.isfile(full_path):
            if item.lower().endswith(MEDIA_EXTENSIONS):
                # Construct relative path from image_library_root
                relative_path_from_root = os.path.relpath(full_path, image_library_root)
                
                file_info = {
                    "original_path": relative_path_from_root,
                    "filename": item # Add filename for convenience
                }

                if is_trash_folder:
                    # For trash, the "thumbnail" is still the trashed file itself,
                    # but we also need the original_path for restoration.
                    file_info["relative_path_in_trash"] = relative_path_from_root # This is the path in trash
                    file_info["thumbnail_path"] = relative_path_from_root # For trash, we serve the trashed file itself as thumbnail
                    # Load metadata to get the original_path for display in frontend
                    metadata_path = f"{full_path}.meta"
                    if os.path.exists(metadata_path):
                        try:
                            with open(metadata_path, 'r') as f:
                                metadata = json.load(f)
                            file_info["original_path_from_metadata"] = metadata.get("original_relative_path")
                        except Exception as e:
                            print(f"Error reading metadata for {item} in trash: {e}")
                            file_info["original_path_from_metadata"] = "Unknown Original Path"
                else:
                    # For non-trash images, provide a thumbnail URL
                    if item.lower().endswith(IMAGE_EXTENSIONS + RAW_EXTENSIONS): # Check against all image types
                        thumbnail_full_path = get_thumbnail_full_path(full_path)
                        # Construct relative path for thumbnail
                        thumbnail_relative_path = os.path.relpath(thumbnail_full_path, image_library_root)
                        file_info["thumbnail_path"] = thumbnail_relative_path
                    else: # For videos, thumbnail is the video itself for now
                        file_info["thumbnail_path"] = relative_path_from_root
                
                files_data.append(file_info)
    
    # Sort directories and files_data
    sorted_directories = sorted(directories)
    # Sort files_data by filename
    sorted_files_data = sorted(files_data, key=lambda x: x['filename'].lower())
    
    return {"directories": sorted_directories, "files": sorted_files_data}

# API endpoint to list years
@app.route('/api/years')
def list_years():
    """Lists all year directories (e.g., '2023', '2024') in the image_library_root."""
    years = []
    if os.path.isdir(image_library_root):
        for item in os.listdir(image_library_root):
            full_path = os.path.join(image_library_root, item)
            # Ensure it's a directory, is a 4-digit number, and is not the trash folder
            if os.path.isdir(full_path) and item.isdigit() and len(item) == 4 and item != TRASH_FOLDER_NAME:
                
                # Count media items for the year (recursive count)
                year_media_count = len(get_all_media_recursive(full_path))
                years.append({"year": item, "count": year_media_count})
    
    # Sort years by year number descending
    return jsonify(sorted(years, key=lambda x: x['year'], reverse=True))

# API endpoint to list months for a given year, and files within that year folder
@app.route('/api/months/<year>')
def list_months(year):
    """Lists all month directories and media files for a given year."""
    year_path = os.path.join(image_library_root, year)
    if not os.path.isdir(year_path):
        return jsonify({"error": "Year not found"}), 404
    
    contents = get_contents_structured(year_path)
    
    # Filter directories to ensure they are valid months (2 digits)
    valid_months = []
    for d in contents["directories"]:
        if d.isdigit() and len(d) == 2:
            month_path = os.path.join(year_path, d)
            month_media_count = len(get_all_media_recursive(month_path))
            valid_months.append({"month": d, "count": month_media_count})
    
    # Sort months numerically
    sorted_months = sorted(valid_months, key=lambda x: int(x['month']))

    return jsonify({"months": sorted_months, "files": contents["files"]})

# API endpoint to list days for a given year and month, and files within that month folder
@app.route('/api/days/<year>/<month>')
def list_days(year, month):
    """Lists all day directories and media files for a given year and month."""
    month_path = os.path.join(image_library_root, year, month)
    if not os.path.isdir(month_path):
        return jsonify({"error": "Month not found"}), 404
    
    contents = get_contents_structured(month_path)
    
    # Filter directories to ensure they are valid days (2 digits)
    valid_days = []
    for d in contents["directories"]:
        if d.isdigit() and len(d) == 2:
            day_path = os.path.join(month_path, d)
            day_media_count = len(get_all_media_recursive(day_path))
            valid_days.append({"day": d, "count": day_media_count})
    
    # Sort days numerically
    sorted_days = sorted(valid_days, key=lambda x: int(x['day']))

    return jsonify({"days": sorted_days, "files": contents["files"]})

# API endpoint to list photos for a given year, month, and day
@app.route('/api/photos/<year>/<month>/<day>')
def list_photos(year, month, day):
    """Lists all image and video files for a given year, month, and day."""
    day_path = os.path.join(image_library_root, year, month, day)
    if not os.path.isdir(day_path):
        return jsonify({"error": "Day not found"}), 404
    
    contents = get_contents_structured(day_path)
    
    return jsonify(contents["files"]) # Return the list of file info dictionaries

# NEW: API endpoint to get all media recursively for a given year
@app.route('/api/recursive_media/year/<year>')
def get_recursive_media_for_year(year):
    """Lists all media files recursively for a given year."""
    year_path = os.path.join(image_library_root, year)
    if not os.path.isdir(year_path):
        return jsonify({"error": "Year not found"}), 404
    
    # get_contents_structured is designed for single directory.
    # get_all_media_recursive is better for this.
    files_data = []
    for f_path in get_all_media_recursive(year_path):
        full_path = os.path.join(image_library_root, f_path)
        file_info = {
            "original_path": f_path,
            "filename": os.path.basename(f_path)
        }
        if f_path.lower().endswith(IMAGE_EXTENSIONS + RAW_EXTENSIONS): # Check against all image types
            thumbnail_full_path = get_thumbnail_full_path(full_path)
            thumbnail_relative_path = os.path.relpath(thumbnail_full_path, image_library_root)
            file_info["thumbnail_path"] = thumbnail_relative_path
        else: # For videos, thumbnail is the video itself for now
            file_info["thumbnail_path"] = f_path
        files_data.append(file_info)

    return jsonify(sorted(files_data, key=lambda x: x['original_path'].lower()))

# NEW: API endpoint to get all media recursively for a given year and month
@app.route('/api/recursive_media/month/<year>/<month>')
def get_recursive_media_for_month(year, month):
    """Lists all media files recursively for a given year and month."""
    month_path = os.path.join(image_library_root, year, month)
    if not os.path.isdir(month_path):
        return jsonify({"error": "Month not found"}), 404
    
    files_data = []
    for f_path in get_all_media_recursive(month_path):
        full_path = os.path.join(image_library_root, f_path)
        file_info = {
            "original_path": f_path,
            "filename": os.path.basename(f_path)
        }
        if f_path.lower().endswith(IMAGE_EXTENSIONS + RAW_EXTENSIONS): # Check against all image types
            thumbnail_full_path = get_thumbnail_full_path(full_path)
            thumbnail_relative_path = os.path.relpath(thumbnail_full_path, image_library_root)
            file_info["thumbnail_path"] = thumbnail_relative_path
        else: # For videos, thumbnail is the video itself for now
            file_info["thumbnail_path"] = f_path
        files_data.append(file_info)

    return jsonify(sorted(files_data, key=lambda x: x['original_path'].lower()))

# Helper function to recursively get all media files (original paths)
def get_all_media_recursive(path):
    """
    Recursively lists all media files (images and videos) in a given path and its subdirectories.
    Returns a list of relative file paths from image_library_root.
    This function specifically excludes thumbnails and trash.
    """
    all_files = []
    if not os.path.isdir(path):
        return []

    for root, dirs, files in os.walk(path):
        # Remove thumbnail directories from traversal
        dirs[:] = [d for d in dirs if d != THUMBNAIL_SUBFOLDER_NAME]

        current_relative_root = os.path.relpath(root, image_library_root)
        if current_relative_root == '.': # If root is the image_library_root itself
            current_relative_root = ''
        
        # Exclude trash folder content from recursive scans for regular views
        if TRASH_FOLDER_NAME in current_relative_root.split(os.sep):
            continue

        for file in files:
            if file.lower().endswith(MEDIA_EXTENSIONS) and not file.endswith('.meta'):
                # Construct the relative path from image_library_root
                if current_relative_root:
                    all_files.append(os.path.join(current_relative_root, file))
                else:
                    all_files.append(file)
    return sorted(all_files)


@app.route('/api/trash_content', methods=['GET'])
def list_trash_content():
    """Lists all files directly within the _Trash folder, including metadata."""
    if not os.path.isdir(TRASH_ROOT):
        return jsonify({"error": "Trash folder not found"}), 404
    try:
        files_data = []
        for item in os.listdir(TRASH_ROOT):
            full_path = os.path.join(TRASH_ROOT, item)
            if os.path.isfile(full_path) and item.lower().endswith(MEDIA_EXTENSIONS):
                file_info = {
                    "filename": item,
                    "relative_path_in_trash": os.path.relpath(full_path, image_library_root),
                    "thumbnail_path": os.path.relpath(full_path, image_library_root) # For trash, thumbnail is the trashed file itself
                }
                # Try to load metadata for original path
                metadata_path = f"{full_path}.meta"
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        file_info["original_path_from_metadata"] = metadata.get("original_relative_path")
                        # If a thumbnail was moved to trash with the original, its original path is also in metadata
                        file_info["original_thumbnail_relative_path_from_metadata"] = metadata.get("original_thumbnail_relative_path") # Changed key for clarity
                    except Exception as e:
                        print(f"Error reading metadata for {item} in trash: {e}")
                        file_info["original_path_from_metadata"] = "Unknown Original Path"
                files_data.append(file_info)
        
        # Sort by filename
        return jsonify({"files": sorted(files_data, key=lambda x: x['filename'].lower()), "count": len(files_data)})
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
        if not source_path.startswith(image_library_root) or TRASH_ROOT in source_path:
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

        # Handle thumbnail: if it exists, move it to trash too
        original_thumbnail_full_path = get_thumbnail_full_path(source_path)
        original_thumbnail_relative_path_in_trash = None # This will store the path of the thumbnail *in trash*
        if os.path.isfile(original_thumbnail_full_path):
            # Move the thumbnail to trash with a similar naming convention
            thumb_base_name, thumb_ext = os.path.splitext(os.path.basename(original_thumbnail_full_path))
            trashed_thumb_filename = f"{thumb_base_name}_thumb_{counter-1}{thumb_ext}" # Use same counter as original
            trashed_thumb_destination_path = os.path.abspath(os.path.join(TRASH_ROOT, trashed_thumb_filename))
            
            # Ensure unique name for thumbnail in trash
            thumb_counter_local = 0
            temp_trashed_thumb_destination_path = trashed_thumb_destination_path
            while os.path.exists(temp_trashed_thumb_destination_path):
                temp_trashed_thumb_filename = f"{thumb_base_name}_thumb_{counter-1}_{thumb_counter_local}{thumb_ext}"
                temp_trashed_thumb_destination_path = os.path.abspath(os.path.join(TRASH_ROOT, temp_trashed_thumb_filename))
                thumb_counter_local += 1
            
            shutil.move(original_thumbnail_full_path, temp_trashed_thumb_destination_path)
            original_thumbnail_relative_path_in_trash = os.path.relpath(temp_trashed_thumb_destination_path, image_library_root)
            print(f"Moved thumbnail to trash as {trashed_thumb_filename}")
            
            # Clean up empty thumbnail directory if it becomes empty
            thumb_dir = os.path.dirname(original_thumbnail_full_path)
            if os.path.exists(thumb_dir) and not os.listdir(thumb_dir): # Check if directory exists before listing
                os.rmdir(thumb_dir)
                print(f"Removed empty thumbnail directory: {thumb_dir}")

        # Create metadata file
        metadata = {
            "original_relative_path": file_relative_path,
            "trashed_filename": os.path.basename(destination_path) # Store the actual name it was trashed as
        }
        if original_thumbnail_relative_path_in_trash:
            metadata["original_thumbnail_relative_path"] = original_thumbnail_relative_path_in_trash

        metadata_path = f"{destination_path}.meta"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

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

        # Read metadata to check for associated thumbnail in trash
        associated_thumbnail_path_in_trash = None
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                associated_thumbnail_path_in_trash = metadata.get("original_thumbnail_relative_path")
            except Exception as e:
                print(f"Warning: Could not read metadata for {file_relative_path} to find associated thumbnail: {e}")

        os.remove(file_to_delete_path) # Delete the media file
        print(f"Permanently deleted: {file_to_delete_path}")

        if os.path.exists(metadata_path): # Delete the metadata file if it exists
            os.remove(metadata_path)
            print(f"Deleted metadata: {metadata_path}")
        
        # If an associated thumbnail was moved to trash, delete it too
        if associated_thumbnail_path_in_trash:
            full_associated_thumbnail_path = os.path.abspath(os.path.join(image_library_root, associated_thumbnail_path_in_trash))
            if os.path.isfile(full_associated_thumbnail_path) and full_associated_thumbnail_path.startswith(TRASH_ROOT):
                os.remove(full_associated_thumbnail_path)
                print(f"Permanently deleted associated thumbnail: {full_associated_thumbnail_path}")

        return jsonify({"message": f"File {file_relative_path} permanently deleted successfully"}), 200

    except Exception as e:
        print(f"An unexpected error occurred during permanent file deletion: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/restore_file', methods=['POST'])
def restore_file():
    """Restores a file from the trash folder to its original location."""
    try:
        data = request.get_json(silent=True)

        if data is None:
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

        # Read original path and original thumbnail path from metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        original_relative_path = metadata.get("original_relative_path")
        original_thumbnail_relative_path_in_trash = metadata.get("original_thumbnail_relative_path") # Get the path of the thumbnail *in trash*

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

        # Move the main file back
        shutil.move(trashed_absolute_path, final_restore_path)
        print(f"Restored file {trashed_absolute_path} to {final_restore_path}")

        # Restore associated thumbnail if it exists in trash and its original path is known
        if original_thumbnail_relative_path_in_trash:
            trashed_thumbnail_full_path = os.path.abspath(os.path.join(image_library_root, original_thumbnail_relative_path_in_trash))
            if os.path.isfile(trashed_thumbnail_full_path) and trashed_thumbnail_full_path.startswith(TRASH_ROOT):
                # Calculate the original thumbnail destination path based on the *restored* original file's path
                # This is crucial if the original file was restored to a new timestamped name
                restored_original_relative_path = os.path.relpath(final_restore_path, image_library_root)
                restored_original_full_path = final_restore_path # This is the absolute path of the restored original file
                
                # Get the expected thumbnail path for the *restored* original file
                expected_restored_thumbnail_full_path = get_thumbnail_full_path(restored_original_full_path)
                
                # Ensure the thumbnail's destination directory exists
                os.makedirs(os.path.dirname(expected_restored_thumbnail_full_path), exist_ok=True)
                
                # Move the thumbnail back
                shutil.move(trashed_thumbnail_full_path, expected_restored_thumbnail_full_path)
                print(f"Restored thumbnail {trashed_thumbnail_full_path} to {expected_restored_thumbnail_full_path}")

        os.remove(metadata_path) # Delete the metadata file after successful restoration

        return jsonify({"message": f"File {trashed_file_relative_path} restored to {original_relative_path} successfully."}), 200

    except Exception as e:
        print(f"An unexpected error occurred during file restoration: {e}")
        return jsonify({"error": str(e)}), 500


# NEW: API endpoint to serve thumbnails
@app.route('/api/thumbnail/<path:filename>')
def serve_thumbnail(filename):
    """
    Serves a thumbnail for the given filename.
    Generates the thumbnail if it doesn't exist.
    """
    original_full_path = os.path.abspath(os.path.join(image_library_root, filename))
    
    # Security check: Ensure the requested file is within image_library_root
    if not original_full_path.startswith(image_library_root):
        return "Forbidden", 403

    # If it's a video, just serve the original video (no thumbnail generation for videos yet)
    if filename.lower().endswith(VIDEO_EXTENSIONS):
        if os.path.isfile(original_full_path):
            return send_from_directory(os.path.dirname(original_full_path), os.path.basename(original_full_path))
        else:
            return "Video not found", 404

    # For images, handle thumbnail generation
    if not os.path.isfile(original_full_path):
        return "Image not found", 404

    thumbnail_full_path = get_thumbnail_full_path(original_full_path)

    # Check if thumbnail exists, if not, generate it
    if not os.path.isfile(thumbnail_full_path):
        print(f"Generating thumbnail for: {filename}")
        success = generate_and_save_thumbnail(original_full_path, thumbnail_full_path)
        if not success:
            # If thumbnail generation fails, fall back to serving the original image
            print(f"Failed to generate thumbnail for {filename}. Serving original image.")
            return send_from_directory(os.path.dirname(original_full_path), os.path.basename(original_full_path))

    # Serve the thumbnail
    return send_from_directory(os.path.dirname(thumbnail_full_path), os.path.basename(thumbnail_full_path))


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
    # You can change the port if 5000 is in use
    app.run(host='0.0.0.0', debug=True, port=8080)
