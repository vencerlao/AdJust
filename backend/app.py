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
      (e.g. 'businessman' → 'business executive', 'anchorman' → 'anchorperson')
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
        {"masculine": ["word1", ...], "feminine": ["word1", ...]}
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

    masculine = sorted({kw for kw in _MASCULINE_KEYWORDS if _matches(kw)})
    feminine  = sorted({kw for kw in _FEMININE_KEYWORDS  if _matches(kw)})

    return {'masculine': masculine, 'feminine': feminine}


def apply_dictionary_substitutions(text: str, max_expansion_ratio: float = 1.5) -> tuple[str, list[dict]]:
    """
    Apply validated neutral substitutions directly from NEUTRAL_ALTERNATIVES
    before sending the text to Groq, with intelligent length preservation.

    Strategy:
    - Longer / multi-word phrases are matched first to avoid partial clobbering.
    - Preserves original capitalisation (Title Case, ALL CAPS, lowercase).
    - Word-boundary regex prevents substring false-positives for single words.
    - SKIP replacements that expand length excessively (> max_expansion_ratio)
    
    Args:
        text: The input text to process
        max_expansion_ratio: Max allowed length expansion (default 1.5x). 
                            E.g., "it" (2 chars) won't replace with something >3 chars.

    Returns:
        (substituted_text, list_of_changes)
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

        confidence_scores = {}
        for i, raw_class_name in enumerate(label_encoder.classes_):
            mapped_class_name = CLASS_NAME_MAPPING.get(raw_class_name, raw_class_name)
            confidence_scores[mapped_class_name] = float(probabilities[i])

        flagged_phrases = extract_flagged_phrases(text)

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
    

def _build_substitution_reference(changes: list[dict], remaining_flagged: dict) -> str:
    """
    Build a concise substitution reference block to inject into the Groq prompt.
    Tells Groq exactly what was already changed and what still needs attention.
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
        for w in remaining_m[:20]:
            alt = NEUTRAL_ALTERNATIVES.get(w, "<find neutral alternative>")
            lines.append(f"  • [masculine] \"{w}\" → suggest: \"{alt}\"")
        for w in remaining_f[:20]:
            alt = NEUTRAL_ALTERNATIVES.get(w, "<find neutral alternative>")
            lines.append(f"  • [feminine]  \"{w}\" → suggest: \"{alt}\"")

    return "\n".join(lines)


def _validate_rewrite_length(original: str, rewritten: str, max_growth: float = 1.15) -> tuple[bool, str]:
    """
    Validate that the rewritten text doesn't expand excessively.
    
    Returns:
        (is_valid, reason)
    where is_valid=True if expansion is acceptable, False if too verbose.
    
    Args:
        original: Original text
        rewritten: Rewritten text
        max_growth: Max allowed growth ratio (default 1.15 = 15% expansion)
    """
    orig_len = len(original)
    new_len = len(rewritten)
    
    growth_ratio = new_len / orig_len if orig_len > 0 else 1.0
    
    if growth_ratio > max_growth:
        excess = ((growth_ratio - 1) * 100)
        return False, f"Excessive expansion: {excess:.1f}% over limit ({new_len} chars vs {orig_len} original)"
    
    return True, f"Length OK: {growth_ratio:.2f}x ({new_len}/{orig_len} chars)"


def apply_residual_cleanup(text: str, original_text: str, max_iterations: int = 3) -> tuple[str, list[dict], bool]:
    """
    Apply cleanup passes to remove any remaining biased words detected after LLM rewrite.
    
    Validates that cleanup doesn't cause excessive expansion.
    
    Returns:
        (cleaned_text, cleanup_changes, was_successful)
    """
    current_text = text
    all_cleanup_changes = []
    
    for iteration in range(max_iterations):
        flagged = extract_flagged_phrases(current_text)
        flagged_count = len(flagged['masculine']) + len(flagged['feminine'])
        
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


