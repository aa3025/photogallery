# filename: server.py
import os
import shutil # Import shutil for moving files
import json   # Import json for reading/writing metadata
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS # Import CORS for cross-origin requests
from datetime import datetime # For timestamping restored files if needed

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
MEDIA_EXTENSIONS = (
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.avif', # Common, HEIC, and AVIF
    '.nef', '.nrw', # Nikon Raw
    '.cr2', '.cr3', '.crw', # Canon Raw
    '.arw', '.srf', '.sr2', # Sony Raw
    '.orf', # Olympus Raw
    '.raf', # Fuji Raw
    '.rw2', '.raw', # Panasonic / Leica Raw
    '.dng', # Adobe Digital Negative (common raw format)
    '.kdc', # Kodak Raw
    '.dcr', # Kodak Raw
    '.erf', # Epson Raw
    '.3fr', # Hasselblad Raw
    '.mef', # Mamiya Raw
    '.pef', # Pentax Raw
    '.x3f', # Sigma Raw
    '.mp4', '.mov', '.webm', '.ogg', '.avi', '.mkv' # Added common video formats
)

# Helper function to get directories and files in a given path
def get_contents_structured(path):
    """
    Lists directories and files in a given path.
    Returns a dictionary: {"directories": [...], "files": [...]}.
    """
    if not os.path.isdir(path):
        return {"directories": [], "files": []}
    
    directories = []
    files = []
    
    for item in os.listdir(path):
        full_path = os.path.join(path, item)
        # Exclude hidden files/directories (starting with '.')
        # Also exclude metadata files (ending with .meta)
        if item.startswith('.') or item.endswith('.meta'):
            continue
        if os.path.isdir(full_path):
            directories.append(item)
        elif os.path.isfile(full_path):
            # Only include files with allowed media extensions
            if item.lower().endswith(MEDIA_EXTENSIONS):
                files.append(item)
    
    return {"directories": sorted(directories), "files": sorted(files)}

# Helper function to get files (images/videos)
# This function is defined globally and used by list_trash_content
def get_files(path):
    # This function uses the globally defined MEDIA_EXTENSIONS
    # Exclude metadata files here too
    return sorted([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.lower().endswith(MEDIA_EXTENSIONS) and not f.endswith('.meta')])


# API endpoint to list years
@app.route('/api/years')
def list_years():
    """Lists all year directories (e.g., '2023', '2024') in the image_library_root."""
    # Years should only contain directories that look like years (4 digits)
    # Files directly in the root are not part of the YYYY/MM/DD structure for this view
    
    # Reusing the original get_contents logic for years to ensure only year directories are returned
    years = []
    if os.path.isdir(image_library_root):
        for item in os.listdir(image_library_root):
            full_path = os.path.join(image_library_root, item)
            # Ensure it's a directory, is a 4-digit number, and is not the trash folder
            if os.path.isdir(full_path) and item.isdigit() and len(item) == 4 and item != TRASH_FOLDER_NAME:
                years.append(item)
    return jsonify(sorted(years))

# API endpoint to list months for a given year, and files within that year folder
@app.route('/api/months/<year>')
def list_months(year):
    """Lists all month directories and media files for a given year."""
    year_path = os.path.join(image_library_root, year)
    if not os.path.isdir(year_path):
        return jsonify({"error": "Year not found"}), 404
    
    contents = get_contents_structured(year_path)
    
    # Filter directories to ensure they are valid months (2 digits)
    valid_months = [d for d in contents["directories"] if d.isdigit() and len(d) == 2]
    
    return jsonify({"months": sorted(valid_months), "files": contents["files"]})

# API endpoint to list days for a given year and month, and files within that month folder
@app.route('/api/days/<year>/<month>')
def list_days(year, month):
    """Lists all day directories and media files for a given year and month."""
    month_path = os.path.join(image_library_root, year, month)
    if not os.path.isdir(month_path):
        return jsonify({"error": "Month not found"}), 404
    
    contents = get_contents_structured(month_path)
    
    # Filter directories to ensure they are valid days (2 digits)
    valid_days = [d for d in contents["directories"] if d.isdigit() and len(d) == 2]

    return jsonify({"days": sorted(valid_days), "files": contents["files"]})

# API endpoint to list photos for a given year, month, and day
@app.route('/api/photos/<year>/<month>/<day>')
def list_photos(year, month, day):
    """Lists all image and video files for a given year, month, and day."""
    day_path = os.path.join(image_library_root, year, month, day)
    if not os.path.isdir(day_path):
        return jsonify({"error": "Day not found"}), 404
    
    # For day folders, we only expect files, not subdirectories.
    # So, we can reuse get_contents_structured and just return the files.
    contents = get_contents_structured(day_path)
    return jsonify(contents["files"])

@app.route('/api/trash_content', methods=['GET'])
def list_trash_content():
    """Lists all files directly within the _Trash folder."""
    if not os.path.isdir(TRASH_ROOT):
        return jsonify({"error": "Trash folder not found"}), 404
    try:
        files = get_files(TRASH_ROOT) # get_files already filters by extension and excludes .meta
        return jsonify(files)
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

        # Create metadata file
        metadata = {"original_relative_path": file_relative_path}
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

        os.remove(file_to_delete_path) # Delete the media file
        if os.path.exists(metadata_path): # Delete the metadata file if it exists
            os.remove(metadata_path)
        
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

        return jsonify({"message": f"File {trashed_file_relative_path} restored to {original_relative_path} successfully."}), 200

    except Exception as e:
        print(f"An unexpected error occurred during file restoration: {e}")
        return jsonify({"error": str(e)}), 500


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
    app.run(host='0.0.0.0', debug=True, port=5000)

