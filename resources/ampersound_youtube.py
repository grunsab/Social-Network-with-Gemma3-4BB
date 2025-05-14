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

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_filename_template = os.path.join(tmpdir, f"ampersound_extract_%(id)s.%(ext)s")
                
                # Use yt-dlp to download and extract audio segment
                # -x: extract audio
                # --audio-format mp3: specify mp3 output
                # --audio-quality 5: good quality
                # -o: output template
                # --postprocessor-args "ffmpeg_i:-ss <start> -to <end>" : pass arguments to ffmpeg for precise cutting
                # Note: yt-dlp handles invoking ffmpeg.
                command = [
                    'yt-dlp',
                    '-x', '--audio-format', 'mp3', '--audio-quality', '5',
                    '-o', temp_filename_template,
                    '--postprocessor-args', f'ffmpeg_i:-ss {start_time} -to {end_time}',
                    youtube_url
                ]
                
                current_app.logger.info(f"Executing yt-dlp command: {' '.join(command)}")
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()

                if process.returncode != 0:
                    current_app.logger.error(f"yt-dlp error: {stderr.decode('utf-8', 'ignore')}")
                    # Try to find a more specific error message for the user
                    if "Unsupported URL" in stderr.decode('utf-8', 'ignore'):
                         return {"message": "Unsupported YouTube URL or video not found."}, 400
                    if "Video unavailable" in stderr.decode('utf-8', 'ignore'):
                        return {"message": "Video is unavailable."}, 400
                    if "ffmpeg" in stderr.decode('utf-8', 'ignore').lower() and "not found" in stderr.decode('utf-8', 'ignore').lower():
                         current_app.logger.error("FFmpeg not found by yt-dlp.")
                         return {"message": "Error processing video: FFmpeg utility not found on server."}, 500
                    return {"message": f"Error processing video. Details: {stderr.decode('utf-8', 'ignore')[:200]}"}, 500

                # Find the created file (yt-dlp replaces %(id)s with video_id, etc.)
                extracted_audio_path = None
                for f_name in os.listdir(tmpdir):
                    if f_name.startswith("ampersound_extract_") and f_name.endswith(".mp3"):
                        extracted_audio_path = os.path.join(tmpdir, f_name)
                        break
                
                if not extracted_audio_path or not os.path.exists(extracted_audio_path):
                    current_app.logger.error(f"Extracted audio file not found in {tmpdir} after yt-dlp. stdout: {stdout.decode()}, stderr: {stderr.decode()}")
                    return {"message": "Failed to retrieve processed audio file."}, 500

                file_size = os.path.getsize(extracted_audio_path)
                MAX_AUDIO_SIZE = 5 * 1024 * 1024 # 5 MB limit for extracted audio
                if file_size == 0: # Check if the file is empty (e.g. if duration was too short or cut failed)
                    return {"message": "Processed audio is empty. Check start/end times or video segment."}, 400
                if file_size > MAX_AUDIO_SIZE:
                    return {"message": f"Processed audio file size ({file_size // 1024}KB) exceeds the limit of {MAX_AUDIO_SIZE / 1024 / 1024}MB."}, 413


                # Upload to S3
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
                    file_path=s3_filename, # Store S3 key
                    privacy=privacy,
                    status=AmpersoundStatus.PENDING_APPROVAL # Default status
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
            # This might happen if a race condition occurs with the name check, though unlikely.
            return {"message": "Failed to save Ampersound due to a database conflict (e.g., name already taken)."}, 409
        except subprocess.CalledProcessError as e:
            current_app.logger.error(f"yt-dlp command failed: {e} - stderr: {e.stderr.decode('utf-8', 'ignore') if e.stderr else 'N/A'}")
            return {"message": f"Error during video processing subprocess. Details: {e.stderr.decode('utf-8', 'ignore')[:200] if e.stderr else 'Unknown error'}"}, 500
        except FileNotFoundError as e: # Catch if yt-dlp or ffmpeg command itself is not found
            current_app.logger.error(f"Command not found (yt-dlp or ffmpeg): {e}")
            if 'yt-dlp' in str(e):
                 return {"message": "Error processing video: yt-dlp utility not found on server."}, 500
            return {"message": "Error processing video: A required utility (like ffmpeg or yt-dlp) was not found on the server."}, 500
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error creating ampersound from YouTube: {e}", exc_info=True)
            return {"message": "An unexpected error occurred while creating the Ampersound."}, 500 