import json
import boto3
import os
from datetime import datetime
from text_processor import preprocess_text
from plagiarism_engine import check_plagiarism
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
textract_client = boto3.client('textract')

# Configuration
BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME')

def lambda_handler(event, context):
    """
    Lambda function triggered by S3 upload events
    Processes uploaded files for plagiarism detection
    """
    try:
        print(f"Received event: {json.dumps(event)}")

        # Process each S3 event record
        for record in event.get('Records', []):
            if record.get('eventName', '').startswith('ObjectCreated'):
                # Extract bucket and key from the event
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']

                print(f"Processing file: s3://{bucket}/{key}")

                # Process the uploaded file
                result = process_uploaded_file(bucket, key)

                if result['success']:
                    print(f"Successfully processed {key}")
                else:
                    print(f"Failed to process {key}: {result.get('error', 'Unknown error')}")
                    # In production, you might want to send this to a DLQ or notification service

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Processing completed'})
        }

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def process_uploaded_file(bucket, key):
    """
    Process an uploaded file: extract text, preprocess, check for plagiarism

    Args:
        bucket (str): S3 bucket name
        key (str): S3 object key

    Returns:
        dict: Processing result
    """
    try:
        # Extract metadata from key
        # Expected key format: uploads/courseId/studentId/submissionId/filename
        key_parts = key.split('/')
        if len(key_parts) < 5 or key_parts[0] != 'uploads':
            return {
                'success': False,
                'error': f'Invalid key format: {key}. Expected: uploads/courseId/studentId/submissionId/filename'
            }

        course_id = key_parts[1]
        student_id = key_parts[2]
        submission_id = key_parts[3]
        filename = '/'.join(key_parts[4:])

        print(f"Extracted metadata - Course: {course_id}, Student: {student_id}, Submission: {submission_id}")

        # Determine file type
        file_extension = get_file_extension(filename)
        if not file_extension:
            return {
                'success': False,
                'error': f'Could not determine file extension for {filename}'
            }

        # Extract text from file
        extracted_text = extract_text_from_s3_file(bucket, key, file_extension)
        if not extracted_text:
            return {
                'success': False,
                'error': 'Failed to extract text from file'
            }

        # Preprocess text
        processed_text = preprocess_text(extracted_text)

        # Store initial submission data in DynamoDB
        table = dynamodb.Table(TABLE_NAME)

        submission_data = {
            'PK': f'SUBMISSION#{course_id}#{student_id}#{submission_id}',
            'SK': f'METADATA#{datetime.utcnow().isoformat()}',
            'GSI1PK': f'STUDENT#{student_id}',
            'GSI1SK': datetime.utcnow().isoformat(),
            'entityType': 'SUBMISSION',
            'submissionId': submission_id,
            'studentId': student_id,
            'courseId': course_id,
            'fileName': filename,
            's3Key': key,
            'extractedText': extracted_text,
            'processedText': processed_text,
            'status': 'PROCESSED',
            'createdAt': datetime.utcnow().isoformat(),
            'similarityScore': 0.0,
            'flagged': False
        }

        table.put_item(Item=submission_data)

        # Perform plagiarism check
        plagiarism_result = perform_plagiarism_check(course_id, student_id, submission_id, processed_text)

        # Update submission with plagiarism results
        update_data = {
            'similarityScore': plagiarism_result['max_similarity'],
            'flagged': plagiarism_result['is_plagiarism'],
            'status': 'COMPLETED'
        }

        table.update_item(
            Key={
                'PK': submission_data['PK'],
                'SK': submission_data['SK']
            },
            UpdateExpression='SET similarityScore = :score, flagged = :flagged, status = :status',
            ExpressionAttributeValues={
                ':score': update_data['similarityScore'],
                ':flagged': update_data['flagged'],
                ':status': update_data['status']
            }
        )

        # Store detailed comparison results
        if plagiarism_result['flagged_sources']:
            for flagged_source in plagiarism_result['flagged_sources']:
                comparison_data = {
                    'PK': submission_data['PK'],
                    'SK': f'COMPARISON#{flagged_source["submission_id"]}#{flagged_source["similarity_score"]}',
                    'entityType': 'COMPARISON',
                    'matchedSubmissionId': flagged_source['submission_id'],
                    'similarityScore': flagged_source['similarity_score'],
                    'matchedSections': flagged_source.get('similar_sections', []),
                    'createdAt': datetime.utcnow().isoformat()
                }
                table.put_item(Item=comparison_data)

        return {
            'success': True,
            'submission_id': submission_id,
            'similarity_score': plagiarism_result['max_similarity'],
            'is_plagiarism': plagiarism_result['is_plagiarism']
        }

    except Exception as e:
        print(f"Error processing file {key}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def extract_text_from_s3_file(bucket, key, file_extension):
    """
    Extract text from file stored in S3

    Args:
        bucket (str): S3 bucket name
        key (str): S3 object key
        file_extension (str): File extension (pdf, doc, docx, txt)

    Returns:
        str: Extracted text or None if failed
    """
    try:
        if file_extension == 'txt':
            # Direct text extraction for TXT files
            response = s3_client.get_object(Bucket=bucket, Key=key)
            text = response['Body'].read().decode('utf-8')
            return text

        elif file_extension in ['pdf', 'doc', 'docx']:
            # Use AWS Textract for PDF and Office documents
            textract_response = textract_client.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                }
            )

            job_id = textract_response['JobId']
            print(f"Started Textract job: {job_id}")

            # Poll for completion (simplified - in production use Step Functions)
            max_attempts = 30  # 5 minutes max
            attempt = 0

            while attempt < max_attempts:
                status_response = textract_client.get_document_text_detection(JobId=job_id)
                status = status_response['JobStatus']

                if status == 'SUCCEEDED':
                    # Extract text from blocks
                    text = ''
                    for block in status_response.get('Blocks', []):
                        if block['BlockType'] == 'LINE':
                            text += block['Text'] + '\n'
                    return text.strip()

                elif status == 'FAILED':
                    error_message = status_response.get('StatusMessage', 'Textract job failed')
                    print(f"Textract job failed: {error_message}")
                    return None

                attempt += 1
                import time
                time.sleep(10)  # Wait 10 seconds before checking again

            print(f"Textract job {job_id} timed out")
            return None

        else:
            print(f"Unsupported file extension: {file_extension}")
            return None

    except Exception as e:
        print(f"Error extracting text from {key}: {str(e)}")
        return None

