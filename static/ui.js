// This module contains functions that directly manipulate the DOM.

import * as state from './state.js';
import dom from './dom-elements.js';
import * as config from './config.js';
import { openLightbox } from './lightbox.js';
import { showConfirmationModal, showCreateFolderModal } from './modals.js';

// --- Theme ---
export function setTheme(theme) {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const lightIcon = dom.themeToggleButton.querySelector('.light_mode_icon');
    const darkIcon = dom.themeToggleButton.querySelector('.dark_mode_icon');
    if (theme === 'dark') {
        lightIcon.classList.remove('hidden');
        darkIcon.classList.add('hidden');
    } else {
        lightIcon.classList.add('hidden');
        darkIcon.classList.remove('hidden');
    }
}

// --- UI Visibility and Updates ---
export function updateActionButtonsVisibility() {
    const isLightboxActive = dom.lightboxOverlay.classList.contains('active');
    const isViewingTrash = state.currentPath.includes(config.TRASH_FOLDER_NAME);

    dom.slideshowBtnBreadcrumb.classList.toggle('hidden', isViewingTrash);

    if (isLightboxActive) {
        dom.slideshowBtnLightbox.classList.remove('hidden');
        dom.trashDeleteBtn.classList.remove('hidden');
        dom.trashRestoreBtn.classList.toggle('hidden', !isViewingTrash);
        const mediaItem = state.currentDisplayedMedia[state.currentMediaIndex];
        const isRaw = mediaItem && config.RAW_EXTENSIONS.includes('.' + mediaItem.filename.split('.').pop().toLowerCase());
        dom.downloadRawBtn.classList.toggle('hidden', !isRaw || isViewingTrash);
    } else {
        dom.slideshowBtnLightbox.classList.add('hidden');
        dom.trashDeleteBtn.classList.add('hidden');
        dom.trashRestoreBtn.classList.add('hidden');
        dom.downloadRawBtn.classList.add('hidden');
    }

    dom.uploadFilesBtn.classList.toggle('hidden', isViewingTrash);
    // REMOVED emptyTrashBtn and restoreAllBtn logic
}

// --- Breadcrumb ---
export function updateBreadcrumb(onNavigate) {
    dom.breadcrumbPathContent.innerHTML = '';
    dom.breadcrumbPathContent.classList.add('flex', 'items-center', 'flex-wrap', 'gap-2');

    const homeBtn = createFolderNavLink("Home", [], null, false, true, onNavigate);
    dom.breadcrumbPathContent.appendChild(homeBtn);

    if (state.currentPath.length > 0) {
        const separator = document.createElement('span');
        separator.className = 'breadcrumb-separator';
        separator.innerHTML = '&#11157;';
        dom.breadcrumbPathContent.appendChild(separator);
    }

    state.currentPath.forEach((segment, index) => {
        const path = state.currentPath.slice(0, index + 1);
        const link = createFolderNavLink(segment, path, null, segment === config.TRASH_FOLDER_NAME, true, onNavigate);
        dom.breadcrumbPathContent.appendChild(link);

        if (index < state.currentPath.length - 1) {
            const separator = document.createElement('span');
            separator.className = 'breadcrumb-separator';
            separator.innerHTML = '&#11157;';
            dom.breadcrumbPathContent.appendChild(separator);
        }
    });
}

// --- Element Creation ---
export function createFolderNavLink(folderName, pathSegments, count, isTrash, isBreadcrumb, onNavigate) {
    const link = document.createElement('a');
    link.href = "#";
    link.className = 'nav-link folder-nav-button';
    link.style.backgroundColor = 'transparent';
    link.style.boxShadow = 'none';
    link.style.color = 'inherit';
    link.style.padding = '0.5rem';

    if (isTrash) link.classList.add('trash-nav-link');
    if (isBreadcrumb) {
        link.classList.add('breadcrumb-folder-link');
        if (folderName === "Home") link.classList.add('home-breadcrumb-btn');
    }

    const folderIconWrapper = document.createElement('div');
    folderIconWrapper.className = 'folder-icon-wrapper';

    const folderIcon = document.createElement('i');
    folderIcon.className = 'material-icons folder-icon';
    folderIcon.textContent = isTrash ? 'delete' : (folderName === "Home" ? 'home' : 'folder');

    const nameText = document.createElement('span');
    nameText.className = 'folder-name-overlay';
    nameText.textContent = folderName;

    folderIconWrapper.append(folderIcon, nameText);
    link.appendChild(folderIconWrapper);

    if (count !== null) {
        const countText = document.createElement('span');
        countText.className = 'item-count';
        countText.textContent = `(${count} items)`;
        link.appendChild(countText);
    }

    if (!isTrash && !isBreadcrumb) {
        const deleteBtn = document.createElement('div');
        deleteBtn.className = 'delete-folder-btn';
        deleteBtn.innerHTML = '<i class="material-icons">close</i>';
        deleteBtn.title = `Delete folder ${folderName}`;
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            showConfirmationModal(pathSegments, false, false);
        };
        link.appendChild(deleteBtn);
    }
    
    link.onclick = (e) => {
        e.preventDefault();
        onNavigate(pathSegments);
    };

    return link;
}

