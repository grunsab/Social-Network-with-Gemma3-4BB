import os
import uuid
import mimetypes
import subprocess
import tempfile
from flask import request, current_app, jsonify
from flask_restful import Resource, reqparse
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
from cryptography.fernet import Fernet

from models import db, Ampersound, AmpersoundStatus
from utils import generate_s3_file_url

class AmpersoundFromYoutubeResource(Resource):
    @login_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('youtube_url', type=str, required=True, help='YouTube video URL is required.')
        parser.add_argument('start_time', type=int, required=True, help='Start time in seconds is required.')
        parser.add_argument('end_time', type=int, required=True, help='End time in seconds is required.')
        parser.add_argument('name', type=str, required=True, help='Ampersound name is required.')
        parser.add_argument('privacy', type=str, default='public', choices=('public', 'friends'), help='Privacy setting.')
        args = parser.parse_args()

        youtube_url = args['youtube_url']
        start_time = args['start_time']
        end_time = args['end_time']
        name = args['name']
        privacy = args['privacy'].lower()

        if start_time >= end_time:
            return {"message": "Start time must be before end time."}, 400
        
        duration = end_time - start_time
        MAX_DURATION = 30 # Max 30 seconds for an ampersound
        if duration > MAX_DURATION:
            return {"message": f"Ampersound duration cannot exceed {MAX_DURATION} seconds." }, 400

        clean_name = secure_filename(name).lower()
        if not clean_name or clean_name != name.lower() or '&' in clean_name or ' ' in clean_name:
            return {"message": "Invalid Ampersound name. Use alphanumeric characters without spaces or '&'."}, 400

        existing_ampersound = Ampersound.query.filter_by(user_id=current_user.id, name=clean_name).first()
        if existing_ampersound:
            return {"message": f"You already have an Ampersound named '{clean_name}'."}, 409

        s3_client = current_app.config.get('S3_CLIENT')
        if not s3_client:
            current_app.logger.error("S3 client not configured.")
            return {"message": "File storage (S3) is not configured on the server."}, 500

        decrypted_cookie_temp_file = None
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_filename_template = os.path.join(tmpdir, f"ampersound_extract_%(id)s.%(ext)s")
                
                # Get encrypted cookie file path from app config
                encrypted_cookie_file_path = os.environ.get('YTDLP_COOKIES_FILE_PATH')
                decryption_key = os.environ.get('COOKIE_DECRYPTION_KEY')

                yt_dlp_common_args = ['-g', '-x', '--audio-format', 'mp3']
                temp_decrypted_cookie_path = None

                if encrypted_cookie_file_path and decryption_key:
                    if os.path.exists(encrypted_cookie_file_path):
                        try:
                            fernet_obj = Fernet(decryption_key.encode())
                            with open(encrypted_cookie_file_path, "rb") as f_encrypted:
                                encrypted_data = f_encrypted.read()
                            decrypted_data = fernet_obj.decrypt(encrypted_data)
                            
                            # Create a named temporary file for the decrypted cookies
                            # This temp file will be created outside the main tmpdir to ensure it's cleaned up separately
                            decrypted_cookie_temp_file = tempfile.NamedTemporaryFile(delete=False, mode='wb', suffix='.txt', prefix='decrypted_cookies_')
                            decrypted_cookie_temp_file.write(decrypted_data)
                            temp_decrypted_cookie_path = decrypted_cookie_temp_file.name
                            decrypted_cookie_temp_file.close() # Close it so yt-dlp can read it

                            current_app.logger.info(f"Successfully decrypted cookies to {temp_decrypted_cookie_path}")
                            yt_dlp_common_args.extend(['--cookies', temp_decrypted_cookie_path])
                        except InvalidToken:
                            current_app.logger.error("Failed to decrypt cookie file: Invalid token (likely wrong key or corrupted file). Proceeding without cookies.")
                        except Exception as e:
                            current_app.logger.error(f"Error decrypting or writing cookie file: {e}. Proceeding without cookies.")
                    else:
                        current_app.logger.warning(f"Encrypted cookie file specified but not found: {encrypted_cookie_file_path}. Proceeding without cookies.")
                elif encrypted_cookie_file_path and not decryption_key:
                    current_app.logger.warning("Cookie file path is configured, but COOKIE_DECRYPTION_KEY environment variable is not set. Proceeding without cookies.")
                else:
                    current_app.logger.info("No encrypted cookie file path configured or decryption key missing. Proceeding without cookies.")

                # Step 1: Get the direct audio stream URL using yt-dlp
                get_url_command = [
                    'yt-dlp',
                    *yt_dlp_common_args,
                    youtube_url
                ]
                current_app.logger.info(f"Executing yt-dlp get URL command: {' '.join(get_url_command)}")
                process_get_url = subprocess.Popen(get_url_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                audio_stream_url_raw, stderr_get_url = process_get_url.communicate()

                if process_get_url.returncode != 0:
                    current_app.logger.error(f"yt-dlp get URL error: {stderr_get_url.decode('utf-8', 'ignore')}")
                    return {"message": f"Error getting audio stream URL. Details: {stderr_get_url.decode('utf-8', 'ignore')[:200]}"}, 500
                
                audio_stream_url = audio_stream_url_raw.decode('utf-8').strip().split('\n')[0]
                if not audio_stream_url:
                    current_app.logger.error(f"yt-dlp did not return an audio stream URL. stdout: {audio_stream_url_raw.decode('utf-8', 'ignore')}, stderr: {stderr_get_url.decode('utf-8', 'ignore')}")
                    return {"message": "Could not retrieve a direct audio stream from the video."}, 500

                current_app.logger.info(f"Retrieved audio stream URL: {audio_stream_url}")
                current_app.logger.info(f"Requested start_time: {start_time}, end_time: {end_time}, calculated duration: {duration}")

                # Step 2: Use ffmpeg to download and cut the segment
                unique_id = uuid.uuid4()
                extracted_audio_filename = f"extracted_audio_{unique_id}.mp3"
                extracted_audio_path_temp = os.path.join(tmpdir, extracted_audio_filename)

                ffmpeg_command = [
                    'ffmpeg',
                    '-i', audio_stream_url,
                    '-ss', str(start_time),
                    '-t', str(duration),
                    '-c:a', 'libmp3lame',
                    '-b:a', '128k',
                    '-vn',
                    '-y',
                    extracted_audio_path_temp
                ]
                
                current_app.logger.info(f"Executing ffmpeg command: {' '.join(ffmpeg_command)}")
                process_ffmpeg = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process_ffmpeg.communicate()

                if process_ffmpeg.returncode != 0:
                    current_app.logger.error(f"ffmpeg error: {stderr.decode('utf-8', 'ignore')}")
                    return {"message": f"Error processing audio with ffmpeg. Details: {stderr.decode('utf-8', 'ignore')[:200]}"}, 500

                extracted_audio_path = extracted_audio_path_temp
                
                if not os.path.exists(extracted_audio_path):
                    current_app.logger.error(f"Extracted audio file {extracted_audio_path} not found in {tmpdir} after ffmpeg. stdout: {stdout.decode()}, stderr: {stderr.decode()}")
                    return {"message": "Failed to retrieve processed audio file."}, 500

                file_size = os.path.getsize(extracted_audio_path)
                MAX_AUDIO_SIZE = 5 * 1024 * 1024
                if file_size == 0:
                    return {"message": "Processed audio is empty. Check start/end times or video segment."}, 400
                if file_size > MAX_AUDIO_SIZE:
                    return {"message": f"Processed audio file size ({file_size // 1024}KB) exceeds the limit of {MAX_AUDIO_SIZE / 1024 / 1024}MB."}, 413

                s3_filename = f"ampersounds/{current_user.id}/{clean_name}.mp3"
                s3_bucket = current_app.config['S3_BUCKET']
                
                with open(extracted_audio_path, 'rb') as f_upload:
                    s3_client.upload_fileobj(
                        f_upload,
                        s3_bucket,
                        s3_filename,
                        ExtraArgs={'ContentType': 'audio/mpeg'}
                    )
                
                file_url = generate_s3_file_url(current_app.config, s3_filename)
                
                ampersound = Ampersound(
                    user_id=current_user.id,
                    name=clean_name,
                    file_path=s3_filename,
                    privacy=privacy,
                    status=AmpersoundStatus.PENDING_APPROVAL
                )
                db.session.add(ampersound)
                db.session.commit()

                return {
                    "message": "Ampersound created successfully from YouTube video! It is pending approval.", 
                    "name": clean_name, 
                    "url": file_url,
                    "ampersound_id": ampersound.id,
                    "status": ampersound.status.value
                }, 201
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Database integrity error: {e}")
            return {"message": "Failed to save Ampersound due to a database conflict (e.g., name already taken)."}, 409
        except subprocess.CalledProcessError as e:
            current_app.logger.error(f"yt-dlp command failed: {e} - stderr: {e.stderr.decode('utf-8', 'ignore') if e.stderr else 'N/A'}")
            return {"message": f"Error during video processing subprocess. Details: {e.stderr.decode('utf-8', 'ignore')[:200] if e.stderr else 'Unknown error'}"}, 500
        except FileNotFoundError as e:
            current_app.logger.error(f"Command not found (yt-dlp or ffmpeg): {e}")
            if 'yt-dlp' in str(e):
                 return {"message": "Error processing video: yt-dlp utility not found on server."}, 500
            return {"message": "Error processing video: A required utility (like ffmpeg or yt-dlp) was not found on the server."}, 500
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error creating ampersound from YouTube: {e}", exc_info=True)
            return {"message": "An unexpected error occurred while creating the Ampersound."}, 500
        finally:
            # Ensure the temporary decrypted cookie file is deleted
            if decrypted_cookie_temp_file and temp_decrypted_cookie_path and os.path.exists(temp_decrypted_cookie_path):
                try:
                    os.remove(temp_decrypted_cookie_path)
                    current_app.logger.info(f"Successfully removed temporary decrypted cookie file: {temp_decrypted_cookie_path}")
                except Exception as e:
                    current_app.logger.error(f"Error removing temporary decrypted cookie file {temp_decrypted_cookie_path}: {e}") 