def _build_rewrite_system_prompt() -> str:
    return (
        "You are an expert in gender-neutral language for job advertisements "
        "in the Philippine market. Your goal: rewrite job ads to be inclusive and neutral.\n\n"

        "CRITICAL RULES (apply rigorously but conservatively):\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "1. PRONOUNS: he→they, she→they, him→them, her→them, his→their, hers→theirs\n"
        "   Use singular 'they' consistently.\n\n"

        "2. GENDERED JOB TITLES:\n"
        "   anchorman→news anchor  |  stewardess→flight attendant\n"
        "   salesman→salesperson   |  chairman→chairperson\n"
        "   fireman→firefighter    |  cameraman→camera operator\n"
        "   businessman→business professional\n\n"

        "3. AVOID GENDERED ROLE NOUNS:\n"
        "   Don't use 'man', 'woman', 'girl', 'boy' to describe roles.\n"
        "   Exception: biological context (pregnancy, childcare) — use anatomically accurate terms.\n\n"

        "4. TRAIT WORDS (minimal substitution — only when context requires):\n"
        "   If a trait word appears biased in context, replace conservatively:\n"
        "   aggressive→assertive or focused (choose shortest neutral form)\n"
        "   nurturing→caring or supportive (preserve meaning)\n"
        "   Note: NOT every adjective needs replacement. Replace only if genuinely biased.\n\n"

        "5. GENDERED PHRASES:\n"
        "   'best man for the job'→'best person for the job'\n"
        "   'manpower'→'workforce'  |  'manning'→'staffing'\n\n"

        "6. LEAVE TERMINOLOGY:\n"
        "   maternity/paternity leave→parental leave\n\n"

        "PRESERVATION RULES:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "• Keep original structure, formatting, bullet points, sections\n"
        "• Preserve ALL technical requirements, qualifications, salary, benefits\n"
        "• Maintain tone and register (formal, casual, corporate, startup)\n"
        "• Keep length similar to original (avoid verbose expansion)\n"
        "• Do NOT add preambles, explanations, or disclaimers\n\n"

        "LENGTH CONSTRAINT:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Rewritten version should be ±10% of original length.\n"
        "Never expand short phrases into verbose alternatives.\n\n"

        "OUTPUT:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Return ONLY the complete rewritten job ad. No preamble, explanation, or prefix."
    )


def _build_rewrite_user_prompt(pre_substituted_text: str, substitution_ref: str) -> str:
    return (
        "Rewrite this job advertisement to be gender-neutral. "
        "Apply the rules conservatively—only replace genuinely biased language.\n\n"
        
        "ALREADY SUBSTITUTED (do NOT undo):\n"
        f"{substitution_ref}\n\n"
        
        "ORIGINAL TEXT:\n"
        f"{pre_substituted_text}\n"
        
        "QUICK CHECKLIST before finalizing:\n"
        "☐ No he/she/him/her/his/hers/himself/herself pronouns\n"
        "☐ No gendered job titles (anchorman, stewardess, salesman, etc.)\n"
        "☐ No gendered role nouns (man, woman, girl, boy as roles)\n"
        "☐ No obviously biased trait words (aggressive, nurturing, etc.)\n"
        "☐ Gendered phrases replaced (best man→best person, manpower→workforce)\n"
        "☐ Length similar to original (no excessive expansion)\n\n"
        
        "Return ONLY the rewritten job ad."
    )


