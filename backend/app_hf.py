"""
AdJust Bias Detection API - Hugging Face Spaces Edition
Integrates Random Forest for bias classification with Gradio UI

This file merges app.py (full backend logic) with the Gradio interface
for deployment on Hugging Face Spaces.
"""
import os
import json
import pickle
import joblib
import numpy as np
import re
import csv
import gradio as gr
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from groq import Groq
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()

load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Load model config
config_path = os.path.join(os.path.dirname(__file__), 'models', 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

print(f"[Model Config] Loaded configuration from {config_path}")
print(f"  - RoBERTa Model: {config.get('roberta_model', 'N/A')}")
print(f"  - Max Length: {config.get('max_length', 'N/A')}")
print(f"  - Classes: {config.get('classes', [])}")
print(f"  - Accuracy: {config.get('accuracy', 'N/A')}%")
print(f"  - Macro F1: {config.get('macro_f1', 'N/A')}%")

# Load models
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

# Load word dictionary
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

# Load RoBERTa
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
    neutral_words = {w for w, e in WORD_DICTIONARY.items() if e['label'] == 'neutral'}

    SUFFIX_PAIRS = [
        (r'man$',   'person'),
        (r'men$',   'people'),
        (r'woman$', 'person'),
        (r'women$', 'people'),
        (r'man\b',  'person'),
        (r'men\b',  'people'),
        (r'ess$',   ''),
        (r'ette$',  ''),
        (r'rix$',   'r'),
        (r'tress$', 'tor'),
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
        'he': 'they', 'him': 'them', 'his': 'their', 'himself': 'themselves',
        'she': 'they', 'her': 'their', 'hers': 'theirs', 'herself': 'themselves',
        'mr.': 'mx.', 'mrs.': 'mx.', 'miss': 'mx.', 'madam': 'mx.', 'sir': 'mx.',
        'man': 'person', 'men': 'people', 'woman': 'person', 'women': 'people',
        'guy': 'person', 'gal': 'person', 'girl': 'person', 'boy': 'person',
        'businessman': 'business professional', 'businesswoman': 'business professional',
        'chairman': 'chairperson', 'chairwoman': 'chairperson',
        'cameraman': 'camera operator', 'fireman': 'firefighter',
        'firemen': 'firefighters', 'policeman': 'police officer',
        'congressman': 'congress member', 'salesman': 'salesperson',
        'salesgirls': 'sales staff', 'spokesman': 'spokesperson',
        'foremen': 'supervisors', 'workmen': 'workers',
        'repairmen': 'repair technicians', 'watchmen': 'security guards',
        'stewardess': 'flight attendant', 'hostess': 'host',
        'waitress': 'server', 'manpower': 'workforce', 'manning': 'staffing',
        'man-made': 'manufactured', 'man-hour': 'work-hour',
        'mankind': 'humankind', 'layman': 'layperson',
        'middleman': 'intermediary', 'anchorman': 'news anchor',
        'weatherman': 'weather reporter', 'draftsmen': 'drafters',
        'craftsmen': 'craftspeople', 'lumbermen': 'lumbercutters',
        'fishermen': 'fisherfolk', 'statesman': 'leader',
        'statesmen': 'leaders', 'pressmen': 'press operators',
        'janitor': 'facilities staff', 'busboys': 'support staff',
        'master': 'expert', 'masterful': 'skilled',
        'mastermind': 'strategist', 'masterplan': 'strategic plan',
        'aggressive': 'proactive', 'assertive': 'confident',
        'ambitious': 'goal-oriented', 'analytical': 'systematic',
        'autonomous': 'independent-minded', 'boast': 'highlight achievements',
        'challenging': 'engaging', 'charismatic': 'compelling',
        'competitive': 'results-driven', 'confident': 'assured',
        'courageous': 'resilient', 'decisive': 'clear-thinking',
        'determined': 'committed', 'dominant': 'authoritative',
        'dominate': 'lead', 'driven': 'motivated', 'dynamic': 'energetic',
        'eager': 'enthusiastic', 'effective': 'capable',
        'efficient': 'productive', 'empower': 'enable',
        'energetic': 'engaged', 'enthusiastic': 'passionate',
        'excel': 'succeed', 'exceptional': 'outstanding',
        'exciting': 'rewarding', 'fast-paced': 'dynamic', 'firm': 'consistent',
        'force': 'strength', 'forward thinking': 'future-focused',
        'greedy': 'highly motivated', 'hands on': 'practical',
        'hard-working': 'diligent', 'headstrong': 'focused',
        'hierarch': 'senior leader', 'high quality': 'excellent',
        'hostile': 'assertive', 'impulsive': 'decisive',
        'independent': 'self-directed', 'individual': 'candidate',
        'initiative': 'proactiveness', 'innovative': 'creative',
        'inspirational': 'motivating', 'intellect': 'expertise',
        'lead': 'guide', 'limitless': 'boundless', 'logic': 'reasoning',
        'negotiating': 'discussing', 'ninja': 'expert', 'outspoken': 'direct',
        'outstanding': 'excellent', 'passion': 'enthusiasm',
        'penetrate': 'enter', 'pioneer': 'innovator', 'practical': 'hands-on',
        'pragmatic': 'solution-focused', 'proactive': 'self-directed',
        'problem solving': 'critical thinking', 'productive': 'efficient',
        'resilient': 'adaptable', 'resolve': 'determination',
        'resourcefulness': 'ingenuity', 'risk': 'opportunity',
        'rockstar': 'top performer', 'self-confident': 'assured',
        'self-driven': 'self-directed', 'self-motivated': 'intrinsically motivated',
        'self-reliant': 'self-sufficient', 'self-starter': 'motivated professional',
        'self-sufficient': 'independent', 'serious': 'professional',
        'skilled': 'capable', 'strong': 'capable', 'stubborn': 'tenacious',
        'superior': 'leading', 'tackle': 'address', 'talented': 'skilled',
        'tough': 'resilient', 'world-class': 'exceptional', 'guru': 'specialist',
        'jedi': 'expert', 'hacker': 'developer', 'superhero': 'high performer',
        'combat': 'address', 'can-do': 'solution-oriented',
        'additional hours': 'extended hours', 'after hours': 'extended hours',
        'night shifts': 'evening shifts', 'overtime': 'additional hours',
        'live-in': 'on-site', 'multisite': 'multi-location',
        'international travel': 'global travel', 'location change': 'relocation',
        'accurate': 'precise', 'administrative': 'operational',
        'affectionate': 'warm', 'agreeable': 'cooperative',
        'attentive': 'detail-focused', 'caring': 'supportive',
        'cheerful': 'positive', 'collaborative': 'team-oriented',
        'commit': 'dedicate', 'committed': 'dedicated',
        'communal': 'team-based', 'compassion': 'empathy',
        'compassionate': 'empathetic', 'considerate': 'thoughtful',
        'cooperative': 'collaborative', 'creative': 'innovative',
        'dedicated': 'committed', 'depend': 'rely', 'emotional': 'expressive',
        'empathetic': 'understanding', 'flexible': 'adaptable',
        'follow': 'implement', 'friendly': 'approachable',
        'gentle': 'tactful', 'honest': 'transparent', 'humble': 'modest',
        'interpersonal': 'collaborative', 'kind': 'considerate',
        'listening': 'active listening', 'loyal': 'dedicated',
        'modesty': 'professionalism', 'nurturing': 'supportive',
        'organized': 'structured', 'organizational': 'administrative',
        'patient': 'composed', 'people skills': 'communication skills',
        'person-centered': 'client-focused', 'persuasive': 'influential',
        'pleasant': 'approachable', 'polite': 'professional',
        'quiet': 'composed', 'responsible': 'accountable',
        'sensitive': 'perceptive', 'social skills': 'interpersonal skills',
        'soft skills': 'professional skills', 'support': 'assist',
        'sympathetic': 'understanding', 'tender': 'thoughtful',
        'thoughtful': 'considerate', 'trust': 'reliability',
        'understand': 'comprehend', 'warm': 'approachable',
        'welcome': 'inclusive',
        "a man's home is his castle": "one's home is one's sanctuary",
        'best man for the job': 'best person for the job',
        'brotherhood': 'community', 'brotherhood of man': 'human community',
        'every man for himself': 'every person for themselves',
        'founding fathers': 'founders',
        "gentlemen's agreement": 'unwritten agreement',
        'lord and lady': 'titled individuals',
        'man on the street': 'ordinary person', 'man up': 'step up',
        'one man show': 'solo operation', 'to a man': 'unanimously',
        'childcare vouchers': 'childcare support',
        'commission package': 'compensation package',
        'contracted hours': 'scheduled hours', 'family friendly': 'flexible',
        'family values': 'inclusive values',
        'flexible benefits': 'comprehensive benefits',
        'guaranteed hours': 'confirmed hours',
        'maternity leave': 'parental leave', 'paternity leave': 'parental leave',
        'parental leave': 'parental leave',
        'monday to friday': 'standard weekday schedule',
        'part time': 'part-time schedule', 'permanent': 'long-term',
        'regular hours': 'standard hours',
        'relocation package': 'relocation support',
        'remote work': 'flexible working arrangements',
        'work life balance': 'well-being support',
        'sickness cover': 'health coverage', 'holiday cover': 'leave coverage',
        'fixed term': 'contract-based', 'evenings': 'evening availability',
        'different areas': 'multiple locations',
        'different locations': 'multiple locations',
        'on-site visits': 'field visits',
    }

    return {**generated, **CURATED}


NEUTRAL_ALTERNATIVES = _build_neutral_alternatives_from_dict()
print(f"[Rewrite] Neutral alternatives map built: {len(NEUTRAL_ALTERNATIVES)} entries")


def extract_flagged_phrases(text: str) -> dict:
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


def apply_dictionary_substitutions(text: str, max_expansion_ratio: float = 1.5) -> tuple:
    changes = []
    result  = text

    sorted_terms = sorted(NEUTRAL_ALTERNATIVES.keys(), key=len, reverse=True)

    for biased_term in sorted_terms:
        neutral_term = NEUTRAL_ALTERNATIVES[biased_term]

        orig_len = len(biased_term)
        new_len  = len(neutral_term)

        if orig_len <= 3 and new_len > orig_len + 2:
            continue
        elif orig_len > 3 and new_len > orig_len * max_expansion_ratio:
            continue

        if ' ' in biased_term or '-' in biased_term:
            pattern = re.compile(re.escape(biased_term), re.IGNORECASE)
        else:
            pattern = re.compile(r'\b' + re.escape(biased_term) + r'\b', re.IGNORECASE)

        def _replace(match):
            original = match.group(0)
            if original.isupper():
                return neutral_term.upper()
            if original.istitle():
                return neutral_term.title()
            return neutral_term

        new_result, n = pattern.subn(_replace, result)
        if n > 0:
            changes.append({'original': biased_term, 'replacement': neutral_term, 'count': n})
            result = new_result

    return result, changes


def summarise_job_ad_context(full_text: str) -> str:
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
                        "1. Job title\n2. Industry / sector\n"
                        "3. Key responsibilities (max 10 words)\n"
                        "4. Tone (e.g. formal, casual, corporate, startup)\n"
                        "5. Any specific audience signals (e.g. fresh grad, senior, technical)\n\n"
                        "Return ONLY these five lines. No extra commentary."
                    )
                },
                {"role": "user", "content": full_text[:3000]}
            ],
            max_tokens=120,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[summarise_job_ad_context] Failed: {e}")
        return ""


