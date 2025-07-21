// This is the main entry point for the application.
// It imports from other modules and sets up initial event listeners.

import * as state from './state.js';
import dom, { initDOMElements } from './dom-elements.js';
import * as api from './api.js';
import * as ui from './ui.js';
import * as lightbox from './lightbox.js';
import * as modals from './modals.js';
import * as config from './config.js';

// --- Authentication Logic ---

function showLoginModal(errorMessage = '') {
    dom.loginErrorMessage.textContent = errorMessage;
    dom.loginErrorMessage.classList.toggle('hidden', !errorMessage);
    dom.loginModalOverlay.classList.add('active');
    dom.usernameInput.focus();
}

function hideLoginModal() {
    dom.loginModalOverlay.classList.remove('active');
    dom.usernameInput.value = '';
    dom.passwordInput.value = '';
    dom.loginErrorMessage.classList.add('hidden');
}

async function handleLogin() {
    const username = dom.usernameInput.value.trim();
    const password = dom.passwordInput.value.trim();

    if (!username || !password) {
        showLoginModal('Username and password are required.');
        return;
    }

    api.setCredentials(username, password);

    try {
        // Try a simple API call to verify credentials
        await api.getFolders(); 
        hideLoginModal();
        navigateToPath([]); // Load the gallery content
    } catch (error) {
        if (error.message === 'Unauthorized') {
            showLoginModal('Invalid username or password.');
        } else {
            showLoginModal('An error occurred. Please try again.');
        }
        api.clearCredentials(); // Clear bad credentials
    }
}

function handleLogout() {
    api.clearCredentials();
    // Reload the page to force login
    window.location.reload();
}


// --- Multi-Select Logic ---

function handleSelectionChange() {
    const checkboxes = dom.galleryContainer.querySelectorAll('.thumbnail-checkbox:checked');
    const selectedPaths = Array.from(checkboxes).map(cb => cb.dataset.path);
    state.setSelectedFiles(selectedPaths);

    const count = state.selectedFiles.length;
    const isViewingTrash = state.currentPath.includes(config.TRASH_FOLDER_NAME);

    // Update the 'Delete Selected' button (for regular folders)
    dom.selectedCount.textContent = count;
    dom.deleteSelectedBtn.classList.toggle('hidden', count === 0 || isViewingTrash);

    // Update the 'Restore Selected' button (for trash)
    dom.selectedRestoreCount.textContent = count;
    dom.restoreSelectedBtn.classList.toggle('hidden', count === 0 || !isViewingTrash);

    // Update the new 'Delete Selected Permanently' button (for trash)
    dom.selectedPermanentDeleteCount.textContent = count;
    dom.deleteSelectedPermanentBtn.classList.toggle('hidden', count === 0 || !isViewingTrash);

    // MODIFIED: Show 'Select All' button whenever there are items, including in trash
    const allCheckboxes = dom.galleryContainer.querySelectorAll('.thumbnail-checkbox');
    dom.selectAllBtn.classList.toggle('hidden', allCheckboxes.length === 0);
}


function resetSelection() {
    dom.galleryContainer.querySelectorAll('.thumbnail-checkbox:checked').forEach(cb => {
        cb.checked = false;
        cb.closest('.gallery-item').classList.remove('selected');
    });
    handleSelectionChange();
}


// --- Navigation ---

async function navigateToPath(pathSegments) {
    state.setCurrentPath(pathSegments);
    ui.updateBreadcrumb(navigateToPath);
    resetSelection();

    dom.topLevelFoldersSection.classList.add('hidden');
    dom.subFoldersSection.classList.add('hidden');
    dom.gallerySection.classList.add('hidden');

    try {
        if (pathSegments.length === 0) {
            await loadTopLevelFolders();
        } else if (pathSegments[0] === config.TRASH_FOLDER_NAME) {
            await loadTrashContent();
        } else {
            await loadSubFoldersAndFiles(pathSegments);
        }
    } catch (error) {
        console.error('Navigation error:', error);
        if (error.message === 'Unauthorized') {
            // If session expires or credentials become invalid, force re-login
            api.clearCredentials();
            showLoginModal('Your session has expired. Please login again.');
        } else {
            ui.showMessage(`Error loading content: ${error.message}`, 'error');
        }
    }
}