@app.route('/rewrite', methods=['POST'])
def rewrite_gender_neutral():
    """
    Rewrite an entire job advertisement to be completely gender-neutral.

    Improvement: two-pass pipeline with length validation
    ───────────────────────────────────────────────────────
    Pass 1 (deterministic):
        apply_dictionary_substitutions() replaces known biased terms using
        the validated NEUTRAL_ALTERNATIVES map, with length-aware filtering
        to prevent excessive text expansion.

    Pass 2 (LLM):
        Groq receives the pre-substituted text with:
        - Explicit guidance to preserve length (±10% of original)
        - List of already-substituted terms (to prevent undoing)
        - Structured prompt with essential rules only (not comprehensive)

    Validation:
        After LLM rewrite, check length expansion. If rewritten text expanded >15%,
        apply targeted cleanup with expansion guards.

    Request:  { "text": "<full job advertisement>" }
    Response: {
        "original_text": "...",
        "rewritten_text": "...",
        "detected_class": "Male"|"Female"|"Neutral",
        "confidence_scores": {...},
        "flagged_phrases": {...},
        "pre_substitution_changes": [...],
        "length_expansion_ratio": 1.05,
        "cleanup_applied": true|false,
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

        original_text_len = len(text)

        pre_substituted, changes = apply_dictionary_substitutions(text, max_expansion_ratio=1.5)

        print(f"[/rewrite] Pass 1: {len(changes)} substitutions applied")
        for c in changes:
            print(f"  '{c['original']}' → '{c['replacement']}' (×{c['count']})")

        remaining_flagged = extract_flagged_phrases(pre_substituted)
        remaining_count   = len(remaining_flagged['masculine']) + len(remaining_flagged['feminine'])
        print(f"[/rewrite] Pass 1 residual flagged words: {remaining_count}")

        substitution_ref  = _build_substitution_reference(changes, remaining_flagged)
        system_prompt     = _build_rewrite_system_prompt()
        user_prompt       = _build_rewrite_user_prompt(pre_substituted, substitution_ref)

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
        print(f"[/rewrite] Length validation: {length_reason}")

        post_flagged = extract_flagged_phrases(rewritten_text)
        post_count   = len(post_flagged['masculine']) + len(post_flagged['feminine'])
        
        cleanup_applied = False
        if post_count > 0 or not is_length_valid:
            print(f"[/rewrite] Residual flagged words: {post_count} | Length valid: {is_length_valid}")
            print(f"[/rewrite] Running targeted cleanup...")
            
            rewritten_text, cleanup_changes, cleanup_applied = apply_residual_cleanup(
                rewritten_text, 
                text,
                max_iterations=3
            )
            
            post_flagged = extract_flagged_phrases(rewritten_text)
            post_count   = len(post_flagged['masculine']) + len(post_flagged['feminine'])
            is_length_valid, length_reason = _validate_rewrite_length(text, rewritten_text, max_growth=1.20)
            print(f"[/rewrite] After cleanup: {post_count} flagged words remain | {length_reason}")

        embeddings = get_embeddings(rewritten_text, max_length=config['max_length'])

        predicted_class_idx = rf_model.predict([embeddings])[0]
        predicted_class_raw = label_encoder.inverse_transform([predicted_class_idx])[0]
        predicted_class     = CLASS_NAME_MAPPING.get(predicted_class_raw, predicted_class_raw)

        probabilities = rf_model.predict_proba([embeddings])[0]

        confidence_scores = {}
        for i, raw_class_name in enumerate(label_encoder.classes_):
            mapped_class_name = CLASS_NAME_MAPPING.get(raw_class_name, raw_class_name)
            confidence_scores[mapped_class_name] = float(probabilities[i])

        masculine_count = len(post_flagged['masculine'])
        feminine_count  = len(post_flagged['feminine'])

        if masculine_count == 0 and feminine_count == 0:
            predicted_class = 'Neutral'
            raw_neutral = confidence_scores.get('Neutral', 0)
            raw_male = confidence_scores.get('Male', 0)
            raw_female = confidence_scores.get('Female', 0)
            total = raw_neutral + raw_male + raw_female 
            total_biased = raw_male + raw_female
            neutral = raw_neutral + (total_biased * 0.5)
            remaining = 1.0 - neutral

            if total_biased > 0:
                confidence_scores['Male']    = round(remaining * (raw_male / total_biased), 4)
                confidence_scores['Female']  = round(remaining * (raw_female / total_biased), 4)
            else:
                confidence_scores['Male']   = 0.0
                confidence_scores['Female'] = 0.0
            confidence_scores['Neutral'] = round(
                1.0 - confidence_scores['Male'] - confidence_scores['Female'], 4
            )

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
            'accuracy_note':            f"Model Accuracy: {config.get('accuracy', 'N/A')}%, Macro F1: {config.get('macro_f1', 'N/A')}%",
        }), 200

    except Exception as e:
        print(f"[/rewrite] Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)