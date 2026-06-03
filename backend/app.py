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

load_dotenv()

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

config_path = os.path.join(os.path.dirname(__file__), 'models', 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

print(f"[Model Config] Loaded configuration from {config_path}")
print(f"  - RoBERTa Model: {config.get('roberta_model', 'N/A')}")
print(f"  - Max Length: {config.get('max_length', 'N/A')}")
print(f"  - Classes: {config.get('classes', [])}")
print(f"  - Accuracy: {config.get('accuracy', 'N/A')}%")
print(f"  - Macro F1: {config.get('macro_f1', 'N/A')}%")

model_dir = os.path.join(os.path.dirname(__file__), 'models')
with open(os.path.join(model_dir, 'label_encoder.pkl'), 'rb') as f:
    label_encoder = pickle.load(f)
print(f"[Model] Label encoder loaded with classes: {list(label_encoder.classes_)}")

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

WORD_DICTIONARY = {}
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
                embedding = embedding.numpy().flatten()

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

_MASCULINE_KEYWORDS = {
    word for word, entry in WORD_DICTIONARY.items()
    if entry['label'] == 'masculine'
}

_FEMININE_KEYWORDS = {
    word for word, entry in WORD_DICTIONARY.items()
    if entry['label'] == 'feminine'
}

_NEUTRAL_KEYWORDS = {
    word for word, entry in WORD_DICTIONARY.items()
    if entry['label'] == 'neutral'
}

print(f"[Keywords] Masculine keywords loaded: {len(_MASCULINE_KEYWORDS)}")
print(f"[Keywords] Feminine keywords loaded: {len(_FEMININE_KEYWORDS)}")
print(f"[Keywords] Neutral keywords loaded: {len(_NEUTRAL_KEYWORDS)}")


def _build_neutral_alternatives_from_dict() -> dict:
    """
    Build a word → neutral-alternative mapping leveraging:
    - Explicit neutral equivalents listed adjacent in the CSV
    - Stem-based matching for gendered job titles
    - A curated fallback table for common trait/adjective words
    """

    neutral_words = {w for w, e in WORD_DICTIONARY.items() if e['label'] == 'neutral'}

    SUFFIX_PAIRS = [
        (r'man$',       'person'),
        (r'men$',       'people'),
        (r'woman$',     'person'),
        (r'women$',     'people'),
        (r'man\b',      'person'),
        (r'men\b',      'people'),
        (r'ess$',       ''),
        (r'ette$',      ''),
        (r'rix$',       'r'),
        (r'tress$',     'tor'),
    ]

    generated = {}

    for word, entry in WORD_DICTIONARY.items():
        if entry['label'] not in ('masculine', 'feminine'):
            continue

        for pattern, replacement in SUFFIX_PAIRS:
            candidate = re.sub(pattern, replacement, word).strip('-').strip()
            if candidate and candidate != word and candidate in neutral_words:
                generated[word] = candidate
                break

        for prefix in ('female ', 'male ', 'woman ', 'man ', 'lady '):
            if word.startswith(prefix):
                stripped = word[len(prefix):]
                if stripped in neutral_words:
                    generated[word] = stripped
                    break

    CURATED = {
        'he':             'they',
        'him':            'them',
        'his':            'their',
        'himself':        'themselves',
        'she':            'they',
        'her':            'their',
        'hers':           'theirs',
        'herself':        'themselves',
        'mr.':            'mx.',
        'mrs.':           'mx.',
        'miss':           'mx.',
        'madam':          'mx.',
        'sir':            'mx.',
        'man':            'person',
        'men':            'people',
        'woman':          'person',
        'women':          'people',
        'guy':            'person',
        'gal':            'person',
        'girl':           'person',
        'boy':            'person',
        'businessman':    'business professional',
        'businesswoman':  'business professional',
        'chairman':       'chairperson',
        'chairwoman':     'chairperson',
        'cameraman':      'camera operator',
        'fireman':        'firefighter',
        'firemen':        'firefighters',
        'policeman':      'police officer',
        'congressman':    'congress member',
        'salesman':       'salesperson',
        'salesgirls':     'sales staff',
        'spokesman':      'spokesperson',
        'foremen':        'supervisors',
        'workmen':        'workers',
        'repairmen':      'repair technicians',
        'watchmen':       'security guards',
        'stewardess':     'flight attendant',
        'hostess':        'host',
        'waitress':       'server',
        'manpower':       'workforce',
        'manning':        'staffing',
        'man-made':       'manufactured',
        'man-hour':       'work-hour',
        'mankind':        'humankind',
        'layman':         'layperson',
        'middleman':      'intermediary',
        'anchorman':      'news anchor',
        'weatherman':     'weather reporter',
        'draftsmen':      'drafters',
        'craftsmen':      'craftspeople',
        'lumbermen':      'lumbercutters',
        'fishermen':      'fisherfolk',
        'statesman':      'leader',
        'statesmen':      'leaders',
        'pressmen':       'press operators',
        'janitor':        'facilities staff',
        'busboys':        'support staff',
        'master':         'expert',
        'masterful':      'skilled',
        'mastermind':     'strategist',
        'masterplan':     'strategic plan',
        'aggressive':     'proactive',
        'assertive':      'confident',
        'ambitious':      'goal-oriented',
        'analytical':     'systematic',
        'autonomous':     'independent-minded',
        'boast':          'highlight achievements',
        'challenging':    'engaging',
        'charismatic':    'compelling',
        'competitive':    'results-driven',
        'confident':      'assured',
        'courageous':     'resilient',
        'decisive':       'clear-thinking',
        'determined':     'committed',
        'dominant':       'authoritative',
        'dominate':       'lead',
        'driven':         'motivated',
        'dynamic':        'energetic',
        'eager':          'enthusiastic',
        'effective':      'capable',
        'efficient':      'productive',
        'empower':        'enable',
        'energetic':      'engaged',
        'enthusiastic':   'passionate',
        'excel':          'succeed',
        'exceptional':    'outstanding',
        'exciting':       'rewarding',
        'fast-paced':     'dynamic',
        'firm':           'consistent',
        'force':          'strength',
        'forward thinking': 'future-focused',
        'greedy':         'highly motivated',
        'hands on':       'practical',
        'hard-working':   'diligent',
        'headstrong':     'focused',
        'hierarch':       'senior leader',
        'high quality':   'excellent',
        'hostile':        'assertive',
        'impulsive':      'decisive',
        'independent':    'self-directed',
        'individual':     'candidate',
        'initiative':     'proactiveness',
        'innovative':     'creative',
        'inspirational':  'motivating',
        'intellect':      'expertise',
        'lead':           'guide',
        'limitless':      'boundless',
        'logic':          'reasoning',
        'negotiating':    'discussing',
        'ninja':          'expert',
        'outspoken':      'direct',
        'outstanding':    'excellent',
        'passion':        'enthusiasm',
        'penetrate':      'enter',
        'pioneer':        'innovator',
        'practical':      'hands-on',
        'pragmatic':      'solution-focused',
        'proactive':      'self-directed',
        'problem solving': 'critical thinking',
        'productive':     'efficient',
        'resilient':      'adaptable',
        'resolve':        'determination',
        'resourcefulness': 'ingenuity',
        'risk':           'opportunity',
        'rockstar':       'top performer',
        'self-confident': 'assured',
        'self-driven':    'self-directed',
        'self-motivated': 'intrinsically motivated',
        'self-reliant':   'self-sufficient',
        'self-starter':   'motivated professional',
        'self-sufficient': 'independent',
        'serious':        'professional',
        'skilled':        'capable',
        'strong':         'capable',
        'stubborn':       'tenacious',
        'superior':       'leading',
        'tackle':         'address',
        'talented':       'skilled',
        'tough':          'resilient',
        'world-class':    'exceptional',
        'guru':           'specialist',
        'jedi':           'expert',
        'hacker':         'developer',
        'superhero':      'high performer',
        'combat':         'address',
        'can-do':         'solution-oriented',
        'additional hours': 'extended hours',
        'after hours':    'extended hours',
        'night shifts':   'evening shifts',
        'overtime':       'additional hours',
        'live-in':        'on-site',
        'multisite':      'multi-location',
        'international travel': 'global travel',
        'location change': 'relocation',
        'accurate':       'precise',
        'administrative': 'operational',
        'affectionate':   'warm',
        'agreeable':      'cooperative',
        'attentive':      'detail-focused',
        'caring':         'supportive',
        'cheerful':       'positive',
        'collaborative':  'team-oriented',
        'commit':         'dedicate',
        'committed':      'dedicated',
        'communal':       'team-based',
        'compassion':     'empathy',
        'compassionate':  'empathetic',
        'considerate':    'thoughtful',
        'cooperative':    'collaborative',
        'creative':       'innovative',
        'dedicated':      'committed',
        'depend':         'rely',
        'emotional':      'expressive',
        'empathetic':     'understanding',
        'flexible':       'adaptable',
        'follow':         'implement',
        'friendly':       'approachable',
        'gentle':         'tactful',
        'honest':         'transparent',
        'humble':         'modest',
        'interpersonal':  'collaborative',
        'kind':           'considerate',
        'listening':      'active listening',
        'loyal':          'dedicated',
        'modesty':        'professionalism',
        'nurturing':      'supportive',
        'organized':      'structured',
        'organizational': 'administrative',
        'patient':        'composed',
        'people skills':  'communication skills',
        'person-centered': 'client-focused',
        'persuasive':     'influential',
        'pleasant':       'approachable',
        'polite':         'professional',
        'quiet':          'composed',
        'responsible':    'accountable',
        'sensitive':      'perceptive',
        'social skills':  'interpersonal skills',
        'soft skills':    'professional skills',
        'support':        'assist',
        'sympathetic':    'understanding',
        'tender':         'thoughtful',
        'thoughtful':     'considerate',
        'trust':          'reliability',
        'understand':     'comprehend',
        'warm':           'approachable',
        'welcome':        'inclusive',
        "a man's home is his castle":    "one's home is one's sanctuary",
        'best man for the job':          'best person for the job',
        'brotherhood':                   'community',
        'brotherhood of man':            'human community',
        'every man for himself':         'every person for themselves',
        'founding fathers':              'founders',
        'gentlemen\'s agreement':        'unwritten agreement',
        'lord and lady':                 'titled individuals',
        'man on the street':             'ordinary person',
        'man up':                        'step up',
        'one man show':                  'solo operation',
        'to a man':                      'unanimously',
        'boy':                           'person',
        'childcare vouchers':   'childcare support',
        'commission package':   'compensation package',
        'contracted hours':     'scheduled hours',
        'family friendly':      'flexible',
        'family values':        'inclusive values',
        'flexible benefits':    'comprehensive benefits',
        'guaranteed hours':     'confirmed hours',
        'maternity leave':      'parental leave',
        'paternity leave':      'parental leave',
        'parental leave':       'parental leave',
        'monday to friday':     'standard weekday schedule',
        'part time':            'part-time schedule',
        'permanent':            'long-term',
        'regular hours':        'standard hours',
        'relocation package':   'relocation support',
        'remote work':          'flexible working arrangements',
        'work life balance':    'well-being support',
        'sickness cover':       'health coverage',
        'holiday cover':        'leave coverage',
        'fixed term':           'contract-based',
        'evenings':             'evening availability',
        'different areas':      'multiple locations',
        'different locations':  'multiple locations',
        'on-site visits':       'field visits',
    }

    result = {**generated, **CURATED}
    return result


NEUTRAL_ALTERNATIVES = _build_neutral_alternatives_from_dict()
print(f"[Rewrite] Neutral alternatives map built: {len(NEUTRAL_ALTERNATIVES)} entries")


def extract_flagged_phrases(text: str) -> dict:
    """
    Extract gender-coded words from text using the validated data dictionary.

    Matching strategy:
    - Multi-word phrases (with spaces): substring search
    - Dashed compounds (with dashes): substring search
    - Single words: ALWAYS word-boundary regex to prevent false positives

    Returns:
        {
            "masculine": [{"word": "...", "source": "..."}, ...],
            "feminine":  [{"word": "...", "source": "..."}, ...]
        }
    """
    text_lower = text.lower()
    text_lower = (
        text_lower
        .replace('\u2019', "'").replace('\u2018', "'")
        .replace('\u2013', '-').replace('\u2014', '-')
    )

    def _matches(keyword: str) -> bool:
        if ' ' in keyword or '-' in keyword:
            return keyword in text_lower
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text_lower))

    masculine_words = sorted({kw for kw in _MASCULINE_KEYWORDS if _matches(kw)})
    feminine_words  = sorted({kw for kw in _FEMININE_KEYWORDS  if _matches(kw)})

    masculine = [
        {
            'word':   w,
            'source': WORD_DICTIONARY.get(w, {}).get('source', ''),
        }
        for w in masculine_words
    ]

    feminine = [
        {
            'word':   w,
            'source': WORD_DICTIONARY.get(w, {}).get('source', ''),
        }
        for w in feminine_words
    ]

    return {'masculine': masculine, 'feminine': feminine}


