from __future__ import unicode_literals
import json
import os
import subprocess
from queue import Queue
from flask import Flask, escape, request, send_from_directory, render_template
from flask_basicauth import BasicAuth
from threading import Thread
import youtube_dl
from pathlib import Path
from collections import ChainMap

app = Flask(__name__,template_folder='.')
app.config['BASIC_AUTH_USERNAME'] = 'user'
app.config['BASIC_AUTH_PASSWORD'] = 'user'
app.config['BASIC_AUTH_FORCE'] = True
basic_auth = BasicAuth(app)

mesg = dict()
emesg = []

app_defaults = {
    'YDL_FORMAT': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
    'YDL_EXTRACT_AUDIO_FORMAT': None,
    'YDL_EXTRACT_AUDIO_QUALITY': '192',
    'YDL_RECODE_VIDEO_FORMAT': None,
    'YDL_OUTPUT_TEMPLATE': '/youtube-dl/%(title)s [%(id)s].%(ext)s',
    'YDL_ARCHIVE_FILE': None,
    'YDL_SERVER_HOST': '0.0.0.0',
    'YDL_SERVER_PORT': 8080,
}


@app.route('/youtube-dl')
def dl_queue_list():
    return render_template('index.html')

@app.route('/youtube-dl/static/<path:path>')
def send_js(path):
    return send_from_directory('static', path)

@app.route('/youtube-dl/q', methods=['GET'])
def q_size():
    return {"success": True, "size": json.dumps(list(dl_q.queue))}

@app.route('/youtube-dl/q', methods=['POST'])
def q_put():
    url = request.values["url"]
    options = {
        'format': request.values["format"]
    }

    if not url:
        return {"success": False, "error": "/q called without a 'url' query param"}

    dl_q.put((url, options))
    print("Added url " + url + " to the download queue")
    return {"success": True, "url": url, "options": options}

@app.route('/youtube-dl/status')
def status():
    global mesg, emesg
    return {"success": True, "status": 'None' if mesg == [] else mesg \
        ,"Error": 'None' if not(len(emesg)) else emesg}

@app.route('/youtube-dl/clear')
def statusclear():
    global mesg, emesg
    del mesg
    del emesg
    mesg = dict()
    emesg = []
    return {"success": True}


def dl_worker():
    while not done:
        url, options = dl_q.get()
        download(url, options)
        dl_q.task_done()


def get_ydl_options(request_options):
    request_vars = {
        'YDL_EXTRACT_AUDIO_FORMAT': None,
        'YDL_RECODE_VIDEO_FORMAT': None,
    }

    requested_format = request_options.get('format', 'bestvideo')

    if requested_format in ['aac', 'flac', 'mp3', 'm4a', 'opus', 'vorbis', 'wav']:
        request_vars['YDL_EXTRACT_AUDIO_FORMAT'] = requested_format
    elif requested_format == 'bestaudio':
        request_vars['YDL_EXTRACT_AUDIO_FORMAT'] = 'best'
    elif requested_format in ['mp4', 'flv', 'webm', 'ogg', 'mkv', 'avi']:
        request_vars['YDL_RECODE_VIDEO_FORMAT'] = requested_format

    ydl_vars = ChainMap(request_vars, os.environ, app_defaults)

    postprocessors = []

    if(ydl_vars['YDL_EXTRACT_AUDIO_FORMAT']):
        postprocessors.append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': ydl_vars['YDL_EXTRACT_AUDIO_FORMAT'],
            'preferredquality': ydl_vars['YDL_EXTRACT_AUDIO_QUALITY'],
        })

    if(ydl_vars['YDL_RECODE_VIDEO_FORMAT']):
        postprocessors.append({
            'key': 'FFmpegVideoConvertor',
            'preferedformat': ydl_vars['YDL_RECODE_VIDEO_FORMAT'],
        })

    return {
        'format': ydl_vars['YDL_FORMAT'],
        'postprocessors': postprocessors,
        'outtmpl': ydl_vars['YDL_OUTPUT_TEMPLATE'],
        'download_archive': ydl_vars['YDL_ARCHIVE_FILE']
    }

def download(url, request_options):
    global mesg,emesg
    with youtube_dl.YoutubeDL(get_ydl_options(request_options)) as ydl:
        try:
            mesg[url]=('Downloading')
            ydl.download([url])
            mesg[url]=('Done')
        except:
            mesg.pop(url,None)
            emesg.append(url)

dl_q = Queue()
done = False
dl_thread = Thread(target=dl_worker)
dl_thread.start()

print("Started download thread")

app_vars = ChainMap(os.environ, app_defaults)

#app.config["DEBUG"] = True
app.run(host=app_vars['YDL_SERVER_HOST'], port=app_vars['YDL_SERVER_PORT'])
done = True
dl_thread.join()
