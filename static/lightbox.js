// This module handles all logic for the lightbox viewer, including zoom and pan.

import * as state from './state.js';
import dom from './dom-elements.js';
import * as config from './config.js';
import { updateActionButtonsVisibility } from './ui.js';

const SWIPE_THRESHOLD_PX = 50;
const SWIPE_DIRECTION_LOCK_PX = 10;
const SWIPE_TRANSITION_MS = 220;
const MAX_PRELOAD_CACHE_ITEMS = 24;

const preloadedMediaCache = new Map();

const lightboxSwipe = {
    tracking: false,
    startX: 0,
    startY: 0,
    deltaX: 0,
    deltaY: 0,
    lockedHorizontal: false,
    cancelled: false,
    transitionInProgress: false,
    previewEl: null,
    previewTargetIndex: null,
    previewDirection: 0
};

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
        document.body.classList.add('lightbox-open');
        document.body.style.overflow = 'hidden';
        updateSlideshowControls();
        updateActionButtonsVisibility();
    }
}

export function closeLightbox() {
    dom.lightboxOverlay.classList.remove('active');
    document.body.classList.remove('lightbox-open');
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

    clearSwipePreview();
    lightboxSwipe.tracking = false;
    lightboxSwipe.transitionInProgress = false;
}

function getWrappedIndex(index) {
    const len = state.currentDisplayedMedia.length;
    if (len === 0) return -1;
    return ((index % len) + len) % len;
}

