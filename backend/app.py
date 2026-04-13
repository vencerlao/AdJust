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
from dotenv import load_dotenv
from groq import Groq

app = Flask(__name__)
CORS(app)

# Load environment variables from .env file
load_dotenv()

# Initialize Groq client for suggestion generation
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

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
    text_lower = text.lower()
    text_lower = (
        text_lower
        .replace('\u2019', "'").replace('\u2018', "'")
        .replace('\u2013', '-').replace('\u2014', '-')
    )

    def _matches(keyword: str) -> bool:
        if ' ' in keyword:
            return keyword in text_lower
        if keyword.endswith(('e', 'al', 'ion', 'ive', 'ment', 'ence', 'ance')):
            return keyword in text_lower
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text_lower))

    masculine = sorted({kw for kw in _MASCULINE_KEYWORDS if _matches(kw)})
    feminine  = sorted({kw for kw in _FEMININE_KEYWORDS  if _matches(kw)})

    return {'masculine': masculine, 'feminine': feminine}


# ---------------------------------------------------------------------------
# Job-ad context summariser
# ---------------------------------------------------------------------------

def summarise_job_ad_context(full_text: str) -> str:
    """
    Use Groq to extract a compact structural summary of the job ad.

    This summary — not the raw full text — is injected into every /suggest
    prompt so Groq understands role, industry, tone, and register without
    exceeding token limits.

    Returns a plain-text summary string, or an empty string on failure.
    """
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a job advertisement analyst. "
                        "Read the job advertisement and return a SHORT structured summary "
                        "covering ONLY these five points, each on its own line:\n"
                        "1. Job title\n"
                        "2. Industry / sector\n"
                        "3. Key responsibilities (max 10 words)\n"
                        "4. Tone (e.g. formal, casual, corporate, startup)\n"
                        "5. Any specific audience signals (e.g. fresh grad, senior, technical)\n\n"
                        "Return ONLY these five lines. No extra commentary."
                    )
                },
                {
                    "role": "user",
                    "content": full_text[:3000]   # cap at ~3 000 chars to stay within token budget
                }
            ],
            max_tokens=120,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[summarise_job_ad_context] Failed: {e}")
        return ""


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


