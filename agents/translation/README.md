# Translation Service

English to Arabic translation service using transformer models (MarianMT).

## Features

- **English to Arabic Translation**: Uses Helsinki-NLP's `opus-mt-en-ar` model
- **Arabic Text Reshaping**: Automatically reshapes Arabic text for proper display
- **Singleton Pattern**: Efficient model loading and reuse
- **GPU Support**: Automatically uses GPU if available, falls back to CPU

## Usage

### API Endpoint

```bash
POST /chat/api/translate/
Content-Type: application/json

{
  "text": "Hello, how are you?",
  "source_lang": "en",
  "target_lang": "ar"
}
```

**Response:**
```json
{
  "success": true,
  "original_text": "Hello, how are you?",
  "translated_text": "مرحبا، كيف حالك؟",
  "source_lang": "en",
  "target_lang": "ar"
}
```

### Python Code

```python
from agents.translation.translation_service import TranslationService

# Get singleton instance
service = TranslationService.get_instance()

# Translate text
english_text = "Hello, how are you?"
arabic_text = service.translate(english_text)
print(arabic_text)  # "مرحبا، كيف حالك؟"
```

## Model

- **Model**: `Helsinki-NLP/opus-mt-en-ar`
- **Type**: MarianMT (Transformer-based)
- **Size**: ~300MB (downloads automatically on first use)
- **Quality**: High-quality English to Arabic translation

## Configuration

You can change the model by setting the environment variable:

```bash
export TRANSLATION_MODEL="Helsinki-NLP/opus-mt-en-ar"
```

Other available models:
- `Helsinki-NLP/opus-mt-en-ar` (default, recommended)
- `facebook/mbart-large-50-many-to-many-mmt` (larger, slower, more languages)

## Dependencies

- `transformers` (already in requirements.txt)
- `torch` (already in requirements.txt)
- `sentencepiece` (for tokenization, added to requirements.txt)
- `arabic-reshaper` (already in requirements.txt)

## Installation

The model will be automatically downloaded from Hugging Face on first use. Make sure you have:

1. Internet connection for first download
2. Sufficient disk space (~300MB for the model)
3. GPU (optional, but recommended for faster inference)

## Notes

- First translation may take longer due to model loading
- Model is loaded lazily (only when first translation is requested)
- Model stays in memory for subsequent translations (singleton pattern)
- Arabic text is automatically reshaped for proper display

