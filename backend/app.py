"""
AdJust Bias Detection API
Integrates Random Forest for bias classification
"""
import os
import json
import pickle
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter Web

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
    """
    Generate embeddings for text using RoBERTa if available, else TF-IDF
    """
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
            
            # Pad to 770 dimensions (RF model expects this)
            if len(embeddings) < 770:
                embeddings = np.pad(embeddings, (0, 770 - len(embeddings)), 'constant')
            elif len(embeddings) > 770:
                embeddings = embeddings[:770]
            
            return embeddings
        except Exception as e:
            print(f"Error generating RoBERTa embeddings: {e}")
            return generate_tfidf_embeddings(text)
    else:
        return generate_tfidf_embeddings(text)


def generate_tfidf_embeddings(text, dim=770):
    """
    Generate TF-IDF based embeddings as fallback
    Pads to match RF model input dimension (770)
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    
    vectorizer = TfidfVectorizer(max_features=100, lowercase=True)
    try:
        embedding = vectorizer.fit_transform([text]).toarray()[0]
    except:
        embedding = np.zeros(100)
    
    # Pad to 770 dimensions to match RF model
    if len(embedding) < dim:
        embedding = np.pad(embedding, (0, dim - len(embedding)), 'constant')
    else:
        embedding = embedding[:dim]
    
    return embedding.flatten()


def extract_flagged_phrases(text, detected_class):
    """
    Extract potentially biased phrases/words based on detected class
    This is a simple implementation - enhance based on your needs
    """
    bias_keywords = {
        'female_biased': [
            'she', 'her', 'girl', 'woman', 'mother', 'nurse', 'secretary',
            'beautiful', 'pretty', 'emotional', 'nurturing', 'caring'
        ],
        'male_biased': [
            'he', 'him', 'boy', 'man', 'father', 'engineer', 'doctor',
            'strong', 'intelligent', 'aggressive', 'leader', 'ambitious'
        ],
        'neutral': []
    }
    
    flagged = []
    text_lower = text.lower()
    
    for keyword in bias_keywords.get(detected_class, []):
        if keyword in text_lower:
            flagged.append(keyword)
    
    return list(set(flagged))  # Remove duplicates


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'model': config.get('label_status', 'baseline'),
        'classes': config.get('classes', [])
    })


@app.route('/detect', methods=['POST'])
def detect_bias():
    """
    Main bias detection endpoint (Simplified)
    
    Request body:
    {
        "text": "Your text here"
    }
    """
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({'error': 'Text field is required'}), 400
        
        # Generate embeddings
        embeddings = get_embeddings(text, max_length=config['max_length'])
        
        # Make prediction
        predicted_class_idx = rf_model.predict([embeddings])[0]
        predicted_class = label_encoder.inverse_transform([predicted_class_idx])[0]
        
        # Get confidence scores
        probabilities = rf_model.predict_proba([embeddings])[0]
        confidence_scores = {
            label_encoder.inverse_transform([i])[0]: float(prob)
            for i, prob in enumerate(probabilities)
        }
        
        # Extract flagged phrases
        flagged_phrases = extract_flagged_phrases(text, predicted_class)
        
        response = {
            'detected_class': predicted_class,
            'confidence_scores': confidence_scores,
            'flagged_phrases': flagged_phrases,
            'accuracy_note': f"Baseline model accuracy: {config.get('accuracy', 'n/a')}%"
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/batch-detect', methods=['POST'])
def batch_detect():
    """
    Batch detection for multiple texts
    
    Request body:
    {
        "texts": ["text1", "text2", ...]
    }
    """
    try:
        data = request.get_json()
        texts = data.get('texts', [])
        
        if not texts or not isinstance(texts, list):
            return jsonify({'error': 'texts array is required'}), 400
        
        results = []
        for text in texts:
            if text.strip():
                embeddings = get_embeddings(text, max_length=config['max_length'])
                predicted_class_idx = rf_model.predict([embeddings])[0]
                predicted_class = label_encoder.inverse_transform([predicted_class_idx])[0]
                
                probabilities = rf_model.predict_proba([embeddings])[0]
                confidence_scores = {
                    label_encoder.inverse_transform([i])[0]: float(prob)
                    for i, prob in enumerate(probabilities)
                }
                
                results.append({
                    'text': text,
                    'detected_class': predicted_class,
                    'confidence_scores': confidence_scores,
                    'flagged_phrases': extract_flagged_phrases(text, predicted_class)
                })
        
        return jsonify({'results': results}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
