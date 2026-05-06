// This is the main entry point for the application.
// It imports from other modules and sets up initial event listeners.

import * as state from './state.js';
import dom, { initDOMElements } from './dom-elements.js';
import * as api from './api.js';
import * as ui from './ui.js';
import * as lightbox from './lightbox.js';
import * as modals from './modals.js';
import * as config from './config.js';


function isAlbumsMode(path = state.currentPath) {
    return path[0] === config.ALBUMS_VIRTUAL_ROOT;
}

const dragSelect = {
    isPointerDown: false,
    isDragging: false,
    startX: 0,
    startY: 0,
    currentX: 0,
    currentY: 0,
    additiveMode: false,
    suppressClickOnce: false,
    framePending: false,
    autoScrollFrame: null,
    boxEl: null,
    initialSelection: new Set()
};

const DRAG_SCROLL_EDGE_PX = 80;
const DRAG_SCROLL_MAX_SPEED = 18;

function clearAllSelections() {
    dom.galleryContainer.querySelectorAll('.thumbnail-checkbox').forEach((cb) => {
        cb.checked = false;
        cb.closest('.gallery-item')?.classList.remove('selected');
    });
}

function rectsIntersect(a, b) {
    return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
}

function updateDragSelectionVisual() {
    dragSelect.framePending = false;
    if (!dragSelect.isDragging || !dragSelect.boxEl) return;

    const left = Math.min(dragSelect.startX, dragSelect.currentX);
    const top = Math.min(dragSelect.startY, dragSelect.currentY);
    const width = Math.abs(dragSelect.currentX - dragSelect.startX);
    const height = Math.abs(dragSelect.currentY - dragSelect.startY);

    dragSelect.boxEl.style.left = `${left}px`;
    dragSelect.boxEl.style.top = `${top}px`;
    dragSelect.boxEl.style.width = `${width}px`;
    dragSelect.boxEl.style.height = `${height}px`;

    const selectionRect = {
        left,
        top,
        right: left + width,
        bottom: top + height
    };

    const items = dom.galleryContainer.querySelectorAll('.gallery-item');
    items.forEach((item) => {
        const checkbox = item.querySelector('.thumbnail-checkbox');
        if (!checkbox) return;

        const intersects = rectsIntersect(selectionRect, item.getBoundingClientRect());
        const wasSelected = dragSelect.initialSelection.has(checkbox.dataset.path);
        const shouldSelect = dragSelect.additiveMode ? (wasSelected || intersects) : intersects;

        checkbox.checked = shouldSelect;
        item.classList.toggle('selected', shouldSelect);
    });

    handleSelectionChange();
}

function scheduleDragSelectionUpdate() {
    if (dragSelect.framePending) return;
    dragSelect.framePending = true;
    window.requestAnimationFrame(updateDragSelectionVisual);
}

function calculateAutoScrollDeltaY(pointerY) {
    if (pointerY < DRAG_SCROLL_EDGE_PX) {
        const ratio = (DRAG_SCROLL_EDGE_PX - pointerY) / DRAG_SCROLL_EDGE_PX;
        return -Math.max(1, Math.round(DRAG_SCROLL_MAX_SPEED * ratio));
    }

    const bottomEdgeStart = window.innerHeight - DRAG_SCROLL_EDGE_PX;
    if (pointerY > bottomEdgeStart) {
        const ratio = (pointerY - bottomEdgeStart) / DRAG_SCROLL_EDGE_PX;
        return Math.max(1, Math.round(DRAG_SCROLL_MAX_SPEED * ratio));
    }

    return 0;
}

function stopAutoScrollLoop() {
    if (dragSelect.autoScrollFrame !== null) {
        window.cancelAnimationFrame(dragSelect.autoScrollFrame);
        dragSelect.autoScrollFrame = null;
    }
}

function runAutoScrollLoop() {
    if (!dragSelect.isDragging) {
        stopAutoScrollLoop();
        return;
    }

    const deltaY = calculateAutoScrollDeltaY(dragSelect.currentY);
    if (deltaY !== 0) {
        window.scrollBy(0, deltaY);
        scheduleDragSelectionUpdate();
    }

    dragSelect.autoScrollFrame = window.requestAnimationFrame(runAutoScrollLoop);
}

function ensureAutoScrollLoop() {
    if (dragSelect.autoScrollFrame !== null) return;
    dragSelect.autoScrollFrame = window.requestAnimationFrame(runAutoScrollLoop);
}

function finishDragSelection() {
    dragSelect.isPointerDown = false;

    if (dragSelect.isDragging) {
        dragSelect.suppressClickOnce = true;
    }

    dragSelect.isDragging = false;
    dragSelect.initialSelection.clear();
    dragSelect.framePending = false;
    stopAutoScrollLoop();

    if (dragSelect.boxEl) {
        dragSelect.boxEl.remove();
        dragSelect.boxEl = null;
    }
    document.body.classList.remove('drag-selecting');
}

