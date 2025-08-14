#!/usr/bin/env python3
"""
Example Usage of the New Agent Architecture

This demonstrates how to use the complete LLM-based agent system for
enterprise form management with natural language queries.
"""

import os
import sys
import json
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set up OpenAI API key (you'll need to set this)
# os.environ['OPENAI_API_KEY'] = 'your-openai-api-key-here'

def example_basic_usage():
    """Basic usage example without OpenAI API"""
    print("=== Basic Usage Example (Without OpenAI API) ===\n")
    
    # Import components
    from src.agent.context_memory import ContextMemory
    from src.agent.database_context_agent import DatabaseContextAgent
    from src.agent.validator_agent import ValidatorAgent
    
    # Initialize context memory
    memory = ContextMemory()
    print("✓ Context Memory initialized")
    
    # Store some context
    memory.store_plan("example_plan", {
        "goal": "Add email validation field",
        "steps": [
            "Explore existing forms",
            "Find the target form", 
            "Add email field with validation",
            "Validate the changeset"
        ]
    })
    print("✓ Plan stored in context memory")
    
    # Initialize database context agent
    db_agent = DatabaseContextAgent(db_path="data/forms.sqlite")
    print("✓ Database Context Agent initialized")
    
    # Explore database structure
    schema_info = db_agent.get_db_schema()
    print(f"✓ Database schema explored: {len(schema_info.get('schema', {}))} tables")
    
    # Get forms information
    forms_info = db_agent.get_forms(limit=3)
    print(f"✓ Forms retrieved: {len(forms_info.get('forms', []))} forms")
    
    # Initialize validator
    validator = ValidatorAgent(db_path="data/forms.sqlite")
    print("✓ Validator Agent initialized")
    
    # Create a sample changeset
    sample_changeset = {
        "forms": {
            "insert": [
                {
                    "id": "$new_form_1",
                    "org_id": "example_org", 
                    "slug": "test-form-example",
                    "title": "Example Test Form",
                    "description": "A form created by the agent system",
                    "status": "draft",
                    "created_at": "2024-08-14T17:00:00Z",
                    "updated_at": "2024-08-14T17:00:00Z"
                }
            ]
        }
    }
    
    # Validate the changeset
    validation_result = validator.validate_changeset(sample_changeset)
    print(f"✓ Changeset validation: {'PASSED' if validation_result.get('valid') else 'FAILED'}")
    
    if not validation_result.get('valid'):
        print(f"  Validation errors: {len(validation_result.get('errors', []))}")
    
    # Show memory summary
    memory_summary = memory.get_memory_summary()
    print(f"✓ Context memory contains {len(memory_summary['categories'])} categories")
    
    print("\n=== Basic Usage Complete ===\n")


def example_full_workflow():
    """Example of full workflow (requires OpenAI API)"""
    print("=== Full Workflow Example (Requires OpenAI API) ===\n")
    
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OpenAI API key not found in environment variables")
        print("To run the full workflow:")
        print("1. Set OPENAI_API_KEY environment variable")
        print("2. Uncomment the master agent usage below")
        print()
        return
    
    try:
        from src.agent.master_agent import create_master_agent
        
        # Create master agent
        master_agent = create_master_agent(model="gpt-4", db_path="data/forms.sqlite")
        print("✓ Master Agent initialized")
        
        # Example queries to process
        example_queries = [
            "Add an email field to the contact form",
            "Create a new customer feedback form with rating and comments",
            "Add validation rules to prevent duplicate email addresses",
            "Create a dropdown field with options for departments"
        ]
        
        for i, query in enumerate(example_queries, 1):
            print(f"\n--- Processing Query {i} ---")
            print(f"Query: {query}")
            
            try:
                result = master_agent.process_query(query)
                
                if result.get('success'):
                    print("✓ Query processed successfully")
                    changeset = result.get('changeset', {})
                    print(f"  Generated changeset with {len(changeset)} table operations")
                
                elif result.get('needs_clarification'):
                    print("❓ Query needs clarification")
                    questions = result.get('questions', [])
                    for j, q in enumerate(questions[:2], 1):  # Show first 2 questions
                        print(f"  Q{j}: {q.get('question', 'N/A')}")
                
                elif result.get('error'):
                    print(f"❌ Error: {result['error']}")
                
                else:
                    print("ℹ️  Response received")
                    print(f"  {result.get('response', 'No specific response')[:100]}...")
                    
            except Exception as e:
                print(f"❌ Failed to process query: {e}")
        
        # Show memory summary
        memory_summary = master_agent.get_memory_summary()
        print(f"\n✓ Agent memory contains {len(memory_summary.get('categories', {}))} categories")
        
        print("\n=== Full Workflow Complete ===\n")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("The full workflow requires proper OpenAI Agents SDK setup")


def example_manual_orchestration():
    """Example of manually orchestrating the agents"""
    print("=== Manual Agent Orchestration Example ===\n")
    
    from src.agent.ask_clarification_agent import AskClarificationAgent
    from src.agent.database_context_agent import DatabaseContextAgent
    from src.agent.validator_agent import ValidatorAgent
    from src.agent.context_memory import ContextMemory
    
    # Initialize all agents
    clarification_agent = AskClarificationAgent()
    db_agent = DatabaseContextAgent(db_path="data/forms.sqlite")
    validator_agent = ValidatorAgent(db_path="data/forms.sqlite")
    memory = ContextMemory()
    
    print("✓ All agents initialized")
    
    # Simulate processing a user query
    user_query = "Add a field to the form"
    print(f"User Query: {user_query}")
    
    # Step 1: Check if clarification is needed
    clarification_result = clarification_agent.generate_questions(user_query)
    
    if clarification_result.get('needs_clarification', False):
        print("❓ Query needs clarification")
        questions = clarification_result.get('questions', [])
        for i, q in enumerate(questions[:3], 1):  # Show first 3 questions
            print(f"  Q{i}: {q.get('question', 'N/A')}")
        print("  (In real usage, you would collect user answers here)")
    else:
        print("✓ Query is clear enough to proceed")
    
    # Step 2: Explore database context
    print("\n--- Database Exploration ---")
    
    # Get forms to understand existing structure
    forms_result = db_agent.explore_database("get_forms", {"limit": 2})
    forms = forms_result.get('forms', [])
    print(f"✓ Found {len(forms)} forms in database")
    
    if forms:
        # Get fields for the first form
        first_form_id = forms[0].get('id')
        fields_result = db_agent.explore_database("get_fields", {"form_id": first_form_id, "limit": 5})
        fields = fields_result.get('fields', [])
        print(f"✓ Form '{forms[0].get('title')}' has {len(fields)} fields")
    
    # Step 3: Generate a sample changeset based on exploration
    print("\n--- Changeset Generation ---")
    
    if forms:
        sample_changeset = {
            "form_fields": {
                "insert": [
                    {
                        "id": "$new_field_1",
                        "form_id": first_form_id,
                        "page_id": None,  # Will be set based on form structure
                        "type_id": 1,  # Assuming type 1 is text field
                        "code": "new_field_example",
                        "label": "Example New Field",
                        "help_text": "This field was added by the agent system",
                        "position": 999,  # Add at end
                        "required": 0,
                        "read_only": 0,
                        "visible_by_default": 1,
                        "created_at": "2024-08-14T17:00:00Z",
                        "updated_at": "2024-08-14T17:00:00Z"
                    }
                ]
            }
        }
        
        print("✓ Sample changeset generated")
        
        # Step 4: Validate the changeset
        print("\n--- Changeset Validation ---")
        
        validation_result = validator_agent.validate_changeset(sample_changeset)
        
        if validation_result.get('valid'):
            print("✅ Changeset validation PASSED")
            diff = validation_result.get('summary', {}).get('diff', {})
            if diff:
                total_ops = diff.get('total_operations', 0)
                print(f"  Total operations: {total_ops}")
        else:
            print("❌ Changeset validation FAILED")
            errors = validation_result.get('errors', [])
            print(f"  Validation errors: {len(errors)}")
            
            if errors:
                for i, error in enumerate(errors[:3], 1):  # Show first 3 errors
                    error_type = error.get('type', 'unknown')
                    print(f"    Error {i}: {error_type}")
    
    # Step 5: Store results in context memory
    print("\n--- Context Storage ---")
    
    memory.store_context("user_query", user_query, "queries")
    memory.store_context("exploration_results", {
        "forms_count": len(forms),
        "clarification_needed": clarification_result.get('needs_clarification', False)
    }, "exploration")
    
    memory_summary = memory.get_memory_summary()
    print(f"✓ Results stored in context memory ({len(memory_summary.get('categories', {}))} categories)")
    
    print("\n=== Manual Orchestration Complete ===\n")


def main():
    """Run all examples"""
    print("🚀 Enterprise Form Management Agent System Examples\n")
    
    # Check database exists
    if not os.path.exists("data/forms.sqlite"):
        print("❌ Database 'data/forms.sqlite' not found")
        print("Please ensure the database exists before running examples")
        return
    
    # Run examples
    example_basic_usage()
    example_manual_orchestration() 
    example_full_workflow()
    
    print("🎉 All examples completed!\n")
    
    print("=== Quick Start Guide ===")
    print("1. Set OpenAI API key: export OPENAI_API_KEY='your-key'")
    print("2. Import the master agent:")
    print("   from src.agent.master_agent import create_master_agent")
    print("3. Create and use the agent:")
    print("   agent = create_master_agent()")
    print("   result = agent.process_query('Add email field to contact form')")
    print("4. Handle the result based on its type (changeset/clarification/error)")
    print()
    
    print("=== Architecture Summary ===")
    print("✅ Master Agent - High-level orchestrator using LLM reasoning")
    print("✅ Ask Clarification Agent - Generates targeted questions for ambiguous queries")
    print("✅ Database Context Agent - Explores database with comprehensive tools:")
    print("   - Schema exploration, table sampling, relationship discovery")
    print("   - Form/field/option retrieval with filtering")
    print("   - High-level context analysis")
    print("✅ Validator Agent - Comprehensive changeset validation:")
    print("   - In-memory database testing")
    print("   - Foreign key and constraint validation")
    print("   - Referential integrity checking")
    print("✅ Context Memory - Persistent storage for plans, history, and context")
    print()
    print("The system converts natural language requests into precise JSON changesets")
    print("while ensuring data integrity and providing intelligent error handling.")


if __name__ == "__main__":
    main()