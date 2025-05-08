import uuid
import mimetypes
from flask import request, jsonify, current_app
from flask_restful import Resource, reqparse
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import joinedload

from models import db, User, Ampersound, AmpersoundStatus, UserType
from utils import generate_s3_file_url

class AmpersoundListResource(Resource):
    @login_required
    def post(self):
        """Create a new Ampersound."""
        if 'audio_file' not in request.files:
            return {"message": "No audio file part"}, 400
        
        file = request.files['audio_file']
        name = request.form.get('name')
        privacy = request.form.get('privacy', 'public').lower()

        if privacy not in ['public', 'friends']:
            privacy = 'public'

        if not name:
            return {"message": "Ampersound name is required"}, 400

        clean_name = secure_filename(name).lower()
        if not clean_name or clean_name != name.lower() or '&' in clean_name or ' ' in clean_name:
            return {"message": "Invalid Ampersound name. Use alphanumeric characters without spaces or '&'."}, 400

        if file.filename == '':
            return {"message": "No selected file"}, 400

        existing_ampersound = Ampersound.query.filter_by(user_id=current_user.id, name=clean_name).first()
        if existing_ampersound:
            return {"message": f"You already have an Ampersound named '{clean_name}'."}, 409

        s3_client = current_app.config.get('S3_CLIENT')
        if file and s3_client:
            filename = secure_filename(file.filename)
            content_type = file.mimetype
            extension = mimetypes.guess_extension(content_type)
            if not extension:
                if 'webm' in content_type: extension = '.webm'
                elif 'wav' in content_type: extension = '.wav'
                elif 'ogg' in content_type: extension = '.ogg'
                else: extension = '.mp3'
            
            s3_filename = f"ampersounds/{current_user.id}/{clean_name}{extension}"
            s3_bucket = current_app.config['S3_BUCKET']

            try:
                s3_client.upload_fileobj(
                    file,
                    s3_bucket,
                    s3_filename,
                    ExtraArgs={'ContentType': content_type}
                )
                file_url = generate_s3_file_url(current_app.config, s3_filename)
                
                ampersound = Ampersound(
                    user_id=current_user.id,
                    name=clean_name,
                    file_path=s3_filename,
                    privacy=privacy
                )
                db.session.add(ampersound)
                db.session.commit()
                return {
                    "message": "Ampersound created successfully! It is pending approval.", 
                    "name": clean_name, 
                    "url": file_url, 
                    "ampersound_id": ampersound.id,
                    "status": ampersound.status.value
                }, 201
            except Exception as e:
                current_app.logger.error(f"Error uploading ampersound to S3: {e}")
                return {"message": "Error uploading file to S3."}, 500
        elif not s3_client:
            return {"message": "File storage (S3) is not configured on the server."}, 500
        else:
            return {"message": "Invalid file."}, 400

    def get(self):
        """List all viewable Ampersounds."""
        base_query = (
            Ampersound.query
            .join(User, User.id == Ampersound.user_id)
            .options(joinedload(Ampersound.user))
        )

        if current_user.is_authenticated and current_user.user_type == UserType.ADMIN:
            pass
        elif current_user.is_authenticated:
            owner_condition = (Ampersound.user_id == current_user.id)
            friend_ids = current_user.get_friend_ids()
            
            approved_public_condition = and_(
                Ampersound.status == AmpersoundStatus.APPROVED, 
                Ampersound.privacy == 'public'
            )
            approved_friends_condition = and_(
                Ampersound.status == AmpersoundStatus.APPROVED, 
                Ampersound.privacy == 'friends',
                Ampersound.user_id.in_(friend_ids) 
            )
            base_query = base_query.filter(or_(owner_condition, approved_public_condition, approved_friends_condition))
        else:
            base_query = base_query.filter(
                and_(Ampersound.status == AmpersoundStatus.APPROVED, Ampersound.privacy == 'public')
            )

        all_ampersounds = (
            base_query
            .order_by(Ampersound.play_count.desc(), Ampersound.timestamp.desc())
            .limit(50)
            .all()
        )

        results = []
        for ampersound in all_ampersounds:
            file_url = generate_s3_file_url(current_app.config, ampersound.file_path)
            results.append({
                'id': ampersound.id,
                'name': ampersound.name,
                'user': {
                    'id': ampersound.user.id,
                    'username': ampersound.user.username
                },
                'url': file_url,
                'timestamp': ampersound.timestamp.isoformat(),
                'play_count': ampersound.play_count,
                'privacy': ampersound.privacy,
                'status': ampersound.status.value
            })
        return results, 200

