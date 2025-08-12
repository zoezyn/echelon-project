#!/usr/bin/env python3
"""
Form Management AI Agent

An interactive CLI tool that processes natural language queries about 
form management operations and outputs structured JSON changesets.
"""

import os
import sys
import json
from typing import Dict, Any, Optional

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.agent.workflow import FormAgentWorkflow
from src.evaluation.metrics import AgentEvaluator

class FormAgentCLI:
    def __init__(self, model_provider: str = "openai"):
        """Initialize the Form Agent CLI"""
        self.agent = FormAgentWorkflow(model_provider)
        self.evaluator = AgentEvaluator()
        self.conversation_history = []
        
    def print_welcome(self):
        """Print welcome message"""
        print("🔧 Form Management AI Agent")
        print("=" * 50)
        print("I can help you modify forms, fields, options, and logic rules.")
        print("Just describe what you want to do in natural language!")
        print()
        print("Examples:")
        print("• 'Add a Paris option to the destination field in travel form'")
        print("• 'Create a new field for phone number in contact form'") 
        print("• 'Make university name required when employment status is Student'")
        print()
        print("Commands:")
        print("• 'exit' or 'quit' - Exit the program")
        print("• 'help' - Show this help message")
        print("• 'eval' - Run baseline evaluation")
        print("• 'clear' - Clear conversation history")
        print("=" * 50)
        print()
    
    def print_help(self):
        """Print help message"""
        print("\n📖 Help - Form Management Operations")
        print("-" * 40)
        print("This agent can handle these types of operations:")
        print()
        print("🏷️  OPTIONS:")
        print("   • Add new options to dropdown/radio fields")
        print("   • Update existing option values/labels")
        print("   • Remove options from fields")
        print()
        print("📝 FIELDS:")
        print("   • Add new fields to forms")
        print("   • Modify field properties (label, type, required, etc.)")
        print("   • Remove fields from forms")
        print()
        print("🔀 LOGIC RULES:")
        print("   • Add conditional logic (show/hide/require fields)")
        print("   • Modify existing logic rules")
        print("   • Remove logic rules")
        print()
        print("📋 FORMS:")
        print("   • Create new forms")
        print("   • Update form properties")
        print("   • Delete forms")
        print()
        print("The agent will output structured JSON changes that can be")
        print("applied to the database tables.")
        print("-" * 40)
        print()
    
    def format_json_output(self, data: Dict[str, Any]) -> str:
        """Format JSON output for display"""
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def process_user_input(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Process user input and return response"""
        
        # Handle commands
        if user_input.lower().strip() in ['exit', 'quit']:
            return None
        elif user_input.lower().strip() == 'help':
            self.print_help()
            return {"command": "help"}
        elif user_input.lower().strip() == 'eval':
            return self.run_evaluation()
        elif user_input.lower().strip() == 'clear':
            self.conversation_history = []
            print("📝 Conversation history cleared.")
            return {"command": "clear"}
        
        # Process query with agent
        print("🤖 Processing your request...")
        print("-" * 30)
        
        try:
            result = self.agent.process_query(user_input)
            
            # Add to conversation history
            self.conversation_history.append({
                "user_query": user_input,
                "agent_response": result
            })
            
            return result
            
        except Exception as e:
            error_result = {"error": f"An error occurred: {str(e)}"}
            self.conversation_history.append({
                "user_query": user_input,
                "agent_response": error_result
            })
            return error_result
    
    def display_result(self, result: Dict[str, Any]):
        """Display the agent's response"""
        
        if "command" in result:
            return  # Commands are handled in process_user_input
        
        if "error" in result:
            print("❌ Error:")
            print(f"   {result['error']}")
            if "errors" in result:
                for error in result["errors"]:
                    print(f"   • {error}")
        
        elif "clarification_needed" in result:
            print("❓ I need more information:")
            for question in result.get("questions", []):
                print(f"   • {question}")
            print()
            print("Please provide more details and try again.")
        
        else:
            print("✅ Generated Database Changes:")
            print(self.format_json_output(result))
        
        print("-" * 30)
        print()
    
    def run_evaluation(self) -> Dict[str, Any]:
        """Run baseline evaluation"""
        print("🧪 Running baseline evaluation...")
        print("-" * 30)
        
        try:
            eval_results = self.evaluator.run_baseline_evaluation(self.agent)
            
            print(f"📊 Evaluation Results:")
            print(f"   Overall Score: {eval_results['overall_score']:.2%}")
            print(f"   Passed Examples: {eval_results['passed_examples']}/{eval_results['total_examples']}")
            print()
            
            print("📈 Metric Breakdown:")
            for metric, score in eval_results['metric_scores'].items():
                print(f"   {metric}: {score:.2%}")
            
            print("-" * 30)
            print()
            
            return eval_results
            
        except Exception as e:
            error_result = {"error": f"Evaluation failed: {str(e)}"}
            print(f"❌ {error_result['error']}")
            return error_result
    
    def run(self):
        """Run the interactive CLI"""
        
        self.print_welcome()
        
        while True:
            try:
                # Get user input
                user_input = input("💬 Your request: ").strip()
                
                if not user_input:
                    continue
                
                # Process input
                result = self.process_user_input(user_input)
                
                # Exit if requested
                if result is None:
                    print("👋 Goodbye!")
                    break
                
                # Display result
                self.display_result(result)
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                print("Please try again.")

def main():
    """Main entry point"""
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help']:
            print("Usage: python main.py [options]")
            print()
            print("Options:")
            print("  -h, --help     Show this help message")
            print("  --eval         Run evaluation and exit")
            print("  --model MODEL  Choose model provider (openai|anthropic)")
            return
        elif sys.argv[1] == '--eval':
            # Run evaluation only
            model_provider = "openai"
            if "--model" in sys.argv:
                model_idx = sys.argv.index("--model")
                if model_idx + 1 < len(sys.argv):
                    model_provider = sys.argv[model_idx + 1]
            
            cli = FormAgentCLI(model_provider)
            cli.run_evaluation()
            return
    
    # Determine model provider
    model_provider = "openai"  # Default
    if "--model" in sys.argv:
        model_idx = sys.argv.index("--model")
        if model_idx + 1 < len(sys.argv):
            model_provider = sys.argv[model_idx + 1]
    
    # Run interactive CLI
    cli = FormAgentCLI(model_provider)
    cli.run()

if __name__ == "__main__":
    main()