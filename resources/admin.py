\
from flask_restful import Resource, reqparse
from flask_login import current_user, login_required
from models import db, Ampersound, AmpersoundStatus, UserType

def admin_required(func):
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.user_type != UserType.ADMIN:
            return {"message": "Administrator access required"}, 403
        return func(*args, **kwargs)
    return wrapper

class AdminAmpersoundApprovalList(Resource):
    @admin_required
    def get(self):
        """List all ampersounds pending approval."""
        pending_ampersounds = Ampersound.query.filter_by(status=AmpersoundStatus.PENDING_APPROVAL).order_by(Ampersound.timestamp.asc()).all()
        
        results = []
        for ampersound in pending_ampersounds:
            results.append({
                'id': ampersound.id,
                'name': ampersound.name,
                'user_id': ampersound.user_id,
                'username': ampersound.user.username, # Assuming relationship is loaded or accessible
                'file_path': ampersound.file_path,
                'timestamp': ampersound.timestamp.isoformat(),
                'privacy': ampersound.privacy
            })
        return results, 200

class AdminAmpersoundApprovalAction(Resource):
    @admin_required
    def put(self, ampersound_id):
        """Approve or reject an ampersound."""
        parser = reqparse.RequestParser()
        parser.add_argument('action', type=str, required=True, help="Action must be 'approve' or 'reject'", choices=('approve', 'reject'))
        args = parser.parse_args()

        ampersound = Ampersound.query.get(ampersound_id)
        if not ampersound:
            return {"message": "Ampersound not found"}, 404

        if ampersound.status != AmpersoundStatus.PENDING_APPROVAL:
            return {"message": f"Ampersound is not pending approval. Current status: {ampersound.status.value}"}, 400

        action = args['action']
        if action == 'approve':
            ampersound.status = AmpersoundStatus.APPROVED
            db.session.commit()
            return {"message": f"Ampersound '{ampersound.name}' approved."}, 200
        elif action == 'reject':
            ampersound.status = AmpersoundStatus.REJECTED
            # Optionally, you might want to delete the S3 object for rejected ampersounds
            # or mark it for deletion later. For now, just updating status.
            db.session.commit()
            return {"message": f"Ampersound '{ampersound.name}' rejected."}, 200
        
        return {"message": "Invalid action."}, 400 # Should be caught by choices in parser

