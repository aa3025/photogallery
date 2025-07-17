
# Local/Web Photo/Video Gallery Browser

This project provides a simple, self-hosted web application to browse your local image and video library, featuring dynamic thumbnail generation, a full-screen lightbox viewer, slideshow capabilities, and a trash management system.

## Features

* **Folder-based Navigation:** Browse your media organized by Year, Month, and Day folders.

* **Dynamic Thumbnail Generation:** Smaller, optimized thumbnails are generated on demand for images (including HEIC and various RAW formats like NEF, CR2, RAF, RW2) to ensure fast loading in the gallery view.

* **Full-Resolution Lightbox:** Click on any thumbnail to view the full-resolution image or play the video in a responsive, immersive lightbox.

* **Slideshow:** Start an automatic slideshow of media within any selected folder (Year, Month, or Day).

* **Trash Management:** Move unwanted media to a dedicated `_Trash` folder, with options to permanently delete or restore files.

* **EXIF Orientation Correction:** Thumbnails are automatically rotated based on EXIF orientation data to display correctly.

* **Cross-Platform (Python-based):** Designed to run on any system where Python and its dependencies can be installed (tested on macOS).
  
* Demo: http://143.47.246.212:8080 (NOT https:// !)

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
    pip install Flask Flask-Cors Pillow numpy
    pip install pillow-heif --no-binary :all:
    pip install rawpy --no-binary :all:
    ```

    *Note: If you encounter build errors for `pillow-heif` or `rawpy`, ensure `libheif` and `libraw` (and their respective development headers) are correctly installed via Homebrew (or your Linux package manager) and that Xcode Command Line Tools are installed on macOS.*

## Configuration

1.  **Set Your Image Library Root:**
    Open `server.py` in a text editor. Locate the `image_library_root` variable and update its value to the **absolute path** of your main photo library folder. This is the folder that contains your year (e.g., `2023`, `2024`) directories.

    ```python
    # server.py
    image_library_root = os.path.abspath('/Volumes/my/photos') # <--- UPDATE THIS PATH
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

    The server will typically start on `http://127.0.0.1:8080` (or `localhost:8080`). You will see output in your terminal indicating the server is running.

3.  **Access the Gallery:**
    Open your web browser and navigate to the address provided by the Flask server (e.g., `http://127.0.0.1:8080`).

## Thumbnail Management

The application dynamically generates thumbnails on demand. They are stored in hidden `.thumbnails` subfolders within the same directory as the original media.

* **Forcing Thumbnail Regeneration:** If you update `server.py` (e.g., for new features like RAW support or orientation fixes), existing thumbnails might be outdated. To force the server to regenerate them:

    1.  **Stop the `server.py` application** (Ctrl+C in the terminal).

    2.  **Delete all `.thumbnails` folders** within your `image_library_root`.

        * **macOS/Linux:**

            ```bash
            find "/Volumes/my/photos" -name ".thumbnails" -type d -exec rm -rf {} +
            ```

            *(Replace `"/Volumes/my/photos"` with your actual `image_library_root` path)*

        * **Windows (PowerShell):**

            ```powershell
            Get-ChildItem -Path "C:\path\to\your\Photos_Backup" -Recurse -Directory -Hidden -Filter ".thumbnails" | Remove-Item -Recurse -Force
            ```

            *(Replace `"C:\path\to\your\Photos_Backup"` with your actual `image_library_root` path)*

    3.  **Restart `server.py`**.

    4.  **Perform a hard refresh** in your browser (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows/Linux) to clear the browser's cache.

## Usage

* **Navigation:** Click on year, month, and day folders to drill down into your media.

* **Media View:** Thumbnails will load with a fade-in effect.

* **Lightbox:** Click on any thumbnail to open the full-resolution image or video in a full-screen viewer.

    * Use the left/right arrows or keyboard arrow keys to navigate between media items.

    * Click the 'X' button or press 'Escape' to close the lightbox.

* **Slideshow:** When viewing a day, month, or year folder, click the "Play" button in the top right corner to start an automatic slideshow. Click again to pause.

* **Trash:** Access the `_Trash` folder from the main "Years" view.

    * **Move to Trash:** When viewing a media item in the lightbox (outside the `_Trash` folder), click the "Delete" (trash can) icon to move it to the `_Trash` folder.

    * **Delete Forever:** When viewing a media item in the lightbox *within* the `_Trash` folder, click the "Delete" (trash can) icon to permanently remove it. **This action cannot be undone.**

    * **Restore:** When viewing a media item in the lightbox *within* the `_Trash` folder, click the "Restore" icon to move it back to its original location.

## Troubleshooting

* **"Error loading years. Is the server running?"**: Ensure `server.py` is running in your terminal and that the `image_library_root` path in `server.py` is correct and accessible.

* **"cannot identify image file" for HEIC/RAW (in server logs):**

    * Verify `libheif` and `libraw` are installed via Homebrew (macOS).

    * Ensure `pillow-heif` and `rawpy` are installed in your Python environment using `pip install --no-binary :all:`.

    * Delete old `.thumbnails` folders and restart `server.py`.

* **Thumbnails have incorrect orientation:** Delete old `.thumbnails` folders and restart `server.py` to force regeneration with EXIF correction.

* **Files not appearing:** Check file permissions for your `image_library_root` and its subfolders. Ensure `server.py` has read access.

* **Slow performance despite thumbnails:** Ensure your browser cache is cleared. If still slow, consider reducing `THUMBNAIL_MAX_DIMENSION` in `server.py` (though 480px is generally a good balance).
````
