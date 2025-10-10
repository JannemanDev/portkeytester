#!/usr/bin/env python3
"""
Portkey AI Gateway Test Script
A CLI tool to test multiple models through the Portkey AI gateway.
"""

import sys
import time
from typing import List, Optional, Tuple, Dict, Any
from portkey_ai import Portkey
from colorama import Fore, Style, init

# Initialize colorama for cross-platform color support
init(autoreset=True)


def print_banner():
    """Print a fancy banner because why not."""
    print("\n" + "="*60)
    print(f"{Fore.CYAN}🔑 Portkey AI Gateway Tester{Style.RESET_ALL}")
    print("="*60 + "\n")


def get_api_key() -> str:
    """Prompt user for Portkey API key."""
    api_key = input("Enter your Portkey API key: ").strip()
    if not api_key:
        print(f"{Fore.RED}❌ Error: API key cannot be empty.{Style.RESET_ALL}")
        sys.exit(1)
    return api_key


def get_config_id() -> Optional[str]:
    """Prompt user for optional config ID."""
    config_id = input("Enter config ID (optional, press Enter to skip): ").strip()
    return config_id if config_id else None


def get_model_slugs() -> List[str]:
    """Prompt user for model slugs (comma-separated)."""
    models_input = input("Enter model slugs (comma-separated): ").strip()
    if not models_input:
        print(f"{Fore.RED}❌ Error: At least one model slug is required.{Style.RESET_ALL}")
        sys.exit(1)
    
    # Split by comma and clean up whitespace
    model_slugs = [slug.strip() for slug in models_input.split(',') if slug.strip()]
    
    if not model_slugs:
        print(f"{Fore.RED}❌ Error: No valid model slugs provided.{Style.RESET_ALL}")
        sys.exit(1)
    
    return model_slugs


def detect_endpoint_type(model_slug: str) -> str:
    """
    Detect which endpoint to use based on model slug.
    
    Args:
        model_slug: Model identifier
    
    Returns:
        'embeddings' or 'chat'
    """
    if 'embed' in model_slug.lower():
        return 'embeddings'
    return 'chat'


def test_chat_completion(client: Portkey, model_slug: str) -> Tuple[bool, Dict[str, Any]]:
    """Test chat completion endpoint."""
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Respond briefly."
            },
            {
                "role": "user",
                "content": "Say 'Hello' if you can hear me."
            }
        ],
        model=model_slug,
        max_tokens=50
    )
    
    if response and hasattr(response, 'choices') and len(response.choices) > 0:
        first_choice = response.choices[0]
        content = first_choice.message.content if hasattr(first_choice.message, 'content') else 'No content'
        
        return True, {
            'endpoint': 'chat',
            'content': content,
            'model': response.model if hasattr(response, 'model') else 'Unknown',
            'usage': response.usage if hasattr(response, 'usage') else None
        }
    
    return False, {'endpoint': 'chat', 'error': 'Invalid response structure'}


def test_embeddings(client: Portkey, model_slug: str) -> Tuple[bool, Dict[str, Any]]:
    """Test embeddings endpoint."""
    response = client.embeddings.create(
        input=["This is a test embedding request."],  # Must be a list for most providers
        model=model_slug
    )
    
    if response and hasattr(response, 'data') and len(response.data) > 0:
        embedding = response.data[0].embedding
        dimension = len(embedding) if hasattr(embedding, '__len__') else 'Unknown'
        
        return True, {
            'endpoint': 'embeddings',
            'dimension': dimension,
            'model': response.model if hasattr(response, 'model') else 'Unknown',
            'usage': response.usage if hasattr(response, 'usage') else None
        }
    
    return False, {'endpoint': 'embeddings', 'error': 'Invalid response structure'}


