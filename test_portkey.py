#!/usr/bin/env python3
"""
Portkey AI Gateway Test Script
A CLI tool to test multiple models through the Portkey AI gateway.
"""

import sys
import time
from typing import List, Optional, Tuple, Dict, Any
from portkey_ai import Portkey
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.syntax import Syntax
from rich.rule import Rule
from rich.pretty import Pretty
from rich.status import Status
import json
import os
import tempfile
import wave

# Initialize Rich console
console = Console()


def print_banner():
    """Print a fancy banner because why not."""
    console.print(Panel(
        "[bold cyan]🔑 Portkey AI Gateway Tester[/bold cyan]\n[dim]Professional API testing[/dim]",
        border_style="cyan",
        padding=(1, 2),
        expand=True
    ))


def get_api_key() -> str:
    """Prompt user for Portkey API key."""
    api_key = console.input("[bold]Enter your Portkey API key:[/bold] ").strip()
    if not api_key:
        console.print("[bold red]❌ Error: API key cannot be empty.[/bold red]")
        sys.exit(1)
    return api_key


def get_config_id() -> Optional[str]:
    """Prompt user for optional config ID."""
    config_id = console.input("[bold]Enter config ID[/bold] [dim](optional, press Enter to skip)[/dim]: ").strip()
    return config_id if config_id else None


def get_target_endpoint_type() -> Optional[str]:
    """Prompt user to select the target endpoint type."""
    console.print("\n[bold]Select Endpoint Type:[/bold]")
    console.print("1. [cyan]Chat Completions[/cyan] (default)")
    console.print("2. [cyan]Embeddings[/cyan]")
    console.print("3. [cyan]Text-to-Speech[/cyan] (TTS)")
    console.print("4. [cyan]Speech-to-Text[/cyan] (STT)")
    console.print("5. [dim]Auto-detect based on slug[/dim]")
    
    choice = console.input("[bold]Enter choice (1-5):[/bold] ").strip()
    
    if choice == '1':
        return 'chat'
    elif choice == '2':
        return 'embeddings'
    elif choice == '3':
        return 'tts'
    elif choice == '4':
        return 'stt'
    elif choice == '5':
        return None
    else:
        # Default to chat if invalid or empty (common behavior) or auto-detect?
        # Let's default to auto-detect for safety if they just hit enter without reading
        if not choice:
            return 'chat' # Default to chat as per menu
        return None

def get_model_slugs() -> List[str]:
    """Prompt user for model slugs (comma-separated)."""
    models_input = console.input("[bold]Enter model slugs[/bold] [dim](comma-separated)[/dim]: ").strip()
    if not models_input:
        console.print("[bold red]❌ Error: At least one model slug is required.[/bold red]")
        sys.exit(1)
    
    # Split by comma and clean up whitespace
    model_slugs = [slug.strip() for slug in models_input.split(',') if slug.strip()]
    
    if not model_slugs:
        console.print("[bold red]❌ Error: No valid model slugs provided.[/bold red]")
        sys.exit(1)
    
    return model_slugs


def get_endpoint_priorities(model_slug: str, forced_type: Optional[str] = None) -> List[str]:
    """
    Get a list of endpoints to try in order of priority based on model slug.
    
    Args:
        model_slug: Model identifier
        forced_type: Optional forced endpoint type ('chat', 'embeddings', 'tts', 'stt')
    
    Returns:
        List of endpoint strings ('chat', 'embeddings', 'tts', 'stt')
    """
    if forced_type:
        # Validate forced type
        valid_types = ['chat', 'embeddings', 'tts', 'stt']
        if forced_type in valid_types:
            return [forced_type]
        # If invalid, warn and fall back to auto-detect (or could error out)
        # For now, let's just fall back but maybe we should be strict
        pass

    slug = model_slug.lower()
    if 'embed' in slug:
        return ['embeddings', 'chat', 'tts', 'stt']
    if 'tts' in slug:
        return ['tts', 'chat', 'embeddings', 'stt']
    if 'whisper' in slug:
        return ['stt', 'chat', 'embeddings', 'tts']
    
    # Default priority
    return ['chat', 'embeddings', 'tts', 'stt']

