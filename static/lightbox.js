// This module handles all logic for the lightbox viewer, including zoom and pan.

import * as state from './state.js';
import dom from './dom-elements.js';
import * as config from './config.js';
import { updateActionButtonsVisibility } from './ui.js';

// --- Main Lightbox Functions ---

export function openLightbox(index) {
    if (state.slideshowInterval) {
        clearInterval(state.slideshowInterval);
        state.setSlideshowInterval(null);
        state.setIsSlideshowRunning(false);
    }
    if (index >= 0 && index < state.currentDisplayedMedia.length) {
        state.setCurrentMediaIndex(index);
        updateLightboxMedia();
        dom.lightboxOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        updateSlideshowControls();
        updateActionButtonsVisibility();
    }
}

export function closeLightbox() {
    dom.lightboxOverlay.classList.remove('active');
    document.body.style.overflow = '';
    const video = dom.lightboxMediaDisplay.querySelector('video');
    if (video) video.pause();
    if (state.slideshowInterval) clearInterval(state.slideshowInterval);
    state.setIsSlideshowRunning(false);
    updateSlideshowControls();
    dom.lightboxFilename.textContent = '';
    
    const mediaElement = dom.lightboxMediaDisplay.querySelector('.media-display');
    if (mediaElement) {
        resetZoom();
        mediaElement.style.transform = '';
        mediaElement.classList.remove('zoomed');
        mediaElement.remove();
    }
}