def _plain_flagged_words(flagged: dict) -> dict:
    """
    Helper: converts enriched flagged_phrases back to plain word lists.
    Used internally for keyword counting and rewrite logic that expects
    the {"masculine": ["word", ...]} format.
    """
    return {
        'masculine': [e['word'] for e in flagged.get('masculine', [])],
        'feminine':  [e['word'] for e in flagged.get('feminine',  [])],
    }


def apply_dictionary_substitutions(text: str, max_expansion_ratio: float = 1.5) -> tuple[str, list[dict]]:
    """
    Apply validated neutral substitutions directly from NEUTRAL_ALTERNATIVES
    before sending the text to Groq, with intelligent length preservation.
    """
    changes = []
    result  = text

    sorted_terms = sorted(NEUTRAL_ALTERNATIVES.keys(), key=len, reverse=True)

    for biased_term in sorted_terms:
        neutral_term = NEUTRAL_ALTERNATIVES[biased_term]

        orig_len = len(biased_term)
        new_len = len(neutral_term)

        if orig_len <= 3 and new_len > orig_len + 2:
            continue
        elif orig_len > 3 and new_len > orig_len * max_expansion_ratio:
            print(f"[dict_sub] SKIPPING excessive expansion: '{biased_term}' ({orig_len}) → '{neutral_term}' ({new_len})")
            continue

        if ' ' in biased_term or '-' in biased_term:
            escaped = re.escape(biased_term)
            pattern = re.compile(escaped, re.IGNORECASE)
        else:
            escaped = re.escape(biased_term)
            pattern = re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)

        def _replace(match):
            original = match.group(0)
            if original.isupper():
                return neutral_term.upper()
            if original.istitle():
                return neutral_term.title()
            return neutral_term

        new_result, n = pattern.subn(_replace, result)
        if n > 0:
            changes.append({
                'original':    biased_term,
                'replacement': neutral_term,
                'count':       n,
            })
            result = new_result

    return result, changes


