"""
AdJust Bias Detection API
Integrates Random Forest for bias classification
"""
import os
import json
import pickle
import joblib
import numpy as np
import re
import csv
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from groq import Groq
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
analyzer = SentimentIntensityAnalyzer()

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

print(f"[Model Config] Loaded configuration from {config_path}")
print(f"  - RoBERTa Model: {config.get('roberta_model', 'N/A')}")
print(f"  - Max Length: {config.get('max_length', 'N/A')}")
print(f"  - Classes: {config.get('classes', [])}")
print(f"  - Accuracy: {config.get('accuracy', 'N/A')}%")
print(f"  - Macro F1: {config.get('macro_f1', 'N/A')}%")

# Load model artifacts
model_dir = os.path.join(os.path.dirname(__file__), 'models')
with open(os.path.join(model_dir, 'label_encoder.pkl'), 'rb') as f:
    label_encoder = pickle.load(f)
print(f"[Model] Label encoder loaded with classes: {list(label_encoder.classes_)}")

# Create class name mapping to normalize encoder output to frontend-compatible format
# The new label encoder uses lowercase names, but frontend expects capitalized names
CLASS_NAME_MAPPING = {
    'feminine': 'Female',
    'masculine': 'Male',
    'neutral': 'Neutral',
}

rf_model = joblib.load(os.path.join(model_dir, 'random_forest.pkl'))
print(f"[Model] Random Forest model loaded successfully ({rf_model.n_estimators} estimators)")
print(f"[Model] Expects {rf_model.n_features_in_} features from embeddings")
print(f"[Model] Label encoder classes: {list(label_encoder.classes_)}")
print(f"[Model] Class name mapping enabled for frontend compatibility")

# ─────────────────────────────────────────────────────────────────────────
# Load validated word dictionary for instant, context-free lookups
# ─────────────────────────────────────────────────────────────────────────
WORD_DICTIONARY = {}  # word (lowercase) → {'label': 'masculine'|'feminine'|'neutral', 'source': str}
dict_path = os.path.join(model_dir, 'data_dictionary.csv')

