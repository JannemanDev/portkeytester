# Portkey AI Gateway Tester

A command-line tool to test multiple models through the Portkey AI gateway using the Portkey Python SDK.

## Features

- 🔑 Test Portkey API keys
- 🎯 Support for multiple model slugs
- ⚙️ Optional config ID/header support
- 📊 Clear success/error reporting
- 🚀 Dynamic model routing via Portkey

## Installation

### Quick Setup (Recommended)

Run the automated setup script with `source` to keep the virtual environment activated:
```bash
source ./install.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Activate the virtual environment automatically

Alternatively, run without `source` to just set up without activating:
```bash
./install.sh
```

### Manual Setup

1. Clone or download this repository

2. (Optional) Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the script:
```bash
python test_portkey.py
```

The script will interactively prompt you for:

1. **Portkey API Key**: Your `x-portkey-api-key` value
2. **Config ID** (optional): Portkey config ID for virtual keys/routing rules
3. **Model Slugs**: Comma-separated list of model identifiers

### Example Session

```
🔑 Portkey AI Gateway Tester
============================================================

Enter your Portkey API key: pK2Zc0yDl4Mc+Engm1xQOfWWS5y0
Enter config ID (optional, press Enter to skip): 
Enter model slugs (comma-separated): mistral-medium, gpt-4, claude-3-opus

🔧 Initializing Portkey client...

📊 Testing 3 model(s)...

🧪 Testing model: mistral-medium
------------------------------------------------------------
✅ Success!
   Response: Hello! I can hear you loud and clear. How can I assist you today?
   Model used: mistral-medium
   Tokens used: CompletionUsage(completion_tokens=15, prompt_tokens=25, total_tokens=40)

🧪 Testing model: gpt-4
------------------------------------------------------------
✅ Success!
   Response: Hello!
   Model used: gpt-4
   Tokens used: CompletionUsage(completion_tokens=2, prompt_tokens=25, total_tokens=27)

...
```

## Example Model Slugs

Depending on your Portkey configuration, you can test various models:

- **OpenAI**: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`
- **Anthropic**: `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`
- **Mistral**: `mistral-medium`, `mistral-small`, `mistral-tiny`
- **Custom slugs**: Any model slug configured in your Portkey dashboard

## How It Works

1. The script initializes a Portkey client with your API key
2. For each model slug, it sends a test completion request
3. Portkey dynamically routes the request to the appropriate provider
4. The script validates the response and reports success/failure
5. A summary shows overall test results

## Plain HTTP/curl Examples

If you prefer not to use the Python SDK, you can test Portkey directly with HTTP requests:

### Basic Request with API Key

```bash
curl --request POST \
  --url https://api.portkey.ai/v1/chat/completions \
  --header 'content-type: application/json' \
  --header 'x-portkey-api-key: YOUR_API_KEY_HERE' \
  --data '{
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant."
      },
      {
        "role": "user",
        "content": "Say hello!"
      }
    ],
    "model": "mistral-medium"
  }'
```

### Request with Config ID

```bash
curl --request POST \
  --url https://api.portkey.ai/v1/chat/completions \
  --header 'content-type: application/json' \
  --header 'x-portkey-api-key: YOUR_API_KEY_HERE' \
  --header 'x-portkey-config: YOUR_CONFIG_ID' \
  --data '{
    "messages": [
      {
        "role": "user",
        "content": "Test message"
      }
    ],
    "model": "gpt-4"
  }'
```

### Testing Multiple Models (bash script)

```bash
#!/bin/bash

API_KEY="YOUR_API_KEY_HERE"
MODELS=("mistral-medium" "gpt-4" "claude-3-opus")

for model in "${MODELS[@]}"; do
  echo "Testing $model..."
  curl --request POST \
    --url https://api.portkey.ai/v1/chat/completions \
    --header 'content-type: application/json' \
    --header "x-portkey-api-key: $API_KEY" \
    --data "{
      \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}],
      \"model\": \"$model\"
    }"
  echo ""
done
```

## Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed
- `130`: User interrupted (Ctrl+C)

## Troubleshooting

**Invalid API Key**: Ensure your Portkey API key is correct and active

**Model Not Found**: Verify the model slug is configured in your Portkey dashboard

**Network Errors**: Check your internet connection and Portkey service status

**Config Errors**: If using a config ID, ensure it exists in your Portkey account

## Requirements

- Python 3.7+
- portkey-ai SDK

## License

Free to use for testing your Portkey configurations.