async function loadTopLevelFolders() {
    dom.topLevelFoldersSection.classList.remove('hidden');
    dom.topLevelFoldersContainer.innerHTML = '<p>Loading...</p>';
    const data = await api.getFolders();
    const trashData = await api.getTrashContent();

    dom.topLevelFoldersContainer.innerHTML = '';
    data.folders.forEach(folder => {
        const link = ui.createFolderNavLink(folder.name, [folder.name], folder.count, false, false, navigateToPath);
        dom.topLevelFoldersContainer.appendChild(link);
    });

    dom.topLevelFoldersContainer.appendChild(ui.createAddFolderButton());

    const trashLink = ui.createFolderNavLink(config.TRASH_FOLDER_NAME, [config.TRASH_FOLDER_NAME], trashData.count, true, false, navigateToPath);
    dom.topLevelFoldersContainer.appendChild(trashLink);

    state.setCurrentDisplayedMedia(data.files);
    ui.displayMediaThumbnails(data.files, handleSelectionChange);
    ui.updateActionButtonsVisibility();
    handleSelectionChange();
}

async function loadSubFoldersAndFiles(pathSegments) {
    dom.subFoldersSection.classList.remove('hidden');
    dom.subFoldersContainer.innerHTML = '<p>Loading...</p>';
    const data = await api.getFolders(pathSegments);

    dom.subFoldersContainer.innerHTML = '';
    data.folders.forEach(folder => {
        const link = ui.createFolderNavLink(folder.name, [...pathSegments, folder.name], folder.count, false, false, navigateToPath);
        dom.subFoldersContainer.appendChild(link);
    });

    dom.subFoldersContainer.appendChild(ui.createAddFolderButton());

    state.setCurrentDisplayedMedia(data.files);
    ui.displayMediaThumbnails(data.files, handleSelectionChange);
    ui.updateActionButtonsVisibility();
    handleSelectionChange();
}

async function loadTrashContent() {
    dom.gallerySection.classList.remove('hidden');
    dom.galleryContainer.innerHTML = '<p>Loading...</p>';
    const data = await api.getTrashContent();
    state.setCurrentDisplayedMedia(data.files);
    ui.displayMediaThumbnails(data.files, handleSelectionChange);
    ui.updateActionButtonsVisibility();
    handleSelectionChange();
}

// --- Slideshow ---
async function toggleSlideshow() {
    if (state.isSlideshowRunning) {
        if (state.slideshowInterval) clearTimeout(state.slideshowInterval);
        state.setIsSlideshowRunning(false);
        const video = dom.lightboxMediaDisplay.querySelector('video');
        if (video) video.pause();
    } else {
        try {
            const media = await api.getRecursiveMedia(state.currentPath);
            if (media.length === 0) {
                ui.showMessage('No media found for slideshow.', 'info');
                return;
            }
            state.setCurrentDisplayedMedia(media);
            if (!dom.lightboxOverlay.classList.contains('active')) {
                state.setCurrentMediaIndex(0);
            }
            state.setIsSlideshowRunning(true);
            lightbox.openLightbox(state.currentMediaIndex);
        } catch (error) {
            ui.showMessage(`Error starting slideshow: ${error.message}`, 'error');
        }
    }
    lightbox.updateSlideshowControls();
}


