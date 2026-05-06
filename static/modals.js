// This module handles the logic for all modals: confirmation, create folder, and upload.

import * as state from './state.js';
import dom from './dom-elements.js';
import * as api from './api.js';
import * as ui from './ui.js';
import * as config from './config.js';
import { closeLightbox, updateLightboxMedia } from './lightbox.js';

let onNavigateCallback;

// --- Confirmation Modal ---
export function showConfirmationModal(actionTarget, isPermanentDelete = false, isRestore = false, isFolderAction = false) {
    state.setIsAlbumRemoval(false);
    state.setAlbumToProcessName('');
    state.setIsFolderDeletion(isFolderAction);
    if (state.isFolderDeletion) {
        state.setFolderToProcessPath(actionTarget);
        state.setFileToProcessPath('');
    } else {
        state.setFileToProcessPath(actionTarget);
        state.setFolderToProcessPath([]);
    }

    let msg = '', btnText = '';

    if (Array.isArray(actionTarget) && isRestore) {
        const count = actionTarget.length;
        msg = `Are you sure you want to restore ${count} selected item(s)?`;
        btnText = `Restore ${count} Item(s)`;
    } else if (Array.isArray(actionTarget) && typeof actionTarget[0] === 'string') {
        const count = actionTarget.length;
        const permanentText = isPermanentDelete ? " permanently" : "";
        msg = `Are you sure you want to${permanentText} delete ${count} selected item(s)?`;
        btnText = `Delete ${count} Item(s)`;
    }
    else if (isRestore) {
        msg = "Are you sure you want to restore this file?";
        btnText = "Restore";
    } else if (isPermanentDelete) {
        msg = "Are you sure you want to permanently delete this? This action cannot be undone.";
        btnText = "Delete Forever";
    } else if (state.isFolderDeletion) {
        msg = `Delete folder "${actionTarget.join('/')}" and move its contents to Trash?`;
        btnText = "Delete Folder";
    } else {
        msg = "Are you sure you want to move this file to Trash?";
        btnText = "Move to Trash";
    }

    dom.confirmationMessage.textContent = msg;
    dom.confirmActionBtn.textContent = btnText;
    dom.confirmationModalOverlay.classList.add('active');
}

function hideConfirmationModal() {
    dom.confirmationModalOverlay.classList.remove('active');
}

export function showRemoveFromAlbumConfirmation(actionTarget, albumName) {
    state.setIsAlbumRemoval(true);
    state.setAlbumToProcessName(albumName);
    state.setIsFolderDeletion(false);
    state.setFolderToProcessPath([]);
    state.setFileToProcessPath(actionTarget);

    const count = Array.isArray(actionTarget) ? actionTarget.length : 1;
    dom.confirmationMessage.textContent = `Remove ${count} item(s) from album '${albumName}'?`;
    dom.confirmActionBtn.textContent = `Remove ${count} Item(s)`;
    dom.confirmationModalOverlay.classList.add('active');
}

async function handleConfirmAction() {
    hideConfirmationModal();
    const wasLightboxActive = dom.lightboxOverlay.classList.contains('active');
    const oldIndex = state.currentMediaIndex;

    try {
        if (state.isAlbumRemoval) {
            const paths = Array.isArray(state.fileToProcessPath)
                ? state.fileToProcessPath
                : [state.fileToProcessPath];
            const result = await api.removeMediaFromAlbum(state.albumToProcessName, paths);
            ui.showMessage(`${result.removed_count} item(s) removed from album.`, 'success');
            state.setIsAlbumRemoval(false);
            state.setAlbumToProcessName('');
        } else if (Array.isArray(state.fileToProcessPath) && dom.confirmActionBtn.textContent.includes("Restore")) {
            await api.restoreMultiple(state.fileToProcessPath);
            ui.showMessage(`${state.fileToProcessPath.length} files restored.`, 'success');
        } else if (Array.isArray(state.fileToProcessPath)) {
            const isPermanent = state.currentPath.includes(config.TRASH_FOLDER_NAME);
            await api.deleteMultiple(state.fileToProcessPath, isPermanent);
            ui.showMessage(`${state.fileToProcessPath.length} files deleted.`, 'success');
        }
        else if (state.isFolderDeletion) {
            await api.deleteFolder(state.folderToProcessPath);
            ui.showMessage('Folder moved to trash.', 'success');
            const newPath = state.currentPath.slice(0, -1);
            onNavigateCallback(newPath);
            return; // Exit early to avoid double-refresh
        } else {
            if (dom.confirmActionBtn.textContent === "Restore") {
                await api.restoreFile(state.fileToProcessPath);
                ui.showMessage('File restored.', 'success');
            } else if (dom.confirmActionBtn.textContent === "Delete Forever") {
                await api.deleteFileForever(state.fileToProcessPath);
                ui.showMessage('File permanently deleted.', 'success');
            } else { // Move to Trash
                await api.moveFileToTrash(state.fileToProcessPath);
                ui.showMessage('File moved to trash.', 'success');
            }
        }

        // Refresh current view after action
        await onNavigateCallback(state.currentPath);

        if (wasLightboxActive) {
            if (state.currentDisplayedMedia.length === 0) {
                closeLightbox();
            } else {
                const newIndex = Math.min(oldIndex, state.currentDisplayedMedia.length - 1);
                state.setCurrentMediaIndex(newIndex);
                updateLightboxMedia();
            }
        }
    } catch (error) {
        ui.showMessage(`Action failed: ${error.message}`, 'error');
    }
}


