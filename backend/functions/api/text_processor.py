import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
import string

# Download required NLTK data (run once)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

def preprocess_text(text):
    """
    Preprocess text for plagiarism detection:
    - Convert to lowercase
    - Remove punctuation
    - Tokenize
    - Remove stopwords
    - Stem words
    - Remove extra whitespace

    Args:
        text (str): Raw text to preprocess

    Returns:
        str: Preprocessed text
    """
    if not text:
        return ""

    try:
        # Convert to lowercase
        text = text.lower()

        # Remove punctuation
        text = text.translate(str.maketrans('', '', string.punctuation))

        # Remove extra whitespace and newlines
        text = re.sub(r'\s+', ' ', text).strip()

        # Tokenize
        tokens = word_tokenize(text)

        # Remove stopwords
        stop_words = set(stopwords.words('english'))
        tokens = [token for token in tokens if token not in stop_words]

        # Stem words
        stemmer = PorterStemmer()
        tokens = [stemmer.stem(token) for token in tokens]

        # Join back into text
        processed_text = ' '.join(tokens)

        return processed_text

    except Exception as e:
        print(f"Error preprocessing text: {str(e)}")
        return text  # Return original text if preprocessing fails

def extract_ngrams(text, n=3):
    """
    Extract n-grams from text for fingerprinting

    Args:
        text (str): Preprocessed text
        n (int): Size of n-grams

    Returns:
        list: List of n-grams
    """
    if not text:
        return []

    words = text.split()
    ngrams = []

    for i in range(len(words) - n + 1):
        ngram = ' '.join(words[i:i+n])
        ngrams.append(ngram)

    return ngrams

def generate_fingerprint(text, n=3):
    """
    Generate a fingerprint (set of n-grams) for text

    Args:
        text (str): Preprocessed text
        n (int): Size of n-grams

    Returns:
        set: Set of n-grams (fingerprint)
    """
    ngrams = extract_ngrams(text, n)
    return set(ngrams)

def calculate_text_similarity(text1, text2, method='jaccard'):
    """
    Calculate similarity between two texts using different methods

    Args:
        text1 (str): First preprocessed text
        text2 (str): Second preprocessed text
        method (str): Similarity method ('jaccard', 'cosine', 'dice')

    Returns:
        float: Similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0

    if method == 'jaccard':
        return jaccard_similarity(text1, text2)
    elif method == 'cosine':
        return cosine_similarity(text1, text2)
    elif method == 'dice':
        return dice_similarity(text1, text2)
    else:
        return jaccard_similarity(text1, text2)  # Default

def jaccard_similarity(text1, text2, n=3):
    """
    Calculate Jaccard similarity using n-gram fingerprints

    Args:
        text1 (str): First text
        text2 (str): Second text
        n (int): Size of n-grams

    Returns:
        float: Jaccard similarity score
    """
    fingerprint1 = generate_fingerprint(text1, n)
    fingerprint2 = generate_fingerprint(text2, n)

    if not fingerprint1 and not fingerprint2:
        return 1.0  # Both empty texts are identical
    if not fingerprint1 or not fingerprint2:
        return 0.0  # One empty text

    intersection = fingerprint1.intersection(fingerprint2)
    union = fingerprint1.union(fingerprint2)

    return len(intersection) / len(union)

def cosine_similarity(text1, text2):
    """
    Calculate cosine similarity using TF (term frequency)

    Args:
        text1 (str): First text
        text2 (str): Second text

    Returns:
        float: Cosine similarity score
    """
    # Simple TF-based cosine similarity
    words1 = set(text1.split())
    words2 = set(text2.split())

    all_words = words1.union(words2)

    # Create term frequency vectors
    vector1 = [text1.split().count(word) for word in all_words]
    vector2 = [text2.split().count(word) for word in all_words]

    # Calculate dot product
    dot_product = sum(a * b for a, b in zip(vector1, vector2))

    # Calculate magnitudes
    magnitude1 = sum(a * a for a in vector1) ** 0.5
    magnitude2 = sum(b * b for b in vector2) ** 0.5

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)

def dice_similarity(text1, text2, n=3):
    """
    Calculate Dice similarity coefficient

    Args:
        text1 (str): First text
        text2 (str): Second text
        n (int): Size of n-grams

    Returns:
        float: Dice similarity score
    """
    fingerprint1 = generate_fingerprint(text1, n)
    fingerprint2 = generate_fingerprint(text2, n)

    if not fingerprint1 and not fingerprint2:
        return 1.0
    if not fingerprint1 or not fingerprint2:
        return 0.0

    intersection = fingerprint1.intersection(fingerprint2)

    return 2 * len(intersection) / (len(fingerprint1) + len(fingerprint2))

def find_similar_sections(text1, text2, min_length=10):
    """
    Find similar sections between two texts

    Args:
        text1 (str): First text
        text2 (str): Second text
        min_length (int): Minimum length of similar sections

    Returns:
        list: List of similar sections with positions
    """
    # This is a simplified implementation
    # In a production system, you'd use more sophisticated algorithms
    # like diff algorithms or longest common subsequence

    words1 = text1.split()
    words2 = text2.split()

    similar_sections = []

    # Simple sliding window approach
    window_size = min_length

    for i in range(len(words1) - window_size + 1):
        window1 = ' '.join(words1[i:i+window_size])

        for j in range(len(words2) - window_size + 1):
            window2 = ' '.join(words2[j:j+window_size])

            if window1 == window2 and len(window1.strip()) > 0:
                similar_sections.append({
                    'text': window1,
                    'position1': i,
                    'position2': j,
                    'length': window_size
                })

    return similar_sections