function canStartDragSelection(e) {
    if (dom.lightboxOverlay.classList.contains('active')) return false;
    if (dom.gallerySection.classList.contains('hidden')) return false;
    if (dom.galleryContainer.querySelectorAll('.gallery-item').length === 0) return false;

    if (e.target.closest('.thumbnail-checkbox')) return false;
    if (e.target.closest('button, a, input, select, textarea, label')) return false;
    if (e.target.closest('#breadcrumbActionButtonsContainer, .breadcrumb, #topLevelFoldersSection, #subFoldersSection')) return false;
    if (e.target.closest('.confirmation-modal-overlay, .create-folder-modal-overlay, .lightbox-overlay')) return false;

    return true;
}

function startDragSelectionFromEvent(e) {
    if (dragSelect.isPointerDown) return;
    if (e.button !== 0) return;
    if (!canStartDragSelection(e)) return;

    dragSelect.isPointerDown = true;
    dragSelect.isDragging = false;
    dragSelect.startX = e.clientX;
    dragSelect.startY = e.clientY;
    dragSelect.currentX = e.clientX;
    dragSelect.currentY = e.clientY;
    dragSelect.additiveMode = true;
    dragSelect.initialSelection = new Set(
        Array.from(dom.galleryContainer.querySelectorAll('.thumbnail-checkbox:checked')).map((cb) => cb.dataset.path)
    );

    // Prevent native browser text selection from kicking in at drag start.
    e.preventDefault();
}

function moveDragSelectionFromEvent(e) {
    if (!dragSelect.isPointerDown) return;

    dragSelect.currentX = e.clientX;
    dragSelect.currentY = e.clientY;

    const dx = Math.abs(dragSelect.currentX - dragSelect.startX);
    const dy = Math.abs(dragSelect.currentY - dragSelect.startY);
    if (!dragSelect.isDragging && (dx > 4 || dy > 4)) {
        dragSelect.isDragging = true;
        document.body.classList.add('drag-selecting');
        dragSelect.boxEl = document.createElement('div');
        dragSelect.boxEl.className = 'drag-select-box';
        document.body.appendChild(dragSelect.boxEl);

        if (!dragSelect.additiveMode) {
            clearAllSelections();
        }
    }

    if (dragSelect.isDragging) {
        scheduleDragSelectionUpdate();
        ensureAutoScrollLoop();
        e.preventDefault();
    }
}

function setupDragSelection() {
    document.addEventListener('pointerdown', startDragSelectionFromEvent);
    document.addEventListener('pointermove', moveDragSelectionFromEvent);
    document.addEventListener('pointerup', () => {
        if (!dragSelect.isPointerDown) return;
        finishDragSelection();
    });

    // Fallback for browsers/input devices where pointer events are inconsistent.
    document.addEventListener('mousedown', startDragSelectionFromEvent);
    document.addEventListener('mousemove', moveDragSelectionFromEvent);
    document.addEventListener('mouseup', () => {
        if (!dragSelect.isPointerDown) return;
        finishDragSelection();
    });

    dom.galleryContainer.addEventListener('click', (e) => {
        if (!dragSelect.suppressClickOnce) return;
        dragSelect.suppressClickOnce = false;
        e.preventDefault();
        e.stopPropagation();
    }, true);

    // Guard against native browser text selection while marquee-selection is active.
    document.addEventListener('selectstart', (e) => {
        if (!dragSelect.isPointerDown && !dragSelect.isDragging) return;
        if (e.target.closest('input, textarea, select')) return;
        e.preventDefault();
    });
}


// --- Multi-Select Logic ---

