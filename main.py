#!/usr/bin/env python3
"""
Interactive Terminal Chat Interface for Enterprise Form Management Agent

This provides a terminal-based chat interface to interact with the master agent
and test the complete agent orchestration system.
"""

import os
import sys
import json
from typing import Dict, Any

# Load environment variables from .env file
def load_env():
    """Load environment variables from .env file if it exists"""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def print_banner():
    """Print welcome banner"""
    print("=" * 70)
    print("🚀 ENTERPRISE FORM MANAGEMENT AGENT SYSTEM")
    print("=" * 70)
    print("Interactive Terminal Chat Interface")
    print()
    print("This agent can help you:")
    print("• Add/modify fields in forms")  
    print("• Create new forms with validation")
    print("• Add dropdown options and logic rules")
    print("• Generate precise database changesets")
    print()
    print("Type 'help' for commands, 'quit' to exit")
    print("💡 Real-time file logging ENABLED - all agent reasoning saved to timestamped files")
    print("💡 Use 'files' command to see log file locations and tail command")
    print("-" * 70)

def print_help():
    """Print help information"""
    print()
    print("📖 AVAILABLE COMMANDS:")
    print("  help          - Show this help message")
    print("  quit/exit     - Exit the chat")
    print("  status        - Show agent system status")
    print("  memory        - Show context memory summary")
    print("  clear         - Clear the screen")
    print("  logs          - Toggle detailed logging output")
    print("  debug         - Show debug logging level")
    print("  sdk           - Toggle OpenAI Agents SDK verbose logging")
    print("  files         - Show file logging session info")
    print()
    print("💬 EXAMPLE QUERIES:")
    print("  'Add an email field to the contact form'")
    print("  'Create a customer feedback form with rating dropdown'")
    print("  'Add validation to prevent duplicate emails'")
    print("  'What forms exist in the database?'")
    print()

def print_status(agent):
    """Print agent system status"""
    print()
    print("🔧 AGENT SYSTEM STATUS:")
    print(f"  Master Agent: ✅ Ready")
    print(f"  Model: {agent.model}")
    print(f"  Database: {agent.db_path}")
    print(f"  Tools Available: {len(agent.agent.tools)}")
    print()
    
    # Show subagent status
    print("  Subagents:")
    print("    • Ask Clarification Agent: ✅ Ready")
    print("    • Database Context Agent: ✅ Ready") 
    print("    • Validator Agent: ✅ Ready")
    print("    • Context Memory: ✅ Ready")
    print()

def print_memory_summary(agent):
    """Print context memory summary"""
    print()
    print("🧠 CONTEXT MEMORY SUMMARY:")
    summary = agent.get_memory_summary()
    
    if summary.get('categories'):
        for category, info in summary['categories'].items():
            print(f"  {category}: {info['count']} items")
    else:
        print("  No stored context yet")
    print()

def format_response(result: Dict) -> str:
    """Format agent response for display"""
    if result.get('error'):
        return f"❌ Error: {result['error']}"
    
    elif result.get('success') and result.get('changeset'):
        changeset = result['changeset']
        response = "✅ SUCCESS! Generated changeset:\n\n"
        response += json.dumps(changeset, indent=2)
        return response
    
    elif result.get('needs_clarification'):
        questions = result.get('questions', [])
        response = "❓ Need clarification:\n\n"
        for i, q in enumerate(questions, 1):
            response += f"{i}. {q.get('question', 'No question')}\n"
            if q.get('context'):
                response += f"   Context: {q['context']}\n"
        return response
    
    elif result.get('response'):
        return f"💬 {result['response']}"
    
    else:
        return f"📄 {json.dumps(result, indent=2)}"