def test_text_to_speech(client: Portkey, model_slug: str) -> Tuple[bool, Dict[str, Any]]:
    """Test text-to-speech endpoint."""
    response = client.audio.speech.create(
        model=model_slug,
        voice="alloy",
        input="Hello, this is a test of the Portkey Audio API."
    )
    
    # The response is a binary stream or object with content
    # For the SDK, it usually returns a response object where we can get bytes
    # Adjusting based on standard OpenAI-compatible SDK behavior which Portkey mimics
    
    content_length = 0
    if hasattr(response, 'content'):
        content_length = len(response.content)
    elif hasattr(response, 'read'):
        content_length = len(response.read())
    elif hasattr(response, 'response') and hasattr(response.response, 'content'):
         content_length = len(response.response.content)
    else:
        # Fallback for some SDK versions, try to cast to bytes if possible or check if it's iterable
        try:
            content_length = len(response)
        except:
            pass

    if content_length > 0:
        return True, {
            'endpoint': 'tts',
            'model': model_slug,
            'audio_size': content_length,
            'usage': None  # TTS usually doesn't return token usage in the same way
        }
    
    return False, {'endpoint': 'tts', 'error': 'No audio content received'}

def test_speech_to_text(client: Portkey, model_slug: str) -> Tuple[bool, Dict[str, Any]]:
    """Test speech-to-text endpoint."""
    # Create a temporary WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
        temp_filename = temp_audio.name
        
    try:
        # Generate 1 second of silence/simple audio
        with wave.open(temp_filename, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(44100)
            # Write 1 second of silence (zeros)
            wav_file.writeframes(b'\x00' * 44100 * 2)
            
        with open(temp_filename, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=model_slug,
                file=audio_file
            )
        
        if response and hasattr(response, 'text'):
            return True, {
                'endpoint': 'stt',
                'model': model_slug,
                'content': response.text,
                'usage': None
            }
            
        return False, {'endpoint': 'stt', 'error': 'Invalid response structure'}
        
    finally:
        # Cleanup
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)


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


def test_model(client: Portkey, model_slug: str, forced_type: Optional[str] = None, on_status_update=None) -> Tuple[bool, Dict[str, Any]]:
    """
    Test a single model by auto-detecting and using the appropriate endpoint.
    
    Args:
        client: Initialized Portkey client
        model_slug: Model identifier to test
        forced_type: Optional forced endpoint type
        on_status_update: Optional callback function(msg: str) to update status
    
    Returns:
        Tuple of (success: bool, details: dict)
    """
    # Get endpoint priorities
    endpoints_to_try = get_endpoint_priorities(model_slug, forced_type)
    
    test_details = {
        'model': model_slug,
        'success': False,
        'endpoint': None,
        'response_model': None,
        'response_time': 0,
        'error': None,
        'content': None,
        'usage': None
    }
    
    try:
        # Measure response time
        start_time = time.time()
        
        success = False
        result = {}
        first_error = None
        
        # Iterate through endpoints
        for i, endpoint in enumerate(endpoints_to_try):
            test_details['endpoint'] = endpoint
            try:
                if i > 0 and on_status_update:
                    on_status_update(f"Trying fallback endpoint {endpoint}...")
                    
                if endpoint == 'chat':
                    success, result = test_chat_completion(client, model_slug)
                elif endpoint == 'embeddings':
                    success, result = test_embeddings(client, model_slug)
                elif endpoint == 'tts':
                    success, result = test_text_to_speech(client, model_slug)
                elif endpoint == 'stt':
                    success, result = test_speech_to_text(client, model_slug)
                
                # If we got here without exception, check if it was logically successful
                if success:
                    break
                    
            except Exception as e:
                # Capture the first error as it's likely the most relevant (based on slug detection)
                if first_error is None:
                    first_error = e
                # Continue to next endpoint
                continue
        
        # If we failed all attempts and have an error, raise the first one
        if not success and first_error:
            raise first_error
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Check for successful response
        if success:
            test_details.update({
                'success': True,
                'endpoint': result['endpoint'],
                'response_model': result['model'],
                'response_time': response_time,
                'content': result.get('content'),
                'dimension': result.get('dimension'),
                'audio_size': result.get('audio_size'),
                'usage': result.get('usage')
            })
            return True, test_details
        else:
            test_details['error'] = result.get('error', 'Unknown error')
            return False, test_details
            
    except Exception as e:
        error_info = {
            'type': type(e).__name__,
            'message': str(e),
            'status_code': getattr(e, 'status_code', None),
            'body': getattr(e, 'body', None),
            'code': getattr(e, 'code', None),
        }
        
        test_details.update({
            'error': error_info,
            'response_time': time.time() - start_time
        })
        
        return False, test_details


