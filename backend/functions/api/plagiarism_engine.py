from text_processor import (
    preprocess_text,
    calculate_text_similarity,
    jaccard_similarity,
    cosine_similarity,
    dice_similarity,
    find_similar_sections
)
import os

def calculate_similarity(text1, text2, method='jaccard'):
    """
    Main function to calculate similarity between two texts

    Args:
        text1 (str): First text (raw or preprocessed)
        text2 (str): Second text (raw or preprocessed)
        method (str): Similarity method to use

    Returns:
        float: Similarity score between 0 and 1
    """
    # Preprocess texts if they appear to be raw text
    if _is_raw_text(text1):
        text1 = preprocess_text(text1)
    if _is_raw_text(text2):
        text2 = preprocess_text(text2)

    return calculate_text_similarity(text1, text2, method)

def check_plagiarism(new_text, existing_texts, threshold=0.60):
    """
    Check if new text plagiarizes from existing texts

    Args:
        new_text (str): New text to check
        existing_texts (list): List of existing texts
        threshold (float): Similarity threshold for flagging

    Returns:
        dict: Plagiarism check results
    """
    if not existing_texts:
        return {
            'is_plagiarism': False,
            'max_similarity': 0.0,
            'flagged_sources': [],
            'details': []
        }

    max_similarity = 0.0
    flagged_sources = []
    details = []

    processed_new = preprocess_text(new_text) if _is_raw_text(new_text) else new_text

    for i, existing_text in enumerate(existing_texts):
        processed_existing = preprocess_text(existing_text) if _is_raw_text(existing_text) else existing_text

        similarity = calculate_similarity(processed_new, processed_existing)

        details.append({
            'source_index': i,
            'similarity_score': similarity,
            'method_used': 'jaccard'
        })

        if similarity > max_similarity:
            max_similarity = similarity

        if similarity >= threshold:
            flagged_sources.append({
                'source_index': i,
                'similarity_score': similarity,
                'similar_sections': find_similar_sections(processed_new, processed_existing)
            })

    return {
        'is_plagiarism': len(flagged_sources) > 0,
        'max_similarity': max_similarity,
        'flagged_sources': flagged_sources,
        'details': details,
        'threshold_used': threshold
    }

def batch_similarity_check(new_text, existing_submissions, threshold=None):
    """
    Check similarity against multiple existing submissions

    Args:
        new_text (str): New text to check
        existing_submissions (list): List of dicts with 'text' and 'id' keys
        threshold (float): Similarity threshold (uses env var if None)

    Returns:
        dict: Batch similarity results
    """
    if threshold is None:
        threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.60'))

    existing_texts = [sub['text'] for sub in existing_submissions]

    results = check_plagiarism(new_text, existing_texts, threshold)

    # Add submission IDs to results
    for flagged in results['flagged_sources']:
        source_index = flagged['source_index']
        flagged['submission_id'] = existing_submissions[source_index]['id']

    return results

def compare_documents(doc1, doc2, methods=['jaccard', 'cosine', 'dice']):
    """
    Compare two documents using multiple similarity methods

    Args:
        doc1 (str): First document text
        doc2 (str): Second document text
        methods (list): List of similarity methods to use

    Returns:
        dict: Comparison results for each method
    """
    results = {}

    for method in methods:
        similarity = calculate_similarity(doc1, doc2, method)
        results[method] = {
            'similarity_score': similarity,
            'is_similar': similarity >= 0.60  # Default threshold
        }

    # Add aggregate score (average of all methods)
    scores = [results[method]['similarity_score'] for method in methods]
    results['aggregate'] = {
        'similarity_score': sum(scores) / len(scores),
        'is_similar': any(results[method]['is_similar'] for method in methods)
    }

    return results

def generate_plagiarism_report(new_submission, existing_submissions, course_id):
    """
    Generate a comprehensive plagiarism report

    Args:
        new_submission (dict): New submission data
        existing_submissions (list): List of existing submissions
        course_id (str): Course identifier

    Returns:
        dict: Comprehensive plagiarism report
    """
    new_text = new_submission.get('processedText', new_submission.get('extractedText', ''))

    if not new_text:
        return {
            'error': 'No text available for plagiarism check',
            'submission_id': new_submission.get('submissionId'),
            'course_id': course_id
        }

    # Filter existing submissions to same course
    course_submissions = [
        sub for sub in existing_submissions
        if sub.get('courseId') == course_id and sub.get('submissionId') != new_submission.get('submissionId')
    ]

    if not course_submissions:
        return {
            'submission_id': new_submission.get('submissionId'),
            'course_id': course_id,
            'total_comparisons': 0,
            'max_similarity': 0.0,
            'is_plagiarism': False,
            'flagged_sources': [],
            'recommendation': 'No previous submissions to compare against'
        }

    # Perform similarity check
    similarity_results = batch_similarity_check(new_text, course_submissions)

    # Generate recommendations
    recommendation = _generate_recommendation(similarity_results)

    report = {
        'submission_id': new_submission.get('submissionId'),
        'student_id': new_submission.get('studentId'),
        'course_id': course_id,
        'total_comparisons': len(course_submissions),
        'max_similarity': similarity_results['max_similarity'],
        'is_plagiarism': similarity_results['is_plagiarism'],
        'flagged_sources': similarity_results['flagged_sources'],
        'similarity_details': similarity_results['details'],
        'recommendation': recommendation,
        'generated_at': '2024-01-01T00:00:00Z',  # Would use datetime.utcnow()
        'threshold_used': similarity_results['threshold_used']
    }

    return report

