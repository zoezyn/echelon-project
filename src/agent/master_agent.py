"""
Master Agent - LLM-Based Enterprise Form Management System

The master agent is a powerful LLM that serves as the high-level orchestrator,
analyzing user queries, developing strategic plans, and coordinating with 
specialized LLM subagents to convert natural language requests into precise 
database operations.
"""

import json
import uuid
import logging
import os
from typing import Dict, List, Any, Optional
from agents import Agent, function_tool, Runner, enable_verbose_stdout_logging, SQLiteSession
from .ask_clarification_agent import AskClarificationAgent
from .database_context_agent import DatabaseContextAgent
from .validator_agent import ValidatorAgent
from .context_memory import ContextMemory
from ..utils.langfuse_config import setup_langfuse_logging, get_langfuse_client, check_langfuse_status

class MasterAgent:
    """
    Master LLM Agent for Enterprise Form Management
    
    This agent uses advanced reasoning to understand complex user queries,
    break them down into manageable subtasks, and orchestrate specialized 
    subagents to achieve the desired database modifications.
    """
    
    def __init__(self, model="gpt-5", db_path="data/forms.sqlite", verbose_logging=True, session_id=None):
        self.db_path = db_path
        self.model = model
        self.session_id = session_id or f"master_agent_{uuid.uuid4().hex[:8]}"
        
        # Initialize session for conversation memory
        self.session = SQLiteSession(self.session_id, "agent_conversations.db")

        # Setup Langfuse observability
        self.langfuse_enabled = setup_langfuse_logging(f"enterprise_form_agent_{self.session_id}")
        self.langfuse_client = get_langfuse_client() if self.langfuse_enabled else None

        # Load database schema
        schema_path = os.path.join(os.path.dirname(db_path), "database_schema.json")
        self.db_schema = self._load_database_schema(schema_path)
        
        # Enable OpenAI Agents SDK verbose logging
        if verbose_logging:
            enable_verbose_stdout_logging()
            
            # Configure SDK loggers
            openai_agents_logger = logging.getLogger("openai.agents")
            openai_tracing_logger = logging.getLogger("openai.agents.tracing")
            
            openai_agents_logger.setLevel(logging.DEBUG)
            openai_tracing_logger.setLevel(logging.DEBUG)

        # Initialize subagents
        self.clarification_agent = AskClarificationAgent(model=model)
        self.db_context_agent = DatabaseContextAgent(model=model, db_path=db_path)
        self.validator_agent = ValidatorAgent(model=model, db_path=db_path)
        self.context_memory = ContextMemory()

        # Create function tools and use agents as tools
        function_tools = self._create_function_tools()
        agent_tools = self._create_agent_tools()
        
        # Create the OpenAI Agent
        self.agent = Agent(
            name="MasterAgent",
            model=model,
            instructions=self._get_instructions(),
            tools=function_tools + agent_tools
        )

    def _load_database_schema(self, schema_path: str) -> Dict:
        """Load database schema from JSON file"""
        try:
            if os.path.exists(schema_path):
                with open(schema_path, 'r') as f:
                    schema = json.load(f)
                return schema
            else:
                return {}
        except Exception as e:
            return {}
        
    def _get_instructions(self):
        
        return f"""# Enterprise Form Management Master Agent

You are an expert AI agent for managing an enterprise form system. Your job is to understand natural language requests and orchestrate specialized subagents to convert them into precise database operations.

## Core Capabilities

- Analyze user queries about forms, fields, options, and logic rules
- Develop strategic execution plans by breaking down complex requests
- Coordinate with specialized subagents when needed
- Generate validated JSON change sets for database operations

## System Knowledge

The form system consists of:
- **Forms**: Top-level containers with metadata
- **Pages**: Form sections that group related fields  
- **Fields**: Individual input elements (text, dropdown, etc.)
- **Option Sets/Items**: Choices for dropdowns and radio buttons
- **Logic System**: Rules, conditions, and actions for dynamic behavior

Key relationships:
- Forms contain Pages contain Fields
- Fields reference Option Sets for choices
- Logic Rules contain Conditions and Actions

## Available Tools

### ask_clarification
Use when user queries are ambiguous or missing critical details.
- Generates targeted clarification questions
- Helps identify missing form names, field references, or unclear requirements

### get_database_context  
Use when you need to explore and understand the current database state.
- Has tools to explore schema, relationships, sample data
- Can discover existing forms, fields, options, and logic rules
- Provides context needed for intelligent decision making
- ALWAYS returns complete table row data with all columns and values
- Provides exact table names for changeset generation

### store_context
Store information in context memory for later use.

### generate_changeset
Generate the final changeset based on all gathered information.


## CRITICAL RULE: 

### ALWAYS EXPLORE DATABASE FIRST

Before generating any changeset, you should use the get_database_context tool to:
- Understand the current database schema
- Identify correct table names and column names
- FOR UPDATES: Find existing records that need to be modified
- FOR CREATION: Explore table structure, required fields, field types, and creation patterns
- Understand relationships between tables

### ALWAYS IDENTIFY THE CORRECT TARGET TABLE

When generating a changeset, you MUST:
- Use the EXACT table names discovered during exploration
- Ensure the changeset table key matches the actual database table name
- **ALWAYS consider dependent tables and foreign key relationships**
- INCLUDE ALL REQUIRED FIELDS for each inserted/updated row.


## Guidelines

- Decompose user queries into subtasks and describes them to those subagents when needed. Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries.
- Use tools proactively to understand context before making assumptions
- Use placeholder IDs (starting with $) for new records
- For update and delete, you must provide the exact existing id from the corresponding table.


## Examples

### UPDATE Example
- **User Query**: "update the dropdown options for the destination field in the travel request form: 1. add a paris option, 2. change tokyo to wuhan"
  **Your internal reasoning**: User wants to MODIFY existing dropdown options. Need to find existing records to update.
  **Call get_database_context tool**: "User wants to update the dropdown options for the destination field in the travel request form. Find the destination field in travel request form and its option set. Return COMPLETE row data for the form, field, option_set, and all existing option_items including the Tokyo option if it exists."
  **Generate changeset**: Use found records to update existing option and insert new option.

### CREATE Example  
- **User Query**: "I want to create a new form for snack requests. There should be a category field (ice cream/beverage/fruit/chips/gum) and name field (text)."
  **Your internal reasoning**: User wants to CREATE new form with dropdown and text fields. Need complete workflow including pages and field-option bindings.
  **Call get_database_context tool**: "User wants to create a new form with dropdown and text fields. Explore the complete structure for creating new forms with fields and dropdowns. Return schemas and sample data for ALL required tables: forms, form_pages, form_fields, field_types, option_sets, option_items, and field_option_binding. Show how dropdown fields connect to option sets via field_option_binding."
  **Generate changeset**: Create records in correct dependency order with all required intermediate tables.

### DELETE Example
- **User Query**: "delete all forms"
  **Your internal reasoning**: User wants to DELETE all forms. This is a cascading operation that affects ALL tables with foreign key dependencies on forms.
  **Call get_database_context tool**: "User wants to delete all forms. Find ALL forms in the database and identify EVERY table that has foreign key dependencies on forms. I need complete data for forms and ALL dependent tables including form_pages, form_fields, option_sets, option_items, field_option_binding, logic_rules, logic_conditions, logic_actions, and any other tables that reference forms. Return the complete dependency chain so I can delete in proper order."
  **Generate changeset**: Delete all dependent records first, then forms last, respecting foreign key constraints. 


## Output Format

Always output valid JSON in this exact structure:
```json
{{
  "table_name": {{
    "insert": [objects with all required fields],
    "update": [objects with id and changed fields], 
    "delete": [objects with id field]
  }}
}}
```
"""

    def _create_function_tools(self) -> List:
        """Create function tools for context management"""
        
        @function_tool
        def store_context(key: str, value: str, category: str = "general") -> str:
            """Store information in context memory for later use
            
            Args:
                key: Context key for retrieval
                value: JSON string of the context value to store
                category: Context category for organization
            """
            try:
                value_dict = json.loads(value) if value else {}
                success = self.context_memory.store_context(key, value_dict, category)
                
                if success:
                    return f"Context stored successfully in {category} category"
                else:
                    return "Failed to store context"
            except json.JSONDecodeError as e:
                return f"Error parsing JSON value: {str(e)}"
            except Exception as e:
                return f"Error storing context: {str(e)}"

        @function_tool  
        def retrieve_context(key: str, category: str = "general") -> str:
            """Retrieve information from context memory
            
            Args:
                key: Context key to retrieve
                category: Context category to search in
            """
            try:
                value = self.context_memory.get_context(key, category=category)
                
                if value:
                    return json.dumps(value, indent=2)
                else:
                    return f"No context found for key '{key}' in category '{category}'"
            except Exception as e:
                return f"Error retrieving context: {str(e)}"

        return [store_context, retrieve_context]
    
    def _create_agent_tools(self) -> List:
        """Create agent tools using custom Runner.run implementation"""

        @function_tool
        async def ask_clarification(user_query: str) -> str:
            """Generate clarification questions when the user query is ambiguous or missing critical details
            
            Args:
                user_query: The user query that needs clarification
            """
            try:
                result = await Runner.run(
                    self.clarification_agent.agent,
                    input=user_query,
                    max_turns=2
                )
                
                return str(result.final_output) if result.final_output else "No clarification response received"
            except Exception as e:
                return f"Error running clarification agent: {str(e)}"
        
        @function_tool
        async def get_database_context(exploration_request: str) -> str:
            """Explore the database to gather context about forms, fields, options, and logic rules
            
            Args:
                exploration_request: Detailed description of what database information is needed
            """
            try:
                result = await Runner.run(
                    self.db_context_agent.agent,
                    input=exploration_request,
                    max_turns=5
                )
                return str(result.final_output) if result.final_output else "No database context response received"
            except Exception as e:
                return f"Error running database context agent: {str(e)}"
        
        tools = [ask_clarification, get_database_context]
        
        return tools

    def process_query(self, user_query: str, user_context: Dict = None) -> Dict:
        """
        Main entry point - process a user query and return a changeset
        
        Args:
            user_query: The user's natural language request
            user_context: Additional context or clarification answers
        
        Returns:
            Dictionary containing the result (changeset, clarification request, or error)
        """
        # Generate unique query ID for tracking
        query_id = str(uuid.uuid4())
        
        try:
            # Store the original query
            self.context_memory.store_context("original_query", {
                "query": user_query,
                "context": user_context,
                "timestamp": self.context_memory.created_at
            })
            
            # Prepare the user message
            message = f"Process this user query and generate the appropriate database changeset:\n\nQuery: {user_query}"
            
            if user_context:
                message += f"\n\nAdditional context: {json.dumps(user_context, indent=2)}"
            
            # Use the OpenAI Agents SDK Runner to process the message with session memory
            
            result = Runner.run_sync(
                self.agent,
                input=message,
                session=self.session
            )

            # Extract the result - the agents SDK provides final_output
            if hasattr(result, 'final_output') and result.final_output:
                content = str(result.final_output)

                # Try to parse as JSON changeset
                try:
                    import re
                    json_pattern = r'\{[^}]*(?:\{[^}]*\}[^}]*)*\}'
                    json_matches = re.findall(json_pattern, content, re.DOTALL)
                    
                    for i, match in enumerate(json_matches):
                        try:
                            changeset = json.loads(match)
                            
                            # Validate it looks like a proper changeset
                            is_changeset = any(key in changeset for key in ['insert', 'update', 'delete']) or any(isinstance(v, dict) and any(op in v for op in ['insert', 'update', 'delete']) for v in changeset.values())
                            
                            if is_changeset:
                                
                                result_dict = {
                                    "success": True,
                                    "changeset": changeset,
                                    "query_id": query_id
                                }
                                
                                return result_dict
                            else:
                                pass  # Not a valid changeset, continue
                        except json.JSONDecodeError as e:
                            continue
                            
                except Exception as e:
                    pass  # Silently handle JSON parsing errors
                
                # Return the response content
                result_dict = {
                    "response": content,
                    "query_id": query_id,
                    "message": "Agent response - may contain clarification questions or analysis"
                }
                
                return result_dict
                
            else:
                error_dict = {"error": "No response received from agent"}
                
                return error_dict
            
        except Exception as e:
            error_dict = {"error": f"Query processing failed: {str(e)}"}
            
            return error_dict

    def handle_clarification_response(self, query_id: str, answers: List[str]) -> Dict:
        """
        Process user's answers to clarification questions
        
        Args:
            query_id: ID of the original query that needed clarification
            answers: List of answers to the clarification questions
        
        Returns:
            Updated processing result with the additional context
        """
        try:
            # Get the original clarification Q&A
            qa_data = self.context_memory.get_clarification_qa(query_id)
            
            if not qa_data:
                return {"error": "Original query not found"}
            
            # Update with answers
            qa_data["answers"] = answers
            qa_data["status"] = "answered"
            self.context_memory.store_clarification_qa(query_id, qa_data)
            
            # Build enriched context
            enriched_context = {
                "clarification_provided": True,
                "questions_and_answers": [
                    {"question": q["question"], "answer": a}
                    for q, a in zip(qa_data["questions"], answers)
                ]
            }
            
            # Reprocess the original query with enriched context
            return self.process_query(qa_data["original_query"], enriched_context)
            
        except Exception as e:
            return {"error": f"Failed to handle clarification response: {str(e)}"}

    def get_memory_summary(self) -> Dict:
        """Get a summary of stored context memory"""
        return self.context_memory.get_memory_summary()
    
    def get_langfuse_status(self) -> Dict[str, Any]:
        """
        Get current Langfuse observability status
        
        Returns:
            Dictionary with Langfuse configuration and status details
        """
        return {
            "enabled": self.langfuse_enabled,
            "client_available": bool(self.langfuse_client),
            "session_id": self.session_id,
            "status": check_langfuse_status() if self.langfuse_enabled else None
        }
    
    def log_user_feedback(self, query_id: str, score: float, comment: Optional[str] = None) -> bool:
        """
        Log user feedback for a specific query
        
        Args:
            query_id: ID of the query to provide feedback for
            score: Numerical score (0.0 to 1.0)
            comment: Optional text comment
            
        Returns:
            bool: True if feedback was logged successfully
        """
        if not self.langfuse_enabled or not self.langfuse_client:
            return False
        
        try:
            from ..utils.langfuse_config import log_user_feedback
            log_user_feedback(query_id, score, comment)
            # Flush to ensure feedback is sent
            self.langfuse_client.flush()
            return True
        except Exception as e:
            return False

def create_master_agent(model="gpt-4", db_path="data/forms.sqlite", verbose_logging=True, session_id=None) -> MasterAgent:
    """Factory function to create a configured master LLM agent"""
    return MasterAgent(model=model, db_path=db_path, verbose_logging=verbose_logging, session_id=session_id)