// --- Create Folder Modal ---
export function showCreateFolderModal() {
    dom.newFolderNameInput.value = '';
    dom.createFolderModalOverlay.classList.add('active');
    dom.newFolderNameInput.focus();
}

function hideCreateFolderModal() {
    dom.createFolderModalOverlay.classList.remove('active');
}

async function handleCreateFolder() {
    const folderName = dom.newFolderNameInput.value.trim();
    if (!folderName) {
        ui.showMessage("Folder name cannot be empty.", "error");
        return;
    }
    try {
        await api.createFolder(state.currentPath, folderName);
        ui.showMessage(`Folder '${folderName}' created.`, 'success');
        hideCreateFolderModal();
        await onNavigateCallback(state.currentPath);
    } catch (error) {
        ui.showMessage(`Error: ${error.message}`, 'error');
    }
}

export function showCreateAlbumModal() {
    dom.newAlbumNameInput.value = '';
    dom.createAlbumModalOverlay.classList.add('active');
    dom.newAlbumNameInput.focus();
}

function hideCreateAlbumModal() {
    dom.createAlbumModalOverlay.classList.remove('active');
}

async function handleCreateAlbum() {
    const albumName = dom.newAlbumNameInput.value.trim();
    if (!albumName) {
        ui.showMessage('Album name cannot be empty.', 'error');
        return;
    }

    try {
        await api.createAlbum(albumName);
        ui.showMessage(`Album '${albumName}' created.`, 'success');
        hideCreateAlbumModal();
        await onNavigateCallback(state.currentPath);
    } catch (error) {
        ui.showMessage(`Error: ${error.message}`, 'error');
    }
}

export async function showAddToAlbumModal(paths) {
    if (!Array.isArray(paths) || paths.length === 0) {
        ui.showMessage('Select media first.', 'info');
        return;
    }

    state.setAlbumSelectionPaths(paths);

    try {
        const data = await api.getAlbums();
        dom.existingAlbumsSelect.innerHTML = '';

        const createOption = document.createElement('option');
        createOption.value = '__create_new__';
        createOption.textContent = 'Create new album...';
        dom.existingAlbumsSelect.appendChild(createOption);

        (data.albums || []).forEach((album) => {
            const option = document.createElement('option');
            option.value = album.name;
            option.textContent = album.name;
            dom.existingAlbumsSelect.appendChild(option);
        });

        dom.existingAlbumsSelect.value = '__create_new__';
        dom.newAlbumNameForAddInput.value = '';
        dom.newAlbumNameForAddInput.classList.remove('hidden');
        dom.addToAlbumModalOverlay.classList.add('active');
        dom.newAlbumNameForAddInput.focus();
    } catch (error) {
        ui.showMessage(`Error loading albums: ${error.message}`, 'error');
    }
}

function hideAddToAlbumModal() {
    dom.addToAlbumModalOverlay.classList.remove('active');
    state.setAlbumSelectionPaths([]);
}

function toggleAddAlbumInput() {
    const creatingNew = dom.existingAlbumsSelect.value === '__create_new__';
    dom.newAlbumNameForAddInput.classList.toggle('hidden', !creatingNew);
}