def _is_raw_text(text):
    """
    Determine if text appears to be raw (unprocessed) text

    Args:
        text (str): Text to check

    Returns:
        bool: True if text appears raw, False if preprocessed
    """
    if not text:
        return True

    # Raw text typically has:
    # - Mixed case
    # - Punctuation
    # - Stopwords
    # - Longer words (not stemmed)

    has_uppercase = any(c.isupper() for c in text)
    has_punctuation = any(c in '.,!?;:' for c in text)
    words = text.split()
    has_stopwords = any(word.lower() in ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'] for word in words)

    # Preprocessed text is typically all lowercase, no punctuation, no stopwords, stemmed words
    return has_uppercase or has_punctuation or has_stopwords

def _generate_recommendation(similarity_results):
    """
    Generate human-readable recommendation based on similarity results
    """
    max_similarity = similarity_results['max_similarity']
    is_plagiarism = similarity_results['is_plagiarism']

    if max_similarity == 0:
        return "No significant similarity detected. Assignment appears original."

    if not is_plagiarism:
        return "Low similarity detected; no plagiarism flag."

    if max_similarity >= 0.90:
        return "High similarity detected; potential plagiarism."
    elif max_similarity >= 0.80:
        return "Moderate similarity detected; review recommended."
    elif max_similarity >= 0.70:
        return "Low similarity detected; no plagiarism flag."
    else:
        return "Low similarity detected; no plagiarism flag."
# Utility functions for advanced plagiarism detection

def detect_section_plagiarism(text1, text2, min_section_length=50):
    """
    Detect plagiarism at the section level (longer passages)

    Args:
        text1 (str): First text
        text2 (str): Second text
        min_section_length (int): Minimum characters for a section

    Returns:
        list: List of plagiarized sections
    """
    # This is a simplified implementation
    # Production systems would use more sophisticated algorithms

    sections1 = _split_into_sections(text1, min_section_length)
    sections2 = _split_into_sections(text2, min_section_length)

    plagiarized_sections = []

    for i, section1 in enumerate(sections1):
        for j, section2 in enumerate(sections2):
            similarity = calculate_similarity(section1, section2)
            if similarity >= 0.80:  # High threshold for section matching
                plagiarized_sections.append({
                    'section1_index': i,
                    'section2_index': j,
                    'similarity': similarity,
                    'text1': section1[:200] + '...' if len(section1) > 200 else section1,
                    'text2': section2[:200] + '...' if len(section2) > 200 else section2
                })

    return plagiarized_sections

def _split_into_sections(text, min_length=50):
    """
    Split text into logical sections

    Args:
        text (str): Text to split
        min_length (int): Minimum section length

    Returns:
        list: List of text sections
    """
    # Simple sentence-based splitting
    sentences = text.split('.')
    sections = []
    current_section = ""

    for sentence in sentences:
        current_section += sentence + "."
        if len(current_section) >= min_length:
            sections.append(current_section.strip())
            current_section = ""

    if current_section:
        sections.append(current_section.strip())

    return sections

def calculate_overall_plagiarism_score(text, sources, weights=None):
    """
    Calculate overall plagiarism score considering multiple sources

    Args:
        text (str): Text to check
        sources (list): List of source texts
        weights (dict): Weights for different factors

    Returns:
        dict: Overall plagiarism assessment
    """
    if weights is None:
        weights = {
            'max_similarity': 0.5,
            'average_similarity': 0.3,
            'source_count': 0.2
        }

    if not sources:
        return {
            'overall_score': 0.0,
            'confidence': 'high',
            'assessment': 'original'
        }

    similarities = [calculate_similarity(text, source) for source in sources]
    max_sim = max(similarities)
    avg_sim = sum(similarities) / len(similarities)
    source_count_factor = min(len(similarities) / 10, 1.0)  # Normalize source count

    overall_score = (
        weights['max_similarity'] * max_sim +
        weights['average_similarity'] * avg_sim +
        weights['source_count'] * source_count_factor
    )

    # Determine confidence and assessment
    if overall_score >= 0.80:
        confidence = 'high'
        assessment = 'high_plagiarism'
    elif overall_score >= 0.60:
        confidence = 'medium'
        assessment = 'moderate_plagiarism'
    elif overall_score >= 0.30:
        confidence = 'low'
        assessment = 'possible_plagiarism'
    else:
        confidence = 'high'
        assessment = 'original'

    return {
        'overall_score': overall_score,
        'max_similarity': max_sim,
        'average_similarity': avg_sim,
        'sources_analyzed': len(sources),
        'confidence': confidence,
        'assessment': assessment,
        'similarity_distribution': {
            'high': len([s for s in similarities if s >= 0.80]),
            'medium': len([s for s in similarities if 0.60 <= s < 0.80]),
            'low': len([s for s in similarities if 0.30 <= s < 0.60]),
            'none': len([s for s in similarities if s < 0.30])
        }
    }