function handleSelectionChange() {
    const checkboxes = dom.galleryContainer.querySelectorAll('.thumbnail-checkbox:checked');
    const selectedPaths = Array.from(checkboxes).map(cb => cb.dataset.path);
    state.setSelectedFiles(selectedPaths);

    const count = state.selectedFiles.length;
    const isViewingTrash = state.currentPath.includes(config.TRASH_FOLDER_NAME);
    const isViewingAlbums = isAlbumsMode();
    const isViewingAlbumContent = isViewingAlbums && state.currentPath.length > 1;

    // Update the 'Delete Selected' button (for regular folders)
    dom.selectedCount.textContent = count;
    dom.deleteSelectedBtn.classList.toggle('hidden', count === 0 || isViewingTrash || (isViewingAlbums && !isViewingAlbumContent));
    dom.deleteSelectedBtn.title = isViewingAlbumContent ? 'Remove Selected From Album' : 'Delete Selected';

    // Show add-to-album action for selected media outside trash
    dom.addToAlbumBtn.classList.toggle('hidden', count === 0 || isViewingTrash);

    // Update the 'Restore Selected' button (for trash)
    dom.selectedRestoreCount.textContent = count;
    dom.restoreSelectedBtn.classList.toggle('hidden', count === 0 || !isViewingTrash || isViewingAlbums);

    // Update the new 'Delete Selected Permanently' button (for trash)
    dom.selectedPermanentDeleteCount.textContent = count;
    dom.deleteSelectedPermanentBtn.classList.toggle('hidden', count === 0 || !isViewingTrash || isViewingAlbums);

    // MODIFIED: Show 'Select All' button whenever there are items, including in trash
    const allCheckboxes = dom.galleryContainer.querySelectorAll('.thumbnail-checkbox');
    dom.selectAllBtn.classList.toggle('hidden', allCheckboxes.length === 0);
    dom.deselectAllBtn.classList.toggle('hidden', count === 0);
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
        } else if (pathSegments[0] === config.ALBUMS_VIRTUAL_ROOT) {
            if (pathSegments.length === 1) {
                await loadAlbums();
            } else {
                await loadAlbumContent(pathSegments[1]);
            }
        } else if (pathSegments[0] === config.TRASH_FOLDER_NAME) {
            await loadTrashContent();
        } else {
            await loadSubFoldersAndFiles(pathSegments);
        }
    } catch (error) {
        console.error('Navigation error:', error);
        if (error.message === 'Unauthorized') {
            // Trigger a full reload so the browser can re-run HTTP Basic auth flow.
            window.location.reload();
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

async function loadAlbums() {
    dom.topLevelFoldersSection.classList.remove('hidden');
    dom.topLevelFoldersContainer.innerHTML = '<p>Loading...</p>';

    const data = await api.getAlbums();

    dom.topLevelFoldersContainer.innerHTML = '';
    (data.albums || []).forEach(album => {
        const link = ui.createFolderNavLink(album.name, [config.ALBUMS_VIRTUAL_ROOT, album.name], album.count, false, false, navigateToPath, 'folder_special');
        dom.topLevelFoldersContainer.appendChild(link);
    });

    dom.topLevelFoldersContainer.appendChild(ui.createAddAlbumButton(modals.showCreateAlbumModal));

    state.setCurrentDisplayedMedia([]);
    dom.gallerySection.classList.add('hidden');
    ui.updateActionButtonsVisibility();
    handleSelectionChange();
}

async function loadAlbumContent(albumName) {
    dom.gallerySection.classList.remove('hidden');
    dom.galleryContainer.innerHTML = '<p>Loading...</p>';

    const data = await api.getAlbumMedia(albumName);
    state.setCurrentDisplayedMedia(data.files || []);
    ui.displayMediaThumbnails(state.currentDisplayedMedia, handleSelectionChange);

    if ((data.missing || []).length > 0) {
        ui.showMessage(`Album loaded with ${data.missing.length} missing file(s).`, 'info');
    }

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
            const media = isAlbumsMode() ? state.currentDisplayedMedia : await api.getRecursiveMedia(state.currentPath);
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
    dom.albumsBtnTopRight.addEventListener('click', () => navigateToPath([config.ALBUMS_VIRTUAL_ROOT]));
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
        const isViewingAlbums = isAlbumsMode();
        const mediaItem = state.currentDisplayedMedia[state.currentMediaIndex];
        if (!mediaItem) return;

        const pathForAction = isViewingTrash ? mediaItem.relative_path_in_trash : mediaItem.original_path;
        if (isViewingAlbums && state.currentPath.length > 1) {
            modals.showRemoveFromAlbumConfirmation(pathForAction, state.currentPath[1]);
            return;
        }

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

    dom.deselectAllBtn.addEventListener('click', () => {
        resetSelection();
    });

    dom.deleteSelectedBtn.addEventListener('click', () => {
        if (isAlbumsMode() && state.currentPath.length > 1) {
            modals.showRemoveFromAlbumConfirmation(state.selectedFiles, state.currentPath[1]);
            return;
        }
        const isPermanent = state.currentPath.includes(config.TRASH_FOLDER_NAME);
        modals.showConfirmationModal(state.selectedFiles, isPermanent);
    });

    dom.addToAlbumBtn.addEventListener('click', () => {
        modals.showAddToAlbumModal(state.selectedFiles);
    });

    dom.restoreSelectedBtn.addEventListener('click', () => {
        modals.showConfirmationModal(state.selectedFiles, false, true);
    });

    dom.deleteSelectedPermanentBtn.addEventListener('click', () => {
        modals.showConfirmationModal(state.selectedFiles, true, false);
    });

    dom.galleryContainer.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!state.currentPath.includes(config.TRASH_FOLDER_NAME) && !isAlbumsMode()) {
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
        if (isAlbumsMode()) {
            ui.showMessage("Cannot upload files directly in Albums view.", "error");
            return;
        }
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            state.setFilesToUpload(files);
            modals.showUploadProgressModal();
            modals.updateUploadList();
        }
    });

    setupDragSelection();

    // Initial page load. If auth is needed, browser-level Basic auth handles it.
    await navigateToPath([]);
});