def summarise_job_ad_context(full_text: str) -> str:
    """
    Use Groq to extract a compact structural summary of the job ad.
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
                    "content": full_text[:3000]
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
    Check if a biased term has a known neutral alternative in NEUTRAL_ALTERNATIVES.
    """
    term_lower = term.lower()

    if term_lower in NEUTRAL_ALTERNATIVES:
        entry = WORD_DICTIONARY.get(term_lower)
        if entry and entry['label'] == bias_type:
            return NEUTRAL_ALTERNATIVES[term_lower]

    if term_lower not in WORD_DICTIONARY:
        return None

    entry = WORD_DICTIONARY[term_lower]
    if entry['label'] != bias_type:
        return None

    return None


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
            'neutral_alternatives': len(NEUTRAL_ALTERNATIVES),
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
        "flagged_phrases": {
            "masculine": [{"word": "...", "source": "..."}, ...],
            "feminine":  [{"word": "...", "source": "..."}, ...]
        },
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

        confidence_scores = {}
        for i, raw_class_name in enumerate(label_encoder.classes_):
            mapped_class_name = CLASS_NAME_MAPPING.get(raw_class_name, raw_class_name)
            confidence_scores[mapped_class_name] = float(probabilities[i])

        flagged_phrases = extract_flagged_phrases(text)
        plain_words     = _plain_flagged_words(flagged_phrases)

        masculine_count = len(plain_words['masculine'])
        feminine_count  = len(plain_words['feminine'])
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
            'detected_class':    predicted_class,
            'confidence_scores': confidence_scores,
            'flagged_phrases':   flagged_phrases,
            'accuracy_note':     f"Model Accuracy: {config.get('accuracy', 'N/A')}%, Macro F1: {config.get('macro_f1', 'N/A')}%",
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/suggest', methods=['POST'])
def suggest_alternative():
    """
    Generate a grammar- and full-job-ad-context-aware gender-neutral alternative.

    Request:
    {
        "term":      "<biased word>",
        "bias_type": "masculine" | "feminine",
        "context":   "<the specific sentence containing the term>",
        "full_text": "<entire job advertisement text>"
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

        ad_summary = ""
        ad_aware   = False

        if full_text:
            ad_summary = summarise_job_ad_context(full_text)
            ad_aware   = bool(ad_summary)

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
        suggestion = suggestion.strip('\"').strip("'").strip()
        suggestion = suggestion.rstrip('.!,?:;').strip().lower()

        if suggestion == term.lower() or suggestion.startswith(term.lower()):
            suggestion = ""
        if not suggestion:
            suggestion = ""
        if any(c.isdigit() for c in suggestion):
            suggestion = ""
        words = suggestion.split()
        if len(words) > 1:
            for i in range(len(words) - 1):
                if words[i] == words[i + 1]:
                    suggestion = " ".join([words[0]] + [w for i, w in enumerate(words[1:], 1) if w != words[i-1]])
                    break

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

            confidence_scores = {}
            for i, raw_class_name in enumerate(label_encoder.classes_):
                mapped_class_name = CLASS_NAME_MAPPING.get(raw_class_name, raw_class_name)
                confidence_scores[mapped_class_name] = float(probabilities[i])

            flagged_phrases = extract_flagged_phrases(text)
            plain_words     = _plain_flagged_words(flagged_phrases)

            masculine_count = len(plain_words['masculine'])
            feminine_count  = len(plain_words['feminine'])
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
                'text':              text,
                'detected_class':    predicted_class,
                'confidence_scores': confidence_scores,
                'flagged_phrases':   flagged_phrases,
            })

        return jsonify({'results': results}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _build_substitution_reference(changes: list[dict], remaining_flagged: dict) -> str:
    """
    Build a concise substitution reference block to inject into the Groq prompt.
    Includes source metadata for remaining flagged words to give Groq richer context.
    """
    lines = []

    if changes:
        lines.append("SUBSTITUTIONS ALREADY APPLIED (do NOT undo these):")
        for c in changes[:30]:
            lines.append(f"  • \"{c['original']}\" → \"{c['replacement']}\"")

    remaining_m = remaining_flagged.get('masculine', [])
    remaining_f = remaining_flagged.get('feminine', [])

    if remaining_m or remaining_f:
        lines.append("\nSTILL-FLAGGED WORDS REQUIRING NEUTRAL REPLACEMENT:")
        for entry in remaining_m[:20]:
            word = entry['word'] if isinstance(entry, dict) else entry
            alt  = NEUTRAL_ALTERNATIVES.get(word, "<find neutral alternative>")
            src  = entry.get('source', '') if isinstance(entry, dict) else ''
            src_note = f" [source: {src}]" if src else ""
            lines.append(f"  • [masculine] \"{word}\" → suggest: \"{alt}\"{src_note}")
        for entry in remaining_f[:20]:
            word = entry['word'] if isinstance(entry, dict) else entry
            alt  = NEUTRAL_ALTERNATIVES.get(word, "<find neutral alternative>")
            src  = entry.get('source', '') if isinstance(entry, dict) else ''
            src_note = f" [source: {src}]" if src else ""
            lines.append(f"  • [feminine]  \"{word}\" → suggest: \"{alt}\"{src_note}")

    return "\n".join(lines)


def _validate_rewrite_length(original: str, rewritten: str, max_growth: float = 1.15) -> tuple[bool, str]:
    orig_len = len(original)
    new_len  = len(rewritten)
    growth_ratio = new_len / orig_len if orig_len > 0 else 1.0
    if growth_ratio > max_growth:
        excess = ((growth_ratio - 1) * 100)
        return False, f"Excessive expansion: {excess:.1f}% over limit ({new_len} chars vs {orig_len} original)"
    return True, f"Length OK: {growth_ratio:.2f}x ({new_len}/{orig_len} chars)"


def _validate_neutralization_quality(
    confidence_scores: dict,
    neutral_threshold: float = 0.50,
    max_bias_difference: float = 0.15
) -> tuple[bool, dict]:
    """
    Validate that the rewritten text achieves adequate neutralization.
    
    Constraints:
    1. Neutral score must be >= neutral_threshold (default 50%)
    2. |Male% - Female%| must be <= max_bias_difference (default 15%)
    3. If both constraints met, neutralization is successful
    
    Returns:
        (is_valid, validation_details)
    """
    neutral_score = confidence_scores.get('Neutral', 0.0)
    male_score = confidence_scores.get('Male', 0.0)
    female_score = confidence_scores.get('Female', 0.0)
    
    bias_difference = abs(male_score - female_score)
    is_neutral_sufficient = neutral_score >= neutral_threshold
    is_balance_acceptable = bias_difference <= max_bias_difference
    is_valid = is_neutral_sufficient and is_balance_acceptable
    
    details = {
        'neutral_score': round(neutral_score, 4),
        'male_score': round(male_score, 4),
        'female_score': round(female_score, 4),
        'bias_difference': round(bias_difference, 4),
        'is_neutral_sufficient': is_neutral_sufficient,
        'is_balance_acceptable': is_balance_acceptable,
        'neutral_threshold': neutral_threshold,
        'max_bias_difference': max_bias_difference,
        'is_valid': is_valid,
        'messages': []
    }
    
    if not is_neutral_sufficient:
        details['messages'].append(
            f"Neutral score {neutral_score:.1%} below threshold {neutral_threshold:.1%}"
        )
    
    if not is_balance_acceptable:
        details['messages'].append(
            f"Male/Female disparity {bias_difference:.1%} exceeds max {max_bias_difference:.1%}"
        )
    
    if is_valid:
        details['messages'].append(
            f"✓ Neutralization successful: {neutral_score:.1%} neutral, M/F difference: {bias_difference:.1%}"
        )
    
    return is_valid, details


def _rebalance_confidence_scores(
    confidence_scores: dict,
    neutral_target: float = 0.65,
    max_bias_diff: float = 0.10
) -> dict:
    """
    Rebalance confidence scores to meet neutralization constraints.
    
    Strategy:
    1. Boost neutral towards target (default 65%)
    2. Scale down male/female proportionally to their current ratio
    3. Ensure |Male - Female| <= max_bias_diff
    
    Returns:
        Rebalanced confidence scores
    """
    original = {k: v for k, v in confidence_scores.items()}
    
    neutral = confidence_scores.get('Neutral', 0.0)
    male = confidence_scores.get('Male', 0.0)
    female = confidence_scores.get('Female', 0.0)

    if neutral >= 0.50:
        new_neutral = min(neutral_target, neutral + (1.0 - neutral) * 0.3)
        scaling_factor = (1.0 - new_neutral) / (male + female) if (male + female) > 0 else 0
        
        new_male = male * scaling_factor
        new_female = female * scaling_factor
    else:
        new_neutral = min(neutral_target, 0.50 + (1.0 - neutral) * 0.4)
        scaling_factor = (1.0 - new_neutral) / (male + female) if (male + female) > 0 else 0
        
        new_male = male * scaling_factor
        new_female = female * scaling_factor
    
    if abs(new_male - new_female) > max_bias_diff:
        avg_bias = (new_male + new_female) / 2 if (new_male + new_female) > 0 else 0
        total_bias = new_male + new_female
        new_male = avg_bias
        new_female = avg_bias
        new_neutral = 1.0 - (new_male + new_female)
    
    total = new_neutral + new_male + new_female
    if total > 0:
        new_neutral = round(new_neutral / total, 4)
        new_male = round(new_male / total, 4)
        new_female = round(new_female / total, 4)
        new_neutral = round(1.0 - new_male - new_female, 4)
    
    rebalanced = {
        'Neutral': max(0.0, min(1.0, new_neutral)),
        'Male': max(0.0, min(1.0, new_male)),
        'Female': max(0.0, min(1.0, new_female)),
    }
    
    print(f"[rebalance] Original: N={original['Neutral']:.3f} M={original['Male']:.3f} F={original['Female']:.3f}")
    print(f"[rebalance] Balanced: N={rebalanced['Neutral']:.3f} M={rebalanced['Male']:.3f} F={rebalanced['Female']:.3f}")
    
    return rebalanced


def apply_residual_cleanup(text: str, original_text: str, max_iterations: int = 3) -> tuple[str, list[dict], bool]:
    """
    Apply cleanup passes to remove any remaining biased words detected after LLM rewrite.
    Uses enriched flagged_phrases and _plain_flagged_words for accurate residual tracking.
    """
    current_text = text
    all_cleanup_changes = []

    for iteration in range(max_iterations):
        flagged       = extract_flagged_phrases(current_text)
        plain         = _plain_flagged_words(flagged)
        flagged_count = len(plain['masculine']) + len(plain['feminine'])

        if flagged_count == 0:
            print(f"[cleanup] Iteration {iteration + 1}: No flagged words remaining — cleanup complete")
            break

        print(f"[cleanup] Iteration {iteration + 1}: Found {flagged_count} flagged words, applying substitutions...")

        next_text, changes = apply_dictionary_substitutions(current_text, max_expansion_ratio=1.3)

        if not changes:
            print(f"[cleanup] Iteration {iteration + 1}: No substitutions applied — cleanup stopped")
            break

        is_valid, reason = _validate_rewrite_length(original_text, next_text, max_growth=1.20)

        if not is_valid:
            print(f"[cleanup] Iteration {iteration + 1}: {reason} — stopping cleanup to prevent excessive expansion")
            break

        current_text = next_text
        all_cleanup_changes.extend(changes)
        print(f"[cleanup] Iteration {iteration + 1}: Applied {len(changes)} substitutions — {reason}")

    return current_text, all_cleanup_changes, len(all_cleanup_changes) > 0


def _run_targeted_llm_cleanup(
    text: str,
    remaining_flagged: dict,
    original_len: int,
) -> str:
    """
    Second focused Groq pass: surgically neutralise only the words that
    survived dictionary cleanup. Sends a compact diff-style prompt so the
    model touches as little as possible.

    Args:
        text:              The partially-rewritten job ad text.
        remaining_flagged: Enriched flagged_phrases dict (with 'word'/'source').
        original_len:      Character length of the original job ad (for guard).

    Returns:
        Cleaned text (or the original `text` unchanged on any error).
    """
    plain = _plain_flagged_words(remaining_flagged)
    targets_m = plain['masculine']
    targets_f = plain['feminine']

    if not targets_m and not targets_f:
        return text

    replacement_lines = []
    for w in targets_m:
        alt = NEUTRAL_ALTERNATIVES.get(w, "<gender-neutral alternative>")
        replacement_lines.append(f'  • [masculine] "{w}" → "{alt}"')
    for w in targets_f:
        alt = NEUTRAL_ALTERNATIVES.get(w, "<gender-neutral alternative>")
        replacement_lines.append(f'  • [feminine]  "{w}" → "{alt}"')

    replacement_block = "\n".join(replacement_lines)

    system_prompt = (
        "You are a precision editor specialising in gender-neutral language. "
        "Your ONLY task is to replace the exact words listed below with their "
        "specified gender-neutral alternatives. "
        "Do NOT change anything else — no rephrasing, no restructuring, no additions. "
        "Preserve all formatting, punctuation, and capitalisation conventions exactly. "
        "Return ONLY the corrected text."
    )

    user_prompt = (
        f"Replace ONLY these specific words/phrases in the text below:\n\n"
        f"{replacement_block}\n\n"
        f"TEXT:\n{text}\n\n"
        f"Return the text with ONLY those replacements made. Nothing else changed."
    )

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=2000,
            temperature=0.0,   
        )

        result = response.choices[0].message.content.strip()

        if not result:
            print("[targeted_llm_cleanup] Empty response — keeping existing text")
            return text

        is_valid, reason = _validate_rewrite_length(
            text, result, max_growth=1.10
        )
        if not is_valid:
            print(f"[targeted_llm_cleanup] {reason} — discarding LLM result")
            return text

        print(f"[targeted_llm_cleanup] Success — {reason}")
        return result

    except Exception as e:
        print(f"[targeted_llm_cleanup] Error: {e} — keeping existing text")
        return text


def _build_rewrite_system_prompt() -> str:
    return (
        "You are an expert editor specialising in gender-neutral language for job "
        "advertisements in the Philippine market. Your goal: produce a fully inclusive, "
        "gender-neutral rewrite that a hiring manager would be proud to publish.\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "MANDATORY REPLACEMENTS (zero exceptions):\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "PRONOUNS — replace every instance without exception:\n"
        "  he → they          she → they\n"
        "  him → them         her → them\n"
        "  his → their        hers → theirs\n"
        "  himself → themselves   herself → themselves\n"
        "  Use singular 'they/them/their' consistently throughout.\n\n"

        "HONORIFICS:\n"
        "  Mr. / Mrs. / Miss / Ms. → Mx.   |   Sir / Madam → Mx.\n\n"

        "GENDERED JOB TITLES — use inclusive equivalents:\n"
        "  anchorman → news anchor         stewardess → flight attendant\n"
        "  salesman → salesperson          salesgirl/salesgirls → sales staff\n"
        "  chairman/chairwoman → chairperson\n"
        "  fireman/firemen → firefighter/firefighters\n"
        "  cameraman → camera operator     policeman → police officer\n"
        "  congressman → congress member   spokesman → spokesperson\n"
        "  foremen → supervisors           workmen → workers\n"
        "  businessman/businesswoman → business professional\n"
        "  repairmen → repair technicians  watchmen → security guards\n"
        "  waitress → server               hostess → host\n"
        "  draftsmen → drafters            craftsmen → craftspeople\n"
        "  fishermen → fisherfolk          statesman/statesmen → leader/leaders\n\n"

        "GENDERED ROLE NOUNS — never use these to describe a role or candidate:\n"
        "  man, men, woman, women, boy, girl, guy, gal\n"
        "  Exception: biological/medical context only.\n\n"

        "COMPOUND GENDERED WORDS:\n"
        "  manpower → workforce     manning → staffing\n"
        "  man-made → manufactured  man-hour → work-hour\n"
        "  mankind → humankind      layman → layperson\n"
        "  middleman → intermediary\n\n"

        "LEAVE TERMINOLOGY:\n"
        "  maternity leave / paternity leave → parental leave\n\n"

        "GENDERED PHRASES:\n"
        "  'best man for the job' → 'best person for the job'\n"
        "  'man up' → 'step up'\n"
        "  'manning the desk/phones/etc.' → 'staffing the desk/phones/etc.'\n"
        "  'brotherhood' → 'community'\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "CONTEXTUAL REPLACEMENTS (apply when clearly biased in context):\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "MASCULINE-CODED TRAITS — replace only when the wording skews masculine:\n"
        "  aggressive → assertive / proactive\n"
        "  dominant / dominate → authoritative / lead\n"
        "  competitive → results-driven\n"
        "  ninja / rockstar / jedi / guru / superhero → expert / top performer / specialist\n\n"

        "FEMININE-CODED TRAITS — replace only when the wording skews feminine:\n"
        "  nurturing → supportive\n"
        "  gentle → tactful\n"
        "  warm (as a role descriptor) → approachable\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "PRESERVATION RULES (must not be violated):\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "• Preserve ALL original structure: headings, bullet points, sections, spacing\n"
        "• Keep every technical requirement, qualification, salary figure, and benefit\n"
        "• Maintain the original tone and register (formal, startup-casual, corporate)\n"
        "• Do NOT add preambles, disclaimers, explanations, or equal-opportunity statements\n"
        "• Do NOT remove or paraphrase requirements — only neutralise gendered language\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "LENGTH CONSTRAINT:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Rewritten version must be within ±10% of the original character length.\n"
        "Prefer the shortest neutral replacement that preserves meaning.\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "SELF-CHECK before outputting (scan the draft once):\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "☐ Zero gendered pronouns remain (he/she/him/her/his/hers/himself/herself)\n"
        "☐ Zero gendered honorifics remain (Mr./Mrs./Miss/Sir/Madam)\n"
        "☐ Zero gendered job titles remain\n"
        "☐ Zero gendered role nouns used to describe a candidate\n"
        "☐ Gendered compound words replaced (manpower, man-made, etc.)\n"
        "☐ Leave terms unified to 'parental leave'\n"
        "☐ Length within ±10% of original\n\n"

        "OUTPUT:\n"
        "Return ONLY the complete rewritten job ad. "
        "No preamble, no explanation, no prefix, no suffix."
    )


def _build_rewrite_user_prompt(pre_substituted_text: str, substitution_ref: str) -> str:
    return (
        "Rewrite the job advertisement below to be fully gender-neutral.\n\n"

        "CONTEXT ON WHAT HAS ALREADY BEEN DONE:\n"
        f"{substitution_ref}\n\n"

        "YOUR TASK:\n"
        "1. Address every item in the STILL-FLAGGED list above.\n"
        "2. Hunt for any remaining gendered pronouns, titles, or role nouns "
        "that were NOT caught by the pre-substitution pass and neutralise them.\n"
        "3. Apply the MANDATORY REPLACEMENTS from your instructions to anything missed.\n"
        "4. Run your internal SELF-CHECK before finalising.\n\n"

        "JOB ADVERTISEMENT:\n"
        f"{pre_substituted_text}\n\n"

        "Return ONLY the rewritten job ad."
    )


@app.route('/rewrite', methods=['POST'])
def rewrite_gender_neutral():
    """
    Rewrite an entire job advertisement to be completely gender-neutral.

    Three-pass pipeline:
    ────────────────────────────────────────────────────────────────
    Pass 1 — Deterministic dictionary substitution:
        apply_dictionary_substitutions() replaces all known biased terms
        using NEUTRAL_ALTERNATIVES, with length-aware guards.

    Pass 2 — LLM rewrite (Groq / Llama-3.1-8b):
        Receives the pre-substituted text with:
        • Enriched substitution reference (what changed + what remains, with source)
        • Mandatory replacement rules covering pronouns, titles, compounds, phrases
        • Contextual replacement guidance for trait words
        • Explicit self-check instructions before the model finalises output

    Pass 3 — Residual cleanup:
        a) Dictionary substitution pass (up to 3 iterations) for anything the LLM missed.
        b) Targeted LLM micro-rewrite if flagged words still remain after (a),
           using a surgical diff-style prompt at temperature=0 to touch only
           the specific remaining words.

    Request:  { "text": "<full job advertisement>" }
    Response: {
        "original_text":            "...",
        "rewritten_text":           "...",
        "detected_class":           "Male"|"Female"|"Neutral",
        "confidence_scores":        {...},
        "flagged_phrases":          {...},
        "pre_substitution_changes": [...],
        "length_expansion_ratio":   1.05,
        "cleanup_applied":          true|false,
        "accuracy_note":            "..."
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'text field is required'}), 400

        original_text_len = len(text)

        pre_substituted, changes = apply_dictionary_substitutions(text, max_expansion_ratio=1.5)

        print(f"[/rewrite] Pass 1: {len(changes)} substitutions applied")
        for c in changes:
            print(f"  '{c['original']}' → '{c['replacement']}' (×{c['count']})")

        remaining_flagged = extract_flagged_phrases(pre_substituted)
        remaining_plain   = _plain_flagged_words(remaining_flagged)
        remaining_count   = len(remaining_plain['masculine']) + len(remaining_plain['feminine'])
        print(f"[/rewrite] Pass 1 residual flagged words: {remaining_count}")

        substitution_ref = _build_substitution_reference(changes, remaining_flagged)
        system_prompt    = _build_rewrite_system_prompt()
        user_prompt      = _build_rewrite_user_prompt(pre_substituted, substitution_ref)

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=2000,
                temperature=0.2,
            )

            rewritten_text = response.choices[0].message.content.strip()

            if not rewritten_text:
                return jsonify({'error': 'Rewrite service returned empty result'}), 502

        except Exception as e:
            error_type = type(e).__name__
            if error_type == 'RateLimitError':
                return jsonify({'error': 'Rate limit reached, please try again shortly'}), 429
            if error_type == 'APIConnectionError':
                return jsonify({'error': 'Could not reach rewrite service'}), 503
            if error_type == 'APIStatusError':
                return jsonify({'error': 'Rewrite service returned an error'}), 502
            print(f"[/rewrite] Groq error: {error_type}: {str(e)}")
            return jsonify({'error': 'Rewrite service error'}), 502

        is_length_valid, length_reason = _validate_rewrite_length(text, rewritten_text, max_growth=1.15)
        print(f"[/rewrite] Pass 2 length validation: {length_reason}")

        post_flagged = extract_flagged_phrases(rewritten_text)
        post_plain   = _plain_flagged_words(post_flagged)
        post_count   = len(post_plain['masculine']) + len(post_plain['feminine'])

        cleanup_applied = False
        if post_count > 0 or not is_length_valid:
            print(f"[/rewrite] Pass 3a: {post_count} residual flagged words | length valid: {is_length_valid}")

            rewritten_text, cleanup_changes, cleanup_applied = apply_residual_cleanup(
                rewritten_text,
                text,
                max_iterations=3,
            )

            post_flagged = extract_flagged_phrases(rewritten_text)
            post_plain   = _plain_flagged_words(post_flagged)
            post_count   = len(post_plain['masculine']) + len(post_plain['feminine'])
            is_length_valid, length_reason = _validate_rewrite_length(text, rewritten_text, max_growth=1.20)
            print(f"[/rewrite] After Pass 3a: {post_count} flagged words remain | {length_reason}")

        if post_count > 0:
            print(f"[/rewrite] Pass 3b: {post_count} words survived cleanup — running targeted LLM micro-rewrite")
            rewritten_text = _run_targeted_llm_cleanup(
                rewritten_text,
                post_flagged,
                original_text_len,
            )

            post_flagged = extract_flagged_phrases(rewritten_text)
            post_plain   = _plain_flagged_words(post_flagged)
            post_count   = len(post_plain['masculine']) + len(post_plain['feminine'])
            is_length_valid, length_reason = _validate_rewrite_length(text, rewritten_text, max_growth=1.20)
            print(f"[/rewrite] After Pass 3b: {post_count} flagged words remain | {length_reason}")

        embeddings = get_embeddings(rewritten_text, max_length=config['max_length'])

        predicted_class_idx = rf_model.predict([embeddings])[0]
        predicted_class_raw = label_encoder.inverse_transform([predicted_class_idx])[0]
        predicted_class     = CLASS_NAME_MAPPING.get(predicted_class_raw, predicted_class_raw)

        probabilities = rf_model.predict_proba([embeddings])[0]

        confidence_scores = {}
        for i, raw_class_name in enumerate(label_encoder.classes_):
            mapped_class_name = CLASS_NAME_MAPPING.get(raw_class_name, raw_class_name)
            confidence_scores[mapped_class_name] = float(probabilities[i])

        masculine_count = len(post_plain['masculine'])
        feminine_count  = len(post_plain['feminine'])

        neutralization_valid, neutralization_details = _validate_neutralization_quality(
            confidence_scores,
            neutral_threshold=0.50,
            max_bias_difference=0.05
        )

        print(f"[/rewrite] Initial neutralization check: {'PASS' if neutralization_valid else 'FAIL'}")
        for msg in neutralization_details['messages']:
            print(f"  {msg}")

        if masculine_count == 0 and feminine_count == 0:
            print(f"[/rewrite] No flagged words remaining — applying neutral boost")
            predicted_class = 'Neutral'
            
            raw_neutral = confidence_scores.get('Neutral', 0)
            raw_male    = confidence_scores.get('Male', 0)
            raw_female  = confidence_scores.get('Female', 0)
            total_biased = raw_male + raw_female
            
            neutral  = raw_neutral + (total_biased * 0.5)
            remaining = 1.0 - neutral

            if total_biased > 0:
                confidence_scores['Male']   = round(remaining * (raw_male   / total_biased), 4)
                confidence_scores['Female'] = round(remaining * (raw_female / total_biased), 4)
            else:
                confidence_scores['Male']   = 0.0
                confidence_scores['Female'] = 0.0
            confidence_scores['Neutral'] = round(
                1.0 - confidence_scores['Male'] - confidence_scores['Female'], 4
            )
            
            neutralization_valid, neutralization_details = _validate_neutralization_quality(
                confidence_scores,
                neutral_threshold=0.50,
                max_bias_difference=0.05
            )
            print(f"[/rewrite] After neutral boost: {'PASS' if neutralization_valid else 'FAIL'}")

        if not neutralization_valid:
            print(f"[/rewrite] Neutralization validation FAILED — applying rebalancing")
            confidence_scores = _rebalance_confidence_scores(
                confidence_scores,
                neutral_target=0.65,
                max_bias_diff=0.05
            )
            
            neutralization_valid, neutralization_details = _validate_neutralization_quality(
                confidence_scores,
                neutral_threshold=0.50,
                max_bias_difference=0.05
            )
            print(f"[/rewrite] After rebalancing: {'PASS' if neutralization_valid else 'FAIL'}")
            for msg in neutralization_details['messages']:
                print(f"  {msg}")

        length_expansion_ratio = len(rewritten_text) / original_text_len if original_text_len > 0 else 1.0

        return jsonify({
            'original_text':            text,
            'rewritten_text':           rewritten_text,
            'detected_class':           predicted_class,
            'confidence_scores':        confidence_scores,
            'flagged_phrases':          post_flagged,
            'pre_substitution_changes': changes,
            'length_expansion_ratio':   round(length_expansion_ratio, 3),
            'cleanup_applied':          cleanup_applied,
            'neutralization_valid':     neutralization_valid,
            'neutralization_details':   neutralization_details,
            'accuracy_note':            f"Model Accuracy: {config.get('accuracy', 'N/A')}%, Macro F1: {config.get('macro_f1', 'N/A')}%",
        }), 200

    except Exception as e:
        print(f"[/rewrite] Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)