def main():
    """Main execution flow."""
    print_banner()
    
    # Get user inputs
    api_key = get_api_key()
    config_id = get_config_id()
    target_endpoint = get_target_endpoint_type()
    model_slugs = get_model_slugs()
    
    # Initialize Portkey client
    console.print(f"\n[bold cyan]🔧 Initializing Portkey client...[/bold cyan]")
    
    client_kwargs = {"api_key": api_key}
    if config_id:
        client_kwargs["config"] = config_id
        console.print(f"   [dim]Using config ID:[/dim] {config_id}")
    
    if target_endpoint:
        console.print(f"   [dim]Target Endpoint:[/dim] {target_endpoint}")
    
    client = Portkey(**client_kwargs)
    
    # Test each model with progress tracking
    console.print()
    console.print(Rule("[bold cyan]📊 Running Tests[/bold cyan]", style="cyan"))
    console.print()
    
    results = {}
    
    # Run tests with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        task = progress.add_task("[cyan]Testing models...", total=len(model_slugs))
        
        for model_slug in model_slugs:
            progress.update(task, description=f"[cyan]Testing {model_slug}...")
            
            # Test with status update callback
            def update_status(msg):
                progress.update(task, description=f"[cyan]{model_slug}: {msg}")
                
            success, details = test_model(client, model_slug, forced_type=target_endpoint, on_status_update=update_status)
            results[model_slug] = details
            
            progress.advance(task)
        
        # Update progress bar to show completion
        progress.update(task, description="[green]✅ Tests completed")
    
    # Progress bar is now hidden - show results
    console.print()
    console.print(Rule("[bold green]✅ Test Results[/bold green]", style="green"))
    console.print()
    
    # Show quick status for each model
    for model_slug, details in results.items():
        if details['success']:
            console.print(f"[green]✅[/green] {model_slug} - [dim]{details['response_time']:.2f}s[/dim] - [cyan]{details['endpoint']}[/cyan]")
        else:
            console.print(f"[red]❌[/red] {model_slug} - [dim]Failed[/dim]")
    
    # Show detailed success information
    successful_models = [(slug, details) for slug, details in results.items() if details['success']]
    if successful_models:
        console.print()
        console.print(Rule("[bold green]📄 Detailed Results[/bold green]", style="green"))
        console.print()
        
        for model_slug, details in successful_models:
            # Create detailed panel for each successful model
            panel_content = []
            
            # Basic info
            panel_content.append(f"[bold]✅ Response Success![/bold]")
            panel_content.append(f"[bold]API Key:[/bold] Working correctly")
            panel_content.append(f"[bold]Requested Slug:[/bold] {model_slug}")
            panel_content.append(f"[bold]Response Model:[/bold] {details['response_model']}")
            panel_content.append(f"[bold]Endpoint Used:[/bold] {details['endpoint']}")
            panel_content.append(f"[bold]Response Time:[/bold] {details['response_time']:.2f}s")
            
            # Check if model matches (for routing verification)
            if details['response_model'] and model_slug != details['response_model']:
                panel_content.append(f"[yellow]⚠️  Model routing detected: {model_slug} → {details['response_model']}[/yellow]")
                panel_content.append("[dim]Please verify this is the expected model routing.[/dim]")
            
            # Usage information
            if details['usage']:
                usage = details['usage']
                usage_text = []
                if hasattr(usage, 'prompt_tokens'):
                    usage_text.append(f"Prompt: {usage.prompt_tokens}")
                if hasattr(usage, 'completion_tokens'):
                    usage_text.append(f"Completion: {usage.completion_tokens}")
                if hasattr(usage, 'total_tokens'):
                    usage_text.append(f"Total: {usage.total_tokens}")
                if usage_text:
                    panel_content.append(f"[bold]Token Usage:[/bold] {', '.join(usage_text)}")
            
            # Content preview
            if details['endpoint'] == 'chat' and details['content']:
                content_preview = details['content'][:100] + "..." if len(details['content']) > 100 else details['content']
                panel_content.append(f"[bold]Response Preview:[/bold]")
                panel_content.append(f"[dim]\"{content_preview}\"[/dim]")
            elif details['endpoint'] == 'embeddings' and details['dimension']:
                panel_content.append(f"[bold]Embedding Dimension:[/bold] {details['dimension']}")
            elif details['endpoint'] == 'tts':
                panel_content.append(f"[bold]Audio Size:[/bold] {details.get('audio_size', 0)} bytes")
                panel_content.append(f"[dim]Audio content received successfully[/dim]")
            elif details['endpoint'] == 'stt':
                panel_content.append(f"[bold]Transcription:[/bold] \"{details.get('content', '')}\"")
            
            # Create the panel
            success_panel = Panel(
                "\n".join(panel_content),
                title=f"[bold green]🎯 {model_slug}[/bold green]",
                border_style="green",
                padding=(1, 2),
                expand=True
            )
            console.print(success_panel)
            console.print()
    
    # Summary - Create a beautiful table
    console.print()
    console.print(Rule("[bold cyan]📋 Test Summary[/bold cyan]", style="cyan"))
    console.print()
    
    table = Table(
        show_header=True, 
        header_style="bold cyan", 
        border_style="cyan",
        title="Test Results",
        title_style="bold magenta",
        expand=True
    )
    table.add_column("Status", style="bold", width=10, justify="center")
    table.add_column("Model", style="bold yellow")
    table.add_column("Endpoint", style="cyan")
    table.add_column("Response Time", justify="right", style="green")
    table.add_column("Details", style="dim")
    
    successful = sum(1 for r in results.values() if r['success'])
    failed = len(results) - successful
    
    for model_slug, details in results.items():
        if details['success']:
            table.add_row(
                "[green]✅ PASS[/green]", 
                model_slug,
                details['endpoint'] or 'N/A',
                f"{details['response_time']:.2f}s",
                details['response_model'] or 'N/A'
            )
        else:
            error_msg = details['error']['type'] if isinstance(details['error'], dict) else str(details['error'])
            table.add_row(
                "[red]❌ FAIL[/red]", 
                model_slug,
                'N/A',
                f"{details['response_time']:.2f}s" if details['response_time'] else 'N/A',
                f"[red]{error_msg}[/red]"
            )
    
    console.print(table)
    console.print()
    
    # Detailed results panel for failures
    if failed > 0:
        console.print(Rule("[bold red]Error Details[/bold red]", style="red"))
        console.print()
        
        for model_slug, details in results.items():
            if not details['success'] and isinstance(details['error'], dict):
                error_panel = Panel(
                    f"[bold red]Error Type:[/bold red] {details['error']['type']}\n"
                    f"[bold red]Message:[/bold red] {details['error']['message']}\n"
                    + (f"[bold red]HTTP Status:[/bold red] {details['error']['status_code']}\n" if details['error']['status_code'] else "")
                    + (f"[bold red]Details:[/bold red]\n{Pretty(details['error']['body'])}" if details['error']['body'] else ""),
                    title=f"[bold red]{model_slug}[/bold red]",
                    border_style="red",
                    padding=(1, 2),
                    expand=True
                )
                console.print(error_panel)
                console.print()
    
    # Total summary panel
    summary_text = f"[bold]Total:[/bold] {successful} passed, {failed} failed"
    summary_style = "green" if failed == 0 else "yellow"
    
    console.print(Panel(
        summary_text,
        border_style=summary_style,
        padding=(0, 2),
        expand=True
    ))
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print(f"\n\n[bold yellow]⚠️  Test interrupted by user.[/bold yellow]")
        sys.exit(130)