def perform_plagiarism_check(course_id, student_id, submission_id, processed_text):
    """
    Perform plagiarism check against existing submissions

    Args:
        course_id (str): Course identifier
        student_id (str): Student identifier
        submission_id (str): Submission identifier
        processed_text (str): Preprocessed text to check

    Returns:
        dict: Plagiarism check results
    """
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Get all processed submissions for this course (excluding current submission)
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('courseId').eq(course_id) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION') &
                           boto3.dynamodb.conditions.Attr('status').eq('COMPLETED') &
                           boto3.dynamodb.conditions.Attr('submissionId').ne(submission_id)
        )

        existing_texts = []
        for item in response.get('Items', []):
            if item.get('processedText'):
                existing_texts.append({
                    'id': item['submissionId'],
                    'text': item['processedText']
                })

        if not existing_texts:
            return {
                'is_plagiarism': False,
                'max_similarity': 0.0,
                'flagged_sources': [],
                'total_comparisons': 0
            }

        # Perform plagiarism check
        texts_only = [item['text'] for item in existing_texts]
        result = check_plagiarism(processed_text, texts_only)

        # Add submission IDs back to flagged sources
        for flagged in result['flagged_sources']:
            source_index = flagged['source_index']
            flagged['submission_id'] = existing_texts[source_index]['id']

        result['total_comparisons'] = len(existing_texts)
        return result

    except Exception as e:
        print(f"Error performing plagiarism check: {str(e)}")
        return {
            'is_plagiarism': False,
            'max_similarity': 0.0,
            'flagged_sources': [],
            'total_comparisons': 0,
            'error': str(e)
        }

def get_file_extension(filename):
    """
    Extract file extension from filename

    Args:
        filename (str): Filename

    Returns:
        str: File extension (lowercase) or None
    """
    if '.' not in filename:
        return None

    extension = filename.rsplit('.', 1)[1].lower()

    # Normalize extensions
    if extension in ['docx']:
        return 'docx'
    elif extension in ['doc']:
        return 'doc'
    elif extension in ['pdf']:
        return 'pdf'
    elif extension in ['txt']:
        return 'txt'
    else:
        return None

# For local testing
if __name__ == '__main__':
    # Test the handler with a mock event
    mock_event = {
        'Records': [{
            'eventName': 'ObjectCreated:Put',
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'uploads/course123/student123/sub123/test.txt'}
            }
        }]
    }

    result = lambda_handler(mock_event, None)
    print(f"Test result: {result}")