if os.path.exists(dict_path):
    try:
        with open(dict_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                word = row.get('word', '').strip().lower()
                label = row.get('label', '').strip().lower()
                source = row.get('source', '').strip()
                if word and label in ('masculine', 'feminine', 'neutral'):
                    WORD_DICTIONARY[word] = {
                        'label': label,
                        'source': source,
                    }
        print(f"[Dictionary] Loaded {len(WORD_DICTIONARY)} words from validated dictionary")
    except Exception as e:
        print(f"[Dictionary] Error loading dictionary: {e}")
        WORD_DICTIONARY = {}
else:
    print(f"[Dictionary] Dictionary file not found at {dict_path}")

# Try to load transformers for RoBERTa embeddings
try:
    from transformers import RobertaTokenizer, RobertaModel
    import torch

    tokenizer = RobertaTokenizer.from_pretrained(config['roberta_model'])
    roberta_model = RobertaModel.from_pretrained(config['roberta_model'])
    roberta_model.eval()
    ROBERTA_LOADED = True
    print("[OK] RoBERTa loaded successfully")
except Exception as e:
    ROBERTA_LOADED = False
    print(f"[WARN] RoBERTa not available: {e}")
    print("  Using TF-IDF fallback for embeddings")


def get_embeddings(text, max_length=512):
    """Generate embeddings matching the training pipeline exactly:
       768-dim mean-pooled RoBERTa + norm_token_length + VADER compound = 770
    """
    if ROBERTA_LOADED:
        try:
            import torch
            with torch.no_grad():
                inputs = tokenizer(
                    text,
                    max_length=max_length,
                    padding=True,
                    truncation=True,
                    return_tensors='pt'
                )
                outputs = roberta_model(**inputs)

                mask = inputs["attention_mask"].unsqueeze(-1).float()
                embedding = (outputs.last_hidden_state * mask).sum(1) / mask.sum(1)
                embedding = embedding.numpy().flatten()  # 768-dim

            tokens   = text.split()
            norm_len = min(len(tokens), max_length) / max_length
            compound = analyzer.polarity_scores(text)["compound"]

            return np.concatenate([embedding, [norm_len, compound]])

        except Exception as e:
            print(f"Error generating embeddings: {e}")
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
# Gender-coded keyword sets — derived directly from the validated
# data_dictionary.csv so that flagging always aligns with the training data.
# Sources: Gaucher et al. (2011), EIGE Toolkit (2019), MCWC, UNDP WACA (2024),
#          Gender-Fair Language Primer — Kintanar (1998), BIAS Word Inventory
#          — Konnikov et al. (2022), LinkedIn Talent Solutions / Cpl HR,
#          BUCGAD Feedback, and common Philippine job advertisement patterns.
# ---------------------------------------------------------------------------

_MASCULINE_KEYWORDS = {
    word for word, entry in WORD_DICTIONARY.items()
    if entry['label'] == 'masculine'
}

_FEMININE_KEYWORDS = {
    word for word, entry in WORD_DICTIONARY.items()
    if entry['label'] == 'feminine'
}

print(f"[Keywords] Masculine keywords loaded: {len(_MASCULINE_KEYWORDS)}")
print(f"[Keywords] Feminine keywords loaded: {len(_FEMININE_KEYWORDS)}")


def extract_flagged_phrases(text: str) -> dict:
    """
    Extract gender-coded words from text using the validated data dictionary.

    Matching strategy:
    - Multi-word phrases (with spaces): substring search — exact phrase match
    - Dashed compounds (with dashes): substring search — exact phrase match
    - Single words: ALWAYS word-boundary regex to prevent false positives
      (e.g. 'he' must not match in 'the', 'where', 'other', 'there')

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
        # Multi-word phrases or dashed compounds: use substring matching
        # (the phrase structure itself prevents false matches)
        if ' ' in keyword or '-' in keyword:
            return keyword in text_lower

        # Single words: ALWAYS use strict word boundary matching
        # This prevents "he" from matching in "the", "where", etc.
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


def lookup_dictionary_suggestion(term: str, bias_type: str) -> str | None:
    """
    Check if a biased term exists in the validated word dictionary.

    Returns a neutral alternative if found, None otherwise.
    Uses common-sense neutral replacements based on the word's bias type.

    Args:
        term: The potentially biased word to look up
        bias_type: 'masculine' or 'feminine'

    Returns:
        A neutral alternative word/phrase if found in dictionary and matches bias_type,
        None if not found or doesn't match bias_type
    """
    term_lower = term.lower()

    if term_lower not in WORD_DICTIONARY:
        return None

    entry = WORD_DICTIONARY[term_lower]

    # Only return a dictionary suggestion if it matches the detected bias type
    if entry['label'] != bias_type:
        return None

    # Map biased words to their neutral alternatives
    # These are common, validated neutral replacements
    neutral_alternatives = {
        # Masculine-coded words → neutral
        'assertive': 'confident',
        'aggressive': 'proactive',
        'ambitious': 'goal-oriented',
        'analytical': 'analytical-minded',
        'active': 'engaged',
        'boast': 'highlight achievements',
        'businessman': 'business professional',
        'cameraman': 'camera operator',
        'chairman': 'chairperson',
        'challenging': 'engaging',
        'confident': 'assured',
        'decisive': 'clear-thinking',
        'determine': 'establish',
        'determined': 'committed',
        'dominance': 'leadership',
        'dominate': 'lead',
        'lead': 'guide',
        'driving': 'motivated',
        'dynamic': 'energetic',
        'expert': 'specialist',
        'fireman': 'firefighter',
        'forceful': 'persuasive',
        'guy': 'person',
        'he': 'they',
        'his': 'their',
        'him': 'them',
        'himself': 'themselves',
        'independent': 'self-reliant',
        'logical': 'systematic',
        'masculine': 'inclusive',
        'master': 'expert',
        'must': 'should',
        'operator': 'specialist',
        'penetrate': 'enter',
        'pioneer': 'innovator',
        'powerful': 'impactful',
        'rocket': 'high-performer',
        'skilled': 'capable',
        'smart': 'intelligent',
        'strength': 'capability',
        'strong': 'capable',
        'tackle': 'address',
        'tough': 'resilient',
        'warrior': 'fighter',
        'ninja': 'expert',
        'rockstar': 'top performer',
        'guru': 'specialist',
        'wizard': 'expert',
        'fast-paced': 'dynamic',
        'self-starter': 'motivated professional',
        'self-motivated': 'self-directed',
        # Feminine-coded words → neutral
        'affectionate': 'warm',
        'agreeable': 'cooperative',
        'caring': 'supportive',
        'considerate': 'thoughtful',
        'compassion': 'empathy',
        'compassionate': 'empathetic',
        'devoted': 'committed',
        'emotional': 'expressive',
        'empathetic': 'understanding',
        'feminine': 'inclusive',
        'friendly': 'approachable',
        'gentle': 'tactful',
        'grateful': 'appreciative',
        'herself': 'themselves',
        'her': 'their',
        'honest': 'truthful',
        'humble': 'modest',
        'interpersonal': 'collaborative',
        'kind': 'considerate',
        'lady': 'person',
        'lovely': 'pleasant',
        'maternal': 'nurturing',
        'modest': 'humble',
        'nurturing': 'supportive',
        'secretary': 'administrative professional',
        'sensitive': 'perceptive',
        'she': 'they',
        'sociable': 'friendly',
        'soft-spoken': 'measured',
        'supporting': 'collaborative',
        'supportive': 'helpful',
        'warm': 'approachable',
        'woman': 'person',
        'women': 'people',
        # Feminine-coded dashed words → neutral
        'family-oriented': 'community-focused',
        'people-oriented': 'people-focused',
        'service-oriented': 'service-focused',
        'harmony-focused': 'collaboration-focused',
        'detail-oriented': 'detail-focused',
    }

    return neutral_alternatives.get(term_lower)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'model': {
            'roberta': config.get('roberta_model', 'N/A'),
            'classes': config.get('classes', []),
            'accuracy': config.get('accuracy', 'N/A'),
            'macro_f1': config.get('macro_f1', 'N/A'),
            'tuning_cv_macro_f1': config.get('tuning_cv_macro_f1', 'N/A'),
        },
        'label_encoder': {
            'classes': list(label_encoder.classes_),
            'n_classes': len(label_encoder.classes_),
        },
        'dictionary': {
            'total_words': len(WORD_DICTIONARY),
            'masculine_keywords': len(_MASCULINE_KEYWORDS),
            'feminine_keywords': len(_FEMININE_KEYWORDS),
        },
    })


@app.route('/detect', methods=['POST'])
def detect_bias():
    """
    Single-text bias detection.

    Request:  { "text": "..." }
    Response: {
        "detected_class": "Male"|"Female"|"Neutral",
        "confidence_scores": {"Male": 0.0, "Female": 0.0, "Neutral": 0.0},
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
        predicted_class_raw = label_encoder.inverse_transform([predicted_class_idx])[0]
        predicted_class = CLASS_NAME_MAPPING.get(predicted_class_raw, predicted_class_raw)

        probabilities = rf_model.predict_proba([embeddings])[0]

        # Build confidence_scores with all classes in consistent order
        confidence_scores = {}
        for i, raw_class_name in enumerate(label_encoder.classes_):
            mapped_class_name = CLASS_NAME_MAPPING.get(raw_class_name, raw_class_name)
            confidence_scores[mapped_class_name] = float(probabilities[i])

        flagged_phrases = extract_flagged_phrases(text)

        # ------------------------------------------------------------------
        # Post-processing override: if the model predicts Male/Female but
        # no corresponding keywords are flagged, and Neutral score is
        # reasonably competitive, override the classification to Neutral.
        # This corrects cases where the RF model over-relies on embeddings
        # for terms that have been reclassified as neutral in the dictionary.
        # ------------------------------------------------------------------
        masculine_count = len(flagged_phrases['masculine'])
        feminine_count  = len(flagged_phrases['feminine'])
        neutral_score   = confidence_scores.get('Neutral', 0)

        if (predicted_class == 'Male'
                and masculine_count == 0
                and neutral_score > 0.25):
            predicted_class = 'Neutral'

        elif (predicted_class == 'Female'
                and feminine_count == 0
                and neutral_score > 0.25):
            predicted_class = 'Neutral'

        return jsonify({
            'detected_class': predicted_class,
            'confidence_scores': confidence_scores,
            'flagged_phrases': flagged_phrases,
            'accuracy_note': f"Model Accuracy: {config.get('accuracy', 'N/A')}%, Macro F1: {config.get('macro_f1', 'N/A')}%",
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
        "full_text": "<entire job advertisement text>"                 # enables full-ad awareness
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

    If `full_text` is absent the endpoint falls back to sentence-only behaviour.

    Response:
    {
        "term":          "<original term>",
        "suggestion":    "<single alternative word or phrase>",
        "context_aware": true | false,
        "ad_aware":      true | false
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

        # ------------------------------------------------------------------
        # Step 1 — Check validated dictionary for instant lookup
        # ------------------------------------------------------------------
        dict_suggestion = lookup_dictionary_suggestion(term, bias_type)
        if dict_suggestion:
            print(f"[/suggest] Dictionary hit for '{term}' ({bias_type}) → '{dict_suggestion}'")
            return jsonify({
                'term':          term,
                'suggestion':    dict_suggestion,
                'context_aware': len(context) > 0,
                'ad_aware':      False,
                'source':        'validated_dictionary',
            }), 200

        # ------------------------------------------------------------------
        # Step 2 — Fall back to Groq for words not in dictionary
        # ------------------------------------------------------------------
        ad_summary = ""
        ad_aware   = False

        if full_text:
            ad_summary = summarise_job_ad_context(full_text)
            ad_aware   = bool(ad_summary)

        # ------------------------------------------------------------------
        # Step 3 — Build the suggestion prompt
        # ------------------------------------------------------------------
        if bias_type == 'masculine':
            bias_context_label = 'a masculine-coded word (stereotypically associated with male characteristics)'
        else:
            bias_context_label = 'a feminine-coded word (stereotypically associated with female characteristics)'

        if ad_summary:
            ad_context_block = (
                f"\n\nJob advertisement context (for tone and role alignment):\n"
                f"{ad_summary}\n"
            )
        else:
            ad_context_block = ""

        if context:
            user_message = (
                f"In the following job advertisement, the term '{term}' is {bias_context_label}."
                f"{ad_context_block}\n"
                f"Specific sentence: \"{context}\"\n\n"
                f"Carefully consider the context and suggest ONE best gender-neutral alternative word or short phrase (2-3 words max) that:\n"
                f"1. Can directly replace '{term}' in the sentence above\n"
                f"2. Maintains the exact grammar and sentence structure (same part of speech)\n"
                f"3. Preserves the meaning, tone, and professional intent\n"
                f"4. Matches the industry context and register of the job ad\n"
                f"5. Is natural and professional in a Philippine job market context\n"
                f"6. Does NOT repeat the original term '{term}' or use it as part of the suggestion\n\n"
                f"Output ONLY the alternative word or phrase. No explanation, no justification, no extra text."
            )
        else:
            user_message = (
                f"The term '{term}' is {bias_context_label}."
                f"{ad_context_block}\n"
                f"Suggest ONE single best gender-neutral alternative word or short phrase (2-3 words max) "
                f"for this term in a Philippine job advertisement context. "
                f"The suggestion must NOT repeat the original term '{term}'.\n"
                f"Output ONLY the alternative word or phrase, nothing else."
            )

        # ------------------------------------------------------------------
        # Step 4 — Call Groq for final suggestion
        # ------------------------------------------------------------------
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert in gender-neutral and inclusive language for job advertisements "
                        "in the Philippine job market. You specialize in:"
                        "\n1. Understanding the context and tone of each job ad\n"
                        "2. Selecting alternatives that match part of speech and grammar\n"
                        "3. Ensuring suggestions are never repetitive or derivative of the original term\n"
                        "4. Providing professional and inclusive language\n"
                        "5. Maintaining the exact meaning and intent of the original sentence\n\n"
                        "CRITICAL: Respond with ONLY the single alternative word or phrase. "
                        "No explanation, no punctuation beyond apostrophes/hyphens, no numbers, no lists. "
                        "The response must be a single, clean word or phrase ready to use as a direct replacement."
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
        # Clean response: remove common artifacts
        suggestion = suggestion.strip('\"').strip("'").strip()
        suggestion = suggestion.rstrip('.!,?:;').strip().lower()

        # Detect and filter out problematic responses
        # 1. Remove if it just repeats the original term
        if suggestion == term.lower() or suggestion.startswith(term.lower()):
            suggestion = ""
        # 2. Remove if empty after cleaning
        if not suggestion:
            suggestion = ""
        # 3. Remove if contains common LLM artifacts (numbers, repeated patterns)
        if any(c.isdigit() for c in suggestion):
            suggestion = ""
        # 4. Check for repetition (word appearing twice consecutively)
        words = suggestion.split()
        if len(words) > 1:
            for i in range(len(words) - 1):
                if words[i] == words[i + 1]:
                    suggestion = " ".join([words[0]] + [w for i, w in enumerate(words[1:], 1) if w != words[i-1]])
                    break

        # If all cleaning failed and we have an invalid response, return empty and log
        if not suggestion or len(suggestion.split()) > 4:
            print(f"[/suggest] WARNING: Groq returned problematic response for '{term}': {response.choices[0].message.content}")
            suggestion = ""

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
            predicted_class_raw = label_encoder.inverse_transform([predicted_class_idx])[0]
            predicted_class = CLASS_NAME_MAPPING.get(predicted_class_raw, predicted_class_raw)

            probabilities = rf_model.predict_proba([embeddings])[0]

            # Build confidence_scores with all classes in consistent order
            confidence_scores = {}
            for i, raw_class_name in enumerate(label_encoder.classes_):
                mapped_class_name = CLASS_NAME_MAPPING.get(raw_class_name, raw_class_name)
                confidence_scores[mapped_class_name] = float(probabilities[i])

            flagged_phrases = extract_flagged_phrases(text)

            # Post-processing override (mirrors /detect endpoint)
            masculine_count = len(flagged_phrases['masculine'])
            feminine_count  = len(flagged_phrases['feminine'])
            neutral_score   = confidence_scores.get('Neutral', 0)

            if (predicted_class == 'Male'
                    and masculine_count == 0
                    and neutral_score > 0.25):
                predicted_class = 'Neutral'

            elif (predicted_class == 'Female'
                    and feminine_count == 0
                    and neutral_score > 0.25):
                predicted_class = 'Neutral'

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