def lookup_dictionary_suggestion(term: str, bias_type: str):
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


def _build_substitution_reference(changes: list, remaining_flagged: dict) -> str:
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


def _validate_rewrite_length(original: str, rewritten: str, max_growth: float = 1.15) -> tuple:
    orig_len     = len(original)
    new_len      = len(rewritten)
    growth_ratio = new_len / orig_len if orig_len > 0 else 1.0
    if growth_ratio > max_growth:
        excess = (growth_ratio - 1) * 100
        return False, f"Excessive expansion: {excess:.1f}% over limit ({new_len} chars vs {orig_len} original)"
    return True, f"Length OK: {growth_ratio:.2f}x ({new_len}/{orig_len} chars)"


def apply_residual_cleanup(text: str, original_text: str, max_iterations: int = 3) -> tuple:
    current_text       = text
    all_cleanup_changes = []

    for iteration in range(max_iterations):
        flagged       = extract_flagged_phrases(current_text)
        flagged_count = len(flagged['masculine']) + len(flagged['feminine'])

        if flagged_count == 0:
            break

        next_text, changes = apply_dictionary_substitutions(current_text, max_expansion_ratio=1.3)

        if not changes:
            break

        is_valid, _ = _validate_rewrite_length(original_text, next_text, max_growth=1.20)
        if not is_valid:
            break

        current_text = next_text
        all_cleanup_changes.extend(changes)

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
        "   aggressive→assertive or focused | nurturing→caring or supportive\n"
        "   Note: NOT every adjective needs replacement. Replace only if genuinely biased.\n\n"
        "5. GENDERED PHRASES:\n"
        "   'best man for the job'→'best person for the job'\n"
        "   'manpower'→'workforce'  |  'manning'→'staffing'\n\n"
        "6. LEAVE TERMINOLOGY: maternity/paternity leave→parental leave\n\n"
        "PRESERVATION RULES:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "• Keep original structure, formatting, bullet points, sections\n"
        "• Preserve ALL technical requirements, qualifications, salary, benefits\n"
        "• Maintain tone and register (formal, casual, corporate, startup)\n"
        "• Keep length similar to original (avoid verbose expansion)\n"
        "• Do NOT add preambles, explanations, or disclaimers\n\n"
        "LENGTH CONSTRAINT: Rewritten version should be ±10% of original length.\n\n"
        "OUTPUT: Return ONLY the complete rewritten job ad. No preamble or explanation."
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
        "☐ No he/she/him/her/his/hers pronouns\n"
        "☐ No gendered job titles\n"
        "☐ No gendered role nouns\n"
        "☐ No obviously biased trait words\n"
        "☐ Length similar to original\n\n"
        "Return ONLY the rewritten job ad."
    )


