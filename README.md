# Photo gallery with lightbox #

Gallery is created from underlying folders in the form YYYY --> MM --> DD  (year -> month -> day)
Many graphics files supported including some RAW formats and video files (HEIC, MP4, MOV, AVIF), however limitation on format support is your web browser
(e.g. Windows MS Edge will not support apple HEIC, but Safari will)

The gallery is served with Flask server (server.py). Server.py scans the folder structure creatin the list of files and directories, which is then interpreted and rendered by index.html file logic.

1. Install flask: ``pip3 install Flask Flask-Cors``
2. Save server.py and index.html in te same folder (can be different from the Gallery folder with images/videos)
3. Edit server.py to change the root directory of the Gallery (where all images are saved)
4. Start the Flask server ``python3 server.py``
5. Navigate to http://127.0.0.1:5000


-----
Created with the help of Google Gemini 2.5 Flash.

   