@app.route('/suggest', methods=['POST'])
def suggest_alternative():
    """
    Generate a grammar- and full-job-ad-context-aware gender-neutral alternative
    using Groq.

    Request:
    {
        "term":      "<biased word>",
        "bias_type": "masculine" | "feminine",
        "context":   "<the specific sentence containing the term>",   # optional but recommended
        "full_text": "<entire job advertisement text>"                 # NEW — enables full-ad awareness
    }

    How full-ad context works
    ─────────────────────────
    When `full_text` is supplied the endpoint runs a lightweight pre-pass with
    Groq to extract a compact structural summary of the ad (job title, industry,
    tone, audience signals, key responsibilities).  That summary — rather than
    the raw full text — is then injected into the suggestion prompt so the LLM
    can choose a replacement word that:

      • fits the role and industry (e.g. "assertive" → "decisive" in a sales
        context vs. "clear-minded" in a healthcare context)
      • matches the register and formality of the ad
      • is idiomatic within the Philippine job market
      • slots in grammatically inside the specific sentence (`context` field)

    If `full_text` is absent the endpoint falls back to the previous
    sentence-only behaviour.

    Response:
    {
        "term":          "<original term>",
        "suggestion":    "<single alternative word or phrase>",
        "context_aware": true | false   // true when `context` was used
        "ad_aware":      true | false   // true when `full_text` was used
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        term      = data.get('term', '').strip()
        bias_type = data.get('bias_type', '').strip()
        context   = data.get('context', '').strip()
        full_text = data.get('full_text', '').strip()

        if not term:
            return jsonify({'error': 'term field is required'}), 400
        if bias_type not in ('masculine', 'feminine'):
            return jsonify({'error': 'bias_type must be "masculine" or "feminine"'}), 400

        # TODO: Insert rule-based dictionary lookup here once validated dictionary
        # is available. If a match is found, return it and skip the Groq call.

        # ------------------------------------------------------------------
        # Step 1 — build job-ad structural summary (new full-ad awareness)
        # ------------------------------------------------------------------
        ad_summary = ""
        ad_aware   = False

        if full_text:
            ad_summary = summarise_job_ad_context(full_text)
            ad_aware   = bool(ad_summary)

        # ------------------------------------------------------------------
        # Step 2 — build the suggestion prompt
        # ------------------------------------------------------------------
        if bias_type == 'masculine':
            bias_context_label = 'a masculine-coded word (stereotypically associated with male characteristics)'
        else:
            bias_context_label = 'a feminine-coded word (stereotypically associated with female characteristics)'

        # Build the ad-context block that will be injected into the prompt
        if ad_summary:
            ad_context_block = (
                f"\n\nJob advertisement context (for tone and role alignment):\n"
                f"{ad_summary}\n"
            )
        else:
            ad_context_block = ""

        if context:
            # Full context-aware path: sentence + optional ad summary
            user_message = (
                f"In the following job advertisement, the term '{term}' is {bias_context_label}."
                f"{ad_context_block}\n"
                f"Specific sentence: \"{context}\"\n\n"
                f"Suggest a single best gender-neutral alternative word or short phrase (2-3 words max) that:\n"
                f"1. Naturally replaces '{term}' in the sentence above\n"
                f"2. Maintains the original grammar and sentence structure\n"
                f"3. Preserves the meaning and intent of the job advertisement\n"
                f"4. Matches the tone and industry context described above\n"
                f"5. Sounds professional and natural in a Philippine job market context\n\n"
                f"Reply with ONLY the alternative word or phrase. No explanation, no brackets, no extra text."
            )
        else:
            # Sentence not provided — use ad summary alone if available
            user_message = (
                f"The term '{term}' is {bias_context_label}."
                f"{ad_context_block}\n"
                f"Suggest a single best gender-neutral alternative word or short phrase "
                f"for this term in a Philippine job advertisement context. "
                f"Reply with ONLY the alternative word or phrase, nothing else."
            )

        # ------------------------------------------------------------------
        # Step 3 — call Groq
        # ------------------------------------------------------------------
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert in gender-neutral and inclusive language for job advertisements "
                        "in the Philippine job market. "
                        "Your role is to help rewrite gender-coded language to be more inclusive and fair "
                        "to all candidates. "
                        "When a job advertisement summary is provided, use it to ensure your suggestion fits "
                        "the role, industry, and register of the ad. "
                        "When a specific sentence is provided, ensure your suggestion slots in grammatically "
                        "and naturally without changing the meaning of the sentence. "
                        "You respond with ONLY a single best gender-neutral alternative word or short phrase "
                        "(2-3 words maximum). "
                        "No explanation, no numbering, no comma-separated lists, no extra text. "
                        "Just the single replacement word or phrase only."
                    )
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=20,
            temperature=0.3,
        )

        suggestion = response.choices[0].message.content.strip()

        return jsonify({
            'term':          term,
            'suggestion':    suggestion,
            'context_aware': len(context) > 0,
            'ad_aware':      ad_aware,
        }), 200

    except Exception as e:
        error_type = type(e).__name__

        if error_type == 'RateLimitError':
            return jsonify({'error': 'Rate limit reached, please try again shortly'}), 429
        if error_type == 'APIConnectionError':
            return jsonify({'error': 'Could not reach suggestion service'}), 503
        if error_type == 'APIStatusError':
            return jsonify({'error': 'Suggestion service returned an error'}), 502

        print(f"[/suggest] Unexpected error: {error_type}: {str(e)}")
        return jsonify({'error': 'Suggestion service returned an error'}), 502


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