from flask import current_app, url_for
from flask_restful import Resource, fields, marshal_with, abort
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from models import db, User, InviteCode
from extensions import login_manager

# --- Field Definitions ---

# For displaying an invite code
invite_code_fields = {
    'id': fields.Integer,
    'code': fields.String,
    'is_used': fields.Boolean,
    'issuer_id': fields.Integer,
    'used_by_id': fields.Integer,
    'used_by_username': fields.String(attribute='used_by.username', default=None), # Get username via relationship
    'timestamp': fields.DateTime(dt_format='iso8601')
    # 'registration_url': fields.FormattedString('{scheme}://{host}/register?invite_code={code}') # Removed - Handled manually in GET
}

# For the overall response of the manage invites endpoint
manage_invites_response_fields = {
    'unused_codes': fields.List(fields.Nested(invite_code_fields)),
    'used_codes': fields.List(fields.Nested(invite_code_fields)),
    'invites_left': fields.Integer
}

class InviteResource(Resource):
    # @login_required # Remove decorator from class if any
    # Removed marshal_with for GET temporarily due to URL generation complexity
    @login_required # Explicitly add to GET
    def get(self):
        # if not current_user.is_authenticated: # Remove manual check
        #     return login_manager.unauthorized()
        # Logic from manage_invites GET
        unused_codes = InviteCode.query.filter_by(issuer_id=current_user.id, is_used=False).all()
        used_codes = InviteCode.query.filter_by(issuer_id=current_user.id, is_used=True).join(User, InviteCode.used_by_id == User.id).options(joinedload(InviteCode.used_by_user)).all()
        
        # Manually construct response for now, especially the URL
        # Use FRONTEND_URL from config for the registration link base
        frontend_base_url = current_app.config.get('FRONTEND_URL', '') # Need to configure this!

        def serialize_code(code):
            return {
                'id': code.id,
                'code': code.code,
                'is_used': code.is_used,
                'issuer_id': code.issuer_id,
                'used_by_id': code.used_by_id,
                'used_by_username': code.used_by_user.username if code.used_by_user else None,
                'timestamp': code.timestamp.isoformat(),
                # Construct URL based on assumed frontend routing
                'registration_url': f"{frontend_base_url}/register?invite_code={code.code}" if frontend_base_url else None
            }

        # Explicitly reload user from DB to ensure fresh data
        fresh_user = User.query.get(current_user.id)
        if not fresh_user:
             # Should not happen if user is authenticated, but good check
             abort(401, message="Could not reload user data.")

        invites_left_value = fresh_user.invites_left # Use reloaded user data
        print(f"INFO: GET /invites: Returning invites_left = {invites_left_value} for user {fresh_user.username}") 

        return {
            'unused_codes': [serialize_code(code) for code in unused_codes],
            'used_codes': [serialize_code(code) for code in used_codes],
            'invites_left': invites_left_value
        }

    @login_required # Explicitly add to POST
    @marshal_with(invite_code_fields) # Can marshal the newly created code
    def post(self):
        # if not current_user.is_authenticated: # Remove manual check
        #     return login_manager.unauthorized()
            
        user_id = current_user.id
        # Fetch the user again to ensure we have the latest invites_left count
        # This is important if other operations might change it within the same session
        # fresh_user = User.query.get(user_id) # Using Session.get() is preferred in SQLAlchemy 2.0
        fresh_user = db.session.get(User, user_id)

        if fresh_user.invites_left <= 0:
            # return {'message': 'No invites left to generate'}, 400 # Old way
            abort(400, message='No invites left to generate') # Use abort

        new_code = InviteCode(issuer_id=current_user.id)
        current_user.invites_left -= 1
        db.session.add(new_code)
        db.session.add(current_user) # Add user to session to save invites_left change
        try:
            db.session.commit()
            # Need to reconstruct URL here too if returned via marshal_with
            # For now, return the code object, marshal omits the URL
            return new_code, 201
        except Exception as e:
            db.session.rollback()
            print(f"Error generating invite code: {e}")
            abort(500, message="Error generating invite code.")