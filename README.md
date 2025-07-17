# Photo gallery with lightbox #

Web Photo Gallery is created using only two files (`index.html` and `server.py`) from underlying photo gallery file tree in the form ./YYYY/MM/DD  (year -> month -> day).

It does not generate small size thumbnails instead of full-size images, hence putting thousands of images in one folder will run you out of RAM. Therefore 3-layer folders' structure based on a calendar date (./YYYY/MM/DD) is recommended. Naming of image and video files is arbitrary, they should have recognisable file extensions.

Quite a few graphics files' formats are supported including some RAW formats and video files (HEIC, MP4, MOV, AVIF etc), however this is mostly the web browser limitation
(e.g. Windows MS Edge will not support apple HEIC, but Safari will, and hardly any browser will render RAW files)

The gallery is served with Flask server (ran with `server.py`). 

On launch, the `server.py` will scan the folders' structure in `image_library_root` creating list of files and folders, which is then passed to index.html by flask.

How to setup:
1. Install flask: ``pip3 install Flask Flask-Cors``
2. Save `server.py` and `index.html` in the same folder (it can be different from the Gallery folder with images/videos)
3. Edit `server.py` to change the top root directory of the Gallery, it is defined  in the beginning of the server.py file as

  `image_library_root = os.path.abspath('/path/to/your/gallery/tree')`
  
  This is where all images will be found by python code. You can also change flask server port number [default is :5000] (defined at the bottom of the file).

  `app.run(host='0.0.0.0', debug=True, port=5000)`
  
6. Start the Flask server ``python3 server.py``, observe the output in the terminal to make sure all is fine and no errors produced.
7. Navigate to http://127.0.0.1:5000 to see your Gallery.

Gallery supports browsing file structure folder-by-folder, deleting files (moving to recycle bin --> folder _Trash) and restoring the files from the Recycle Bin to the original location in the Gallery.

##### Example demo: http://143.47.246.212:8080/ #####


-----
Created with the help of Google Gemini 2.5 Flash.

   
