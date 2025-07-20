// This module manages the dynamic state of the application.

// --- Navigation and Media State ---
export let currentPath = []; // Stores the current navigation path (e.g., ['2023', '01', '01'])
export let currentDisplayedMedia = []; // Stores the list of media objects currently displayed
export let currentMediaIndex = 0; // Index of the currently viewed media in the lightbox

// --- NEW: Multi-select State ---
export let selectedFiles = []; // Stores the paths of selected files for batch operations

// --- Slideshow State ---
export let slideshowInterval = null;
export let isSlideshowRunning = false;
export const slideshowDelay = 5000;

// --- Zoom and Pan State ---
export let isZoomed = false;
export let scale = 1;
export let position = { x: 0, y: 0 };
export let start = { x: 0, y: 0 };
export let isPanning = false;

// --- File/Folder Action State ---
export let fileToProcessPath = ''; // Stores the path of the file to be moved/deleted/restored
export let folderToProcessPath = []; // Stores the path of the folder to be deleted
export let isFolderDeletion = false; // Flag to differentiate between file and folder deletion

// --- Upload State ---
export let filesToUpload = [];
export let uploadedFilesCount = 0;

// --- State Modifier Functions ---

export function setCurrentPath(newPath) {
    currentPath = newPath;
}

export function setCurrentDisplayedMedia(media) {
    currentDisplayedMedia = media;
}

export function setCurrentMediaIndex(index) {
    currentMediaIndex = index;
}

export function setSelectedFiles(files) {
    selectedFiles = files;
}

export function setSlideshowInterval(interval) {
    slideshowInterval = interval;
}

export function setIsSlideshowRunning(isRunning) {
    isSlideshowRunning = isRunning;
}

export function setZoomState(newZoomState) {
    isZoomed = newZoomState.isZoomed;
    scale = newZoomState.scale;
    position = newZoomState.position;
    start = newZoomState.start;
    isPanning = newZoomState.isPanning;
}

export function setFileToProcessPath(path) {
    fileToProcessPath = path;
}

export function setFolderToProcessPath(path) {
    folderToProcessPath = path;
}

export function setIsFolderDeletion(isDeleting) {
    isFolderDeletion = isDeleting;
}

export function setFilesToUpload(files) {
    filesToUpload = files;
}

export function setUploadedFilesCount(count) {
    uploadedFilesCount = count;
}