function getMediaDetailsAtIndex(index) {
    const wrappedIndex = getWrappedIndex(index);
    if (wrappedIndex < 0) return null;

    const mediaItem = state.currentDisplayedMedia[wrappedIndex];
    if (!mediaItem) return null;

    const isViewingTrash = state.currentPath.includes(config.TRASH_FOLDER_NAME);
    const fileExtension = mediaItem.filename.split('.').pop().toLowerCase();
    const isVideo = config.VIDEO_EXTENSIONS.includes('.' + fileExtension);
    const pathForApi = isViewingTrash ? mediaItem.relative_path_in_trash : mediaItem.original_path;

    if (typeof pathForApi !== 'string') {
        console.error("Error: Could not determine a valid API path for the media item.", mediaItem);
        dom.lightboxFilename.textContent = "Error: Invalid Path";
        return null;
    }

    const displayPath = isViewingTrash
        ? `Trashed: ${mediaItem.filename} (from: ${mediaItem.original_path_from_metadata || 'Unknown'})`
        : pathForApi.replace(/\//g, '   ⮕   ');

    return {
        wrappedIndex,
        mediaItem,
        isViewingTrash,
        isVideo,
        pathForApi,
        displayPath,
        mediaUrl: `/api/media/${pathForApi}`
    };
}

function trimPreloadCache() {
    while (preloadedMediaCache.size > MAX_PRELOAD_CACHE_ITEMS) {
        const firstKey = preloadedMediaCache.keys().next().value;
        preloadedMediaCache.delete(firstKey);
    }
}

function preloadMediaAtIndex(index) {
    const details = getMediaDetailsAtIndex(index);
    if (!details || details.isVideo) return;
    if (preloadedMediaCache.has(details.mediaUrl)) return;

    const img = new Image();
    img.decoding = 'async';
    img.src = details.mediaUrl;

    preloadedMediaCache.set(details.mediaUrl, img);
    trimPreloadCache();
}

function preloadAdjacentMedia(centerIndex) {
    preloadMediaAtIndex(centerIndex + 1);
    preloadMediaAtIndex(centerIndex - 1);
}

function createLightboxMediaElement(details, options = {}) {
    const { useFade = true, allowSlideshowHooks = true, isPreview = false } = options;
    const newMediaElement = document.createElement(details.isVideo ? 'video' : 'img');

    newMediaElement.className = 'media-display';
    newMediaElement.style.opacity = useFade ? '0' : '1';

    newMediaElement.onload = newMediaElement.onloadeddata = () => {
        if (useFade) {
            newMediaElement.classList.add('fade-in');
        } else {
            newMediaElement.style.opacity = '1';
        }

        if (!allowSlideshowHooks) return;
        if (state.isSlideshowRunning) {
            if (details.isVideo) {
                newMediaElement.play();
                newMediaElement.onended = showNextMedia;
            } else {
                state.setSlideshowInterval(setTimeout(showNextMedia, state.slideshowDelay));
            }
        }
    };

    if (details.isVideo) {
        newMediaElement.controls = !isPreview;
        newMediaElement.preload = 'metadata';
        if (isPreview) {
            newMediaElement.muted = true;
        }
    }

    if (isPreview) {
        newMediaElement.style.pointerEvents = 'none';
    }

    newMediaElement.src = details.mediaUrl;
    return newMediaElement;
}

function getActiveMediaElement() {
    return dom.lightboxMediaDisplay.querySelector('.media-display:not([data-swipe-preview="1"])');
}

function setHorizontalTransform(mediaElement, offsetX, withTransition = false) {
    if (!mediaElement) return;
    mediaElement.style.transition = withTransition ? `transform ${SWIPE_TRANSITION_MS}ms ease-out` : 'none';
    mediaElement.style.transform = `translate(calc(-50% + ${offsetX}px), -50%)`;
}

function clearSwipePreview() {
    if (lightboxSwipe.previewEl) {
        lightboxSwipe.previewEl.remove();
        lightboxSwipe.previewEl = null;
    }
    lightboxSwipe.previewTargetIndex = null;
    lightboxSwipe.previewDirection = 0;
}

function ensureSwipePreview(direction) {
    if (lightboxSwipe.previewEl && lightboxSwipe.previewDirection === direction) {
        return true;
    }

    clearSwipePreview();

    const details = getMediaDetailsAtIndex(
        direction < 0 ? state.currentMediaIndex + 1 : state.currentMediaIndex - 1
    );
    if (!details) return false;

    const previewEl = createLightboxMediaElement(details, {
        useFade: false,
        allowSlideshowHooks: false,
        isPreview: true
    });

    previewEl.dataset.swipePreview = '1';
    const width = dom.lightboxMediaDisplay.clientWidth || window.innerWidth;
    setHorizontalTransform(previewEl, direction < 0 ? width : -width, false);

    dom.lightboxMediaDisplay.appendChild(previewEl);
    lightboxSwipe.previewEl = previewEl;
    lightboxSwipe.previewTargetIndex = details.wrappedIndex;
    lightboxSwipe.previewDirection = direction;
    return true;
}

function updateSwipeDragPreview() {
    const activeEl = getActiveMediaElement();
    if (!activeEl) return;

    const direction = lightboxSwipe.deltaX < 0 ? -1 : 1;
    if (!ensureSwipePreview(direction)) return;

    const width = dom.lightboxMediaDisplay.clientWidth || window.innerWidth;
    const deltaX = lightboxSwipe.deltaX;
    const previewBase = direction < 0 ? width : -width;

    setHorizontalTransform(activeEl, deltaX, false);
    setHorizontalTransform(lightboxSwipe.previewEl, previewBase + deltaX, false);
}

function settleSwipeToCurrent() {
    const activeEl = getActiveMediaElement();
    if (!activeEl) {
        clearSwipePreview();
        return;
    }

    const width = dom.lightboxMediaDisplay.clientWidth || window.innerWidth;
    const direction = lightboxSwipe.previewDirection || (lightboxSwipe.deltaX < 0 ? -1 : 1);

    setHorizontalTransform(activeEl, 0, true);
    if (lightboxSwipe.previewEl) {
        const previewOffscreenX = direction < 0 ? width : -width;
        setHorizontalTransform(lightboxSwipe.previewEl, previewOffscreenX, true);
        window.setTimeout(clearSwipePreview, SWIPE_TRANSITION_MS + 20);
    }
}

function commitSwipeTransition() {
    const activeEl = getActiveMediaElement();
    if (!activeEl || !lightboxSwipe.previewEl || lightboxSwipe.previewTargetIndex === null) {
        settleSwipeToCurrent();
        return;
    }

    const width = dom.lightboxMediaDisplay.clientWidth || window.innerWidth;
    const direction = lightboxSwipe.previewDirection;
    const activeTargetX = direction < 0 ? -width : width;

    lightboxSwipe.transitionInProgress = true;
    setHorizontalTransform(activeEl, activeTargetX, true);
    setHorizontalTransform(lightboxSwipe.previewEl, 0, true);

    window.setTimeout(() => {
        state.setCurrentMediaIndex(lightboxSwipe.previewTargetIndex);
        clearSwipePreview();
        updateLightboxMedia({ transition: 'none' });
        lightboxSwipe.transitionInProgress = false;
    }, SWIPE_TRANSITION_MS + 20);
}

export function updateLightboxMedia(options = {}) {
    const { transition = 'fade' } = options;

    clearSwipePreview();
    resetZoom();
    const existingMedia = dom.lightboxMediaDisplay.querySelector('.media-display');
    if (existingMedia) {
        existingMedia.style.transform = '';
        existingMedia.classList.remove('zoomed');
    }

    // Clear any pending slideshow timer before loading the new media.
    // A new timer will be set in the onload handler if the slideshow is still active.
    if (state.slideshowInterval) {
        clearTimeout(state.slideshowInterval);
        state.setSlideshowInterval(null);
    }

    const details = getMediaDetailsAtIndex(state.currentMediaIndex);
    if (!details) {
        dom.lightboxMediaDisplay.innerHTML = '';
        return;
    }

    preloadAdjacentMedia(details.wrappedIndex);
    dom.lightboxFilename.textContent = details.displayPath;

    const useFade = transition === 'fade';
    const newMediaElement = createLightboxMediaElement(details, {
        useFade,
        allowSlideshowHooks: true,
        isPreview: false
    });

    dom.lightboxMediaDisplay.querySelectorAll('.media-display').forEach(el => {
        if (useFade) {
            el.classList.add('fade-out');
            setTimeout(() => el.remove(), 800);
        } else {
            el.remove();
        }
    });

    dom.lightboxMediaDisplay.appendChild(newMediaElement);
    updateActionButtonsVisibility();
}

export function showNextMedia() {
    // This function is now used for both automatic and manual "next" actions.
    const newIndex = (state.currentMediaIndex + 1) % state.currentDisplayedMedia.length;
    state.setCurrentMediaIndex(newIndex);
    updateLightboxMedia();
}

export function showPreviousMedia() {
    // This function is now used for manual "previous" actions.
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
    
    // MODIFIED: Removed logic that disabled navigation buttons during slideshow.
    // This allows the user to manually navigate while the slideshow is active.
    if (dom.lightboxOverlay.classList.contains('active')) {
        dom.lightboxPrev.style.pointerEvents = 'auto';
        dom.lightboxNext.style.pointerEvents = 'auto';
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

function onLightboxTouchStart(e) {
    if (!dom.lightboxOverlay.classList.contains('active')) return;
    if (state.currentDisplayedMedia.length < 2) return;
    if (state.isZoomed) return;
    if (lightboxSwipe.transitionInProgress) return;
    if (e.touches.length !== 1) return;
    if (e.target.closest('video')) return;

    const touch = e.touches[0];
    lightboxSwipe.tracking = true;
    lightboxSwipe.startX = touch.clientX;
    lightboxSwipe.startY = touch.clientY;
    lightboxSwipe.deltaX = 0;
    lightboxSwipe.deltaY = 0;
    lightboxSwipe.lockedHorizontal = false;
    lightboxSwipe.cancelled = false;
}

function onLightboxTouchMove(e) {
    if (!lightboxSwipe.tracking || lightboxSwipe.cancelled) return;
    if (e.touches.length !== 1) {
        lightboxSwipe.cancelled = true;
        return;
    }

    const touch = e.touches[0];
    lightboxSwipe.deltaX = touch.clientX - lightboxSwipe.startX;
    lightboxSwipe.deltaY = touch.clientY - lightboxSwipe.startY;

    if (!lightboxSwipe.lockedHorizontal) {
        const absX = Math.abs(lightboxSwipe.deltaX);
        const absY = Math.abs(lightboxSwipe.deltaY);
        if (absX < SWIPE_DIRECTION_LOCK_PX && absY < SWIPE_DIRECTION_LOCK_PX) {
            return;
        }
        lightboxSwipe.lockedHorizontal = absX > absY;
    }

    // Block browser gesture handling once we know this is a horizontal swipe.
    if (lightboxSwipe.lockedHorizontal) {
        e.preventDefault();
        updateSwipeDragPreview();
    }
}

function onLightboxTouchEnd() {
    if (!lightboxSwipe.tracking || lightboxSwipe.cancelled) {
        lightboxSwipe.tracking = false;
        return;
    }

    const absX = Math.abs(lightboxSwipe.deltaX);
    const absY = Math.abs(lightboxSwipe.deltaY);

    if (lightboxSwipe.lockedHorizontal && absX >= SWIPE_THRESHOLD_PX && absX > absY) {
        commitSwipeTransition();
    } else if (lightboxSwipe.lockedHorizontal) {
        settleSwipeToCurrent();
    } else {
        clearSwipePreview();
    }

    lightboxSwipe.tracking = false;
}

function onLightboxTouchCancel() {
    lightboxSwipe.tracking = false;
    lightboxSwipe.cancelled = true;
}

function onLightboxPointerDown(e) {
    if (!e.isPrimary) return;
    if (e.pointerType !== 'touch' && e.pointerType !== 'pen') return;

    onLightboxTouchStart({
        touches: [{ clientX: e.clientX, clientY: e.clientY }],
        target: e.target
    });
}

function onLightboxPointerMove(e) {
    if (!e.isPrimary) return;
    if (e.pointerType !== 'touch' && e.pointerType !== 'pen') return;

    onLightboxTouchMove({
        touches: [{ clientX: e.clientX, clientY: e.clientY }],
        preventDefault: () => e.preventDefault()
    });
}

function onLightboxPointerUp(e) {
    if (!e.isPrimary) return;
    if (e.pointerType !== 'touch' && e.pointerType !== 'pen') return;
    onLightboxTouchEnd();
}

function onLightboxPointerCancel(e) {
    if (!e.isPrimary) return;
    if (e.pointerType !== 'touch' && e.pointerType !== 'pen') return;
    onLightboxTouchCancel();
}

// --- Initialization Function ---
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

    dom.lightboxMediaDisplay.addEventListener('touchstart', onLightboxTouchStart, { passive: true });
    dom.lightboxMediaDisplay.addEventListener('touchmove', onLightboxTouchMove, { passive: false });
    dom.lightboxMediaDisplay.addEventListener('touchend', onLightboxTouchEnd, { passive: true });
    dom.lightboxMediaDisplay.addEventListener('touchcancel', onLightboxTouchCancel, { passive: true });

    // Pointer-event fallback for touch-enabled desktop browsers where touch events are limited.
    dom.lightboxMediaDisplay.addEventListener('pointerdown', onLightboxPointerDown, { passive: true });
    dom.lightboxMediaDisplay.addEventListener('pointermove', onLightboxPointerMove, { passive: false });
    dom.lightboxMediaDisplay.addEventListener('pointerup', onLightboxPointerUp, { passive: true });
    dom.lightboxMediaDisplay.addEventListener('pointercancel', onLightboxPointerCancel, { passive: true });
}
