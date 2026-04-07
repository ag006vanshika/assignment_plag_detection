import json
import boto3
import os
from datetime import datetime
from plagiarism_engine import generate_plagiarism_report
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# AWS clients
dynamodb = boto3.resource('dynamodb')

# Configuration
TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME')

def lambda_handler(event, context):
    """
    Lambda function for performing plagiarism similarity checks
    Can be triggered by API Gateway or Step Functions
    """
    try:
        print(f"Received event: {json.dumps(event)}")

        # Handle different event sources
        if 'body' in event:
            # API Gateway event
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            submission_id = body.get('submissionId')
            course_id = body.get('courseId')
        else:
            # Direct Lambda invocation
            submission_id = event.get('submissionId')
            course_id = event.get('courseId')

        if not submission_id or not course_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing submissionId or courseId'})
            }

        print(f"Checking similarity for submission {submission_id} in course {course_id}")

        # Perform similarity check
        result = perform_similarity_check(submission_id, course_id)

        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        print(f"Error in similarity handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def perform_similarity_check(submission_id, course_id):
    """
    Perform comprehensive similarity check for a submission

    Args:
        submission_id (str): Submission to check
        course_id (str): Course context

    Returns:
        dict: Similarity check results
    """
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Get the target submission
        submission_response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('PK').eq(f'SUBMISSION#{course_id}#*#{submission_id}'),
            FilterExpression=boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION')
        )

        if not submission_response.get('Items'):
            return {
                'error': f'Submission {submission_id} not found',
                'submission_id': submission_id,
                'course_id': course_id
            }

        target_submission = submission_response['Items'][0]

        # Get all other submissions in the course
        all_submissions_response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('courseId').eq(course_id) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION') &
                           boto3.dynamodb.conditions.Attr('submissionId').ne(submission_id)
        )

        existing_submissions = all_submissions_response.get('Items', [])

        # Generate comprehensive plagiarism report
        report = generate_plagiarism_report(target_submission, existing_submissions, course_id)

        # Update the submission with results
        table.update_item(
            Key={
                'PK': target_submission['PK'],
                'SK': target_submission['SK']
            },
            UpdateExpression='SET similarityScore = :score, flagged = :flagged, status = :status, lastChecked = :checked',
            ExpressionAttributeValues={
                ':score': report['max_similarity'],
                ':flagged': report['is_plagiarism'],
                ':status': 'COMPLETED',
                ':checked': datetime.utcnow().isoformat()
            }
        )

        # Store detailed comparison results
        for flagged_source in report.get('flagged_sources', []):
            comparison_data = {
                'PK': target_submission['PK'],
                'SK': f'COMPARISON#{flagged_source["submission_id"]}#{flagged_source["similarity_score"]}',
                'entityType': 'COMPARISON',
                'matchedSubmissionId': flagged_source['submission_id'],
                'similarityScore': flagged_source['similarity_score'],
                'matchedSections': flagged_source.get('similar_sections', []),
                'createdAt': datetime.utcnow().isoformat()
            }
            table.put_item(Item=comparison_data)

        return report

    except Exception as e:
        print(f"Error performing similarity check: {str(e)}")
        return {
            'error': str(e),
            'submission_id': submission_id,
            'course_id': course_id
        }

def batch_similarity_check(event, context):
    """
    Lambda function for batch processing multiple submissions
    Useful for re-checking all submissions when new ones are added
    """
    try:
        course_id = event.get('courseId')
        if not course_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing courseId'})
            }

        table = dynamodb.Table(TABLE_NAME)

        # Get all submissions for the course
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('courseId').eq(course_id) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION')
        )

        submissions = response.get('Items', [])
        processed_count = 0
        flagged_count = 0

        # Process each submission
        for submission in submissions:
            if submission.get('processedText'):
                # Re-run similarity check
                result = perform_similarity_check(submission['submissionId'], course_id)
                if result.get('is_plagiarism'):
                    flagged_count += 1
                processed_count += 1

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Batch processing completed for course {course_id}',
                'total_submissions': len(submissions),
                'processed_count': processed_count,
                'flagged_count': flagged_count
            })
        }

    except Exception as e:
        print(f"Error in batch similarity check: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_similarity_stats(event, context):
    """
    Lambda function to get similarity statistics for a course
    """
    try:
        course_id = event.get('courseId')
        if not course_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing courseId'})
            }

        table = dynamodb.Table(TABLE_NAME)

        # Get all submissions for the course
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('courseId').eq(course_id) &
                           boto3.dynamodb.conditions.Attr('entityType').eq('SUBMISSION')
        )

        submissions = response.get('Items', [])

        if not submissions:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'course_id': course_id,
                    'total_submissions': 0,
                    'stats': {}
                })
            }

        # Calculate statistics
        similarity_scores = [s.get('similarityScore', 0.0) for s in submissions]
        flagged_count = sum(1 for s in submissions if s.get('flagged', False))

        stats = {
            'total_submissions': len(submissions),
            'flagged_submissions': flagged_count,
            'flagged_percentage': (flagged_count / len(submissions)) * 100 if submissions else 0,
            'average_similarity': sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0,
            'max_similarity': max(similarity_scores) if similarity_scores else 0,
            'min_similarity': min(similarity_scores) if similarity_scores else 0,
            'similarity_distribution': {
                'high': len([s for s in similarity_scores if s >= 0.80]),
                'medium': len([s for s in similarity_scores if 0.60 <= s < 0.80]),
                'low': len([s for s in similarity_scores if 0.30 <= s < 0.60]),
                'none': len([s for s in similarity_scores if s < 0.30])
            }
        }

        return {
            'statusCode': 200,
            'body': json.dumps({
                'course_id': course_id,
                'stats': stats
            })
        }

    except Exception as e:
        print(f"Error getting similarity stats: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

# For local testing
if __name__ == '__main__':
    # Test the similarity check
    test_event = {
        'submissionId': 'test-submission-123',
        'courseId': 'test-course-123'
    }

    result = lambda_handler(test_event, None)
    print(f"Test result: {result}")