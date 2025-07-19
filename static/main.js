
        // --- Configuration for Image Library Path ---
        const TRASH_FOLDER_NAME = '_Trash'; // Keep this consistent with server.py

        let currentPath = []; // Stores the current navigation path (e.g., ['2023', '01', '01'])
        let currentDisplayedMedia = []; // Stores the list of media (full relative paths) currently displayed in the gallery grid or slideshow
        let currentMediaIndex = 0; // Stores the index of the currently viewed media in the lightbox

        // Slideshow variables
        let slideshowInterval = null;
        let isSlideshowRunning = false;
        const slideshowDelay = 5000; // Changed to 5 seconds as per your previous request

        // Define image and video extensions for client-side check (matching server.py)
        const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.avif'];
        const RAW_EXTENSIONS = ['.nef', '.nrw', '.cr2', '.cr3', '.crw', '.arw', '.srf', '.sr2',
                                  '.orf', '.raf', '.rw2', '.raw', '.dng', '.kdc', '.dcr', '.erf',
                                  '.3fr', '.mef', '.pef', '.x3f'];
        const VIDEO_EXTENSIONS = ['.mp4', '.mov', '.webm', '.ogg', '.avi', '.mkv'];
        const MEDIA_EXTENSIONS = IMAGE_EXTENSIONS.concat(RAW_EXTENSIONS).concat(VIDEO_EXTENSIONS);


        const topLevelFoldersContainer = document.getElementById('topLevelFoldersContainer');
        const subFoldersContainer = document.getElementById('subFoldersContainer');
        const galleryContainer = document.getElementById('galleryContainer');

        const topLevelFoldersSection = document.getElementById('topLevelFoldersSection');
        const subFoldersSection = document.getElementById('subFoldersSection');
        const gallerySection = document.getElementById('gallerySection');

        const breadcrumbPathContent = document.getElementById('breadcrumbPathContent'); // NEW: Reference to the new container
        
        // Action buttons (now distinct for breadcrumb and lightbox)
        const slideshowBtnBreadcrumb = document.getElementById('slideshowBtnBreadcrumb'); 
        const slideshowBtnLightbox = document.getElementById('slideshowBtnLightbox');
        const trashDeleteBtn = document.getElementById('trashDeleteBtn'); // This is now the single delete button in lightbox
        const trashRestoreBtn = document.getElementById('trashRestoreBtn'); // This is now the single restore button in lightbox
        const downloadRawBtn = document.getElementById('downloadRawBtn'); // NEW: Download RAW button
        const emptyTrashBtn = document.getElementById('emptyTrashBtn'); // NEW: Empty Trash button
        const restoreAllBtn = document.getElementById('restoreAllBtn'); // NEW: Restore All button

        // Lightbox elements
        const lightboxOverlay = document.getElementById('lightboxOverlay');
        const lightboxMediaDisplay = document.getElementById('lightboxMediaDisplay');
        const lightboxPrev = document.getElementById('lightboxPrev');
        const lightboxNext = document.getElementById('lightboxNext');
        const lightboxClose = document.getElementById('lightboxClose'); // Now a button inside the container
        const lightboxFilename = document.getElementById('lightboxFilename'); 
        const loadingSpinner = document.getElementById('loadingSpinner'); // Get reference to the spinner

        // Confirmation Modal elements
        const confirmationModalOverlay = document.getElementById('confirmationModalOverlay');
        const confirmActionBtn = document.getElementById('confirmActionBtn');
        const cancelActionBtn = document.getElementById('cancelActionBtn');
        const confirmationMessage = document.getElementById('confirmationMessage');

        let fileToProcessPath = ''; // Stores the full relative path of the file to be moved/deleted/restored
        let folderToProcessPath = []; // Stores the array path of the folder to be deleted
        let isFolderDeletion = false; // Flag to differentiate between file and folder deletion
        let spinnerTimeout = null; // To hold the timeout ID for the spinner

        // Theme Toggle Button
        const themeToggleButton = document.getElementById('themeToggleButton');

        // NEW: Create Folder Modal Elements (variables for elements, not the buttons themselves)
        const createFolderModalOverlay = document.getElementById('createFolderModalOverlay');
        const createFolderModalContent = document.getElementById('createFolderModalContent'); // Added to match new class
        const createFolderModalTitle = document.getElementById('createFolderModalTitle');
        const newFolderNameInput = document.getElementById('newFolderNameInput');
        const confirmCreateFolderBtn = document.getElementById('confirmCreateFolderBtn');
        const cancelCreateFolderBtn = document.getElementById('cancelCreateFolderBtn');
        let folderCreationType = ''; // 'year', 'month', 'day'

        // NEW: Upload Elements
        const uploadFilesBtn = document.getElementById('uploadFilesBtn');
        const fileInput = document.getElementById('fileInput');
        const uploadProgressModalOverlay = document.getElementById('uploadProgressModalOverlay');
        const uploadList = document.getElementById('uploadList');
        const overallProgressBarContainer = document.getElementById('overallProgressBarContainer');
        const overallProgressBar = document.getElementById('overallProgressBar');
        const overallProgressText = document.getElementById('overallProgressText');
        const startUploadBtn = document.getElementById('startUploadBtn');
        const cancelUploadBtn = document.getElementById('cancelUploadBtn');
        const uploadTargetFolderInfo = document.getElementById('uploadTargetFolderInfo'); // NEW: Target folder info element
        let filesToUpload = [];
        let uploadedFilesCount = 0;

        // NEW: Home Button (Top Right) reference
        const homeBtnTopRight = document.getElementById('homeBtnTopRight');


        // Function to set the theme
        function setTheme(theme) {
            document.body.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
            // Update button icon
            const lightIcon = themeToggleButton.querySelector('.light_mode_icon');
            const darkIcon = themeToggleButton.querySelector('.dark_mode_icon');
            if (theme === 'dark') {
                lightIcon.classList.remove('hidden');
                darkIcon.classList.add('hidden');
            } else {
                lightIcon.classList.add('hidden');
                darkIcon.classList.remove('hidden');
            }
        }

        // Function to update the visibility of action buttons based on current view
        function updateActionButtonsVisibility() {
            const isLightboxActive = lightboxOverlay.classList.contains('active');
            const isViewingTrash = currentPath.includes(TRASH_FOLDER_NAME);
            
            // MODIFIED: Simplified the logic to show the slideshow button
            if (!isViewingTrash) {
                slideshowBtnBreadcrumb.classList.remove('hidden');
            } else {
                slideshowBtnBreadcrumb.classList.add('hidden');
            }

            if (isLightboxActive) {
                slideshowBtnLightbox.classList.remove('hidden');
                // Trash/Restore buttons in lightbox
                if (isViewingTrash) {
                    trashDeleteBtn.classList.remove('hidden'); // Permanent delete
                    trashRestoreBtn.classList.remove('hidden'); // Restore
                } else {
                    trashDeleteBtn.classList.remove('hidden'); // Move to trash
                    trashRestoreBtn.classList.add('hidden');
                }
                // Download RAW button in lightbox
                const isRawFile = currentDisplayedMedia[currentMediaIndex] && RAW_EXTENSIONS.includes('.' + currentDisplayedMedia[currentMediaIndex].filename.split('.').pop().toLowerCase());
                if (isRawFile && !isViewingTrash) {
                    downloadRawBtn.classList.remove('hidden');
                } else {
                    downloadRawBtn.classList.add('hidden');
                }
            } else {
                slideshowBtnLightbox.classList.add('hidden');
                trashDeleteBtn.classList.add('hidden');
                trashRestoreBtn.classList.add('hidden');
                downloadRawBtn.classList.add('hidden');
            }

            // Upload button
            if (isViewingTrash) {
                uploadFilesBtn.classList.add('hidden');
            } else {
                uploadFilesBtn.classList.remove('hidden');
            }

            // MODIFIED: Show/hide bulk trash action buttons
            if (isViewingTrash) {
                emptyTrashBtn.classList.remove('hidden');
                restoreAllBtn.classList.remove('hidden');
            } else {
                emptyTrashBtn.classList.add('hidden');
                restoreAllBtn.classList.add('hidden');
            }

            updateSlideshowControls(); // Ensure slideshow icons are correct
        }


        // Intersection Observer for lazy loading images
        const lazyLoadObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const mediaElement = entry.target;
                    // Check if it's an image or video and load the actual source
                    if (mediaElement.tagName === 'IMG' && mediaElement.dataset.src) {
                        mediaElement.src = mediaElement.dataset.src;
                        mediaElement.onload = () => mediaElement.classList.add('loaded'); // Add 'loaded' class on image load
                    } else if (mediaElement.tagName === 'VIDEO' && mediaElement.dataset.src) {
                        mediaElement.src = mediaElement.dataset.src;
                        mediaElement.load(); // For videos, call load() to start loading
                        mediaElement.addEventListener('loadeddata', () => mediaElement.classList.add('loaded')); // Add 'loaded' class on video metadata load
                    }
                    observer.unobserve(mediaElement); // Stop observing once loaded
                }
            });
        }, {
            rootMargin: '0px 0px 100px 0px', // Load images 100px before they enter the viewport
            threshold: 0.01 // Trigger when 1% of the element is visible
        });

        // Function to update the breadcrumb navigation and button visibility
        function updateBreadcrumb() {
            breadcrumbPathContent.innerHTML = ''; // Clear existing content
            // Ensure breadcrumbPathContent is the flex container for its children
            breadcrumbPathContent.classList.add('flex', 'items-center', 'flex-wrap', 'gap-2');

            // Create the Home button for the breadcrumb
            const homeBreadcrumbBtn = createFolderNavLink("Home", [], null, false, true); // Added isBreadcrumb = true
            homeBreadcrumbBtn.onclick = async (e) => {
                e.preventDefault();
                currentPath = [];
                await loadTopLevelFolders();
                updateBreadcrumb();
            };
            breadcrumbPathContent.appendChild(homeBreadcrumbBtn);

            // Add the first separator after the home button, if there are path segments
            if (currentPath.length > 0) {
                const separator = document.createElement('span');
                separator.classList.add('breadcrumb-separator');
                separator.innerHTML = '&#11157;'; // Right arrow
                breadcrumbPathContent.appendChild(separator);
            }

            currentPath.forEach((segment, index) => {
                const link = createFolderNavLink(segment, currentPath.slice(0, index + 1), null, segment === TRASH_FOLDER_NAME, true); // Added isBreadcrumb = true
                link.onclick = (e) => {
                    e.preventDefault();
                    currentPath = currentPath.slice(0, index + 1);
                    loadSubFoldersAndFiles(currentPath);
                    updateBreadcrumb();
                };
                breadcrumbPathContent.appendChild(link);

                // Add separator after each segment, except the last one
                if (index < currentPath.length - 1) {
                    const separator = document.createElement('span');
                    separator.classList.add('breadcrumb-separator');
                    separator.innerHTML = '&#11157;'; // Right arrow
                    breadcrumbPathContent.appendChild(separator);
                }
            });

            updateActionButtonsVisibility(); // Update visibility of action buttons
        }

        // Home button functionality (new circular button in top right)
        homeBtnTopRight.addEventListener('click', async (event) => {
            event.preventDefault();
            currentPath = [];
            await loadTopLevelFolders();
            updateBreadcrumb();
        });

        // Helper function to show loading state
        function showLoading(container) {
            container.innerHTML = '<p class="text-center text-gray-600 col-span-full">Loading...</p>';
        }

        // Helper function to render media thumbnails in the gallery grid
        function displayMediaThumbnails(mediaFiles, pathSegments) {
            const isViewingTrash = pathSegments.includes(TRASH_FOLDER_NAME);
            
            // Filter out any null or undefined items before sorting
            const filteredMediaFiles = mediaFiles.filter(item => item !== null && item !== undefined);

            currentDisplayedMedia = filteredMediaFiles.sort((a, b) => {
                // Sort by filename
                let nameA = (a && typeof a === 'object' && a.filename) ? a.filename.toLowerCase() : '';
                let nameB = (b && typeof b === 'object' && b.filename) ? b.filename.toLowerCase() : '';
                return nameA.localeCompare(nameB);
            });
            currentPath = pathSegments; 

            galleryContainer.innerHTML = '';

            // Disconnect observer before adding new elements to avoid observing old elements
            lazyLoadObserver.disconnect();

            if (currentDisplayedMedia.length > 0) {
                gallerySection.classList.remove('hidden');
                currentDisplayedMedia.forEach((mediaItem, index) => {
                    // mediaItem is now guaranteed to be an object with filename and original_path (or relative_path_in_trash)
                    let fullRelativePathForOriginal; 
                    let filename = mediaItem.filename; 

                    if (isViewingTrash) {
                        fullRelativePathForOriginal = mediaItem.relative_path_in_trash; 
                    } else {
                        fullRelativePathForOriginal = mediaItem.original_path; 
                    }
                    
                    if (typeof filename === 'string' && filename) { 
                        const fileExtension = filename.split('.').pop().toLowerCase();
                        const isVideo = VIDEO_EXTENSIONS.includes('.' + fileExtension);

                        const galleryItem = document.createElement('div');
                        galleryItem.classList.add('gallery-item', 'relative');
                        galleryItem.dataset.index = index; 

                        // MODIFIED: Always use an <img> for the thumbnail, even for videos
                        let mediaElement = document.createElement('img');
                        const thumbnailMediaUrl = `/api/thumbnail/${fullRelativePathForOriginal}`;
                        mediaElement.dataset.src = thumbnailMediaUrl; 
                        mediaElement.src = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='; 

                        if (isVideo) {
                            const videoOverlay = document.createElement('div');
                            videoOverlay.classList.add('video-thumbnail-overlay');
                            galleryItem.appendChild(videoOverlay);
                        }

                        mediaElement.classList.add('thumbnail-fade-in');
                        mediaElement.alt = `Media from ${pathSegments.join('/')}`;
                        mediaElement.title = filename;

                        mediaElement.onerror = function() {
                            this.onerror=null;
                            this.src = `https://placehold.co/300x250/cccccc/333333?text=Unsupported+Format`;
                            this.alt = `File not found: ${filename}`;
                            console.error(`Failed to load media: ${thumbnailMediaUrl}`); 
                        };

                        galleryItem.onclick = (e) => {
                            if (!e.target.classList.contains('delete-thumbnail-btn')) {
                                openLightbox(index);
                            }
                        };

                        const filenameOverlay = document.createElement('div');
                        filenameOverlay.classList.add('absolute', 'bottom-0', 'left-0', 'right-0', 'bg-black', 'bg-opacity-50', 'text-white', 'text-sm', 'p-2', 'truncate', 'rounded-b-lg');
                        filenameOverlay.textContent = filename;

                        const deleteBtn = document.createElement('div');
                        deleteBtn.classList.add('delete-thumbnail-btn');
                        deleteBtn.innerHTML = '<i class="material-icons">delete</i>';
                        deleteBtn.title = isViewingTrash ? `Delete ${filename} Forever` : `Move ${filename} to Trash`;
                        deleteBtn.onclick = (e) => {
                            e.stopPropagation(); 
                            const pathForAction = isViewingTrash ? mediaItem.relative_path_in_trash : mediaItem.original_path;
                            showConfirmationModal(pathForAction, isViewingTrash, false);
                        };

                        galleryItem.appendChild(mediaElement);
                        galleryItem.appendChild(filenameOverlay);
                        galleryItem.appendChild(deleteBtn); 
                        galleryContainer.appendChild(galleryItem);

                        lazyLoadObserver.observe(mediaElement);
                    } else {
                        console.warn(`Skipping invalid media item: filename is not a valid string for mediaItem:`, mediaItem);
                    }
                });
            } else {
                gallerySection.classList.remove('hidden');
                galleryContainer.innerHTML = `<div class="col-span-full border-4 border-dashed border-gray-500 rounded-lg h-64 flex flex-col items-center justify-center text-center text-gray-500">
                                                <i class="material-icons text-6xl">cloud_upload</i>
                                                <p class="mt-4">No media found in this folder.</p>
                                                <p>Drag and drop files here to upload.</p>
                                            </div>`;
            }
            updateActionButtonsVisibility(); 
        }

        // Helper function to create the dynamic '+' button
        function createAddFolderButton(type) {
            const button = document.createElement('a');
            button.href = "#";
            // NEW: Styles for square + button
            button.classList.add('nav-link', 'folder-nav-button', 'add-folder-square-btn'); 
            button.title = "Create New";
            
            const icon = document.createElement('i');
            icon.classList.add('material-icons');
            icon.textContent = 'add'; // Plus icon

            button.appendChild(icon);

            button.onclick = (e) => {
                e.preventDefault();
                showCreateFolderModal(type);
            };
            return button;
        }

        // Helper function to create a folder navigation link with delete button
        function createFolderNavLink(folderName, pathSegments, count = null, isTrashFolder = false, isBreadcrumb = false) {
            const link = document.createElement('a');
            link.href = "#";
            link.classList.add('nav-link', 'folder-nav-button'); // Keep base classes

            // NEW: Remove background/shadow for folder-nav-button
            link.style.backgroundColor = 'transparent';
            link.style.boxShadow = 'none';
            link.style.color = 'inherit'; /* Inherit text color from parent for light/dark theme */
            link.style.padding = '0.5rem'; /* Adjust padding for compact look */

            if (isTrashFolder) {
                link.classList.add('trash-nav-link');
            }
            // Add specific class for breadcrumb items if needed for further styling
            if (isBreadcrumb) {
                link.classList.add('breadcrumb-folder-link');
                // For breadcrumb home button, make it round
                if (folderName === "Home") {
                    link.classList.add('home-breadcrumb-btn'); /* Apply specific home button styles */
                }
            }

            const folderIconWrapper = document.createElement('div');
            folderIconWrapper.classList.add('folder-icon-wrapper');

            const folderIcon = document.createElement('i');
            folderIcon.classList.add('material-icons', 'folder-icon');
            folderIcon.textContent = isTrashFolder ? 'delete' : (folderName === "Home" ? 'home' : 'folder'); // Use home icon for Home button

            const nameText = document.createElement('span');
            nameText.classList.add('folder-name-overlay');
            nameText.textContent = folderName;

            folderIconWrapper.appendChild(folderIcon);
            folderIconWrapper.appendChild(nameText);
            link.appendChild(folderIconWrapper);

            if (count !== undefined && count !== null) {
                const countText = document.createElement('span');
                countText.classList.add('item-count');
                countText.textContent = `(${count} items)`;
                link.appendChild(countText);
            }

            // Add delete button for non-trash folders (and not for breadcrumb items, as they are navigation, not actual folders to delete from that context)
            if (!isTrashFolder && !isBreadcrumb) {
                const deleteBtn = document.createElement('div');
                deleteBtn.classList.add('delete-folder-btn');
                deleteBtn.innerHTML = '<i class="material-icons">close</i>'; // Red cross icon
                deleteBtn.title = `Delete folder ${folderName}`;
                deleteBtn.onclick = (e) => {
                    e.stopPropagation(); // Prevent folder navigation when clicking delete
                    // Pass the full path segments for the folder to be deleted
                    const fullFolderPathToDelete = [...pathSegments]; // Use the pathSegments passed to the function
                    showConfirmationModal(fullFolderPathToDelete, false, false); // Pass array, not permanent, not restore
                };
                link.appendChild(deleteBtn);
            }

            return link;
        }


        // 1. Load Top-Level Folders
        async function loadTopLevelFolders() {
            subFoldersSection.classList.add('hidden');
            gallerySection.classList.add('hidden');
            topLevelFoldersSection.classList.remove('hidden');
            currentPath = []; 
            
            topLevelFoldersContainer.innerHTML = '';
            showLoading(topLevelFoldersContainer);
            try {
                const response = await fetch('/api/folders');
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`HTTP error! status: ${response.status}, response: ${errorText}`);
                }
                const data = await response.json();
                const foldersData = data.folders;
                const files = data.files;

                topLevelFoldersContainer.innerHTML = ''; 
                if (foldersData.length > 0) {
                    foldersData.forEach(folderItem => {
                        const link = createFolderNavLink(folderItem.name, [folderItem.name], folderItem.count);
                        link.onclick = (e) => {
                            e.preventDefault();
                            currentPath = [folderItem.name]; 
                            loadSubFoldersAndFiles(currentPath);
                            updateBreadcrumb();
                        };
                        topLevelFoldersContainer.appendChild(link);
                    });
                } else {
                    topLevelFoldersContainer.innerHTML = '<p class="text-center text-gray-600 col-span-full">No folders found.</p>';
                }

                displayMediaThumbnails(files, []);

                // Add the dynamic "Create New Folder" button
                topLevelFoldersContainer.appendChild(createAddFolderButton('folder'));

                // Add the Trash button as the last item
                const trashLink = createFolderNavLink(TRASH_FOLDER_NAME, [TRASH_FOLDER_NAME], 0, true); // Initial count 0
                trashLink.onclick = (e) => {
                    e.preventDefault();
                    currentPath = [TRASH_FOLDER_NAME]; 
                    loadTrashContent();
                    updateBreadcrumb();
                };
                
                // Fetch trash count separately for the button
                try {
                    const trashResponse = await fetch('/api/trash_content');
                    if (trashResponse.ok) {
                        const trashData = await trashResponse.json();
                        if (trashData.count !== undefined && trashData.count !== null) {
                            // Update the count displayed on the trashLink
                            const existingCountSpan = trashLink.querySelector('.item-count');
                            if (existingCountSpan) {
                                existingCountSpan.textContent = `(${trashData.count} items)`;
                            } else {
                                const trashCountText = document.createElement('span'); 
                                trashCountText.classList.add('item-count');
                                trashCountText.textContent = `(${trashData.count} items)`;
                                trashLink.appendChild(trashCountText);
                            }
                        }
                    }
                } catch (trashError) {
                    console.error('Error fetching trash count for button:', trashError);
                }
                topLevelFoldersContainer.appendChild(trashLink);

            } catch (error) {
                console.error('Error fetching top-level folders:', error);
                topLevelFoldersContainer.innerHTML = '<p class="text-center text-red-600 col-span-full">Error loading folders. Is the server running?</p>';
            }
            updateActionButtonsVisibility(); 
        }

        // 2. Load Sub-Folders and Files
        async function loadSubFoldersAndFiles(pathSegments) {
            topLevelFoldersSection.classList.add('hidden');
            subFoldersSection.classList.remove('hidden');
            
            showLoading(subFoldersContainer);
            currentPath = pathSegments; 

            try {
                const response = await fetch(`/api/folders/${pathSegments.join('/')}`);
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`HTTP error! status: ${response.status}, response: ${errorText}`);
                }
                const data = await response.json();
                const subFoldersData = data.folders; 
                const files = data.files; 

                subFoldersContainer.innerHTML = '';
                if (subFoldersData.length > 0) {
                    subFoldersData.forEach(folderItem => {
                        const link = createFolderNavLink(folderItem.name, [...pathSegments, folderItem.name], folderItem.count);
                        link.onclick = (e) => {
                            e.preventDefault();
                            currentPath = [...pathSegments, folderItem.name]; 
                            loadSubFoldersAndFiles(currentPath);
                            updateBreadcrumb();
                        };
                        subFoldersContainer.appendChild(link);
                    });
                } else {
                    subFoldersContainer.innerHTML = `<p class="text-center text-gray-600 col-span-full">No sub-folders found.</p>`;
                }

                // Add the dynamic "Create New Folder" button
                subFoldersContainer.appendChild(createAddFolderButton('folder'));

                displayMediaThumbnails(files, pathSegments);

            } catch (error) {
                console.error('Error fetching sub-folders and files:', error);
                subFoldersContainer.innerHTML = `<p class="text-center text-red-600 col-span-full">Error loading content for ${pathSegments.join('/')}.</p>`;
                gallerySection.classList.add('hidden');
                galleryContainer.innerHTML = `<p class="text-center text-red-600 col-span-full">Error loading media for ${pathSegments.join('/')}.</p>`;
            }
            updateActionButtonsVisibility(); 
        }

        // --- Lightbox Functions ---

        // Helper function to show the loading spinner
        function showLoadingSpinner() {
            loadingSpinner.classList.remove('hidden');
        }

        // Helper function to hide the loading spinner
        function hideLoadingSpinner() {
            if (spinnerTimeout) {
                clearTimeout(spinnerTimeout);
                spinnerTimeout = null;
            }
            loadingSpinner.classList.add('hidden');
        }

        // Opens the lightbox with a specific image/video
        function openLightbox(index) {
            // Ensure any running slideshow is stopped before opening lightbox manually
            if (slideshowInterval) {
                clearInterval(slideshowInterval);
                slideshowInterval = null;
                isSlideshowRunning = false; 
            }

            if (index >= 0 && index < currentDisplayedMedia.length) {
                currentMediaIndex = index;
                updateLightboxMedia();
                lightboxOverlay.classList.add('active');
                document.body.style.overflow = 'hidden';
                
                updateSlideshowControls(); 
                updateActionButtonsVisibility(); 
            } else {
                console.warn(`[openLightbox] Invalid index: ${index} or currentDisplayedMedia is empty.`);
            }
        }

        // Updates the media displayed in the lightbox
        function updateLightboxMedia() {
            // Always clear any existing interval when updating media
            if (slideshowInterval) {
                clearInterval(slideshowInterval);
                slideshowInterval = null;
            }
            // Always clear any pending spinner timeout when updating media
            if (spinnerTimeout) {
                clearTimeout(spinnerTimeout);
                spinnerTimeout = null;
            }
            hideLoadingSpinner(); // Ensure spinner is hidden initially for a new load

            const mediaItem = currentDisplayedMedia[currentMediaIndex];
            if (!mediaItem) {
                console.error(`[updateLightboxMedia] mediaItem is undefined or null at index ${currentMediaIndex}. Cannot update lightbox.`);
                // Remove all media elements if no valid mediaItem
                lightboxMediaDisplay.querySelectorAll('.media-display').forEach(el => el.remove());
                return;
            }

            const isViewingTrash = currentPath.includes(TRASH_FOLDER_NAME);
            const fileExtension = mediaItem.filename.split('.').pop().toLowerCase();
            const isConvertible = RAW_EXTENSIONS.includes('.' + fileExtension) || fileExtension === 'heic';
            const isVideo = VIDEO_EXTENSIONS.includes('.' + fileExtension);

            let mediaUrlForLightbox;
            let filename = mediaItem.filename;
            let displayPath;

            if (isViewingTrash) {
                fileToProcessPath = mediaItem.relative_path_in_trash;
                if (IMAGE_EXTENSIONS.includes('.' + fileExtension) || RAW_EXTENSIONS.includes('.' + fileExtension)) {
                    mediaUrlForLightbox = `/api/media/${fileToProcessPath}`;
                } else {
                    mediaUrlForLightbox = `/${fileToProcessPath}`;
                }
                displayPath = `Trashed: ${filename}`;
                if (mediaItem.original_path_from_metadata) { // Use original_path_from_metadata for display
                    displayPath += ` (from: ${mediaItem.original_path_from_metadata})`;
                }
            } else {
                fileToProcessPath = mediaItem.original_path;
                mediaUrlForLightbox = `/api/media/${fileToProcessPath}`;
                displayPath = mediaItem.original_path.replace(/\//g, '   ⮕   ');
            }

            lightboxFilename.textContent = displayPath;

            // Create the new media element
            const newMediaElement = document.createElement(isVideo ? 'video' : 'img');
            newMediaElement.classList.add('media-display');
            newMediaElement.alt = `Full size media: ${filename}`;
            newMediaElement.title = filename;
            newMediaElement.style.opacity = '0'; // Start new element hidden for fade-in

            // Attach event listeners for loading and errors
            const handleMediaLoad = () => {
                hideLoadingSpinner(); // Hide spinner when media is loaded
                newMediaElement.classList.add('fade-in'); // Start fade-in animation
                // If slideshow is running, set interval or video ended listener
                if (isSlideshowRunning && !isVideo) {
                    slideshowInterval = setInterval(showNextImage, slideshowDelay);
                } else if (isSlideshowRunning && isVideo) {
                    newMediaElement.autoplay = true;
                    newMediaElement.play(); // Ensure video plays if autoplay is set
                    newMediaElement.addEventListener('ended', showNextImage, { once: true });
                }
            };

            const handleMediaError = () => {
                hideLoadingSpinner();
                newMediaElement.src = `https://placehold.co/800x600/cccccc/333333?text=${isVideo ? 'Video' : 'Image'}+Error`;
                newMediaElement.alt = `Error loading ${isVideo ? 'video' : 'image'}: ${filename}`;
                console.error(`Failed to load media: ${mediaUrlForLightbox}`);
            };

            if (isVideo) {
                newMediaElement.controls = true;
                newMediaElement.preload = "auto";
                newMediaElement.addEventListener('loadeddata', handleMediaLoad);
                newMediaElement.addEventListener('error', handleMediaError);
            } else { // Image (including convertible types)
                newMediaElement.addEventListener('load', handleMediaLoad);
                newMediaElement.addEventListener('error', handleMediaError);
            }

            // --- CRITICAL CHANGE: Handle all existing media elements for fade-out and removal ---
            const allExistingMediaElements = lightboxMediaDisplay.querySelectorAll('.media-display');
            allExistingMediaElements.forEach(element => {
                // Apply fade-out to all currently visible media elements
                element.classList.remove('fade-in'); // Remove any lingering fade-in class
                element.classList.add('fade-out');
                // Schedule removal after the fade-out animation completes
                setTimeout(() => {
                    element.remove();
                }, 800); // Matches the CSS fadeOut animation duration (0.8s)
            });

            // Append the new media element. It will start at opacity 0 and fade in on load.
            lightboxMediaDisplay.appendChild(newMediaElement);
            newMediaElement.src = mediaUrlForLightbox;

            // Control visibility of the download RAW button
            if (isConvertible && !isViewingTrash) {
                downloadRawBtn.classList.remove('hidden');
            } else {
                downloadRawBtn.classList.add('hidden');
            }
        }

        // Closes the lightbox
        function closeLightbox() {
            lightboxOverlay.classList.remove('active');
            document.body.style.overflow = '';
            const videoInLightbox = lightboxMediaDisplay.querySelector('video');
            if (videoInLightbox) {
                videoInLightbox.pause();
                videoInLightbox.currentTime = 0;
            }
            if (slideshowInterval) {
                clearInterval(slideshowInterval);
                slideshowInterval = null;
            }
            isSlideshowRunning = false;
            updateSlideshowControls(); 
            lightboxFilename.textContent = ''; 
            hideLoadingSpinner(); // Ensure spinner is hidden when closing lightbox
            updateActionButtonsVisibility();
            // MODIFIED: Remove the media element from the DOM when closing the lightbox
            lightboxMediaDisplay.querySelectorAll('.media-display').forEach(el => el.remove());
        }

        // Navigates to the next image/video in the lightbox
        function showNextImage() {
            if (currentDisplayedMedia.length === 0) return;
            currentMediaIndex = (currentMediaIndex + 1) % currentDisplayedMedia.length;
            updateLightboxMedia(); 
        }

        // Navigates to the previous image/video in the lightbox
        function showPreviousImage() {
            if (currentDisplayedMedia.length === 0) return;
            currentMediaIndex = (currentMediaIndex - 1 + currentDisplayedMedia.length) % currentDisplayedMedia.length;
            updateLightboxMedia(); 
        }

        // --- Slideshow Functions ---
        async function toggleSlideshow() {
            if (isSlideshowRunning) {
                if (slideshowInterval) {
                    clearInterval(slideshowInterval);
                    slideshowInterval = null;
                }
                const videoInLightbox = lightboxMediaDisplay.querySelector('video');
                if (videoInLightbox) {
                    videoInLightbox.pause(); 
                }
                isSlideshowRunning = false;
                console.log('Slideshow paused.');
            } else {
                let apiUrl = '';
                let pathSegmentsForApi = [...currentPath]; // Copy currentPath to modify for API call

                if (currentPath.length === 0) {
                    apiUrl = `/api/recursive_media`;
                } else {
                    apiUrl = `/api/recursive_media/${pathSegmentsForApi.join('/')}`;
                }

                try {
                    const response = await fetch(apiUrl);
                    if (!response.ok) {
                        const errorText = await response.text();
                        throw new Error(`HTTP error! status: ${response.status}, response: ${errorText}`);
                    }
                    const recursiveFiles = await response.json();

                    if (recursiveFiles.length === 0) {
                        showMessage('No media found for slideshow in this selection.', 'info');
                        return;
                    }

                    currentDisplayedMedia = recursiveFiles.sort((a, b) => {
                        let pathA = a.original_path ? a.original_path.toLowerCase() : '';
                        let pathB = b.original_path ? b.original_path.toLowerCase() : '';
                        return pathA.localeCompare(pathB);
                    });

                    if (!lightboxOverlay.classList.contains('active')) {
                        currentMediaIndex = 0;
                    }

                } catch (error) {
                    console.error('Error fetching recursive media for slideshow:', error);
                    showMessage(`Error starting slideshow: ${error.message}`, 'error');
                    closeLightbox();
                    return; 
                }
                
                isSlideshowRunning = true;
                openLightbox(currentMediaIndex); 
                console.log('Slideshow resumed/started.');
            }
            updateSlideshowControls(); 
        }

        // Updates the icons and tooltips for the slideshow buttons
        function updateSlideshowControls() {
            const breadcrumbPlayIcon = slideshowBtnBreadcrumb.querySelector('.play_icon'); 
            const breadcrumbPauseIcon = slideshowBtnBreadcrumb.querySelector('.pause_icon'); 
            const lightboxPlayIcon = slideshowBtnLightbox.querySelector('.play_icon');
            const lightboxPauseIcon = slideshowBtnLightbox.querySelector('.pause_icon');
            
            if (isSlideshowRunning) {
                breadcrumbPlayIcon.classList.add('hidden');
                breadcrumbPauseIcon.classList.remove('hidden');
                slideshowBtnBreadcrumb.title = 'Pause slideshow';

                lightboxPlayIcon.classList.add('hidden');
                lightboxPauseIcon.classList.remove('hidden');
                slideshowBtnLightbox.title = 'Pause slideshow';
            } else {
                breadcrumbPlayIcon.classList.remove('hidden');
                breadcrumbPauseIcon.classList.add('hidden');
                slideshowBtnBreadcrumb.title = 'Resume slideshow'; 

                lightboxPlayIcon.classList.remove('hidden');
                lightboxPauseIcon.classList.add('hidden');
                slideshowBtnLightbox.title = 'Resume slideshow';
            }
            
            if (lightboxOverlay.classList.contains('active')) {
                if (isSlideshowRunning) {
                    lightboxPrev.style.opacity = '0';
                    lightboxNext.style.opacity = '0';
                    lightboxPrev.style.pointerEvents = 'none';
                    lightboxNext.style.pointerEvents = 'none';
                } else {
                    lightboxPrev.style.opacity = '1';
                    lightboxNext.style.opacity = '1';
                    lightboxPrev.style.pointerEvents = 'auto';
                    lightboxNext.style.pointerEvents = 'auto';
                }
            }
        }


        // Event listeners for lightbox controls
        lightboxClose.addEventListener('click', closeLightbox);
        lightboxPrev.addEventListener('click', showPreviousImage);
        lightboxNext.addEventListener('click', showNextImage);
        
        // Event listener for the slideshow button in the breadcrumb
        slideshowBtnBreadcrumb.addEventListener('click', toggleSlideshow); 

        // Event listener for the slideshow button in the lightbox
        slideshowBtnLightbox.addEventListener('click', toggleSlideshow);

        // Event listener for the new download RAW button
        downloadRawBtn.addEventListener('click', () => {
            const mediaItem = currentDisplayedMedia[currentMediaIndex];
            if (mediaItem && mediaItem.original_path) {
                const downloadUrl = `/api/download_original_raw/${mediaItem.original_path}`;
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = mediaItem.filename; // Suggests the original filename for download
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            } else {
                console.error("No media item selected or original path missing for download.");
                showMessage("No media selected or original path missing for download.", "error");
            }
        });

        // Event listeners for delete/restore buttons (now in lightbox)
        trashDeleteBtn.addEventListener('click', () => {
            const isViewingTrash = currentPath.includes(TRASH_FOLDER_NAME);
            const mediaItemInLightbox = currentDisplayedMedia[currentMediaIndex];
            const pathForAction = isViewingTrash ? mediaItemInLightbox.relative_path_in_trash : mediaItemInLightbox.original_path;
            showConfirmationModal(pathForAction, isViewingTrash, false); 
        });

        trashRestoreBtn.addEventListener('click', () => {
            const mediaItemInLightbox = currentDisplayedMedia[currentMediaIndex];
            const pathForAction = mediaItemInLightbox.relative_path_in_trash; 
            showConfirmationModal(pathForAction, false, true); 
        });

        // Add click listener to lightbox media display for pause/resume
        lightboxMediaDisplay.addEventListener('click', (event) => {
            // Prevent closing if the click was on the video controls
            if (event.target.tagName === 'VIDEO' && event.target.controls) {
                return; 
            }
            if (isSlideshowRunning) {
                toggleSlideshow(); 
            } else {
                closeLightbox();
            }
        });


        // Close lightbox when clicking outside the media (on the overlay itself)
        lightboxOverlay.addEventListener('click', (event) => {
            // Only close if the click is directly on the overlay or the close button, not on the media itself or controls
            if (event.target === lightboxOverlay || event.target === lightboxClose) {
                closeLightbox();
            }
        });

        // Keyboard navigation for lightbox (Escape to close, arrows for next/prev)
        document.addEventListener('keydown', (event) => {
            if (lightboxOverlay.classList.contains('active')) {
                if (event.key === 'Escape') {
                    closeLightbox();
                } else if (!isSlideshowRunning && event.key === 'ArrowRight') { 
                    showNextImage();
                } else if (!isSlideshowRunning && event.key === 'ArrowLeft') { 
                    showPreviousImage();
                }
            }
        });

        // --- Confirmation Modal Functions ---
        // Unified function for file and folder deletion/restoration
        function showConfirmationModal(actionTarget, isPermanentDelete = false, isRestore = false) {
            if (actionTarget === 'empty_trash') {
                isFolderDeletion = false;
                fileToProcessPath = 'empty_trash'; // Use a special string
                confirmationMessage.textContent = "Are you sure you want to permanently delete ALL items in the trash? This action cannot be undone.";
                confirmActionBtn.textContent = "Empty Trash";
                confirmActionBtn.classList.remove('bg-green-500', 'hover:bg-green-600');
                confirmActionBtn.classList.add('bg-red-600', 'hover:bg-red-700');
            } else if (actionTarget === 'restore_all') {
                isFolderDeletion = false;
                fileToProcessPath = 'restore_all'; // Use a special string
                confirmationMessage.textContent = "Are you sure you want to restore ALL items from the trash to their original locations?";
                confirmActionBtn.textContent = "Restore All";
                confirmActionBtn.classList.remove('bg-red-600', 'hover:bg-red-700');
                confirmActionBtn.classList.add('bg-green-500', 'hover:bg-green-600');
            } else {
                isFolderDeletion = Array.isArray(actionTarget);
                if (isFolderDeletion) {
                    folderToProcessPath = actionTarget;
                    fileToProcessPath = '';
                } else {
                    fileToProcessPath = actionTarget;
                    folderToProcessPath = [];
                }

                if (isRestore) {
                    confirmationMessage.textContent = "Are you sure you want to restore this file to its original location?";
                    confirmActionBtn.textContent = "Restore";
                    confirmActionBtn.classList.remove('bg-red-600', 'hover:bg-red-700');
                    confirmActionBtn.classList.add('bg-green-500', 'hover:bg-green-600');
                } else if (isPermanentDelete) {
                    confirmationMessage.textContent = "Are you sure you want to permanently delete this file? This action cannot be undone.";
                    confirmActionBtn.textContent = "Delete Forever";
                    confirmActionBtn.classList.remove('bg-green-500', 'hover:bg-green-600');
                    confirmActionBtn.classList.add('bg-red-600', 'hover:bg-red-700');
                } else if (isFolderDeletion) {
                    const folderName = folderToProcessPath.join('/');
                    confirmationMessage.textContent = `Are you sure you want to delete the folder "${folderName}" and move all its contents to Trash?`;
                    confirmActionBtn.textContent = "Delete Folder";
                    confirmActionBtn.classList.remove('bg-green-500', 'hover:bg-green-600');
                    confirmActionBtn.classList.add('bg-red-600', 'hover:bg-red-700');
                } else {
                    confirmationMessage.textContent = "Are you sure you want to move this file to Trash?";
                    confirmActionBtn.textContent = "Move to Trash";
                    confirmActionBtn.classList.remove('bg-green-500', 'hover:bg-green-600');
                    confirmActionBtn.classList.add('bg-red-600', 'hover:bg-red-700');
                }
            }

            confirmationModalOverlay.classList.add('active');
            document.body.style.overflow = 'hidden'; 
        }

        function hideConfirmationModal() {
            confirmationModalOverlay.classList.remove('active');
            document.body.style.overflow = ''; 
            isFolderDeletion = false; // Reset flag
        }

        // New function to handle refreshing the gallery and lightbox after an action
        async function handlePostActionRefresh() {
            const wasLightboxActive = lightboxOverlay.classList.contains('active');
            const oldCurrentMediaIndex = currentMediaIndex; // Store the index before refreshing

            // Re-fetch the media for the current path.
            if (currentPath.length > 0) {
                if (currentPath[0] === TRASH_FOLDER_NAME) {
                    await loadTrashContent();
                } else {
                    await loadSubFoldersAndFiles(currentPath);
                }
            } else { // At root
                await loadTopLevelFolders();
            }

            // After re-loading, currentDisplayedMedia is updated.
            // Now, determine the new index for the lightbox.
            if (wasLightboxActive) {
                if (currentDisplayedMedia.length === 0) {
                    // If no media left in the folder, close lightbox
                    closeLightbox();
                } else {
                    // Adjust currentMediaIndex:
                    // If the old index is now out of bounds (because the last item was removed),
                    // set it to the new last item's index.
                    if (oldCurrentMediaIndex >= currentDisplayedMedia.length) {
                        currentMediaIndex = currentDisplayedMedia.length - 1;
                    } else {
                        // Otherwise, keep the index. This will effectively show the item that
                        // moved into the old index's position (the "next" item).
                        currentMediaIndex = oldCurrentMediaIndex;
                    }
                    updateLightboxMedia();
                }
            }
        }


        // Event listeners for confirmation modal buttons
        confirmActionBtn.addEventListener('click', async () => {
            hideConfirmationModal(); // Hide modal immediately

            let actionSuccessful = false;
            try {
                if (confirmActionBtn.textContent === "Empty Trash") {
                    await emptyTrash();
                    actionSuccessful = true;
                } else if (confirmActionBtn.textContent === "Restore All") {
                    await restoreAll();
                    actionSuccessful = true;
                } else if (confirmActionBtn.textContent === "Delete Folder") {
                    await deleteFolder(folderToProcessPath);
                    actionSuccessful = true;
                } else if (confirmActionBtn.textContent === "Restore") { 
                    await restoreFile(fileToProcessPath);
                    actionSuccessful = true;
                } else if (confirmActionBtn.textContent === "Delete Forever") { 
                    await deleteFileForever(fileToProcessPath);
                    actionSuccessful = true;
                } else { // Move file to trash
                    await moveFileToTrash(fileToProcessPath);
                    actionSuccessful = true;
                }
            } catch (error) {
                console.error("Error during action:", error);
                showMessage(`An unexpected error occurred: ${error.message}`, 'error'); 
            }

            if (actionSuccessful) {
                // For folder deletion, we need to navigate up one level after the action
                if (confirmActionBtn.textContent === "Delete Folder") { // Re-check condition for navigation
                    const newPath = [...currentPath];
                    if (newPath.length > 0) {
                        newPath.pop(); // Remove the last segment (the deleted folder)
                    }
                    currentPath = newPath; // Update currentPath
                    await handlePostActionRefresh(); // Refresh the new currentPath
                    updateBreadcrumb(); // Update breadcrumb to reflect new path
                } else {
                    await handlePostActionRefresh(); // For file actions, just refresh current path
                }
            } else {
                // If action wasn't successful, just close lightbox as a fallback
                closeLightbox();
            }
        });

        cancelActionBtn.addEventListener('click', hideConfirmationModal);

        // --- File Movement Logic ---
        async function moveFileToTrash(filePath) {
            console.log(`Attempting to move to trash: ${filePath}`);
            try {
                const response = await fetch('/api/move_to_trash', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ path: filePath }),
                });

                if (response.ok) {
                    console.log('File moved to trash successfully.');
                    showMessage('File moved to trash successfully.', 'success');
                } else {
                    const errorData = await response.json();
                    console.error('Failed to move file to trash:', errorData.error);
                    throw new Error(errorData.error); // Throw error to be caught by caller
                }
            } catch (error) {
                console.error('Network or unexpected error during file movement:', error);
                throw error; // Re-throw to be caught by caller
            }
        }

        // --- New function to permanently delete file ---
        async function deleteFileForever(filePath) {
            console.log(`Attempting to permanently delete: ${filePath}`);
            try {
                const response = await fetch('/api/delete_file_forever', {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ path: filePath }),
                });

                if (response.ok) {
                    console.log('File permanently deleted successfully.');
                    showMessage('File permanently deleted successfully.', 'success');
                } else {
                    const errorData = await response.json();
                    console.error('Failed to permanently delete file:', errorData.error);
                    throw new Error(errorData.error); // Throw error to be caught by caller
                }
            } catch (error) {
                console.error('Network or unexpected error during permanent deletion:', error);
                throw error; // Re-throw to be caught by caller
            }
        }

        // --- New function to restore file ---
        async function restoreFile(filePath) {
            console.log(`Attempting to restore: ${filePath}`);
            try {
                const response = await fetch('/api/restore_file', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ path: filePath }),
                });

                if (response.ok) {
                    console.log('File restored successfully.');
                    showMessage('File restored successfully.', 'success');
                } else {
                    const errorData = await response.json();
                    console.error('Failed to restore file:', errorData.error);
                    throw new Error(errorData.error); // Throw error to be caught by caller
                }
            } catch (error) {
                console.error('Network or unexpected error during restoration:', error);
                throw error; // Re-throw to be caught by caller
            }
        }

        // --- NEW: Function to delete a folder and its contents to trash ---
        async function deleteFolder(folderPathArray) {
            const folderPathString = folderPathArray.join('/');
            console.log(`Attempting to delete folder: ${folderPathString}`);
            try {
                const response = await fetch('/api/delete_folder', {
                    method: 'POST', // Or 'DELETE' depending on backend design
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ path: folderPathArray }), // Send as array of segments
                });

                if (response.ok) {
                    console.log(`Folder "${folderPathString}" and its contents moved to trash successfully.`);
                    showMessage(`Folder "${folderPathString}" and its contents moved to trash successfully.`, 'success');
                } else {
                    const errorData = await response.json();
                    console.error('Failed to delete folder:', errorData.error);
                    throw new Error(errorData.error); // Throw error to be caught by caller
                }
            } catch (error) {
                console.error('Network or unexpected error during folder deletion:', error);
                throw error; // Re-throw to be caught by caller
            }
        }

        // --- NEW: Bulk Trash Actions ---
        async function emptyTrash() {
            try {
                const response = await fetch('/api/empty_trash', { method: 'POST' });
                if (response.ok) {
                    showMessage('Trash emptied successfully.', 'success');
                } else {
                    const errorData = await response.json();
                    throw new Error(errorData.error);
                }
            } catch (error) {
                console.error('Error emptying trash:', error);
                showMessage(`Error emptying trash: ${error.message}`, 'error');
                throw error;
            }
        }

        async function restoreAll() {
            try {
                const response = await fetch('/api/restore_all', { method: 'POST' });
                if (response.ok) {
                    showMessage('All files restored successfully.', 'success');
                } else {
                    const errorData = await response.json();
                    throw new Error(errorData.error);
                }
            } catch (error) {
                console.error('Error restoring all files:', error);
                showMessage(`Error restoring all files: ${error.message}`, 'error');
                throw error;
            }
        }


        // --- New function to load Trash content ---
        async function loadTrashContent() {
            topLevelFoldersSection.classList.add('hidden');
            subFoldersSection.classList.add('hidden');
            gallerySection.classList.remove('hidden'); 
            currentPath = [TRASH_FOLDER_NAME]; 

            showLoading(galleryContainer);

            try {
                const response = await fetch('/api/trash_content');
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`HTTP error! status: ${response.status}, response: ${errorText}`);
                }
                const trashData = await response.json(); 
                displayMediaThumbnails(trashData.files, [TRASH_FOLDER_NAME]);

            } catch (error) {
                console.error('Error fetching trash content:', error);
                galleryContainer.innerHTML = `<p class="text-center text-red-600 col-span-full">Error loading trash content: ${error.message}.</p>`;
                showMessage(`Error loading trash content: ${error.message}.`, 'error');
            }
            updateActionButtonsVisibility(); 
        }

        // --- Message Box Function ---
        const messageBox = document.getElementById('messageBox');
        let messageTimeout = null;

        function showMessage(message, type = 'info') {
            if (messageTimeout) {
                clearTimeout(messageTimeout);
            }
            messageBox.textContent = message;
            messageBox.className = ''; // Clear existing classes
            messageBox.classList.add('show');

            if (type === 'success') {
                messageBox.style.backgroundColor = '#10B981'; // Green
            } else if (type === 'error') {
                messageBox.style.backgroundColor = '#EF4444'; // Red
            } else {
                messageBox.style.backgroundColor = '#333'; // Default dark
            }

            messageTimeout = setTimeout(() => {
                messageBox.classList.remove('show');
            }, 3000); // Message disappears after 3 seconds
        }

        // --- NEW: Create Folder Logic ---
        function showCreateFolderModal(type) {
            folderCreationType = type;
            createFolderModalTitle.textContent = `Create New Folder`;
            newFolderNameInput.value = ''; // Clear previous input
            newFolderNameInput.placeholder = `Enter folder name`;
            createFolderModalOverlay.classList.add('active');
            document.body.style.overflow = 'hidden';
            newFolderNameInput.focus(); // Focus on the input field
        }

        async function handleCreateFolder() {
            const folderName = newFolderNameInput.value.trim();
            if (!folderName) {
                showMessage("Folder name cannot be empty.", "error");
                return;
            }

            let parentPath = currentPath;

            try {
                const response = await fetch('/api/create_folder', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        parent_path: parentPath,
                        folder_name: folderName
                    }),
                });

                const result = await response.json();
                if (response.ok) {
                    showMessage(result.message, 'success');
                    hideCreateFolderModal();
                    await handlePostActionRefresh(); // Refresh the relevant section
                } else {
                    showMessage(`Error creating folder: ${result.error}`, 'error');
                }
            } catch (error) {
                console.error('Error creating folder:', error);
                showMessage(`An unexpected error occurred: ${error.message}`, 'error');
            }
        }

        function hideCreateFolderModal() {
            createFolderModalOverlay.classList.remove('active');
            document.body.style.overflow = '';
        }

        // Event listeners for Create Folder modal buttons
        confirmCreateFolderBtn.addEventListener('click', handleCreateFolder);
        cancelCreateFolderBtn.addEventListener('click', hideCreateFolderModal);
        newFolderNameInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                handleCreateFolder();
            }
        });

        // --- NEW: Upload Logic ---
        function handleUploadClick() {
            fileInput.click(); // Trigger the hidden file input click
        }

        fileInput.addEventListener('change', (event) => {
            filesToUpload = Array.from(event.target.files);
            if (filesToUpload.length > 0) {
                showUploadProgressModal();
                updateUploadList();
                // Reset file input value to allow selecting same files again if needed
                fileInput.value = ''; 
            }
        });

        function showUploadProgressModal() {
            uploadProgressModalOverlay.classList.add('active');
            document.body.style.overflow = '';
            overallProgressBar.style.width = '0%';
            overallProgressText.textContent = '0% Complete';
            startUploadBtn.classList.remove('hidden'); // Show start upload button
            cancelUploadBtn.textContent = 'Close'; // Change cancel to close
            uploadedFilesCount = 0; // Reset count

            let targetPathDisplay = currentPath.length > 0 ? currentPath.join('/') : 'root';
            uploadTargetFolderInfo.textContent = `Target Folder: ${targetPathDisplay}`;
        }

        function hideUploadProgressModal() {
            uploadProgressModalOverlay.classList.remove('active');
            document.body.style.overflow = '';
            filesToUpload = []; // Clear files
            uploadList.innerHTML = ''; // Clear list
            overallProgressBar.style.width = '0%';
            overallProgressText.textContent = '0% Complete';
        }

        function updateUploadList() {
            uploadList.innerHTML = '';
            if (filesToUpload.length === 0) {
                uploadList.innerHTML = '<li>No files selected.</li>';
                startUploadBtn.classList.add('hidden');
            } else {
                filesToUpload.forEach(file => {
                    const li = document.createElement('li');
                    li.textContent = file.name;
                    uploadList.appendChild(li);
                });
                startUploadBtn.classList.remove('hidden');
            }
        }

        async function startFileUpload() {
            if (filesToUpload.length === 0) {
                showMessage("No files to upload.", "info");
                return;
            }

            startUploadBtn.disabled = true; // Disable button during upload
            cancelUploadBtn.textContent = 'Close'; // Change cancel to close
            uploadedFilesCount = 0;

            for (const file of filesToUpload) {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('current_path', JSON.stringify(currentPath)); // Send current path as JSON string

                try {
                    const response = await fetch('/api/upload_file', {
                        method: 'POST',
                        body: formData,
                    });

                    const result = await response.json();
                    if (response.ok) {
                        uploadedFilesCount++;
                        const progress = (uploadedFilesCount / filesToUpload.length) * 100;
                        overallProgressBar.style.width = `${progress}%`;
                        overallProgressText.textContent = `${Math.round(progress)}% Complete (${uploadedFilesCount}/${filesToUpload.length} files)`;
                        console.log(`Uploaded ${file.name}: ${result.message}`);
                    } else {
                        console.error(`Failed to upload ${file.name}: ${result.error}`);
                        showMessage(`Failed to upload ${file.name}: ${result.error}`, 'error');
                    }
                } catch (error) {
                    console.error(`Error uploading ${file.name}:`, error);
                    showMessage(`Error uploading ${file.name}: ${error.message}`, 'error');
                }
            }

            startUploadBtn.disabled = false; // Re-enable button
            showMessage(`Upload complete! ${uploadedFilesCount} of ${filesToUpload.length} files uploaded.`, 'success');
            hideUploadProgressModal(); // Close modal after upload
            await handlePostActionRefresh(); // Refresh gallery
        }

        // Drag and Drop Event Handlers
        galleryContainer.addEventListener('dragover', (e) => {
            e.preventDefault(); // Prevent default to allow drop
            // Only add drag-over class if not in trash
            if (!currentPath.includes(TRASH_FOLDER_NAME)) {
                galleryContainer.classList.add('drag-over');
            }
        });

        galleryContainer.addEventListener('dragleave', (e) => {
            e.preventDefault();
            galleryContainer.classList.remove('drag-over');
        });

        galleryContainer.addEventListener('drop', (e) => {
            e.preventDefault();
            galleryContainer.classList.remove('drag-over');
            // Only allow drop if not in trash
            if (currentPath.includes(TRASH_FOLDER_NAME)) {
                showMessage("Cannot upload files to the Trash folder.", "error");
                return;
            }
            filesToUpload = Array.from(e.dataTransfer.files);
            if (filesToUpload.length > 0) {
                showUploadProgressModal();
                updateUploadList();
            }
        });

        // Event listeners for Upload functionality
        uploadFilesBtn.addEventListener('click', handleUploadClick);
        startUploadBtn.addEventListener('click', startFileUpload);
        cancelUploadBtn.addEventListener('click', hideUploadProgressModal);

        // MODIFIED: Added listeners for bulk trash actions
        emptyTrashBtn.addEventListener('click', () => showConfirmationModal('empty_trash'));
        restoreAllBtn.addEventListener('click', () => showConfirmationModal('restore_all'));


        // Initial load: Start by showing years
        document.addEventListener('DOMContentLoaded', async () => {
            // Apply saved theme on load
            const savedTheme = localStorage.getItem('theme') || 'dark'; // Default to dark
            setTheme(savedTheme);

            // Event listener for theme toggle button
            themeToggleButton.addEventListener('click', () => {
                const currentTheme = document.body.getAttribute('data-theme');
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                setTheme(newTheme);
            });

            await loadTopLevelFolders();
            updateBreadcrumb(); // MODIFIED: Call updateBreadcrumb on initial load
        });
