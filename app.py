from flask import Flask, request, jsonify, send_file, render_template, after_this_request
import os
import urllib.parse
import zipfile
from yt_dlp import YoutubeDL
import time
import shutil

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'Rutra Downloader')
SERVER_URL = "http://localhost:5000"

print(f"Download folder: {DOWNLOAD_FOLDER}")

# Certifica-se de que a pasta de downloads existe
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Inicialização do Flask
app = Flask(__name__)

# Funções para download
def download_video(url, progress_hook=None):
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'format': 'best',
        'progress_hooks': [progress_hook] if progress_hook else [],
        'cookies':'cookies.txt',
        'ffmpeg_location': 'C:/Program Files/ffmpeg/bin',
        'ffprobe_location': 'C:/Program Files/ffmpeg/bin',
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        return info, file_path

def download_audio(url, progress_hook=None):
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'format': 'bestaudio/best',
        'progress_hooks': [progress_hook] if progress_hook else [],
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'force_generic_extractor': True,
        'cookies':'cookies.txt',
        'ffmpeg_location': 'C:/Program Files/ffmpeg/bin',
        'ffprobe_location': 'C:/Program Files/ffmpeg/bin',
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        file_paths = []

        if "entries" in info_dict:
            # Caso seja uma playlist
            playlist_title = info_dict.get("title", "Unknown Playlist")
            print(f"Baixando playlist: {playlist_title}")

            for entry in info_dict["entries"]:
                if not entry:  # Ignora entradas inválidas
                    continue

                # Obtém o caminho do arquivo processado
                output_file = ydl.prepare_filename(entry)
                output_file_mp3 = os.path.splitext(output_file)[0] + ".mp3"
                file_paths.append(output_file_mp3)
                print(f"Arquivo baixado: {output_file_mp3}")

        else:
            # Caso seja um único vídeo
            output_file = ydl.prepare_filename(info_dict)
            output_file_mp3 = os.path.splitext(output_file)[0] + ".mp3"
            file_paths.append(output_file_mp3)
            print(f"Arquivo baixado: {output_file_mp3}")

        return info_dict, file_paths

def download_playlist(url, progress_hook=None):
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s'),
        'format': 'best',
        'progress_hooks': [progress_hook] if progress_hook else [],
        'cookies':'cookies.txt',
        'ffmpeg_location': 'C:/Program Files/ffmpeg/bin',
        'ffprobe_location': 'C:/Program Files/ffmpeg/bin',
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        file_paths = []

        if "entries" in info_dict:
            for entry in info_dict["entries"]:
                if not entry:  # Ignora entradas inválidas
                    continue

                file_path = ydl.prepare_filename(entry)
                file_paths.append(file_path)
        
        # Cria um arquivo ZIP com todos os vídeos da playlist
        zip_filename = os.path.join(DOWNLOAD_FOLDER, f"{info_dict['title']}.zip")
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for file in file_paths:
                zipf.write(file, os.path.basename(file))
                
        return info_dict, zip_filename


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
        info_dict, zip_filename = download_playlist(url)
        file_link = f"{SERVER_URL}/serve-file/{urllib.parse.quote(os.path.basename(zip_filename))}"
        return jsonify({'message': 'Download concluído!', 'file_link': file_link})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download-video', methods=['POST'])
def download_video_route():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL é obrigatória!'}), 400

    try:
        _, file_path = download_video(url)
        file_link = f"{SERVER_URL}/serve-file/{urllib.parse.quote(os.path.basename(file_path))}"
        return jsonify({'message': 'Download concluído!', 'file_link': file_link})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download-audio', methods=['POST'])
def download_audio_route():
     data = request.get_json()
     url = data.get('url')

     if not url:
        return jsonify({'error': 'URL é obrigatória!'}), 400

     try:
        info_dict, file_paths = download_audio(url)
        
        if len(file_paths) > 1:
            # Cria um ZIP se for uma playlist
            zip_filename = os.path.join(DOWNLOAD_FOLDER, f"{info_dict.get('title', 'playlist')}_audio.zip")
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for file in file_paths:
                    zipf.write(file, os.path.basename(file))
            file_link = f"{SERVER_URL}/serve-file/{urllib.parse.quote(os.path.basename(zip_filename))}"
        else:
            # Apenas um arquivo
            file_link = f"{SERVER_URL}/serve-file/{urllib.parse.quote(os.path.basename(file_paths[0]))}"

        return jsonify({'message': 'Download concluído!', 'file_link': file_link})
     except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
    
def delete_download_folder(folder_path):
    # Verifica se a pasta existe
    if os.path.exists(folder_path):
        try:
            # Exclui a pasta e todo seu conteúdo
            shutil.rmtree(folder_path)
            print(f"Pasta '{folder_path}' excluída com sucesso!")
        except Exception as e:
            print(f"Erro ao excluir a pasta '{folder_path}': {e}")
    else:
        print(f"A pasta '{folder_path}' não existe!")    


@app.route('/delete-file', methods=['POST'])
def delete_file():
   delete_download_folder(DOWNLOAD_FOLDER)
   return "Pasta de downloads excluída com sucesso!", 200

@app.route('/serve-file/<path:filename>', methods=['GET'])
def serve_file(filename):
    decoded_filename = urllib.parse.unquote(filename)
    file_path = os.path.abspath(os.path.join(DOWNLOAD_FOLDER, decoded_filename))

    # Certifique-se de que o caminho está dentro do DOWNLOAD_FOLDER
    if not file_path.startswith(os.path.abspath(DOWNLOAD_FOLDER)):
        return jsonify({'error': 'Acesso negado!'}), 403

    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'error': 'Arquivo não encontrado!'}), 404

# Inicia o servidor
if __name__ == '__main__':
    app.run(debug=True)
