from flask_restful import Resource, fields, marshal_with
from flask_login import login_required, current_user
from models import db, Notification, User

# Actor (user who performed the action) fields
actor_fields = {
    'id': fields.Integer,
    'username': fields.String
}

notification_fields = {
    'id': fields.Integer,
    'notification_type': fields.String(attribute=lambda n: n.notification_type.value),
    'actor': fields.Nested(actor_fields, attribute=lambda n: n.actor),
    'post_id': fields.Integer,
    'comment_id': fields.Integer,
    'timestamp': fields.DateTime(dt_format='iso8601'),
    'is_read': fields.Boolean
}

class NotificationListResource(Resource):
    @login_required
    @marshal_with(notification_fields)
    def get(self):
        # Return all notifications for current user, newest first
        notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
        return notifs, 200

class NotificationResource(Resource):
    @login_required
    @marshal_with(notification_fields)
    def patch(self, notif_id):
        notif = Notification.query.get_or_404(notif_id)
        if notif.user_id != current_user.id:
            return {'message': 'Forbidden'}, 403
        notif.is_read = True
        db.session.commit()
        return notif, 200

class UnreadCountResource(Resource):
    @login_required
    def get(self):
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return {'unread_count': count}, 200
