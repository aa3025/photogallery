# Local/Web Photo & Video Gallery Browser

This project provides a simple, self-hosted web application to browse your local image and video library, featuring a flexible folder structure, dynamic thumbnail generation for both images and videos, a full-screen lightbox viewer, slideshow capabilities, and a robust trash management system.

## Features

* **Flexible Folder-based Navigation:** Browse your media organized in any nested folder structure you prefer. The system is no longer restricted to a Year/Month/Day format.
* **Dynamic Thumbnail Generation:** Fast-loading, optimized thumbnails are generated on-demand for:
    * **Images:** Including HEIC and various RAW formats (NEF, CR2, ARW, etc.).
    * **Videos:** A frame is automatically extracted from `.MOV` and `.MP4` files to create a static preview.
* **Full-Resolution Lightbox:** Click any thumbnail to view the full-resolution image or play the video in a responsive, immersive lightbox.
* **Recursive Slideshow:** Start an automatic slideshow of all media within any selected folder and its subfolders.
* **Trash Management:** Move unwanted media to a dedicated `_Trash` folder, with options to permanently delete or restore files. Associated thumbnails and previews are correctly handled during these operations.
* **EXIF Orientation Correction:** Thumbnails are automatically rotated based on EXIF orientation data to display correctly.
* **Drag-and-Drop Uploads:** Easily upload new files directly to the folder you are currently viewing.
* **Dark/Light Theme Switching:** Toggle between themes for comfortable viewing.
* **Cross-Platform (Python-based):** Designed to run on any system where Python and its dependencies can be installed.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

* **Python 3.8+**: Download from [python.org](https://www.python.org/downloads/).
* **pip**: Python's package installer (usually comes with Python).
* **Homebrew (macOS users only)**: A package manager for macOS. Install it by running:
    ```bash
    /bin/bash -c "$(curl -fsSL [https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh](https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh))"
    ```
    Follow the on-screen instructions to add Homebrew to your PATH.
* **Xcode Command Line Tools (macOS users only)**: Essential for compiling many open-source libraries.
    ```bash
    xcode-select --install
    ```

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/aa3025/photogallery.git](https://github.com/aa3025/photogallery.git)
    cd photogallery
    ```

2.  **Install System-Level Dependencies (macOS users):**
    These libraries are crucial for `rawpy` and `pillow-heif` to function correctly.
    ```bash
    brew install libheif libraw pkg-config
    ```

3.  **Create a Python Virtual Environment (Recommended):**
    This isolates your project's dependencies from your system's Python installation.
    ```bash
    python3 -m venv gallery
    source gallery/bin/activate  # On Windows: .\gallery\Scripts\activate
    ```

4.  **Install Python Dependencies:**
    Install the required Python packages using pip. The `--no-binary :all:` flag for `pillow-heif` and `rawpy` is important to force compilation against your system's `libheif` and `libraw` installations.
    ```bash
    pip install Flask Flask-Cors Pillow numpy opencv-python-headless
    pip install pillow-heif --no-binary :all:
    pip install rawpy --no-binary :all:
    ```
    *Note: If you encounter build errors, ensure `libheif` and `libraw` are correctly installed via Homebrew (or your Linux package manager) and that Xcode Command Line Tools are installed on macOS.*

## Configuration

1.  **Set Your Image Library Root:**
    Open `server.py` in a text editor. Locate the `image_library_root` variable and update its value to the **absolute path** of your main photo library folder. This is the top-level folder you want the gallery to display.
    ```python
    # server.py
    image_library_root = os.path.abspath('/path/to/your/photos') # <--- UPDATE THIS PATH
    ```
    *Example for Windows:* `image_library_root = os.path.abspath('C:\\Users\\YourUser\\Pictures\\MyPhotos')`

## Running the Application

1.  **Activate your virtual environment** (if you haven't already):
    ```bash
    source gallery/bin/activate  # On Windows: .\gallery\Scripts\activate
    ```

2.  **Start the Flask Server:**
    ```bash
    python server.py
    ```
    The server will perform a one-time scan to count media in your folders and will then start, typically on `http://127.0.0.1:8080`.

3.  **Access the Gallery:**
    Open your web browser and navigate to the address provided by the Flask server (e.g., `http://127.0.0.1:8080`).

## Thumbnail Management

The application dynamically generates thumbnails on demand. They are stored in hidden `.thumbnails` subfolders within the same directory as the original media.

* **Forcing Thumbnail Regeneration:** If you update media files or want to regenerate all thumbnails (e.g., after adding video support):
    1.  **Stop the `server.py` application** (Ctrl+C in the terminal).
    2.  **Delete all `.thumbnails` folders** within your `image_library_root`.
        * **macOS/Linux:**
            ```bash
            find "/path/to/your/photos" -name ".thumbnails" -type d -exec rm -rf {} +
            ```
            *(Replace `"/path/to/your/photos"` with your actual `image_library_root` path)*
        * **Windows (PowerShell):**
            ```powershell
            Get-ChildItem -Path "C:\path\to\your\photos" -Recurse -Directory -Hidden -Filter ".thumbnails" | Remove-Item -Recurse -Force
            ```
            *(Replace `"C:\path\to\your\photos"` with your actual `image_library_root` path)*
    3.  **Restart `server.py`**. Thumbnails will be regenerated as you browse.
    4.  **Perform a hard refresh** in your browser (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows/Linux) to clear its cache.

## Usage

* **Navigation:** Click on any folder to navigate into it. Use the breadcrumb trail or the "Home" icon to navigate back up.
* **Lightbox:** Click on any thumbnail to open the full-resolution viewer.
    * Use the on-screen arrows or your keyboard's arrow keys to navigate between media items.
    * Click the 'X' button or press 'Escape' to close.
* **Slideshow:** When viewing any folder, click the "Play" button in the top right to start a slideshow of all media within that folder and its subfolders.
* **Trash Management:**
    * **Move to Trash:** From the lightbox view, click the trash can icon.
    * **Delete Forever/Restore:** Navigate to the `_Trash` folder from the root view. Open a trashed item in the lightbox to see options for permanent deletion or restoration.

## Troubleshooting

* **"No folders found" on first launch:** Ensure the `image_library_root` path in `server.py` is correct and that the server has read permissions for that directory.
* **"cannot identify image file" for HEIC/RAW (in server logs):**
    * Verify `libheif` and `libraw` are installed via Homebrew (macOS).
    * Ensure `pillow-heif` and `rawpy` were installed using the `--no-binary :all:` flag.
* **Video thumbnails not generating:** Ensure `opencv-python-headless` is installed in your virtual environment.
* **Incorrect thumbnail orientation:** Delete the `.thumbnails` folder within the affected directory and restart the server to force regeneration.