# ==================== GRADIO INTERFACE ====================

def detect_bias_interface(text: str):
    """Gradio interface for bias detection"""
    if not text or text.strip() == "":
        return "Error", "No text provided", "{}"

    try:
        embeddings  = get_embeddings(text)
        prediction  = rf_model.predict([embeddings])[0]
        proba       = rf_model.predict_proba([embeddings])[0]

        detected_class         = label_encoder.inverse_transform([prediction])[0]
        detected_class_display = CLASS_NAME_MAPPING.get(detected_class, detected_class.title())

        confidence_scores = {
            CLASS_NAME_MAPPING.get(label, label.title()): float(score)
            for label, score in zip(label_encoder.classes_, proba)
        }

        flagged_phrases = extract_flagged_phrases(text)

        result_str = f"Detected Bias: {detected_class_display}\n\nConfidence Scores:\n"
        for label, score in confidence_scores.items():
            result_str += f"  {label}: {score:.2%}\n"
        result_str += f"\nFlagged masculine words: {flagged_phrases['masculine']}"
        result_str += f"\nFlagged feminine words:  {flagged_phrases['feminine']}"

        return detected_class_display, result_str, json.dumps(confidence_scores, indent=2)
    except Exception as e:
        return "Error", f"Error during detection: {str(e)}", "{}"


