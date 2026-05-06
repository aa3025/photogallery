# 📸 Photo & Video Gallery



A self-hosted, web-based gallery application for browsing and managing a personal library of photos and videos. Built with a Python Flask backend and a modern vanilla JavaScript frontend.


Demo: http://143.47.246.212:8080 

![Screenshot](gallery.jpeg)
---

## 🔑 Key Features

- **Folder-Based Browsing**: Navigate your media library through a familiar folder structure (e.g., `Year > Month > Day`). Upload files with drag-n-drop or using upload button into any folder.
- **Wide Format Support**: Handles common image (`.jpg`, `.png`, `.webp`), video (`.mp4`, `.mov`), and various camera RAW formats (`.nef`, `.cr2`, `.dng`, etc.).
- **HEIC Support**: Automatically converts Apple's `.heic` format for web viewing on the fly.
- **Automatic Thumbnail Generation**: Fast-loading `.webp` thumbnails are created automatically for all media types.
- **Interactive Lightbox**: View media in a fullscreen overlay with smooth zoom, pan, and keyboard navigation.
- **Recursive Slideshow**: Start a slideshow from any folder to view all media within it and its subfolders. Root-level files are intelligently played first.

### 🗑️ Trash System

- Move individual files, multiple files, or entire folders to a dedicated Trash folder.
- Restore individual or selected items from the trash to their original locations.
- Permanently delete selected items from the trash.

### 🧰 Multi-Select

- Select multiple files in the gallery view to perform batch actions (delete, restore, permanent delete, or add to album).
- Use drag-select with a rectangle to add groups of tiles quickly, including auto-scroll near the viewport edges.
- Clear the current selection with `Esc` or the `Deselect All` toolbar button.

### 🖼️ Virtual Albums

- Create albums directly in the app.
- Add selected items from any folder into an album.
- Remove items from an album without deleting the underlying media file.
- Album data is stored in a JSON database, typically `${GALLERY_PATH}/albums.json`.

### 🗂️ File & Folder Management

- Upload files directly to the current folder via a file selector or drag-and-drop.
- Create new subfolders.

### 🎨 Customizable Theme

- Toggle between a sleek dark mode and a clean light mode.

---

## ⚙️ Technology Stack

- **Backend**: Python 3, Flask  
- **Image/Video Processing**: Pillow, OpenCV, rawpy, pillow-heif  
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (ES6 Modules)  
- **Styling**: Tailwind utility stylesheet plus custom CSS  

---

## 🛠️ Setup and Installation

Follow these steps to get the gallery running on your local machine.

### 1. Prerequisites

- Python 3.7+
- `pip` (Python package installer)
- `openssl` (for generating SSL certificates)

### 2. Backend Setup

**Clone the Repository:**

```bash
git clone https://github.com/aa3025/photogallery
cd photogallery
````

`requirements.txt` is already included in this repository.

**Preferred startup flow:**

```bash
./start_server.sh
```

On first run, this script:

- creates `.venv` if missing
- installs dependencies from `requirements.txt`
- creates `.gallery.env` with placeholder values if it does not exist

Then update `.gallery.env` with real values:

```bash
export GALLERY_USERNAME='your_username'
export GALLERY_PASSWORD='your_strong_password'
export GALLERY_PATH='/absolute/path/to/your/gallery'
export GALLERY_PORT='8080'
export GALLERY_ALBUMS_DB_PATH="${GALLERY_PATH}/albums.json"
```

**Manual dependency install (optional):**

```bash
pip3 install -r requirements.txt
```

If you have trouble installing `opencv-python`, you can disable the `import cv2` line near the top of `server.py`.
It is only needed for video thumbnail generation.

### 3. Runtime Configuration

`server.py` still contains fallback placeholder defaults, but the active runtime configuration should come from environment variables or `.gallery.env`.

Required variables:

```bash
export GALLERY_USERNAME='your_username'
export GALLERY_PASSWORD='your_strong_password'
export GALLERY_PATH='/absolute/path/to/your/gallery'
```

Optional runtime variables:

```bash
export GALLERY_PORT='8080'
export FLASK_DEBUG=0
export GALLERY_SSL_CERT='/absolute/path/to/cert.pem'
export GALLERY_SSL_KEY='/absolute/path/to/key.pem'
export GALLERY_ALBUMS_DB_PATH="${GALLERY_PATH}/albums.json"
```

**(Optional) Set Up SSL (for HTTPS):**

Generate a self-signed certificate:

```bash
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

> Press `Enter` to accept the defaults for all prompts.

If `GALLERY_SSL_CERT` and `GALLERY_SSL_KEY` are not set, the app runs over HTTP.

---

### 4. Frontend Setup

Folder named `static` in your project root contains all frontend files.

```
/photogallery
|-- server.py
|-- cert.pem
|-- key.pem
|-- requirements.txt
|-- /static
    |-- index.html
    |-- main.js
    |-- styles.css
    |-- api.js
    |-- ... (other .js files)
```

---

### 5. Running the Application

Preferred:

```bash
./start_server.sh
```

Manual alternative, from the project root after your environment is configured:

```bash
python3 server.py
```

The server will perform a one-time scan to index your folders.

To stop the app:

```bash
./kill_server.sh
```

Once running, open your browser and visit:

```
http://localhost:8080
```

(there is also an option to serve via HTTPS when `GALLERY_SSL_CERT` and `GALLERY_SSL_KEY` are set)

---

## 🧪 API Endpoints

| Method   | Endpoint                      | Description                                      |
| -------- | ----------------------------- | ------------------------------------------------ |
| `GET`    | `/api/folders/<path>`         | Gets subfolders and media files for a given path |
| `GET`    | `/api/recursive_media/<path>` | Gets all media files recursively from a path     |
| `GET`    | `/api/media/<path>`           | Serves a specific media file (RAW/HEIC to WEBP)  |
| `GET`    | `/api/thumbnail/<path>`       | Serves a generated thumbnail for a media file    |
| `GET`    | `/api/albums`                 | Lists all virtual albums                         |
| `GET`    | `/api/albums/<path>`          | Gets media in a specific album                   |
| `POST`   | `/api/albums`                 | Creates a new album                              |
| `POST`   | `/api/albums/add`             | Adds media paths to an album                     |
| `POST`   | `/api/albums/remove`          | Removes media paths from an album                |
| `POST`   | `/api/move_to_trash`          | Moves a file to the trash                        |
| `POST`   | `/api/restore_file`           | Restores a single file from the trash            |
| `DELETE` | `/api/delete_file_forever`    | Permanently deletes a file from the trash        |
| `POST`   | `/api/delete_multiple`        | Deletes or permanently deletes multiple files    |
| `POST`   | `/api/restore_multiple`       | Restores multiple files from trash               |
| `POST`   | `/api/upload_file`            | Handles file uploads                             |
| `POST`   | `/api/create_folder`          | Creates a new folder                             |
| `GET`    | `/api/trash_content`          | Gets the list of all files in the trash          |
| `POST`   | `/api/empty_trash`            | Permanently deletes all items in the trash       |
| `POST`   | `/api/restore_all`            | Restores all items from the trash                |


---

Initially created with the help of Google Gemini 2.5 Flash (it was a struggle :) and improved using GitHub CoPilot (way easier).
