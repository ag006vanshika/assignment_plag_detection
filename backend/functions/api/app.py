from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
import botocore
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import json
import traceback
from datetime import datetime, timezone
import uuid
from decimal import Decimal

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) # Enable CORS for frontend

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        headers = response.headers

        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

        return response

# AWS clients
s3_client = boto3.client('s3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)

dynamodb = boto3.resource('dynamodb',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)

textract_client = boto3.client('textract',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)

# Configuration
BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'plagiarism-detection-assignments')
TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'submissions')
UPLOAD_FOLDER = 'uploads/'

# Import our custom modules
from text_processor import preprocess_text
from plagiarism_engine import calculate_similarity

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now(timezone.utc).isoformat()})

@app.route('/upload', methods=['POST'])
def upload_assignment():
    """
    Upload assignment file and trigger processing
    Expected form data: file, studentId, courseId
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        student_id = request.form.get('studentId')
        course_id = request.form.get('courseId')

        if not all([file, student_id, course_id]):
            return jsonify({'error': 'Missing required fields: file, studentId, courseId'}), 400

        # Validate file type
        allowed_extensions = {'pdf', 'txt'}
        filename = secure_filename(file.filename)
        file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

        if file_extension not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Allowed: PDF, TXT'}), 400

        # Generate unique submission ID
        submission_id = str(uuid.uuid4())

        # Upload to S3
        s3_key = f"{UPLOAD_FOLDER}{submission_id}/{filename}"
        s3_client.upload_fileobj(file, BUCKET_NAME, s3_key)

        # Extract text based on file type
        extracted_text = extract_text_from_file(s3_key, file_extension)

        if not extracted_text:
            return jsonify({'error': 'Failed to extract text from file'}), 500

        # Preprocess text
        processed_text = preprocess_text(extracted_text)

        # Store in DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        created_at = datetime.now(timezone.utc).isoformat()
        submission_data = {
            'PK': f'SUBMISSION#{course_id}#{student_id}#{submission_id}',
            'SK': f'METADATA#{created_at}',
            'GSI1PK': f'STUDENT#{student_id}',
            'GSI1SK': created_at,
            'entityType': 'SUBMISSION',
            'submissionId': submission_id,
            'studentId': student_id,
            'courseId': course_id,
            'fileName': filename,
            's3Key': s3_key,
            'extractedText': extracted_text,
            'processedText': processed_text,
            'status': 'UPLOADED',
            'createdAt': created_at,
            'similarityScore': Decimal('0.0'),
            'flagged': False
        }

        table.put_item(Item=submission_data)

        # Trigger similarity check (async)
        # In a real implementation, this would be a separate Lambda function
        # For now, we'll do it synchronously for simplicity
        check_similarity_for_submission(submission_id, course_id, student_id, processed_text, submission_data['PK'], submission_data['SK'])

        return jsonify({
            'message': 'Assignment uploaded successfully',
            'submissionId': submission_id,
            'status': 'processing'
        }), 201

    except Exception as e:
        print(f"Upload error: {str(e)}")
        traceback.print_exc()
        if os.getenv('FLASK_ENV') == 'development' or os.getenv('FLASK_DEBUG', '').lower() == 'true':
            return jsonify({'error': 'Internal server error', 'details': str(e)}), 500
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/submissions', methods=['GET'])
def get_submissions():
    """
    Get submissions with optional filtering
    Query parameters: courseId, studentId, status, limit, offset
    """
    try:
        table = dynamodb.Table(TABLE_NAME)

        course_id = request.args.get('courseId')
        student_id = request.args.get('studentId')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = request.args.get('offset', '0')

        # Build query based on filters
        if student_id:
            # Query by student
            response = table.query(
                IndexName='GSI1',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('GSI1PK').eq(f'STUDENT#{student_id}'),
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )
        elif course_id:
            # Query by course (would need another GSI in production)
            # For now, scan with filter
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('courseId').eq(course_id),
                Limit=limit
            )
        else:
            # Get all submissions (with pagination)
            response = table.scan(Limit=limit)

        submissions = []
        for item in response.get('Items', []):
            if item.get('entityType') == 'SUBMISSION':
                submissions.append({
                    'id': item['submissionId'],
                    'studentId': item['studentId'],
                    'courseId': item['courseId'],
                    'fileName': item['fileName'],
                    'status': item['status'],
                    'similarityScore': item.get('similarityScore', Decimal('0.0')),
                    'flagged': item.get('flagged', False),
                    'createdAt': item['createdAt']
                })

        # Apply status filter if specified
        if status:
            submissions = [s for s in submissions if s['status'] == status]

        return jsonify({
            'submissions': submissions,
            'total': len(submissions),
            'limit': limit
        })

    except Exception as e:
        print(f"Get submissions error: {str(e)}")
        return jsonify({'error': 'Failed to fetch submissions'}), 500

@app.route('/submissions/<submission_id>', methods=['GET'])
def get_submission_details(submission_id):
    """
    Get detailed information about a specific submission
    """
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Query for the submission
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('submissionId').eq(submission_id) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION')
        )

        items = response.get('Items', [])
        if not items:
            return jsonify({'error': 'Submission not found'}), 404

        submission = items[0]

        # Get comparison results if any
        comparison_response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('PK').eq(submission['PK']),
            FilterExpression=boto3.dynamodb.conditions.Attr('entityType').eq('COMPARISON')
        )

        comparisons = []
        for item in comparison_response.get('Items', []):
            comparisons.append({
                'matchedSubmissionId': item.get('matchedSubmissionId'),
                'similarityScore': item.get('similarityScore', Decimal('0.0')),
                'matchedSections': item.get('matchedSections', [])
            })

        return jsonify({
            'submission': {
                'id': submission['submissionId'],
                'studentId': submission['studentId'],
                'courseId': submission['courseId'],
                'fileName': submission['fileName'],
                'status': submission['status'],
                'similarityScore': submission.get('similarityScore', Decimal('0.0')),
                'flagged': submission.get('flagged', False),
                'createdAt': submission['createdAt'],
                'extractedText': submission.get('extractedText', ''),
                'processedText': submission.get('processedText', ''),
                'matchedSubmissionId': submission.get('matchedSubmissionId')
            },
            'comparisons': comparisons
        })

    except Exception as e:
        print(f"Get submission details error: {str(e)}")
        return jsonify({'error': 'Failed to fetch submission details'}), 500

@app.route('/submissions/<submission_id>/review', methods=['PATCH'])
def review_submission(submission_id):
    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('submissionId').eq(submission_id) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION')
        )
        items = response.get('Items', [])
        if not items:
            return jsonify({'error': 'Submission not found'}), 404

        submission = items[0]
        update_response = table.update_item(
            Key={
                'PK': submission['PK'],
                'SK': submission['SK']
            },
            UpdateExpression='SET flagged = :flagged, #status = :status',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':flagged': False,
                ':status': 'REVIEWED'
            }
        )

        return jsonify({'message': 'Submission marked as reviewed'}), 200
    except Exception as e:
        print(f"Review submission error: {str(e)}")
        return jsonify({'error': 'Failed to mark submission as reviewed'}), 500

@app.route('/submissions/<submission_id>/flag', methods=['PATCH'])
def flag_submission(submission_id):
    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('submissionId').eq(submission_id) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION')
        )
        items = response.get('Items', [])
        if not items:
            return jsonify({'error': 'Submission not found'}), 404

        submission = items[0]
        update_response = table.update_item(
            Key={
                'PK': submission['PK'],
                'SK': submission['SK']
            },
            UpdateExpression='SET flagged = :flagged, #status = :status',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':flagged': True,
                ':status': 'FLAGGED'
            }
        )

        return jsonify({'message': 'Submission flagged for review'}), 200
    except Exception as e:
        print(f"Flag submission error: {str(e)}")
        return jsonify({'error': 'Failed to flag submission for review'}), 500

@app.route('/submissions/<submission_id>', methods=['DELETE'])
def delete_submission(submission_id):
    """
    Delete a specific submission and its associated S3 object + comparison records.
    """
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Find the submission record by submissionId
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('submissionId').eq(submission_id) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION')
        )
        items = response.get('Items', [])
        if not items:
            return jsonify({'error': 'Submission not found'}), 404

        submission = items[0]
        submission_pk = submission['PK']
        submission_sk = submission['SK']
        s3_key = submission.get('s3Key')

        # Delete file from S3
        if s3_key:
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
            except Exception as e:
                print(f"S3 delete error: {str(e)}")

        # Delete comparison records
        comparison_response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('PK').eq(submission_pk) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('COMPARISON')
        )
        for comparison in comparison_response.get('Items', []):
            table.delete_item(Key={'PK': comparison['PK'], 'SK': comparison['SK']})

        # Delete the submission item
        table.delete_item(Key={'PK': submission_pk, 'SK': submission_sk})

        return jsonify({'message': 'Submission deleted successfully'}), 200
    except Exception as e:
        print(f"Delete submission error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': 'Failed to delete submission'}), 500


def extract_text_from_file(s3_key, file_extension):
    """
    Extract text from uploaded file using appropriate method
    """
    try:
        if file_extension == 'txt':
            # Direct text extraction
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            return response['Body'].read().decode('utf-8')

        elif file_extension == 'pdf':
            # Use Textract for PDF files
            response = textract_client.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': BUCKET_NAME,
                        'Name': s3_key
                    }
                }
            )

            job_id = response['JobId']

            # Wait for completion (simplified - in production use async)
            while True:
                status_response = textract_client.get_document_text_detection(JobId=job_id)
                status = status_response['JobStatus']

                if status == 'SUCCEEDED':
                    break
                elif status == 'FAILED':
                    raise Exception('Textract job failed')

                import time
                time.sleep(2)  # Wait before checking again

            # Extract text from results
            text = ''
            for block in status_response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    text += block['Text'] + '\n'

            return text

        else:
            raise Exception(f'Unsupported file type: {file_extension}')

    except Exception as e:
        print(f"Text extraction error: {str(e)}")
        return None

def check_similarity_for_submission(submission_id, course_id, student_id, processed_text, submission_pk, submission_sk):
    """
    Check similarity against other submissions in the same course
    """
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Get all submissions for this course
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('courseId').eq(course_id) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION') &
                           boto3.dynamodb.conditions.Attr('submissionId').ne(submission_id)
        )

        items = response.get('Items', [])
        print(f"Similarity check for submission {submission_id} in course {course_id}: found {len(items)} other submissions")

        max_similarity = Decimal('0.0')
        best_match = None

        for item in items:
            other_text = item.get('processedText', '')
            if other_text:
                similarity = Decimal(str(calculate_similarity(processed_text, other_text)))
                print(f"  compared with {item.get('submissionId')} (student {item.get('studentId')}): similarity={similarity}")
                if similarity > max_similarity:
                    max_similarity = similarity
                    best_match = item

        is_flagged = max_similarity >= Decimal(os.getenv('SIMILARITY_THRESHOLD', '0.60'))
        status_value = 'FLAGGED' if is_flagged else 'COMPLETED'

        # Update submission with similarity score
        update_response = table.update_item(
            Key={
                'PK': submission_pk,
                'SK': submission_sk
            },
            UpdateExpression='SET similarityScore = :score, flagged = :flagged, #status = :status',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':score': max_similarity,
                ':flagged': is_flagged,
                ':status': status_value
            }
        )

        # Store comparison details if similarity is high
        if max_similarity >= Decimal('0.3'):  # Store even lower similarity matches for reference
            comparison_data = {
                'PK': submission_pk,
                'SK': f'COMPARISON#{best_match["submissionId"] if best_match else "none"}#{max_similarity}',
                'entityType': 'COMPARISON',
                'matchedSubmissionId': best_match['submissionId'] if best_match else None,
                'similarityScore': max_similarity,
                'matchedSections': [],  # Would implement detailed section matching
                'createdAt': datetime.now(timezone.utc).isoformat()
            }
            table.put_item(Item=comparison_data)

    except Exception as e:
        print(f"Similarity check error: {str(e)}")

# Lambda handler for AWS deployment
def lambda_handler(event, context):
    # This would be used when deploying to Lambda
    # For local development, we use Flask's development server
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Hello from Lambda!'})
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)