def rewrite_interface(text: str) -> str:
    """Gradio interface for rewriting text to be gender-neutral"""
    if not text or text.strip() == "":
        return "No text provided"

    try:
        # Pass 1: dictionary substitutions
        pre_substituted, changes = apply_dictionary_substitutions(text, max_expansion_ratio=1.5)

        # Pass 2: Groq LLM rewrite
        remaining_flagged = extract_flagged_phrases(pre_substituted)
        substitution_ref  = _build_substitution_reference(changes, remaining_flagged)
        system_prompt     = _build_rewrite_system_prompt()
        user_prompt       = _build_rewrite_user_prompt(pre_substituted, substitution_ref)

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

        # Cleanup pass
        post_flagged  = extract_flagged_phrases(rewritten_text)
        post_count    = len(post_flagged['masculine']) + len(post_flagged['feminine'])
        if post_count > 0:
            rewritten_text, _, _ = apply_residual_cleanup(rewritten_text, text, max_iterations=3)

        return rewritten_text

    except Exception as e:
        return f"Error during rewriting: {str(e)}"


# Create Gradio interface
with gr.Blocks(title="AdJust - Bias Detection Tool") as demo:
    gr.Markdown("""
    # AdJust: Gender Bias Detection in Job Descriptions
    This tool helps identify and remove gender bias from job advertisements using Machine Learning and AI.
    **Features:** 🔍 Detect gender bias (Masculine, Feminine, or Neutral) | ✏️ Rewrite to gender-neutral | 📊 View confidence scores
    """)

    with gr.Tab("Detect Bias"):
        gr.Markdown("### Analyze text for gender bias")
        text_input  = gr.Textbox(label="Job Description", placeholder="Paste your job description here...", lines=5)
        detect_btn  = gr.Button("Detect Bias", variant="primary")
        with gr.Row():
            bias_output   = gr.Textbox(label="Detected Bias", interactive=False)
            scores_output = gr.Textbox(label="Confidence Scores (JSON)", interactive=False)
        result_text = gr.Textbox(label="Detailed Results", interactive=False, lines=6)
        detect_btn.click(detect_bias_interface, inputs=[text_input], outputs=[bias_output, result_text, scores_output])

    with gr.Tab("Rewrite to Neutral"):
        gr.Markdown("### Rewrite your text to be completely gender-neutral")
        rewrite_input  = gr.Textbox(label="Original Text", placeholder="Paste your job description here...", lines=8)
        rewrite_btn    = gr.Button("Rewrite", variant="primary")
        rewrite_output = gr.Textbox(label="Gender-Neutral Version", interactive=False, lines=8)
        rewrite_btn.click(rewrite_interface, inputs=[rewrite_input], outputs=[rewrite_output])

    gr.Markdown("---\n**About AdJust:** Random Forest + RoBERTa embeddings for gender-coded language detection in Philippine job postings.")