def test_model(client: Portkey, model_slug: str) -> bool:
    """
    Test a single model by auto-detecting and using the appropriate endpoint.
    
    Args:
        client: Initialized Portkey client
        model_slug: Model identifier to test
    
    Returns:
        True if test successful, False otherwise
    """
    print(f"\n{Fore.CYAN}🧪 Testing model: {model_slug}{Style.RESET_ALL}")
    print("-" * 60)
    
    # Auto-detect endpoint type
    primary_endpoint = detect_endpoint_type(model_slug)
    fallback_endpoint = 'chat' if primary_endpoint == 'embeddings' else 'embeddings'
    
    try:
        # Measure response time
        start_time = time.time()
        
        # Try primary endpoint
        success = False
        result = {}
        
        try:
            if primary_endpoint == 'chat':
                success, result = test_chat_completion(client, model_slug)
            else:
                success, result = test_embeddings(client, model_slug)
        except Exception as primary_error:
            # Try fallback endpoint
            print(f"   {Fore.YELLOW}⚠️  Primary endpoint ({primary_endpoint}) failed, trying {fallback_endpoint}...{Style.RESET_ALL}")
            try:
                if fallback_endpoint == 'chat':
                    success, result = test_chat_completion(client, model_slug)
                else:
                    success, result = test_embeddings(client, model_slug)
            except Exception as fallback_error:
                # Both failed, raise the original error
                raise primary_error
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Check for successful response
        if success:
            print(f"{Fore.GREEN}✅ Response Success! API Key is working.{Style.RESET_ALL}")
            print(f"   Requested model: {model_slug}")
            print(f"   Endpoint used: {result['endpoint']}")
            print(f"   Response from model: {result['model']}")
            print(f"   ⏱️  Response time: {response_time:.2f}s")
            print(f"   {Fore.CYAN}➜ Please verify this is the correct routing for your config.{Style.RESET_ALL}")
            print(f"")
            
            # Show endpoint-specific info
            if result['endpoint'] == 'chat':
                print(f"   Sample response: {result['content'][:100]}...")
            else:
                print(f"   Embedding dimension: {result['dimension']}")
            
            if result.get('usage'):
                print(f"   Tokens used: {result['usage']}")
            
            return True
        else:
            print(f"{Fore.RED}❌ Failed: {result.get('error', 'Unknown error')}{Style.RESET_ALL}")
            return False
            
    except Exception as e:
        print(f"{Fore.RED}❌ Error: {type(e).__name__}{Style.RESET_ALL}")
        print(f"   Message: {str(e)}")
        
        # Check for HTTP-related error attributes
        if hasattr(e, 'status_code'):
            print(f"   HTTP Status: {e.status_code}")
        
        # Get response body if available (avoid duplication with error.body)
        if hasattr(e, 'response') and not hasattr(e, 'body'):
            try:
                response_body = e.response
                if hasattr(response_body, 'text'):
                    print(f"   Response Body: {response_body.text[:500]}")
                elif hasattr(response_body, 'json'):
                    print(f"   Response JSON: {response_body.json()}")
                else:
                    print(f"   Response: {str(response_body)[:500]}")
            except:
                pass
        
        # Check for Portkey-specific error metadata
        if hasattr(e, 'body') and e.body:
            print(f"   Details: {e.body}")
        
        # Show additional error attributes
        error_attrs = ['code', 'type', 'param']
        for attr in error_attrs:
            if hasattr(e, attr) and getattr(e, attr):
                print(f"   {attr.capitalize()}: {getattr(e, attr)}")
        
        return False


def main():
    """Main execution flow."""
    print_banner()
    
    # Get user inputs
    api_key = get_api_key()
    config_id = get_config_id()
    model_slugs = get_model_slugs()
    
    # Initialize Portkey client
    print(f"\n{Fore.CYAN}🔧 Initializing Portkey client...{Style.RESET_ALL}")
    
    client_kwargs = {"api_key": api_key}
    if config_id:
        client_kwargs["config"] = config_id
        print(f"   Using config ID: {config_id}")
    
    client = Portkey(**client_kwargs)
    
    # Test each model
    print(f"\n{Fore.CYAN}📊 Testing {len(model_slugs)} model(s)...{Style.RESET_ALL}")
    
    results = {}
    for model_slug in model_slugs:
        results[model_slug] = test_model(client, model_slug)
    
    # Summary
    print("\n" + "="*60)
    print(f"{Fore.CYAN}📋 TEST SUMMARY{Style.RESET_ALL}")
    print("="*60)
    
    successful = sum(1 for success in results.values() if success)
    failed = len(results) - successful
    
    for model, success in results.items():
        if success:
            print(f"  {Fore.GREEN}✅ PASS{Style.RESET_ALL} - {model}")
        else:
            print(f"  {Fore.RED}❌ FAIL{Style.RESET_ALL} - {model}")
    
    if failed == 0:
        print(f"\n{Fore.GREEN}Total: {successful} passed, {failed} failed{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}Total: {successful} passed, {failed} failed{Style.RESET_ALL}")
    print("="*60 + "\n")
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}⚠️  Test interrupted by user.{Style.RESET_ALL}")
        sys.exit(130)