export function createAddFolderButton() {
    const button = document.createElement('a');
    button.href = "#";
    button.classList.add('nav-link', 'folder-nav-button', 'add-folder-square-btn');
    button.title = "Create New Folder";

    const icon = document.createElement('i');
    icon.classList.add('material-icons');
    icon.textContent = 'add';

    button.appendChild(icon);

    button.onclick = (e) => {
        e.preventDefault();
        showCreateFolderModal();
    };
    return button;
}


// --- Gallery Display ---
const lazyLoadObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const mediaElement = entry.target;
            mediaElement.src = mediaElement.dataset.src;
            if (mediaElement.tagName === 'IMG') {
                mediaElement.onload = () => mediaElement.classList.add('loaded');
            }
            observer.unobserve(mediaElement);
        }
    });
}, { rootMargin: '0px 0px 100px 0px', threshold: 0.01 });

export function displayMediaThumbnails(mediaFiles, onSelectionChange) {
    const isViewingTrash = state.currentPath.includes(config.TRASH_FOLDER_NAME);
    dom.galleryContainer.innerHTML = '';
    lazyLoadObserver.disconnect();
    
    if (mediaFiles.length > 0) {
        dom.gallerySection.classList.remove('hidden');
        mediaFiles.forEach((mediaItem, index) => {
            const isVideo = config.VIDEO_EXTENSIONS.includes('.' + mediaItem.filename.split('.').pop().toLowerCase());
            const galleryItem = document.createElement('div');
            galleryItem.className = 'gallery-item relative';
            galleryItem.dataset.index = index;

            const mediaElement = document.createElement('img');
            const path = isViewingTrash ? mediaItem.relative_path_in_trash : mediaItem.original_path;
            mediaElement.dataset.src = `/api/thumbnail/${path}`;
            mediaElement.src = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
            mediaElement.className = 'thumbnail-fade-in';
            mediaElement.alt = `Thumbnail for ${mediaItem.filename}`;
            mediaElement.title = mediaItem.filename;

            if (isVideo) {
                const videoOverlay = document.createElement('div');
                videoOverlay.className = 'video-thumbnail-overlay';
                galleryItem.appendChild(videoOverlay);
            }

            galleryItem.onclick = (e) => {
                // Prevent lightbox opening if the click was on the checkbox
                if (e.target.type !== 'checkbox') {
                    openLightbox(index);
                }
            };

            // Create and append the selection checkbox
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'thumbnail-checkbox';
            checkbox.dataset.path = path; // Store the path for identification
            checkbox.onchange = () => {
                galleryItem.classList.toggle('selected', checkbox.checked);
                onSelectionChange();
            };
            
            galleryItem.append(checkbox, mediaElement);
            dom.galleryContainer.appendChild(galleryItem);
            lazyLoadObserver.observe(mediaElement);
        });
    } else {
        dom.gallerySection.classList.remove('hidden');
        dom.galleryContainer.innerHTML = `<div class="col-span-full border-4 border-dashed border-gray-500 rounded-lg h-64 flex flex-col items-center justify-center text-center text-gray-500">
                                            <i class="material-icons text-6xl">cloud_upload</i>
                                            <p class="mt-4">No media found in this folder.</p>
                                            <p>Drag and drop files here to upload.</p>
                                        </div>`;
    }
}

// --- Message Box ---
let messageTimeout = null;
export function showMessage(message, type = 'info') {
    if (messageTimeout) clearTimeout(messageTimeout);
    dom.messageBox.textContent = message;
    dom.messageBox.className = 'show';
    if (type === 'success') dom.messageBox.style.backgroundColor = '#10B981';
    else if (type === 'error') dom.messageBox.style.backgroundColor = '#EF4444';
    else dom.messageBox.style.backgroundColor = '#333';
    messageTimeout = setTimeout(() => dom.messageBox.classList.remove('show'), 3000);
}
