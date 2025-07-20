// --- Configuration for Image Library Path ---
export const TRASH_FOLDER_NAME = '_Trash'; // Keep this consistent with server.py

// Define image and video extensions for client-side check (matching server.py)
export const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.avif'];
export const RAW_EXTENSIONS = ['.nef', '.nrw', '.cr2', '.cr3', '.crw', '.arw', '.srf', '.sr2',
                          '.orf', '.raf', '.rw2', '.raw', '.dng', '.kdc', '.dcr', '.erf',
                          '.3fr', '.mef', '.pef', '.x3f'];
export const VIDEO_EXTENSIONS = ['.mp4', '.mov', '.webm', '.ogg', '.avi', '.mkv'];
export const MEDIA_EXTENSIONS = IMAGE_EXTENSIONS.concat(RAW_EXTENSIONS).concat(VIDEO_EXTENSIONS);