class AmpersoundResource(Resource):
    def get(self, sound_id=None, username=None, sound_name=None):
        """Get a specific Ampersound by ID or by username and sound_name."""
        ampersound = None
        if sound_id:
            ampersound = Ampersound.query.get(sound_id)
        elif username and sound_name:
            user = User.query.filter_by(username=username).first()
            if not user:
                return {"message": "User not found"}, 404
            clean_sound_name = secure_filename(sound_name).lower()
            ampersound = Ampersound.query.filter_by(user_id=user.id, name=clean_sound_name).first()
        
        if not ampersound:
            return {"message": "Ampersound not found"}, 404

        if not ampersound.is_visible_to(current_user): 
            return {"message": "You do not have permission to view this Ampersound"}, 403

        can_play_and_increment = False
        if ampersound.status == AmpersoundStatus.APPROVED:
            can_play_and_increment = True
        elif current_user.is_authenticated and ampersound.user_id == current_user.id:
            can_play_and_increment = True
        
        if can_play_and_increment:
            try:
                ampersound.play_count = (Ampersound.play_count or 0) + 1
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error incrementing play_count for ampersound {ampersound.id}: {e}")

        file_url = generate_s3_file_url(current_app.config, ampersound.file_path)
        if not file_url:
            current_app.logger.error(f"Failed to generate URL for ampersound {ampersound.id} with key {ampersound.file_path}")
            return {"message": "Error retrieving Ampersound URL due to configuration issue."}, 500
            
        return {
            "id": ampersound.id,
            "name": ampersound.name, 
            "url": file_url, 
            "user": ampersound.user.username, 
            "play_count": ampersound.play_count,
            "privacy": ampersound.privacy,
            "status": ampersound.status.value
        }, 200

    @login_required
    def delete(self, sound_id):
        """Delete an Ampersound by ID."""
        ampersound = Ampersound.query.get(sound_id)
        if not ampersound:
            return {"message": "Ampersound not found"}, 404

        if not (current_user.user_type == UserType.ADMIN or ampersound.user_id == current_user.id):
            return {"message": "You do not have permission to delete this Ampersound"}, 403

        s3_client = current_app.config.get('S3_CLIENT')
        s3_bucket = current_app.config.get('S3_BUCKET')
        s3_key_to_delete = ampersound.file_path

        try:
            db.session.delete(ampersound)
            db.session.commit()

            if s3_client and s3_bucket and s3_key_to_delete:
                try:
                    s3_client.delete_object(Bucket=s3_bucket, Key=s3_key_to_delete)
                    current_app.logger.info(f"Successfully deleted S3 object: {s3_key_to_delete}")
                except Exception as s3_error:
                    current_app.logger.error(f"Error deleting S3 object {s3_key_to_delete} for deleted ampersound {sound_id}: {s3_error}")
            
            return {"message": "Ampersound deleted successfully"}, 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting ampersound {sound_id} from database: {e}")
            return {"message": "Failed to delete Ampersound"}, 500

class MyAmpersoundsResource(Resource):
    @login_required
    def get(self):
        """List Ampersounds owned by the current user."""
        user_ampersounds = Ampersound.query.filter_by(user_id=current_user.id).order_by(Ampersound.timestamp.desc()).all()
        results = []
        for ampersound in user_ampersounds:
            file_url = generate_s3_file_url(current_app.config, ampersound.file_path)
            results.append({
                'id': ampersound.id,
                'name': ampersound.name,
                'file_path': ampersound.file_path,
                'url': file_url,
                'timestamp': ampersound.timestamp.isoformat(),
                'privacy': ampersound.privacy,
                'status': ampersound.status.value
            })
        return results, 200

class AmpersoundSearchResource(Resource):
    def get(self):
        """Search for Ampersounds."""
        query_term = request.args.get('q', '').strip()
        limit = request.args.get('limit', 10, type=int)

        if not query_term:
            return [], 200 

        base_query = Ampersound.query.join(User, User.id == Ampersound.user_id)

        if '.' in query_term:
            parts = query_term.split('.', 1)
            username_part = parts[0]
            soundname_part = parts[1]
            username_pattern = f"{username_part}%"
            soundname_pattern = f"{soundname_part}%"
            base_query = base_query.filter(
                func.lower(User.username).ilike(username_pattern),
                func.lower(Ampersound.name).ilike(soundname_pattern)
            )
        else:
            soundname_pattern = f"{query_term}%"
            base_query = base_query.filter(func.lower(Ampersound.name).ilike(soundname_pattern))

        if current_user.is_authenticated and current_user.user_type == UserType.ADMIN:
            pass
        elif current_user.is_authenticated:
            owner_condition = (Ampersound.user_id == current_user.id)
            friend_ids = current_user.get_friend_ids()
            
            approved_public_condition = and_(
                Ampersound.status == AmpersoundStatus.APPROVED, 
                Ampersound.privacy == 'public'
            )
            approved_friends_condition = and_(
                Ampersound.status == AmpersoundStatus.APPROVED, 
                Ampersound.privacy == 'friends',
                Ampersound.user_id.in_(friend_ids)
            )
            base_query = base_query.filter(or_(owner_condition, approved_public_condition, approved_friends_condition))
        else:
            base_query = base_query.filter(
                and_(Ampersound.status == AmpersoundStatus.APPROVED, Ampersound.privacy == 'public')
            )

        ampersounds_query = (
            base_query
            .options(joinedload(Ampersound.user))
            .order_by(User.username, Ampersound.name)
            .limit(limit)
        )
        found_ampersounds = ampersounds_query.all()
        
        results = []
        for sound in found_ampersounds:
            tag = f"&{sound.user.username}.{sound.name}"
            file_url = generate_s3_file_url(current_app.config, sound.file_path)
            results.append({
                "id": sound.id,
                "tag": tag,
                "user": {
                    "id": sound.user.id,
                    "username": sound.user.username
                },
                "name": sound.name,
                "url": file_url,
                "privacy": sound.privacy,
                "status": sound.status.value
            })
        return results, 200
