# Gemini LLM Setup for Member 2

## Overview

Member 2 now supports Google Gemini as a real LLM provider (in addition to Groq and OpenRouter).

## Getting Started with Gemini

### Step 1: Get Gemini API Key

1. Go to: https://aistudio.google.com/app/apikeys
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated API key

### Step 2: Install Gemini Package

```bash
pip install google-generativeai
```

Or install via requirements:

```bash
pip install -r requirements/member2.txt
```

### Step 3: Set Environment Variables

```bash
export RESOLVEONE_LLM_PROVIDER=gemini
export GEMINI_API_KEY=your_actual_gemini_key_here
export RESOLVEONE_LLM_MODEL=gemini-1.5-flash
export RESOLVEONE_LLM_TIMEOUT_SECONDS=30
```

### Step 4: Run Tests with Gemini

```bash
cd /home/labuser/Desktop/Persistent_Folder/hackathon/Capstone

# Run all Member 2 tests with Gemini
python -m pytest tests/chat/ -v

# Or run evaluation
python -m chat.evaluation
```

## Configuration Options

### Environment Variables

| Variable | Value | Default |
|----------|-------|---------|
| `RESOLVEONE_LLM_PROVIDER` | `gemini` | `groq` |
| `GEMINI_API_KEY` | Your API key | Required |
| `RESOLVEONE_LLM_MODEL` | Model ID | `gemini-1.5-flash` |
| `RESOLVEONE_LLM_TIMEOUT_SECONDS` | Timeout in seconds | `30` |

### Supported Models

- `gemini-1.5-flash` (recommended - fastest, free tier)
- `gemini-1.5-pro` (most capable)
- `gemini-1.0-pro` (older, still available)

## Quick Start Command

```bash
cd /home/labuser/Desktop/Persistent_Folder/hackathon/Capstone && \
export RESOLVEONE_LLM_PROVIDER=gemini && \
export GEMINI_API_KEY=your_key_here && \
export RESOLVEONE_LLM_MODEL=gemini-1.5-flash && \
python -m pytest tests/chat/ -v
```

## Using .env File (Optional)

Create `.env` file:

```bash
cat > .env << 'EOF'
RESOLVEONE_LLM_PROVIDER=gemini
GEMINI_API_KEY=your_actual_key_here
RESOLVEONE_LLM_MODEL=gemini-1.5-flash
RESOLVEONE_LLM_TIMEOUT_SECONDS=30
EOF
```

Load and run:

```bash
export $(cat .env | xargs)
python -m pytest tests/chat/ -v
```

## How It Works

The `chat/adapters/gemini_provider.py` implements:

1. **GeminiProvider** class - Handles API calls to Google Gemini
2. **Message conversion** - Converts OpenAI format to Gemini format
3. **JSON schema validation** - Ensures responses match expected Pydantic models
4. **Error handling** - Graceful fallback to FakeLLMProvider on errors

## Features

✅ Structured output (JSON schema validation)  
✅ Timeout enforcement  
✅ Token counting (estimated for free tier)  
✅ Error handling and fallback  
✅ Latency measurement  
✅ Full Member 2 compatibility  

## Troubleshooting

### Error: "Missing API key: GEMINI_API_KEY environment variable not set"

```bash
# Make sure key is set
echo $GEMINI_API_KEY

# If empty, set it
export GEMINI_API_KEY=your_key_here
```

### Error: "google.generativeai package required"

```bash
# Install the package
pip install google-generativeai
```

### Error: "Gemini response is not valid JSON"

- Gemini may wrap response in markdown code blocks
- The adapter handles this automatically
- If still failing, increase timeout

```bash
export RESOLVEONE_LLM_TIMEOUT_SECONDS=60
```

### Error: Timeout

```bash
# Gemini is slow on free tier, increase timeout
export RESOLVEONE_LLM_TIMEOUT_SECONDS=60
python -m pytest tests/chat/ -v
```

## Switching Between Providers

### Switch from Gemini to Groq

```bash
export RESOLVEONE_LLM_PROVIDER=groq
export GROQ_API_KEY=your_groq_key_here
python -m pytest tests/chat/ -v
```

### Switch to OpenRouter

```bash
export RESOLVEONE_LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=your_openrouter_key_here
python -m pytest tests/chat/ -v
```

### Switch to Fake (Offline Testing)

```bash
unset RESOLVEONE_LLM_PROVIDER
# Or set to non-existent provider to trigger fallback
python -m pytest tests/chat/ -v
```

## Test Results

When running with Gemini, all 31 tests should pass:

```
tests/chat/test_api.py::test_handle_explain_returns_explanation PASSED
tests/chat/test_api.py::test_handle_query_returns_query_result PASSED
tests/chat/test_api.py::test_handle_act_returns_proposed_action PASSED
...
tests/chat/test_guardrails.py::TestRunGuardrails::test_missing_citations_blocked PASSED

======================== 31 passed in X.XXs ========================
```

## Architecture

```
chat/adapters/gemini_provider.py
  ├── GeminiProvider
  │   ├── __init__() - Initialize with API key
  │   └── generate() - Call Gemini API with structured output
  └── get_gemini_provider() - Factory with fallback support

chat/adapters/__init__.py
  └── get_llm_provider() - Routes to Groq/OpenRouter/Gemini/Fake
```

## API Pricing

Gemini free tier includes:
- 60 requests per minute
- Limited tokens per request
- No credit card required

For production use:
- Pay-per-token pricing
- Higher rate limits
- Billing through Google Cloud

See: https://ai.google.dev/pricing

## Next Steps

1. ✅ Install `google-generativeai`
2. ✅ Get API key from https://aistudio.google.com/app/apikeys
3. ✅ Set environment variables
4. ✅ Run tests: `python -m pytest tests/chat/ -v`
5. ✅ Verify all 31 tests pass with Gemini

## References

- [Google AI Studio](https://aistudio.google.com)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [Pricing](https://ai.google.dev/pricing)
- [Models Documentation](https://ai.google.dev/models)
