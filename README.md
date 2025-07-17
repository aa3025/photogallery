# Photo gallery with lightbox #

Gallery is created from underlying folders' tree in the form ./YYYY/MM/DD  (year -> month -> day).

Quite a few graphics files' formats are supported including some RAW formats and video files (HEIC, MP4, MOV, AVIF etc), however this is mostly the web browser limitation
(e.g. Windows MS Edge will not support apple HEIC, but Safari will, and hardly any browser will render RAW files)

The gallery is served with Flask server (ran with `server.py`). 

On launch, the server.py will scan the folders' structure creating the list of files and folders, which is then passed to index.html file logic.

How to setup:
1. Install flask: ``pip3 install Flask Flask-Cors``
2. Save server.py and index.html in the same folder (it can be different from the Gallery folder with images/videos)
3. Edit server.py and change the root directory of the Gallery, top of the server.py file, thi is where all images can be found; You can also change flask server port [default is :5000] (bottom of the file).
4. Start the Flask server ``python3 server.py``, observe the output in the terminal to make sure all is fine and no errors produced.
5. Navigate to http://127.0.0.1:5000 to see your Gallery.

Gallery supports browsing file structure folder-by-folder, deleting files (moving to recycle bin --> folder _Trash) and restoring the files from the Recycle Bin to the original location in the Gallery.

##### Example demo: http://143.47.246.212:8080/ #####


-----
Created with the help of Google Gemini 2.5 Flash.

   
