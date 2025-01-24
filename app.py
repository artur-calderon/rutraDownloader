from flask import Flask, request, jsonify, send_file, render_template
import os
import urllib.parse
import zipfile
import io
from yt_dlp import YoutubeDL

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_URL = "http://localhost:5000"

# Inicialização do Flask
app = Flask(__name__)

# Funções para download
def download_video(url, progress_hook=None):
    ydl_opts = {
        'format': 'best',
        'progress_hooks': [progress_hook] if progress_hook else [],
        'ffmpeg_location': 'C:/Program Files/ffmpeg/bin',
        'ffprobe_location': 'C:/Program Files/ffmpeg/bin',
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)  # Não faz o download
        video_data = ydl.urlopen(info['url']).read()  # Baixa o vídeo diretamente em memória
        return info, video_data

def download_audio(url, progress_hook=None):
    ydl_opts = {
        'format': 'bestaudio/best',
        'progress_hooks': [progress_hook] if progress_hook else [],
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'ffmpeg_location': 'C:/Program Files/ffmpeg/bin',
        'ffprobe_location': 'C:/Program Files/ffmpeg/bin',
    }

    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)  # Não faz o download

        if 'entries' in info_dict:  # Se for uma playlist
            audio_data = []
            for entry in info_dict['entries']:
                if entry:  # Ignora entradas inválidas
                    # Baixa o áudio de cada entrada da playlist
                    audio_data.append(ydl.urlopen(entry['url']).read())
            return info_dict, audio_data
        else:
            # Para vídeo único
            audio_data = ydl.urlopen(info_dict['url']).read()  # Baixa o áudio diretamente em memória
            return info_dict, [audio_data]  # Coloca o áudio em uma lista para uniformizar a saída

def download_playlist(url, progress_hook=None):
    ydl_opts = {
        'format': 'best',
        'progress_hooks': [progress_hook] if progress_hook else [],
        'ffmpeg_location': 'C:/Program Files/ffmpeg/bin',
        'ffprobe_location': 'C:/Program Files/ffmpeg/bin',
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)  # Não faz o download
        video_data = []
        if "entries" in info_dict:
            for entry in info_dict["entries"]:
                if not entry:  # Ignora entradas inválidas
                    continue
                video_data.append(ydl.urlopen(entry['url']).read())  # Baixa os vídeos diretamente em memória
        return info_dict, video_data

# Rotas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preview', methods=['POST'])
def preview():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL é obrigatória!'}), 400

    try:
        with YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:  # Playlist
                items = [
                    {'title': entry['title'], 'duration': entry['duration']} for entry in info['entries']
                ]
                return jsonify({
                    'title': info.get('title', 'Unknown Playlist'),
                    'thumbnail': info['entries'][0].get('thumbnail', ''),
                    'items': items
                })
            else:  # Single video
                return jsonify({
                    'title': info.get('title', 'Unknown Video'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0)
                })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download-playlist', methods=['POST'])
def download_playlist_route():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL é obrigatória!'}), 400

    try:
        info_dict, video_data = download_playlist(url)
        playlist_title = info_dict.get('title', 'playlist')  # Pega o título da playlist

        # Cria um ZIP com os vídeos
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for i, video in enumerate(video_data):
                zipf.writestr(f"video_{i+1}.mp4", video)
        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name=f"{playlist_title}.zip")
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download-video', methods=['POST'])
def download_video_route():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL é obrigatória!'}), 400

    try:
        info_dict, video_data = download_video(url)
        video_title = info_dict.get('title', 'video')  # Pega o título do vídeo para nomear o arquivo
        return send_file(io.BytesIO(video_data), as_attachment=True, download_name=f"{video_title}.mp4")
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download-audio', methods=['POST'])
def download_audio_route():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL é obrigatória!'}), 400

    try:
        # Baixa as informações do vídeo ou playlist
        info_dict, audio_data = download_audio(url)

        # Título do áudio ou playlist
        audio_title = info_dict.get('title', 'audio')

        if isinstance(audio_data, list) and len(audio_data) > 1:
            # Cria um ZIP com os áudios para playlists
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                for i, audio in enumerate(audio_data):
                    zipf.writestr(f"audio_{i+1}.mp3", audio)
            zip_buffer.seek(0)
            return send_file(zip_buffer, as_attachment=True, download_name=f"{audio_title}_audio.zip")
        else:
            # Apenas um arquivo de áudio
            return send_file(io.BytesIO(audio_data), as_attachment=True, download_name=f"{audio_title}.mp3")

    except Exception as e:
        return jsonify({'error': str(e)}), 500


    
@app.route('/serve-file/<path:filename>', methods=['GET'])
def serve_file(filename):
    # Esta rota não é mais necessária se estivermos enviando os arquivos diretamente
    return jsonify({'error': 'Arquivo não encontrado!'}), 404

# Inicia o servidor
if __name__ == '__main__':
    app.run(debug=True)