// --- Initial Setup ---
document.addEventListener('DOMContentLoaded', async () => {
    initDOMElements();
    lightbox.initializeLightbox();
    modals.initializeModals(navigateToPath);

    const savedTheme = localStorage.getItem('theme') || 'dark';
    ui.setTheme(savedTheme);

    // --- Event Listeners ---
    dom.themeToggleButton.addEventListener('click', () => {
        const newTheme = document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        ui.setTheme(newTheme);
    });

    dom.homeBtnTopRight.addEventListener('click', () => navigateToPath([]));
    dom.slideshowBtnBreadcrumb.addEventListener('click', toggleSlideshow);
    dom.slideshowBtnLightbox.addEventListener('click', toggleSlideshow);

    dom.lightboxClose.addEventListener('click', lightbox.closeLightbox);
    dom.lightboxPrev.addEventListener('click', lightbox.showPreviousMedia);
    dom.lightboxNext.addEventListener('click', lightbox.showNextMedia);
    dom.lightboxOverlay.addEventListener('click', (e) => {
        if (e.target === dom.lightboxOverlay) lightbox.closeLightbox();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && state.selectedFiles.length > 0) {
            resetSelection();
        }
        else if (dom.lightboxOverlay.classList.contains('active')) {
            if (e.key === 'Escape') lightbox.closeLightbox();
            else if (!state.isSlideshowRunning && !state.isZoomed && e.key === 'ArrowRight') lightbox.showNextMedia();
            else if (!state.isSlideshowRunning && !state.isZoomed && e.key === 'ArrowLeft') lightbox.showPreviousMedia();
        }
    });

    dom.trashDeleteBtn.addEventListener('click', () => {
        const isViewingTrash = state.currentPath.includes(config.TRASH_FOLDER_NAME);
        const mediaItem = state.currentDisplayedMedia[state.currentMediaIndex];
        const pathForAction = isViewingTrash ? mediaItem.relative_path_in_trash : mediaItem.original_path;
        modals.showConfirmationModal(pathForAction, isViewingTrash, false);
    });

    dom.trashRestoreBtn.addEventListener('click', () => {
        const mediaItem = state.currentDisplayedMedia[state.currentMediaIndex];
        const pathForAction = mediaItem.relative_path_in_trash;
        modals.showConfirmationModal(pathForAction, false, true);
    });

    dom.downloadRawBtn.addEventListener('click', () => {
        const mediaItem = state.currentDisplayedMedia[state.currentMediaIndex];
        if (mediaItem && mediaItem.original_path) {
            const downloadUrl = `/api/download_original_raw/${mediaItem.original_path}`;
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = mediaItem.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    });

    // REMOVED event listeners for emptyTrashBtn and restoreAllBtn

    dom.selectAllBtn.addEventListener('click', () => {
        const allCheckboxes = dom.galleryContainer.querySelectorAll('.thumbnail-checkbox');
        const isAllSelected = allCheckboxes.length > 0 && state.selectedFiles.length === allCheckboxes.length;

        allCheckboxes.forEach(cb => {
            cb.checked = !isAllSelected;
            cb.closest('.gallery-item').classList.toggle('selected', !isAllSelected);
        });
        handleSelectionChange();
    });

    dom.deleteSelectedBtn.addEventListener('click', () => {
        const isPermanent = state.currentPath.includes(config.TRASH_FOLDER_NAME);
        modals.showConfirmationModal(state.selectedFiles, isPermanent);
    });

    dom.restoreSelectedBtn.addEventListener('click', () => {
        modals.showConfirmationModal(state.selectedFiles, false, true);
    });

    dom.deleteSelectedPermanentBtn.addEventListener('click', () => {
        modals.showConfirmationModal(state.selectedFiles, true, false);
    });

    dom.galleryContainer.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!state.currentPath.includes(config.TRASH_FOLDER_NAME)) {
            dom.galleryContainer.classList.add('drag-over');
        }
    });

    dom.galleryContainer.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dom.galleryContainer.classList.remove('drag-over');
    });

    dom.galleryContainer.addEventListener('drop', (e) => {
        e.preventDefault();
        dom.galleryContainer.classList.remove('drag-over');
        if (state.currentPath.includes(config.TRASH_FOLDER_NAME)) {
            ui.showMessage("Cannot upload files to the Trash folder.", "error");
            return;
        }
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            state.setFilesToUpload(files);
            modals.showUploadProgressModal();
            modals.updateUploadList();
        }
    });

    // --- Login and Logout Listeners ---
    dom.loginBtn.addEventListener('click', handleLogin);
    dom.passwordInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleLogin();
    });
    dom.logoutBtn.addEventListener('click', handleLogout);

    // --- Initial Authentication Check ---
    if (api.hasCredentials()) {
        try {
            await navigateToPath([]); // Try to load content with stored credentials
        } catch (error) {
            // This catch is for initial load. navigateToPath has its own more specific catch.
            if (error.message === 'Unauthorized') {
                api.clearCredentials();
                showLoginModal('Your session has expired. Please login again.');
            }
        }
    } else {
        showLoginModal();
    }
});
