// This module handles the logic for all modals: confirmation, create folder, and upload.

import * as state from './state.js';
import dom from './dom-elements.js';
import * as api from './api.js';
import * as ui from './ui.js';
import * as config from './config.js';
import { closeLightbox, updateLightboxMedia } from './lightbox.js';

let onNavigateCallback;

// --- Confirmation Modal ---
export function showConfirmationModal(actionTarget, isPermanentDelete = false, isRestore = false) {
    state.setIsFolderDeletion(Array.isArray(actionTarget) && typeof actionTarget[0] !== 'string');
    if (state.isFolderDeletion) {
        state.setFolderToProcessPath(actionTarget);
        state.setFileToProcessPath('');
    } else {
        state.setFileToProcessPath(actionTarget);
        state.setFolderToProcessPath([]);
    }

    let msg = '', btnText = '';

    if (actionTarget === 'empty_trash') {
        msg = "Are you sure you want to permanently delete ALL items in the trash? This action cannot be undone.";
        btnText = "Empty Trash";
    } else if (actionTarget === 'restore_all') {
        msg = "Are you sure you want to restore ALL items from the trash to their original locations?";
        btnText = "Restore All";
    } else if (Array.isArray(actionTarget) && isRestore) {
        // NEW: Handles restoring multiple selected files
        const count = actionTarget.length;
        msg = `Are you sure you want to restore ${count} selected item(s)?`;
        btnText = `Restore ${count} Item(s)`;
    } else if (Array.isArray(actionTarget) && typeof actionTarget[0] === 'string') {
        // Handles multiple file deletion
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

async function handleConfirmAction() {
    hideConfirmationModal();
    const wasLightboxActive = dom.lightboxOverlay.classList.contains('active');
    const oldIndex = state.currentMediaIndex;

    try {
        if (state.fileToProcessPath === 'empty_trash') {
            await api.emptyTrash();
            ui.showMessage('Trash emptied successfully.', 'success');
        } else if (state.fileToProcessPath === 'restore_all') {
            await api.restoreAll();
            ui.showMessage('All files restored.', 'success');
        } else if (Array.isArray(state.fileToProcessPath) && dom.confirmActionBtn.textContent.includes("Restore")) {
            // NEW: Handles the action for restoring multiple files
            await api.restoreMultiple(state.fileToProcessPath);
            ui.showMessage(`${state.fileToProcessPath.length} files restored.`, 'success');
        } else if (Array.isArray(state.fileToProcessPath)) {
            // Handles multi-delete
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