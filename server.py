# filename: server.py
import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS # Import CORS for cross-origin requests

app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing your HTML to fetch data

# --- Configuration for your Image Library ---
# Set this to the ABSOLUTE path of the directory that contains your YYYY (year) folders.
# Example: If your images are in /Users/YourUser/Pictures/MyPhotos/2023/01/01
# then image_library_root should be '/Users/YourUser/Pictures/MyPhotos'
image_library_root = '/Volumes/My_Gallery' # <<<-------------------------------IMPORTANT: CHANGE THIS PATH!

# Ensure the image_library_root exists
if not os.path.isdir(image_library_root):
    print(f"Warning: Image library root '{image_library_root}' does not exist or is not a directory.")
    print("Please update the 'image_library_root' variable in server.py to your actual image folder path.")
    # You might want to exit or handle this more gracefully in a production app
    # For now, we'll let it run but it won't find any images.

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
        if os.path.isdir(full_path):
            directories.append(item)
        elif os.path.isfile(full_path):
            if item.lower().endswith(MEDIA_EXTENSIONS):
                files.append(item)
    
    return {"directories": sorted(directories), "files": sorted(files)}

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
            if os.path.isdir(full_path) and item.isdigit() and len(item) == 4:
                years.append(item)
    return jsonify(sorted(years))

# API endpoint to list months for a given year, and files within that year folder
@app.route('/api/months/<year>')
def list_months(year):
    """Lists all month directories and media files for a given year."""
    year_path = os.path.join(image_library_root, year)
    contents = get_contents_structured(year_path)
    
    # Filter directories to ensure they are valid months (2 digits)
    valid_months = [d for d in contents["directories"] if d.isdigit() and len(d) == 2]
    
    return jsonify({"months": sorted(valid_months), "files": contents["files"]})

# API endpoint to list days for a given year and month, and files within that month folder
@app.route('/api/days/<year>/<month>')
def list_days(year, month):
    """Lists all day directories and media files for a given year and month."""
    month_path = os.path.join(image_library_root, year, month)
    contents = get_contents_structured(month_path)
    
    # Filter directories to ensure they are valid days (2 digits)
    valid_days = [d for d in contents["directories"] if d.isdigit() and len(d) == 2]

    return jsonify({"days": sorted(valid_days), "files": contents["files"]})

# API endpoint to list photos for a given year, month, and day
@app.route('/api/photos/<year>/<month>/<day>')
def list_photos(year, month, day):
    """Lists all image and video files for a given year, month, and day."""
    day_path = os.path.join(image_library_root, year, month, day)
    # For day folders, we only expect files, not subdirectories.
    # So, we can reuse get_contents_structured and just return the files.
    contents = get_contents_structured(day_path)
    return jsonify(contents["files"])

# Serve static files (the HTML and actual images/videos)
# This route serves files from the image_library_root.
# The HTML's imageLibraryBasePath should match how this route is configured.
@app.route('/<path:filename>')
def serve_static_files(filename):
    """Serves static files (images, etc.) directly from the image_library_root."""
    # This route handles requests like /2023/01/01/image.jpg or /2023/01/01/video.mp4
    # It sends the file from the image_library_root.
    return send_from_directory(image_library_root, filename)

# Route to serve the main HTML file
@app.route('/')
def serve_index():
    """Serves the main index.html file."""
    # Assuming index.html is in the same directory as server.py
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')


if __name__ == '__main__':
    # You can change the port if 5000 is in use
    app.run(debug=True, port=5000)
