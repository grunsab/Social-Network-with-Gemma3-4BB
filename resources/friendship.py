from flask import request
from flask_restful import Resource, reqparse, fields, marshal_with, abort
from flask_login import current_user, login_required
from extensions import login_manager

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
        pending_requests = current_user.get_pending_received_requests()
        return pending_requests, 200

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

        new_request_obj = current_user.send_friend_request(user_to_request)
        
        if new_request_obj: # If method returned a request object, it succeeded
            try:
                 db.session.commit() # Commit the new request
                 return new_request_obj, 201
            except Exception as e: # Catch potential commit errors (like unique constraint) 
                 db.session.rollback()
                 # Log the error e
                 abort(500, message="Database error saving friend request.")
        else:
            # If None was returned, it means request was not sent (e.g., already friends/pending)
            # We need a more specific message here, maybe the model method should return it?
            # For now, return a generic error.
            abort(400, message="Could not send friend request (already friends or request pending?).") 

class FriendRequestResource(Resource):
    # Add decorators back
    method_decorators = [login_required]

    # Accept or Reject a received friend request
    @marshal_with(friend_request_fields)
    def put(self, request_id):
        args = friend_request_manage_parser.parse_args()
        action = args['action']
        friend_request = FriendRequest.query.get_or_404(request_id)

        if friend_request.receiver_id != current_user.id:
            abort(403, message="You cannot manage this friend request.")
        
        if friend_request.status != FriendRequestStatus.PENDING:
             abort(400, message="This request is not pending.")

        success = False # Initialize success flag
        if action == 'accept':
            # success, message = current_user.accept_friend_request(request_id)
            success = current_user.accept_friend_request(request_id) # Returns boolean
        elif action == 'reject':
            # success, message = current_user.reject_friend_request(request_id)
            success = current_user.reject_friend_request(request_id) # Returns boolean
        else: # Should be caught by parser choices
            abort(400, message="Invalid action.")

        if success:
            try:
                db.session.commit()
                # Fetch the updated request to return it
                # Note: If reject deletes, this will be None or raise error - handle downstream?
                updated_request = FriendRequest.query.get(request_id)
                if updated_request is None and action == 'reject':
                    # If reject deletes the request, return success message instead of marshaling None
                    return {'message': 'Friend request rejected successfully.'}, 200 
                elif updated_request:    
                    return updated_request # Marshal the updated request (for accept)
                else: # Should not happen if accept worked unless concurrent delete
                    abort(404, message="Friend request not found after update.")
            except Exception as e:
                db.session.rollback()
                abort(500, message=f"Database error managing friend request: {e}")
        else:
            # If the model method returned False
            abort(400, message=f"Could not {action} friend request.")

    # Cancel a sent friend request
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
    # Add decorator back - Reverted, apply manual check
    method_decorators = [login_required]

    # Unfriend a user (remove friendship)
    def delete(self, user_id):
        # <<< Manual authentication check >>> - REMOVED, handled by decorator
        # if not current_user.is_authenticated:
        #     return login_manager.unauthorized()

        user_to_unfriend = User.query.get(user_id)
        if not user_to_unfriend:
             abort(404, message="User to unfriend not found.")
        
        if user_to_unfriend.id == current_user.id:
            abort(400, message="Cannot unfriend yourself.")
        
        # success, message = current_user.unfriend(user_to_unfriend)
        success = current_user.unfriend(user_to_unfriend) # Returns boolean

        if success:
            try:
                 db.session.commit()
                 return {'message': f'Successfully unfriended {user_to_unfriend.username}'}, 200
            except Exception as e:
                 db.session.rollback()
                 abort(500, message=f"Database error unfriending user: {e}")
        else:
            # If unfriend returned False, likely means they weren't friends
            abort(400, message="Could not unfriend user. Maybe you were not friends?") 