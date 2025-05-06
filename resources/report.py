from flask import request, jsonify
from flask_restful import Resource, reqparse, abort
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from models import db, User, Post, Comment, Ampersound, Report
from models import UserType, ReportContentType, ReportStatus, PostPrivacy, CommentVisibility

report_parser = reqparse.RequestParser()
report_parser.add_argument('content_type', type=str, required=True, help='Type of content being reported (post, comment, ampersound)', location='json', choices=('post', 'comment', 'ampersound'))
report_parser.add_argument('content_id', type=int, required=True, help='ID of the content being reported', location='json')
report_parser.add_argument('reason', type=str, required=False, help='Reason for the report', location='json', default='')

class ReportResource(Resource):
    @login_required
    def post(self):
        args = report_parser.parse_args()
        
        reporter = current_user
        content_type_str = args['content_type']
        content_id = args['content_id']
        reason = args['reason']

        try:
            content_type = ReportContentType(content_type_str)
        except ValueError:
            abort(400, message=f"Invalid content_type. Must be one of {[e.value for e in ReportContentType]}.")

        reported_item = None
        reported_user_id = None

        if content_type == ReportContentType.POST:
            reported_item = Post.query.get(content_id)
            if reported_item:
                reported_user_id = reported_item.user_id
        elif content_type == ReportContentType.COMMENT:
            reported_item = Comment.query.get(content_id)
            if reported_item:
                reported_user_id = reported_item.user_id
        elif content_type == ReportContentType.AMPERSOUND:
            reported_item = Ampersound.query.get(content_id)
            if reported_item:
                reported_user_id = reported_item.user_id
        
        if not reported_item:
            abort(404, message=f"{content_type.value.capitalize()} with ID {content_id} not found.")

        if reported_user_id == reporter.id:
            abort(400, message="You cannot report your own content.")

        # Check for existing report by the same user for the same content
        existing_report = Report.query.filter_by(
            reporter_id=reporter.id,
            content_type=content_type,
            content_id=content_id
        ).first()

        if existing_report:
            abort(409, message="You have already reported this content.")

        report_status = ReportStatus.PENDING
        message = "Report submitted successfully."

        # If reported by an Admin, take immediate action
        if reporter.user_type == UserType.ADMIN:
            reported_user = User.query.get(reported_user_id)
            if not reported_user:
                # This should ideally not happen if reported_item was found
                abort(500, message="Reported user not found unexpectedly.")

            # Make all posts friends-only
            for post in reported_user.posts:
                post.privacy = PostPrivacy.FRIENDS
            
            # Make all comments friends-only
            for comment in reported_user.comments:
                comment.visibility = CommentVisibility.FRIENDS_ONLY
            
            # Make all ampersounds friends-only
            for ampersound in reported_user.ampersounds:
                ampersound.privacy = 'friends' # Ampersound uses string 'friends'

            report_status = ReportStatus.RESOLVED_AUTO
            message = "Report submitted and user's content automatically restricted."
            db.session.add_all(reported_user.posts + reported_user.comments + reported_user.ampersounds)


        new_report = Report(
            reporter_id=reporter.id,
            reported_user_id=reported_user_id,
            content_type=content_type,
            content_id=content_id,
            reason=reason,
            status=report_status
        )

        try:
            db.session.add(new_report)
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            # Catch potential race conditions if uq_report_once_per_content is violated
            # This is a fallback, the check above should prevent it.
            return abort(409, message="Report already exists or other integrity error.")
        except Exception as e:
            db.session.rollback()
            return abort(500, message=f"Could not submit report: {str(e)}")

        return {'message': message, 'report_id': new_report.id}, 201 