# ==================== FLASK API ENDPOINTS ====================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'model': {
            'roberta_model': config.get('roberta_model'),
            'accuracy': config.get('accuracy'),
            'macro_f1': config.get('macro_f1'),
        },
        'dictionary': {
            'total_words': len(WORD_DICTIONARY),
            'masculine_keywords': len(_MASCULINE_KEYWORDS),
            'feminine_keywords': len(_FEMININE_KEYWORDS),
            'neutral_alternatives': len(NEUTRAL_ALTERNATIVES),
        }
    })


@app.route('/detect', methods=['POST'])
def detect_bias():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'text field is required'}), 400

        embeddings          = get_embeddings(text, max_length=config['max_length'])
        predicted_class_idx = rf_model.predict([embeddings])[0]
        predicted_class_raw = label_encoder.inverse_transform([predicted_class_idx])[0]
        predicted_class     = CLASS_NAME_MAPPING.get(predicted_class_raw, predicted_class_raw)
        probabilities       = rf_model.predict_proba([embeddings])[0]

        confidence_scores = {
            CLASS_NAME_MAPPING.get(raw, raw): float(prob)
            for raw, prob in zip(label_encoder.classes_, probabilities)
        }

        flagged_phrases = extract_flagged_phrases(text)

        if predicted_class == 'Male' and len(flagged_phrases['masculine']) == 0 and confidence_scores.get('Neutral', 0) > 0.25:
            predicted_class = 'Neutral'
        elif predicted_class == 'Female' and len(flagged_phrases['feminine']) == 0 and confidence_scores.get('Neutral', 0) > 0.25:
            predicted_class = 'Neutral'

        return jsonify({
            'detected_class':   predicted_class,
            'confidence_scores': confidence_scores,
            'flagged_phrases':  flagged_phrases,
            'accuracy_note':    f"Model Accuracy: {config.get('accuracy', 'N/A')}%, Macro F1: {config.get('macro_f1', 'N/A')}%",
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/suggest', methods=['POST'])
def suggest_alternative():
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
            return jsonify({
                'term': term, 'suggestion': dict_suggestion,
                'context_aware': len(context) > 0, 'source': 'validated_dictionary',
            }), 200

        ad_summary = summarise_job_ad_context(full_text) if full_text else ""

        bias_label = (
            'a masculine-coded word (stereotypically associated with male characteristics)'
            if bias_type == 'masculine'
            else 'a feminine-coded word (stereotypically associated with female characteristics)'
        )
        ad_block = f"\n\nJob advertisement context:\n{ad_summary}\n" if ad_summary else ""

        user_message = (
            f"In the following job advertisement, the term '{term}' is {bias_label}.{ad_block}\n"
            f"Specific sentence: \"{context}\"\n\n"
            f"Suggest ONE gender-neutral alternative (2-3 words max) that directly replaces '{term}'. "
            f"Output ONLY the alternative. No explanation."
        ) if context else (
            f"The term '{term}' is {bias_label}.{ad_block}\n"
            f"Suggest ONE gender-neutral alternative (2-3 words max). Output ONLY the alternative."
        )

        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": (
                    "You are an expert in gender-neutral language for Philippine job advertisements. "
                    "Respond with ONLY the single alternative word or phrase. No explanation."
                )},
                {"role": "user", "content": user_message}
            ],
            max_tokens=20,
            temperature=0.3,
        )

        suggestion = response.choices[0].message.content.strip().strip('"\'').rstrip('.!,?').lower()
        if suggestion == term.lower() or any(c.isdigit() for c in suggestion) or len(suggestion.split()) > 4:
            suggestion = ""

        return jsonify({
            'term': term, 'suggestion': suggestion,
            'context_aware': len(context) > 0, 'ad_aware': bool(ad_summary),
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 502


@app.route('/batch-detect', methods=['POST'])
def batch_detect():
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

            embeddings          = get_embeddings(text, max_length=config['max_length'])
            predicted_class_idx = rf_model.predict([embeddings])[0]
            predicted_class_raw = label_encoder.inverse_transform([predicted_class_idx])[0]
            predicted_class     = CLASS_NAME_MAPPING.get(predicted_class_raw, predicted_class_raw)
            probabilities       = rf_model.predict_proba([embeddings])[0]

            confidence_scores = {
                CLASS_NAME_MAPPING.get(raw, raw): float(prob)
                for raw, prob in zip(label_encoder.classes_, probabilities)
            }
            flagged_phrases = extract_flagged_phrases(text)

            if predicted_class == 'Male' and len(flagged_phrases['masculine']) == 0 and confidence_scores.get('Neutral', 0) > 0.25:
                predicted_class = 'Neutral'
            elif predicted_class == 'Female' and len(flagged_phrases['feminine']) == 0 and confidence_scores.get('Neutral', 0) > 0.25:
                predicted_class = 'Neutral'

            results.append({
                'text': text, 'detected_class': predicted_class,
                'confidence_scores': confidence_scores, 'flagged_phrases': flagged_phrases,
            })

        return jsonify({'results': results}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/rewrite', methods=['POST'])
def rewrite_gender_neutral():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'text field is required'}), 400

        original_text_len    = len(text)
        pre_substituted, changes = apply_dictionary_substitutions(text, max_expansion_ratio=1.5)
        remaining_flagged    = extract_flagged_phrases(pre_substituted)
        substitution_ref     = _build_substitution_reference(changes, remaining_flagged)

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": _build_rewrite_system_prompt()},
                    {"role": "user",   "content": _build_rewrite_user_prompt(pre_substituted, substitution_ref)},
                ],
                max_tokens=2000,
                temperature=0.2,
            )
            rewritten_text = response.choices[0].message.content.strip()
            if not rewritten_text:
                return jsonify({'error': 'Rewrite service returned empty result'}), 502
        except Exception as e:
            return jsonify({'error': 'Rewrite service error'}), 502

        is_valid, _      = _validate_rewrite_length(text, rewritten_text, max_growth=1.15)
        post_flagged     = extract_flagged_phrases(rewritten_text)
        post_count       = len(post_flagged['masculine']) + len(post_flagged['feminine'])
        cleanup_applied  = False

        if post_count > 0 or not is_valid:
            rewritten_text, _, cleanup_applied = apply_residual_cleanup(rewritten_text, text, max_iterations=3)
            post_flagged = extract_flagged_phrases(rewritten_text)

        embeddings          = get_embeddings(rewritten_text, max_length=config['max_length'])
        predicted_class_idx = rf_model.predict([embeddings])[0]
        predicted_class_raw = label_encoder.inverse_transform([predicted_class_idx])[0]
        predicted_class     = CLASS_NAME_MAPPING.get(predicted_class_raw, predicted_class_raw)
        probabilities       = rf_model.predict_proba([embeddings])[0]

        confidence_scores = {
            CLASS_NAME_MAPPING.get(raw, raw): float(prob)
            for raw, prob in zip(label_encoder.classes_, probabilities)
        }

        if len(post_flagged['masculine']) == 0 and len(post_flagged['feminine']) == 0:
            predicted_class = 'Neutral'

        return jsonify({
            'original_text':            text,
            'rewritten_text':           rewritten_text,
            'detected_class':           predicted_class,
            'confidence_scores':        confidence_scores,
            'flagged_phrases':          post_flagged,
            'pre_substitution_changes': changes,
            'length_expansion_ratio':   round(len(rewritten_text) / original_text_len, 3),
            'cleanup_applied':          cleanup_applied,
            'accuracy_note':            f"Model Accuracy: {config.get('accuracy', 'N/A')}%, Macro F1: {config.get('macro_f1', 'N/A')}%",
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    # Launch Gradio on HF Spaces (port 7860)
    demo.launch(server_name="0.0.0.0", server_port=7860)