// This module exports a single object `dom` which will hold all element references.
// It must be initialized by calling initDOMElements() after the DOM is loaded.

const dom = {};

export function initDOMElements() {
    // --- Main Containers ---
    dom.topLevelFoldersContainer = document.getElementById('topLevelFoldersContainer');
    dom.subFoldersContainer = document.getElementById('subFoldersContainer');
    dom.galleryContainer = document.getElementById('galleryContainer');
    dom.topLevelFoldersSection = document.getElementById('topLevelFoldersSection');
    dom.subFoldersSection = document.getElementById('subFoldersSection');
    dom.gallerySection = document.getElementById('gallerySection');
    dom.breadcrumbPathContent = document.getElementById('breadcrumbPathContent');

    // --- Action Buttons ---
    dom.slideshowBtnBreadcrumb = document.getElementById('slideshowBtnBreadcrumb');
    dom.slideshowBtnLightbox = document.getElementById('slideshowBtnLightbox');
    dom.trashDeleteBtn = document.getElementById('trashDeleteBtn');
    dom.trashRestoreBtn = document.getElementById('trashRestoreBtn');
    dom.downloadRawBtn = document.getElementById('downloadRawBtn');
    dom.emptyTrashBtn = document.getElementById('emptyTrashBtn');
    dom.restoreAllBtn = document.getElementById('restoreAllBtn');
    dom.homeBtnTopRight = document.getElementById('homeBtnTopRight');
    dom.themeToggleButton = document.getElementById('themeToggleButton');
    dom.uploadFilesBtn = document.getElementById('uploadFilesBtn');

    // --- Multi-Select Action Buttons ---
    dom.selectAllBtn = document.getElementById('selectAllBtn');
    dom.deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
    dom.selectedCount = document.getElementById('selectedCount');
    dom.restoreSelectedBtn = document.getElementById('restoreSelectedBtn');
    dom.selectedRestoreCount = document.getElementById('selectedRestoreCount');
    // NEW "Delete Selected Permanently" BUTTON ELEMENTS ADDED HERE
    dom.deleteSelectedPermanentBtn = document.getElementById('deleteSelectedPermanentBtn');
    dom.selectedPermanentDeleteCount = document.getElementById('selectedPermanentDeleteCount');


    // --- Lightbox Elements ---
    dom.lightboxOverlay = document.getElementById('lightboxOverlay');
    dom.lightboxMediaDisplay = document.getElementById('lightboxMediaDisplay');
    dom.lightboxPrev = document.getElementById('lightboxPrev');
    dom.lightboxNext = document.getElementById('lightboxNext');
    dom.lightboxClose = document.getElementById('lightboxClose');
    dom.lightboxFilename = document.getElementById('lightboxFilename');
    dom.loadingSpinner = document.getElementById('loadingSpinner');

    // --- Confirmation Modal Elements ---
    dom.confirmationModalOverlay = document.getElementById('confirmationModalOverlay');
    dom.confirmActionBtn = document.getElementById('confirmActionBtn');
    dom.cancelActionBtn = document.getElementById('cancelActionBtn');
    dom.confirmationMessage = document.getElementById('confirmationMessage');

    // --- Create Folder Modal Elements ---
    dom.createFolderModalOverlay = document.getElementById('createFolderModalOverlay');
    dom.createFolderModalTitle = document.getElementById('createFolderModalTitle');
    dom.newFolderNameInput = document.getElementById('newFolderNameInput');
    dom.confirmCreateFolderBtn = document.getElementById('confirmCreateFolderBtn');
    dom.cancelCreateFolderBtn = document.getElementById('cancelCreateFolderBtn');

    // --- Upload Modal Elements ---
    dom.fileInput = document.getElementById('fileInput');
    dom.uploadProgressModalOverlay = document.getElementById('uploadProgressModalOverlay');
    dom.uploadList = document.getElementById('uploadList');
    dom.overallProgressBar = document.getElementById('overallProgressBar');
    dom.overallProgressText = document.getElementById('overallProgressText');
    dom.startUploadBtn = document.getElementById('startUploadBtn');
    dom.cancelUploadBtn = document.getElementById('cancelUploadBtn');
    dom.uploadTargetFolderInfo = document.getElementById('uploadTargetFolderInfo');

    // --- Message Box ---
    dom.messageBox = document.getElementById('messageBox');
}

export default dom;