export function updateLightboxMedia() {
    resetZoom();
    const existingMedia = dom.lightboxMediaDisplay.querySelector('.media-display');
    if (existingMedia) {
        existingMedia.style.transform = '';
        existingMedia.classList.remove('zoomed');
    }

    if (state.slideshowInterval) clearInterval(state.slideshowInterval);

    const mediaItem = state.currentDisplayedMedia[state.currentMediaIndex];
    if (!mediaItem) {
        dom.lightboxMediaDisplay.innerHTML = '';
        return;
    }

    const isViewingTrash = state.currentPath.includes(config.TRASH_FOLDER_NAME);
    const fileExtension = mediaItem.filename.split('.').pop().toLowerCase();
    const isVideo = config.VIDEO_EXTENSIONS.includes('.' + fileExtension);
    
    const pathForApi = isViewingTrash ? mediaItem.relative_path_in_trash : mediaItem.original_path;
    
    if (typeof pathForApi !== 'string') {
        console.error("Error: Could not determine a valid API path for the media item.", mediaItem);
        dom.lightboxFilename.textContent = "Error: Invalid Path";
        return;
    }

    let displayPath;
    if (isViewingTrash) {
        const originalPath = mediaItem.original_path_from_metadata || 'Unknown';
        displayPath = `Trashed: ${mediaItem.filename} (from: ${originalPath})`;
    } else {
        displayPath = pathForApi.replace(/\//g, '   ⮕   ');
    }
    dom.lightboxFilename.textContent = displayPath;

    const mediaUrl = `/api/media/${pathForApi}`;

    const newMediaElement = document.createElement(isVideo ? 'video' : 'img');
    newMediaElement.className = 'media-display';
    newMediaElement.style.opacity = '0';

    newMediaElement.onload = newMediaElement.onloadeddata = () => {
        newMediaElement.classList.add('fade-in');
        if (state.isSlideshowRunning) {
            if (isVideo) {
                newMediaElement.play();
                newMediaElement.onended = showNextMedia;
            } else {
                state.setSlideshowInterval(setTimeout(showNextMedia, state.slideshowDelay));
            }
        }
    };
    
    if (isVideo) newMediaElement.controls = true;

    dom.lightboxMediaDisplay.querySelectorAll('.media-display').forEach(el => {
        el.classList.add('fade-out');
        setTimeout(() => el.remove(), 800);
    });

    dom.lightboxMediaDisplay.appendChild(newMediaElement);
    newMediaElement.src = mediaUrl;
    updateActionButtonsVisibility();
}

export function showNextMedia() {
    const newIndex = (state.currentMediaIndex + 1) % state.currentDisplayedMedia.length;
    state.setCurrentMediaIndex(newIndex);
    updateLightboxMedia();
}

export function showPreviousMedia() {
    const newIndex = (state.currentMediaIndex - 1 + state.currentDisplayedMedia.length) % state.currentDisplayedMedia.length;
    state.setCurrentMediaIndex(newIndex);
    updateLightboxMedia();
}

export function updateSlideshowControls() {
    const isRunning = state.isSlideshowRunning;
    dom.slideshowBtnBreadcrumb.querySelector('.play_icon').classList.toggle('hidden', isRunning);
    dom.slideshowBtnBreadcrumb.querySelector('.pause_icon').classList.toggle('hidden', !isRunning);
    dom.slideshowBtnLightbox.querySelector('.play_icon').classList.toggle('hidden', isRunning);
    dom.slideshowBtnLightbox.querySelector('.pause_icon').classList.toggle('hidden', !isRunning);
    
    if (dom.lightboxOverlay.classList.contains('active')) {
        dom.lightboxPrev.style.pointerEvents = isRunning ? 'none' : 'auto';
        dom.lightboxNext.style.pointerEvents = isRunning ? 'none' : 'auto';
    }
}

// --- Stable Zoom and Pan Implementation ---

function resetZoom() {
    state.setZoomState({ isZoomed: false, scale: 1, position: { x: 0, y: 0 }, start: { x: 0, y: 0 }, isPanning: false });
}

function applyTransform(mediaElement) {
    if (!mediaElement) return;

    const parentRect = dom.lightboxMediaDisplay.getBoundingClientRect();
    const rect = mediaElement.getBoundingClientRect();

    const maxX = Math.max(0, (rect.width - parentRect.width) / 2);
    const maxY = Math.max(0, (rect.height - parentRect.height) / 2);
    
    const clampedX = Math.max(-maxX, Math.min(maxX, state.position.x));
    const clampedY = Math.max(-maxY, Math.min(maxY, state.position.y));

    state.setZoomState({ ...state, position: { x: clampedX, y: clampedY } });

    mediaElement.style.transform = `translate(-50%, -50%) translate(${clampedX}px, ${clampedY}px) scale(${state.scale})`;
}

function handlePanMove(e) {
    if (!state.isPanning) return;
    e.preventDefault();
    const mediaElement = dom.lightboxMediaDisplay.querySelector('.media-display.zoomed');
    if (!mediaElement) return;
    
    const newX = e.clientX - state.start.x;
    const newY = e.clientY - state.start.y;

    state.setZoomState({ ...state, position: { x: newX, y: newY } });
    applyTransform(mediaElement);
}

function handlePanEnd() {
    if (!state.isPanning) return;
    state.setZoomState({ ...state, isPanning: false });
    const mediaElement = dom.lightboxMediaDisplay.querySelector('.media-display.zoomed');
    if (mediaElement) mediaElement.style.cursor = 'grab';
    window.removeEventListener('mousemove', handlePanMove);
    window.removeEventListener('mouseup', handlePanEnd);
}

// --- NEW: Initialization Function ---
export function initializeLightbox() {
    dom.lightboxMediaDisplay.addEventListener('wheel', (e) => {
        const mediaElement = dom.lightboxMediaDisplay.querySelector('.media-display:not(video)');
        if (!mediaElement || state.isSlideshowRunning) return;
        e.preventDefault();

        const newScale = Math.max(1, Math.min(state.scale + (e.deltaY < 0 ? 0.1 : -0.1), 4));

        if (newScale === 1) {
            resetZoom();
            mediaElement.style.transform = 'translate(-50%, -50%)';
            mediaElement.classList.remove('zoomed');
            return;
        }

        const rect = mediaElement.getBoundingClientRect();
        const growthX = (e.clientX - (rect.left + rect.width / 2)) * (newScale / state.scale - 1);
        const growthY = (e.clientY - (rect.top + rect.height / 2)) * (newScale / state.scale - 1);

        const newPositionX = state.position.x - growthX;
        const newPositionY = state.position.y - growthY;
        
        state.setZoomState({ ...state, isZoomed: true, scale: newScale, position: {x: newPositionX, y: newPositionY} });
        mediaElement.classList.add('zoomed');
        
        applyTransform(mediaElement);
    });

    dom.lightboxMediaDisplay.addEventListener('mousedown', (e) => {
        if (state.isZoomed && e.button === 0) {
            const mediaElement = dom.lightboxMediaDisplay.querySelector('.media-display.zoomed');
            if (mediaElement) {
                e.preventDefault();
                state.setZoomState({ ...state, isPanning: true, start: { x: e.clientX - state.position.x, y: e.clientY - state.position.y } });
                mediaElement.style.cursor = 'grabbing';
                window.addEventListener('mousemove', handlePanMove);
                window.addEventListener('mouseup', handlePanEnd);
            }
        }
    });
}