def main():
    """Main interactive chat loop"""
    # Load environment variables
    load_env()
    
    print_banner()
    
    # Initialize logging settings
    show_logs = True  # Show logs by default to demonstrate agent thinking
    debug_mode = False
    verbose_sdk_logging = True  # Enable OpenAI Agents SDK verbose logging
    file_logging_enabled = True  # Enable real-time file logging
    
    # Check for OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️  WARNING: OPENAI_API_KEY not found in environment variables")
        print("   The agent will not be able to use LLM reasoning without an API key.")
        print("   You can still test the basic structure and individual components.")
        print()
        
        response = input("Continue anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("Please set your OpenAI API key and try again:")
            print("export OPENAI_API_KEY='your-key-here'")
            return
        print()
    
    # Check database
    if not os.path.exists("data/forms.sqlite"):
        print("❌ ERROR: Database file 'data/forms.sqlite' not found")
        print("   Please ensure the database file exists before starting.")
        return
    
    # Setup file logging if enabled
    file_logger = None
    if file_logging_enabled:
        try:
            from src.utils.file_logger import setup_file_logging
            file_logger = setup_file_logging(minimal_console=True)
        except Exception as e:
            print(f"⚠️  WARNING: Failed to setup file logging: {e}")
            print("   Continuing with console logging only...")

    # Initialize the master agent
    try:
        print("🔄 Initializing agent system...")
        from src.agent.master_agent import create_master_agent
        
        agent = create_master_agent(model="gpt-4o", db_path="data/forms.sqlite", verbose_logging=verbose_sdk_logging)
        print("✅ Agent system ready!\n")
        
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize agent system: {e}")
        print("   Please check your setup and try again.")
        if file_logger:
            from src.utils.file_logger import cleanup_file_logging
            cleanup_file_logging()
        return
    
    # Main chat loop
    while True:
        try:
            # Get user input
            user_input = input("👤 You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() in ['quit', 'exit']:
                print("👋 Goodbye!")
                break
            
            elif user_input.lower() == 'help':
                print_help()
                continue
            
            elif user_input.lower() == 'status':
                print_status(agent)
                continue
            
            elif user_input.lower() == 'memory':
                print_memory_summary(agent)
                continue
                
            elif user_input.lower() == 'logs':
                show_logs = not show_logs
                status = "ENABLED" if show_logs else "DISABLED"
                print(f"🔧 Detailed logging {status}")
                continue
            
            elif user_input.lower() == 'debug':
                debug_mode = not debug_mode
                status = "ENABLED" if debug_mode else "DISABLED"
                print(f"🔧 Debug mode {status}")
                continue
                
            elif user_input.lower() == 'sdk':
                verbose_sdk_logging = not verbose_sdk_logging
                status = "ENABLED" if verbose_sdk_logging else "DISABLED"
                print(f"🔧 SDK verbose logging {status}")
                print("   Note: Restart required for SDK logging changes to take effect")
                continue
                
            elif user_input.lower() == 'files':
                if file_logger:
                    info = file_logger.get_session_info()
                    print("📁 File Logging Session Info:")
                    print(f"   Session ID: {info['session_id']}")
                    print(f"   Session Directory: {info['session_dir']}")
                    print(f"   Combined Log: {info['combined_log']}")
                    print(f"   Tail Command: {file_logger.tail_command()}")
                else:
                    print("📁 File logging is not enabled")
                continue
            
            elif user_input.lower() == 'clear':
                os.system('clear' if os.name == 'posix' else 'cls')
                print_banner()
                continue
            
            # Process query with agent
            print("🤖 Agent: Processing your request...")
            
            try:
                # Set logging level based on settings
                if debug_mode:
                    import logging
                    logging.getLogger().setLevel(logging.DEBUG)
                elif show_logs:
                    import logging
                    logging.getLogger().setLevel(logging.INFO)
                else:
                    import logging
                    logging.getLogger().setLevel(logging.ERROR)
                
                result = agent.process_query(user_input)
                
                if show_logs:
                    print("═" * 60)
                
                response = format_response(result)
                print(f"🤖 Agent: {response}")
                
            except Exception as e:
                if show_logs:
                    print("═" * 60)
                print(f"🤖 Agent: ❌ Error processing query: {e}")
                if debug_mode:
                    import traceback
                    print("🔍 Debug traceback:")
                    traceback.print_exc()
            
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"💥 Unexpected error: {e}")
            continue
    
    # Cleanup file logging
    # if file_logger:
    #     from src.utils.file_logger import cleanup_file_logging
    #     cleanup_file_logging()

if __name__ == "__main__":
    main()