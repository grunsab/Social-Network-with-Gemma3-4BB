from openai import OpenAI
from flask import current_app, jsonify, request
from flask_restful import Resource, reqparse, abort
from flask_login import current_user, login_required
import os
import uuid
import mimetypes
import io
import base64

from models import db, Post, User

# --- Parser for image generation ---
image_gen_parser = reqparse.RequestParser()
image_gen_parser.add_argument('prompt', type=str, required=True, help='Prompt for image generation cannot be blank')

class ImageGenerationResource(Resource):
    def _get_r2_file_url(self, app_config, s3_key):
        """Helper to generate R2/S3 file URL based on app configuration."""
        if not s3_key:
            return None

        s3_bucket = app_config.get('S3_BUCKET')
        domain_name_images = app_config.get('DOMAIN_NAME_IMAGES')
        s3_endpoint_url = app_config.get('S3_ENDPOINT_URL')

        file_url = None
        if s3_bucket:
            try:
                if domain_name_images:
                    file_url = f"{domain_name_images}/{s3_key}"
                elif s3_endpoint_url:
                    file_url = f"{s3_endpoint_url}/{s3_bucket}/{s3_key}"
            except Exception as e:
                current_app.logger.error(f"Error generating R2/S3 URL for key {s3_key}: {e}")
                return None
        return file_url

    @login_required
    def post(self):
        args = image_gen_parser.parse_args()
        prompt = args['prompt']
        
        openai_api_key = current_app.config.get('OPENAI_API_KEY')
        openai_client = OpenAI(
                api_key=openai_api_key,
                base_url="https://api.deepinfra.com/v1/openai",
             )
        s3_client = current_app.config.get('S3_CLIENT')
        s3_bucket = current_app.config.get('S3_BUCKET')
        if not s3_client or not s3_bucket:
            abort(500, message="S3/R2 storage is not configured.")

        try:
            # 1. Call OpenAI API to generate image
            response = openai_client.images.generate(
                prompt=prompt,
                model="black-forest-labs/FLUX-1-schnell",
                n=4,
                size="512x512",
                response_format="b64_json"
            )

            if not response.data or not response.data[0].b64_json:
                current_app.logger.error(f"Unexpected OpenAI API response structure: {response}")
                abort(500, message="Failed to retrieve image data from OpenAI API.")

            # 2. Decode the base64 image data
            image_b64_json = response.data[0].b64_json
            image_data_bytes = base64.b64decode(image_b64_json)
            image_data = io.BytesIO(image_data_bytes)

            if image_data.getbuffer().nbytes == 0:
                abort(500, message="Decoded image data is empty.")

            content_type = 'image/png'
            extension = '.png'

            # 3. Upload to R2
            s3_filename = f"generated_images/{current_user.id}/{uuid.uuid4()}{extension}"
            
            s3_client.upload_fileobj(
                image_data,
                s3_bucket,
                s3_filename,
                ExtraArgs={'ContentType': content_type}
            )
            
            # 4. Get the R2 public URL
            final_image_url = self._get_r2_file_url(current_app.config, s3_filename)
            if not final_image_url:
                try:
                    s3_client.delete_object(Bucket=s3_bucket, Key=s3_filename)
                    current_app.logger.info(f"Cleaned up S3 object {s3_filename} after URL generation failure.")
                except Exception as s3_del_e:
                    current_app.logger.error(f"Failed to cleanup S3 object {s3_filename}: {s3_del_e}")
                abort(500, message="Failed to construct final image URL after uploading to R2.")

            # 5. Create a new post with the R2 image URL
            new_post = Post(
                content=f"Generated image with prompt: {prompt}",
                user_id=current_user.id,
                image_url=final_image_url 
            )
            db.session.add(new_post)
            db.session.commit()

            return {'message': 'Image generated via OpenAI, uploaded to R2, and post created successfully', 'post_id': new_post.id, 'image_url': final_image_url}, 201

        except openai.APIError as e:
            current_app.logger.error(f"OpenAI API error: {e}")
            abort(e.http_status or 500, message=f"OpenAI API error: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"An unexpected error occurred during OpenAI image generation and upload: {e}", exc_info=True)
            abort(500, message="An unexpected error occurred during image generation and R2 upload.")
