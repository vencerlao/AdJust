"""
AdJust Bias Detection API
Integrates Random Forest for bias classification
"""
import os
import json
import pickle
import numpy as np
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load configuration
config_path = os.path.join(os.path.dirname(__file__), 'models', 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

# Load model artifacts
model_dir = os.path.join(os.path.dirname(__file__), 'models')
with open(os.path.join(model_dir, 'label_encoder.pkl'), 'rb') as f:
    label_encoder = pickle.load(f)

with open(os.path.join(model_dir, 'random_forest.pkl'), 'rb') as f:
    rf_model = pickle.load(f)

# Try to load transformers for RoBERTa embeddings
try:
    from transformers import RobertaTokenizer, RobertaModel
    import torch

    tokenizer = RobertaTokenizer.from_pretrained(config['roberta_model'])
    roberta_model = RobertaModel.from_pretrained(config['roberta_model'])
    roberta_model.eval()
    ROBERTA_LOADED = True
    print("✓ RoBERTa loaded successfully")
except Exception as e:
    ROBERTA_LOADED = False
    print(f"⚠ RoBERTa not available: {e}")
    print("  Using TF-IDF fallback for embeddings")


def get_embeddings(text, max_length=256):
    """Generate embeddings using RoBERTa if available, else TF-IDF."""
    if ROBERTA_LOADED:
        try:
            import torch
            with torch.no_grad():
                inputs = tokenizer(
                    text,
                    max_length=max_length,
                    padding='max_length',
                    truncation=True,
                    return_tensors='pt'
                )
                outputs = roberta_model(**inputs)
                embeddings = outputs.last_hidden_state[:, 0, :].numpy().flatten()

            if len(embeddings) < 770:
                embeddings = np.pad(embeddings, (0, 770 - len(embeddings)), 'constant')
            elif len(embeddings) > 770:
                embeddings = embeddings[:770]

            return embeddings
        except Exception as e:
            print(f"Error generating RoBERTa embeddings: {e}")
            return _generate_tfidf_embeddings(text)
    else:
        return _generate_tfidf_embeddings(text)


def _generate_tfidf_embeddings(text, dim=770):
    """TF-IDF fallback — pads to 770 dims to match RF model input."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(max_features=100, lowercase=True)
    try:
        embedding = vectorizer.fit_transform([text]).toarray()[0]
    except Exception:
        embedding = np.zeros(100)

    if len(embedding) < dim:
        embedding = np.pad(embedding, (0, dim - len(embedding)), 'constant')
    else:
        embedding = embedding[:dim]

    return embedding.flatten()


# ---------------------------------------------------------------------------
# Gender-coded keyword lists
# Sources: Gaucher et al. (2011), Textio gender tone research,
#          Ongley (2016) masculine/feminine word banks, and
#          common patterns observed in Philippine job advertisements.
# ---------------------------------------------------------------------------

_FEMININE_KEYWORDS = [
    # Pronouns / explicit gendered references
    "she", "her", "girl", "woman", "women", "female", "mother", "lady", "gal",
    # Stereotypically feminine job titles
    "nurse", "secretary", "receptionist", "housekeeper", "caregiver",
    "nanny", "midwife", "stewardess",
    # Appearance
    "beautiful", "pretty", "attractive", "gorgeous", "lovely", "presentable",
    # Communal / relational traits (Gaucher et al.)
    "emotional", "sensitive", "nurturing", "caring", "compassionate",
    "empathetic", "empathy", "understanding", "patient", "warm", "kind",
    "gentle", "loyal", "supportive", "cheerful", "pleasant", "friendly",
    "tactful", "intuitive", "enthusiastic", "passionate",
    "dedicated", "committed", "commitment", "trustworthy", "honest",
    "humble", "sincere", "cooperative", "accommodating", "helpful",
    # Collaboration / communication language
    "collaborate", "collaboration", "collaborative", "communicate",
    "communication", "interpersonal", "team player", "teamwork",
    "community", "relationship", "networking", "social", "connect",
    "connection", "inclusive", "inclusion", "diversity", "belonging",
    "together", "collective", "harmony", "consensus",
    # Organisational / support traits
    "organized", "organised", "detail-oriented", "attention to detail",
    "flexible", "adaptable", "multitask", "multitasking",
    "responsive", "responsible", "reliable", "dependable",
    # Empowerment / positive culture language
    "empower", "empowered", "empowerment", "celebrate", "encourage",
    "respect", "contribution", "contribute", "positive",
    "support", "mentor", "mentoring", "service",
]

_MASCULINE_KEYWORDS = [
    # Pronouns / explicit gendered references
    "he", "him", "boy", "man", "men", "male", "gentleman", "guy", "bloke", "father",
    # Agentic / assertive traits (Gaucher et al.)
    "aggressive", "assertive", "competitive", "ambitious", "driven",
    "dominant", "commanding", "forceful", "authoritative", "bold",
    "confident", "fearless", "tough", "strong", "robust", "powerful",
    "independent", "decisive", "determined", "persistent",
    # Analytical / technical traits
    "logical", "analytical", "analysis", "strategic", "strategy",
    "technical", "expert", "master", "intelligent", "brilliant",
    "sharp", "clever", "smart", "skilled", "experienced",
    "proficient", "proficiency", "excellent", "superior", "outstanding",
    # Leadership / hierarchy language
    "lead", "leader", "leadership", "manage", "management", "manager",
    "executive", "director", "senior", "officer", "supervisor",
    "head", "chief", "principal", "superintendent", "coordinator",
    "oversee", "administer", "administration", "administrative",
    "operations", "operational", "authority",
    # Performance / achievement language
    "achieve", "achievement", "perform", "performance", "deliver",
    "results", "target", "objective", "goal-oriented",
    "drive", "pioneer", "champion", "spearhead", "execute",
    "exceed", "outperform", "maximize", "optimise", "optimize",
    # Self-reliant / individual-focus language
    "self-starter", "self-motivated", "entrepreneurial",
    "ninja", "rockstar", "guru", "wizard",
    # High-pressure language
    "complex", "fast-paced", "demanding", "rigorous", "challenging",
    # Technical/engineering stereotypes
    "engineer", "developer", "architect", "programmer",
    "analyst", "scientist", "technician",
]


def extract_flagged_phrases(text: str) -> dict:
    """
    Extract gender-coded words from text.

    Matching strategy:
    - Multi-word phrases: substring search (the phrase itself prevents false positives).
    - Single words ending in common inflection suffixes: substring search so that
      e.g. "manage" catches "management", "manages", "managing".
    - All other single words: word-boundary regex to avoid partial hits
      (e.g. "her" should not match "here" or "other").

    Returns:
        {"masculine": ["word1", ...], "feminine": ["word1", ...]}
        Both lists are sorted and deduplicated.
    """
    # Normalise the text once
    text_lower = text.lower()
    # Normalise smart quotes / curly apostrophes that survive copy-paste
    text_lower = (
        text_lower
        .replace('\u2019', "'").replace('\u2018', "'")
        .replace('\u2013', '-').replace('\u2014', '-')
    )

    def _matches(keyword: str) -> bool:
        # Multi-word phrase — plain substring is safe
        if ' ' in keyword:
            return keyword in text_lower
        # Root words that inflect by adding suffixes — use substring so
        # "manage" catches "management" / "managing" / "manages"
        if keyword.endswith(('e', 'al', 'ion', 'ive', 'ment', 'ence', 'ance')):
            return keyword in text_lower
        # Default: whole-word boundary match
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text_lower))

    masculine = sorted({kw for kw in _MASCULINE_KEYWORDS if _matches(kw)})
    feminine  = sorted({kw for kw in _FEMININE_KEYWORDS  if _matches(kw)})

    return {'masculine': masculine, 'feminine': feminine}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'model': config.get('label_status', 'baseline'),
        'classes': config.get('classes', []),
    })


@app.route('/detect', methods=['POST'])
def detect_bias():
    """
    Single-text bias detection.

    Request:  { "text": "..." }
    Response: {
        "detected_class": "male_biased"|"female_biased"|"neutral",
        "confidence_scores": {"male_biased": 0.0, "female_biased": 0.0, "neutral": 0.0},
        "flagged_phrases": {"masculine": [...], "feminine": [...]},
        "accuracy_note": "..."
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'text field is required'}), 400

        embeddings = get_embeddings(text, max_length=config['max_length'])

        predicted_class_idx = rf_model.predict([embeddings])[0]
        predicted_class = label_encoder.inverse_transform([predicted_class_idx])[0]

        probabilities = rf_model.predict_proba([embeddings])[0]
        confidence_scores = {
            label_encoder.inverse_transform([i])[0]: float(prob)
            for i, prob in enumerate(probabilities)
        }

        flagged_phrases = extract_flagged_phrases(text)

        return jsonify({
            'detected_class': predicted_class,
            'confidence_scores': confidence_scores,
            'flagged_phrases': flagged_phrases,
            'accuracy_note': f"Baseline model accuracy: {config.get('accuracy', 'n/a')}%",
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/batch-detect', methods=['POST'])
def batch_detect():
    """
    Batch bias detection.

    Request:  { "texts": ["text1", "text2", ...] }
    Response: { "results": [ <detect response>, ... ] }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        texts = data.get('texts', [])
        if not texts or not isinstance(texts, list):
            return jsonify({'error': 'texts array is required'}), 400

        results = []
        for text in texts:
            text = text.strip()
            if not text:
                continue

            embeddings = get_embeddings(text, max_length=config['max_length'])
            predicted_class_idx = rf_model.predict([embeddings])[0]
            predicted_class = label_encoder.inverse_transform([predicted_class_idx])[0]

            probabilities = rf_model.predict_proba([embeddings])[0]
            confidence_scores = {
                label_encoder.inverse_transform([i])[0]: float(prob)
                for i, prob in enumerate(probabilities)
            }

            flagged_phrases = extract_flagged_phrases(text)

            results.append({
                'text': text,
                'detected_class': predicted_class,
                'confidence_scores': confidence_scores,
                'flagged_phrases': flagged_phrases,
            })

        return jsonify({'results': results}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)