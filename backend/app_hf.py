"""
AdJust Bias Detection API - Hugging Face Spaces Edition
Integrates Random Forest for bias classification with Gradio UI
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
        print(f"[Dictionary] Loaded {len(WORD_DICTIONARY)} words")
    except Exception as e:
        print(f"[Dictionary] Error loading dictionary: {e}")
        WORD_DICTIONARY = {}

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


def get_embeddings(text, max_length=512):
    """Generate embeddings matching training pipeline: 768-dim mean-pooled RoBERTa + norm_token_length + VADER compound"""
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


# ==================== GRADIO INTERFACE ====================

def detect_bias_interface(text: str) -> tuple[str, str, str]:
    """Gradio interface for bias detection"""
    if not text or text.strip() == "":
        return "Error", "No text provided", "{}"
    
    try:
        embeddings = get_embeddings(text)
        prediction = rf_model.predict([embeddings])[0]
        proba = rf_model.predict_proba([embeddings])[0]
        
        detected_class = label_encoder.inverse_transform([prediction])[0]
        detected_class_display = CLASS_NAME_MAPPING.get(detected_class, detected_class.title())
        
        confidence_scores = {
            CLASS_NAME_MAPPING.get(label, label.title()): float(score)
            for label, score in zip(label_encoder.classes_, proba)
        }
        
        # Find flagged phrases
        flagged_phrases = {"masculine": [], "feminine": []}
        words = text.lower().split()
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in _MASCULINE_KEYWORDS:
                flagged_phrases["masculine"].append(clean_word)
            elif clean_word in _FEMININE_KEYWORDS:
                flagged_phrases["feminine"].append(clean_word)
        
        result_str = f"Detected Bias: {detected_class_display}\n\nConfidence Scores:\n"
        for label, score in confidence_scores.items():
            result_str += f"  {label}: {score:.2%}\n"
        
        return detected_class_display, result_str, json.dumps(confidence_scores, indent=2)
    except Exception as e:
        return "Error", f"Error during detection: {str(e)}", "{}"


def rewrite_interface(text: str) -> str:
    """Gradio interface for rewriting text to be gender-neutral"""
    if not text or text.strip() == "":
        return "No text provided"
    
    try:
        from app import rewrite_gender_neutral_text
        rewritten = rewrite_gender_neutral_text(text)
        return rewritten
    except Exception as e:
        return f"Error during rewriting: {str(e)}"


# Create Gradio interface
with gr.Blocks(title="AdJust - Bias Detection Tool") as demo:
    gr.Markdown("""
    # AdJust: Gender Bias Detection in Job Descriptions
    
    This tool helps identify and remove gender bias from job advertisements using Machine Learning and AI.
    
    **Features:**
    - 🔍 Detect gender bias (Masculine, Feminine, or Neutral)
    - ✏️ Rewrite job ads to be gender-neutral
    - 📊 View confidence scores and flagged terms
    """)
    
    with gr.Tab("Detect Bias"):
        gr.Markdown("### Analyze text for gender bias")
        text_input = gr.Textbox(
            label="Job Description",
            placeholder="Paste your job description here...",
            lines=5
        )
        detect_btn = gr.Button("Detect Bias", variant="primary")
        
        with gr.Row():
            bias_output = gr.Textbox(label="Detected Bias", interactive=False)
            scores_output = gr.Textbox(label="Confidence Scores", interactive=False)
        
        result_text = gr.Textbox(label="Detailed Results", interactive=False, lines=5)
        
        detect_btn.click(
            detect_bias_interface,
            inputs=[text_input],
            outputs=[bias_output, result_text, scores_output]
        )
    
    with gr.Tab("Rewrite to Neutral"):
        gr.Markdown("### Rewrite your text to be completely gender-neutral")
        rewrite_input = gr.Textbox(
            label="Original Text",
            placeholder="Paste your job description here...",
            lines=8
        )
        rewrite_btn = gr.Button("Rewrite", variant="primary")
        
        rewrite_output = gr.Textbox(
            label="Gender-Neutral Version",
            interactive=False,
            lines=8
        )
        
        rewrite_btn.click(
            rewrite_interface,
            inputs=[rewrite_input],
            outputs=[rewrite_output]
        )
    
    gr.Markdown("""
    ---
    **About AdJust:** This tool uses Random Forest classification and RoBERTa embeddings to detect gender-coded language patterns in job postings. 
    The Groq AI API helps generate more contextually appropriate rewrites.
    """)


# ==================== FLASK API ENDPOINTS ====================
# These endpoints are also available for programmatic access

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'model': {
            'roberta_model': config.get('roberta_model'),
            'accuracy': config.get('accuracy'),
            'macro_f1': config.get('macro_f1'),
        }
    })


@app.route('/detect', methods=['POST'])
def detect_bias():
    """Detect bias in text"""
    data = request.get_json()
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    try:
        embeddings = get_embeddings(text)
        prediction = rf_model.predict([embeddings])[0]
        proba = rf_model.predict_proba([embeddings])[0]
        
        detected_class = label_encoder.inverse_transform([prediction])[0]
        
        confidence_scores = {
            label: float(score)
            for label, score in zip(label_encoder.classes_, proba)
        }
        
        flagged_phrases = {"masculine": [], "feminine": []}
        words = text.lower().split()
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in _MASCULINE_KEYWORDS:
                flagged_phrases["masculine"].append(clean_word)
            elif clean_word in _FEMININE_KEYWORDS:
                flagged_phrases["feminine"].append(clean_word)
        
        return jsonify({
            'detected_class': CLASS_NAME_MAPPING.get(detected_class, detected_class),
            'confidence_scores': confidence_scores,
            'flagged_phrases': flagged_phrases,
            'accuracy_note': f"Model accuracy: {config.get('accuracy')}%",
            'model_version': 'HF-Space-v1'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    # For Hugging Face Spaces, expose the Gradio interface
    demo.launch(server_name="0.0.0.0", server_port=7860)
