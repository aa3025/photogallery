// This module handles all communication with the backend API.

/**
 * Fetches folder and file data from a specific path.
 * @param {string[]} pathSegments - The path to fetch content from.
 * @returns {Promise<object>} - A promise that resolves with the folder and file data.
 */
export async function getFolders(pathSegments = []) {
    const path = pathSegments.join('/');
    const url = path ? `/api/folders/${path}` : '/api/folders';
    const response = await fetch(url);
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, response: ${errorText}`);
    }
    return response.json();
}

/**
 * Fetches all media files recursively from a given path.
 * @param {string[]} pathSegments - The path to fetch recursive media from.
 * @returns {Promise<object>} - A promise that resolves with the media file list.
 */
export async function getRecursiveMedia(pathSegments = []) {
    const path = pathSegments.join('/');
    const url = path ? `/api/recursive_media/${path}` : '/api/recursive_media';
    const response = await fetch(url);
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, response: ${errorText}`);
    }
    return response.json();
}

/**
 * Fetches the content of the trash folder.
 * @returns {Promise<object>} - A promise that resolves with the trash content data.
 */
export async function getTrashContent() {
    const response = await fetch('/api/trash_content');
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, response: ${errorText}`);
    }
    return response.json();
}

/**
 * Sends a request to move a file to the trash.
 * @param {string} filePath - The relative path of the file to trash.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function moveFileToTrash(filePath) {
    const response = await fetch('/api/move_to_trash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath }),
    });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}

/**
 * Sends a request to permanently delete a file from the trash.
 * @param {string} filePath - The relative path of the file to delete.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function deleteFileForever(filePath) {
    const response = await fetch('/api/delete_file_forever', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath }),
    });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}

/**
 * Sends a request to restore a file from the trash.
 * @param {string} filePath - The relative path of the file to restore.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function restoreFile(filePath) {
    const response = await fetch('/api/restore_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath }),
    });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}

/**
 * Sends a request to move an entire folder to the trash.
 * @param {string[]} folderPathArray - The path segments of the folder to delete.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function deleteFolder(folderPathArray) {
    const response = await fetch('/api/delete_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: folderPathArray }),
    });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}

/**
 * Sends a request to empty the entire trash folder.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function emptyTrash() {
    const response = await fetch('/api/empty_trash', { method: 'POST' });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}

/**
 * Sends a request to restore all files from the trash.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function restoreAll() {
    const response = await fetch('/api/restore_all', { method: 'POST' });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}

/**
 * Sends a request to create a new folder.
 * @param {string[]} parentPath - The path where the new folder should be created.
 * @param {string} folderName - The name of the new folder.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function createFolder(parentPath, folderName) {
    const response = await fetch('/api/create_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            parent_path: parentPath,
            folder_name: folderName
        }),
    });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}

/**
 * Uploads a single file to the server.
 * @param {File} file - The file to upload.
 * @param {string[]} currentPath - The destination path for the upload.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function uploadFile(file, currentPath) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('current_path', JSON.stringify(currentPath));

    const response = await fetch('/api/upload_file', {
        method: 'POST',
        body: formData,
    });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}

/**
 * NEW: Sends a request to delete multiple files.
 * @param {string[]} paths - An array of relative file paths to delete.
 * @param {boolean} isPermanent - Whether to delete permanently from trash.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function deleteMultiple(paths, isPermanent) {
    const response = await fetch('/api/delete_multiple', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths, is_permanent: isPermanent }),
    });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}

/**
 * NEW: Sends a request to restore multiple files from trash.
 * @param {string[]} paths - An array of relative file paths to restore.
 * @returns {Promise<object>} - A promise that resolves with the server's response.
 */
export async function restoreMultiple(paths) {
    const response = await fetch('/api/restore_multiple', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths }),
    });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
    }
    return response.json();
}