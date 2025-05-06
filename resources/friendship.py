from flask import request
from flask_restful import Resource, reqparse, fields, marshal_with, abort
from flask_login import current_user, login_required

from models import db, User, FriendRequest, FriendRequestStatus

# --- Field Definitions for Marshaling ---
user_summary_fields = {
    'id': fields.Integer,
    'username': fields.String,
    'profile_picture': fields.String
}

friend_request_fields = {
    'id': fields.Integer,
    'sender': fields.Nested(user_summary_fields),
    'receiver': fields.Nested(user_summary_fields),
    'status': fields.String(attribute='status.name'),
    'timestamp': fields.DateTime(dt_format='iso8601')
}

# --- Parsers ---
friend_request_parser = reqparse.RequestParser()
friend_request_parser.add_argument('user_id', type=int, required=True, help='User ID of the person to send request to', location='json')

friend_request_manage_parser = reqparse.RequestParser()
friend_request_manage_parser.add_argument('action', type=str, required=True, choices=('accept', 'reject'), help='Action to perform: accept or reject', location='json')

class FriendRequestListResource(Resource):
    # List pending received friend requests
    @login_required
    @marshal_with(friend_request_fields)
    def get(self):
        pending_requests = current_user.get_pending_received_requests() # Assumes method exists
        return pending_requests

    # Send a new friend request
    @login_required
    @marshal_with(friend_request_fields)
    def post(self):
        args = friend_request_parser.parse_args()
        user_to_request = User.query.get(args['user_id'])
        
        if not user_to_request:
            abort(404, message="User to send request to not found.")
        
        if user_to_request.id == current_user.id:
             abort(400, message="Cannot send friend request to yourself.")

        success, message, new_request = current_user.send_friend_request(user_to_request)
        if success:
            db.session.commit() # Commit if the model method indicated success
            return new_request, 201
        else:
            # Use the message from the model method
            abort(400, message=message or "Could not send friend request.") 

class FriendRequestResource(Resource):
    # Accept or Reject a received friend request
    @login_required
    @marshal_with(friend_request_fields)
    def put(self, request_id):
        args = friend_request_manage_parser.parse_args()
        action = args['action']
        friend_request = FriendRequest.query.get_or_404(request_id)

        if friend_request.receiver_id != current_user.id:
            abort(403, message="You cannot manage this friend request.")
        
        if friend_request.status != FriendRequestStatus.PENDING:
             abort(400, message="This request is not pending.")

        if action == 'accept':
            success, message = current_user.accept_friend_request(request_id)
        elif action == 'reject':
            success, message = current_user.reject_friend_request(request_id)
        else: # Should be caught by parser choices
            abort(400, message="Invalid action.")

        if success:
            db.session.commit()
            # Fetch the updated request to return it
            updated_request = FriendRequest.query.get(request_id)
            return updated_request
        else:
            abort(400, message=message or f"Could not {action} friend request.")

    # Cancel a sent friend request
    @login_required
    def delete(self, request_id):
        friend_request = FriendRequest.query.get_or_404(request_id)

        if friend_request.sender_id != current_user.id:
            abort(403, message="You cannot cancel a request you did not send.")
        
        if friend_request.status != FriendRequestStatus.PENDING:
             abort(400, message="This request is not pending and cannot be canceled.")

        try:
            db.session.delete(friend_request)
            db.session.commit()
            return {'message': 'Friend request canceled'}, 200 # Or 204
        except Exception as e:
            db.session.rollback()
            print(f"Error canceling friend request: {e}")
            abort(500, message="Failed to cancel friend request.")

class FriendshipResource(Resource):
    # Unfriend a user (remove friendship)
    @login_required
    def delete(self, user_id):
        user_to_unfriend = User.query.get(user_id)
        if not user_to_unfriend:
             abort(404, message="User to unfriend not found.")
        
        if user_to_unfriend.id == current_user.id:
            abort(400, message="Cannot unfriend yourself.")
        
        success, message = current_user.unfriend(user_to_unfriend)
        if success:
            db.session.commit()
            return {'message': f'Successfully unfriended {user_to_unfriend.username}'}, 200
        else:
            abort(400, message=message or "Could not unfriend user. Maybe you were not friends?") 