async function handleConfirmAddToAlbum() {
    const creatingNew = dom.existingAlbumsSelect.value === '__create_new__';
    const albumName = creatingNew ? dom.newAlbumNameForAddInput.value.trim() : dom.existingAlbumsSelect.value;

    if (!albumName) {
        ui.showMessage('Album name is required.', 'error');
        return;
    }

    try {
        const result = await api.addMediaToAlbum(albumName, state.albumSelectionPaths, creatingNew);
        ui.showMessage(`Added ${result.added_count} item(s) to '${albumName}'.`, 'success');
        hideAddToAlbumModal();
        await onNavigateCallback(state.currentPath);
    } catch (error) {
        ui.showMessage(`Error: ${error.message}`, 'error');
    }
}

// --- Upload Modal ---

export function showUploadProgressModal() {
    dom.uploadTargetFolderInfo.textContent = `Target: ${state.currentPath.join('/') || 'root'}`;
    dom.uploadProgressModalOverlay.classList.add('active');
}

function hideUploadProgressModal() {
    dom.uploadProgressModalOverlay.classList.remove('active');
}

export function updateUploadList() {
    dom.uploadList.innerHTML = '';
    state.filesToUpload.forEach(f => {
        const li = document.createElement('li');
        li.textContent = f.name;
        dom.uploadList.appendChild(li);
    });
}

async function startFileUpload() {
    const totalFiles = state.filesToUpload.length;
    if (totalFiles === 0) return;

    dom.startUploadBtn.disabled = true;
    state.setUploadedFilesCount(0);

    for (const file of state.filesToUpload) {
        try {
            await api.uploadFile(file, state.currentPath);
            state.setUploadedFilesCount(state.uploadedFilesCount + 1);
            const progress = (state.uploadedFilesCount / totalFiles) * 100;
            dom.overallProgressBar.style.width = `${progress}%`;
            dom.overallProgressText.textContent = `${Math.round(progress)}% Complete`;
        } catch (error) {
            ui.showMessage(`Failed to upload ${file.name}: ${error.message}`, 'error');
        }
    }

    ui.showMessage('Upload complete!', 'success');
    hideUploadProgressModal();
    await onNavigateCallback(state.currentPath);
    dom.startUploadBtn.disabled = false;
}


// --- Initialization ---
export function initializeModals(onNavigate) {
    onNavigateCallback = onNavigate;

    // Confirmation Modal Listeners
    dom.confirmActionBtn.addEventListener('click', handleConfirmAction);
    dom.cancelActionBtn.addEventListener('click', hideConfirmationModal);

    // Create Folder Modal Listeners
    dom.confirmCreateFolderBtn.addEventListener('click', handleCreateFolder);
    dom.cancelCreateFolderBtn.addEventListener('click', hideCreateFolderModal);
    dom.newFolderNameInput.addEventListener('keydown', (e) => e.key === 'Enter' && handleCreateFolder());

    // Create Album Modal Listeners
    dom.confirmCreateAlbumBtn.addEventListener('click', handleCreateAlbum);
    dom.cancelCreateAlbumBtn.addEventListener('click', hideCreateAlbumModal);
    dom.newAlbumNameInput.addEventListener('keydown', (e) => e.key === 'Enter' && handleCreateAlbum());

    // Add To Album Modal Listeners
    dom.existingAlbumsSelect.addEventListener('change', toggleAddAlbumInput);
    dom.confirmAddToAlbumBtn.addEventListener('click', handleConfirmAddToAlbum);
    dom.cancelAddToAlbumBtn.addEventListener('click', hideAddToAlbumModal);
    dom.newAlbumNameForAddInput.addEventListener('keydown', (e) => e.key === 'Enter' && handleConfirmAddToAlbum());

    // Upload Modal Listeners
    dom.uploadFilesBtn.addEventListener('click', () => dom.fileInput.click());
    dom.fileInput.addEventListener('change', () => {
        state.setFilesToUpload(Array.from(dom.fileInput.files));
        if (state.filesToUpload.length > 0) {
            showUploadProgressModal();
            updateUploadList();
        }
        dom.fileInput.value = ''; // Allow re-selecting same file
    });
    dom.startUploadBtn.addEventListener('click', startFileUpload);
    dom.cancelUploadBtn.addEventListener('click', hideUploadProgressModal);
}
