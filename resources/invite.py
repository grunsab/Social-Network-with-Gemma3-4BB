from flask import current_app, url_for
from flask_restful import Resource, fields, marshal_with, abort
from flask_login import current_user, login_required

from models import db, User, InviteCode

# --- Field Definitions ---

# For displaying an invite code
invite_code_fields = {
    'id': fields.Integer,
    'code': fields.String,
    'is_used': fields.Boolean,
    'issuer_id': fields.Integer,
    'used_by_id': fields.Integer,
    'used_by_username': fields.String(attribute='used_by.username', default=None), # Get username via relationship
    'timestamp': fields.DateTime(dt_format='iso8601'),
    'registration_url': fields.FormattedString('{scheme}://{host}/register?invite_code={code}') # Construct URL - needs request context
    # Need a way to pass scheme/host or construct this differently
}

# For the overall response of the manage invites endpoint
manage_invites_response_fields = {
    'unused_codes': fields.List(fields.Nested(invite_code_fields)),
    'used_codes': fields.List(fields.Nested(invite_code_fields)),
    'invites_left': fields.Integer
}

class InviteResource(Resource):
    @login_required
    # Removed marshal_with for GET temporarily due to URL generation complexity
    def get(self):
        # Logic from manage_invites GET
        unused_codes = InviteCode.query.filter_by(issuer_id=current_user.id, is_used=False).all()
        used_codes = InviteCode.query.filter_by(issuer_id=current_user.id, is_used=True).join(User, InviteCode.used_by_id == User.id).options(joinedload(InviteCode.used_by)).all()
        
        # Manually construct response for now, especially the URL
        # This might need request context or config for base URL
        base_url = url_for('index', _external=True).replace('/', '') # Hacky way to get base URL
        register_base_url = url_for('register', _external=True) # Assuming a route named 'register' exists for URL generation?
                                                                # This is problematic as we removed the Flask register route.
                                                                # We need a frontend URL base from config.
        frontend_base_url = current_app.config.get('FRONTEND_URL', '') # Need to configure this!

        def serialize_code(code):
            return {
                'id': code.id,
                'code': code.code,
                'is_used': code.is_used,
                'issuer_id': code.issuer_id,
                'used_by_id': code.used_by_id,
                'used_by_username': code.used_by.username if code.used_by else None,
                'timestamp': code.timestamp.isoformat(),
                # Construct URL based on assumed frontend routing
                'registration_url': f"{frontend_base_url}/register?invite_code={code.code}" if frontend_base_url else None
            }

        return {
            'unused_codes': [serialize_code(code) for code in unused_codes],
            'used_codes': [serialize_code(code) for code in used_codes],
            'invites_left': current_user.invites_left
        }

    @login_required
    @marshal_with(invite_code_fields) # Can marshal the newly created code
    def post(self):
        # Logic from manage_invites POST (Generate new code)
        if current_user.invites_left <= 0:
            abort(400, message="You have no invites left.")

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