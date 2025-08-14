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
from typing import Dict, List, Any
from agents import Agent, function_tool, Runner, enable_verbose_stdout_logging
from .ask_clarification_agent import AskClarificationAgent
from .database_context_agent import DatabaseContextAgent
from .validator_agent import ValidatorAgent
from .context_memory import ContextMemory
from ..utils.logger import get_agent_logger, log_json_pretty


class MasterAgent:
    """
    Master LLM Agent for Enterprise Form Management
    
    This agent uses advanced reasoning to understand complex user queries,
    break them down into manageable subtasks, and orchestrate specialized 
    subagents to achieve the desired database modifications.
    """
    
    def __init__(self, model="gpt-5", db_path="data/forms.sqlite", verbose_logging=True):
        self.db_path = db_path
        self.model = model
        
        # Initialize logging first
        self.logger = get_agent_logger("MasterAgent", "DEBUG")
        
        # Load database schema
        schema_path = os.path.join(os.path.dirname(db_path), "database_schema.json")
        self.db_schema = self._load_database_schema(schema_path)
        self.logger.log_step("Initializing MasterAgent", {
            "model": model,
            "db_path": db_path,
            "schema_loaded": bool(self.db_schema),
            "verbose_logging": verbose_logging
        })
        
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
        
        self.logger.log_step("Subagents initialized successfully")
        
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
        
        self.logger.log_step("MasterAgent initialized", {
            "total_tools": len(function_tools + agent_tools),
            "function_tools": len(function_tools),
            "agent_tools": len(agent_tools)
        })
    
    def _load_database_schema(self, schema_path: str) -> Dict:
        """Load database schema from JSON file"""
        try:
            if os.path.exists(schema_path):
                with open(schema_path, 'r') as f:
                    schema = json.load(f)
                self.logger.log_step("Database schema loaded successfully", {
                    "schema_path": schema_path,
                    "table_count": len(schema.get("tables", {}))
                })
                return schema
            else:
                self.logger.log_step("Database schema file not found", {
                    "schema_path": schema_path
                })
                return {}
        except Exception as e:
            self.logger.log_error(e, "Failed to load database schema")
            return {}
        
    def _get_instructions(self):
        # Include database schema in instructions if available
        schema_context = ""
        if self.db_schema and "tables" in self.db_schema:
            schema_context = f"""

## Database Schema Context

You have access to the complete database schema with exact table names and column structures:

**Available Tables:**
{', '.join(self.db_schema["tables"].keys())}

**Key Tables for Common Operations:**
- **option_items**: For modifying dropdown/radio button choices (not "options")
- **form_fields**: For modifying form field properties (not "fields") 
- **logic_rules**: For form logic rules
- **logic_conditions**: For rule conditions
- **logic_actions**: For rule actions
- **forms**: For form metadata
- **form_pages**: For form page structure
- **option_sets**: For grouping options
- **field_option_binding**: For linking fields to option sets

**COMPLETE FORM CREATION REQUIRES ALL OF:**
1. **forms** - form metadata
2. **form_pages** - page structure (fields belong to pages)
3. **form_fields** - field definitions
4. **field_types** - field type references
5. **option_sets** - dropdown option groups
6. **option_items** - individual dropdown choices
7. **field_option_binding** - connects dropdown fields to option sets

**Table Relationships:**
{json.dumps(self.db_schema.get("relationships", []), indent=2)}

CRITICAL: Always use these EXACT table names in your changesets. Never assume or guess table names.
"""
        
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
- All operations must respect foreign key constraints{schema_context}

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

Notice: when calling tools, provide a concrete description of what you need, for example: the `get_database_context` tool should be called with a clear request like "Find the destination field in travel request form and its option set".
## Working Process

1. **Understand**: Classify the query and identify affected components
2. **Plan**: Develop a strategic approach using your reasoning abilities
3. **ALWAYS EXPLORE FIRST**: Use get_database_context tool to gather current schema, data, and context - this is MANDATORY before generating any changeset
4. **Clarify**: Use ask_clarification tool if requirements are unclear after exploration
5. **Generate**: Create the database changeset using your expertise and the explored context
7. **Output**: Return clean JSON with proper structure

## CRITICAL RULE: ALWAYS EXPLORE DATABASE FIRST

Before generating any changeset, you MUST use the get_database_context tool to:
- Understand the current database schema
- See existing data structures  
- Identify correct table names and column names
- FOR UPDATES: Find existing records that need to be modified
- FOR CREATION: Explore table structure, required fields, field types, and creation patterns
- Understand relationships between tables

## CRITICAL RULE: ALWAYS IDENTIFY THE CORRECT TARGET TABLE

When generating a changeset, you MUST:
- Use the EXACT table names discovered during exploration
- Never assume table names - always use what you found in the database
- Ensure the changeset table key matches the actual database table name
- For option modifications, use "option_items" (not "options" or "option_set_items")
- For form field modifications, use "form_fields" (not "fields")
- For logic rule modifications, use "logic_rules", "logic_conditions", "logic_actions"

Failure to explore first will result in incorrect column names, table structures, and invalid changesets.

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

## Guidelines

- Use tools proactively to understand context before making assumptions
- Prefer updates over inserts when modifying existing data
- Only delete when explicitly requested
- Use placeholder IDs (starting with $) for new records
- Build understanding incrementally rather than trying to solve everything at once
- Apply advanced reasoning to handle complex multi-step requirements
- Always decompose user queries into subtasks and describes them to those subagents when needed. Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries.

## Examples

### UPDATE Example
- **User Query**: "update the dropdown options for the destination field in the travel request form: 1. add a paris option, 2. change tokyo to wuhan"
  **Your internal reasoning**: User wants to MODIFY existing dropdown options. Need to find existing records to update.
  **Call get_database_context tool**: "Find the destination field in travel request form and its option set. Return COMPLETE row data for the form, field, option_set, and all existing option_items including the Tokyo option if it exists."
  **Generate changeset**: Use found records to update existing option and insert new option.

### CREATE Example  
- **User Query**: "I want to create a new form for snack requests. There should be a category field (ice cream/beverage/fruit/chips/gum) and name field (text)."
  **Your internal reasoning**: User wants to CREATE new form with dropdown and text fields. Need complete workflow including pages and field-option bindings.
  **Call get_database_context tool**: "Explore the complete structure for creating new forms with fields and dropdowns. Return schemas and sample data for ALL required tables: forms, form_pages, form_fields, field_types, option_sets, option_items, and field_option_binding. Show how dropdown fields connect to option sets via field_option_binding."
  **Generate changeset**: Create records in correct dependency order with all required intermediate tables. 

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
            self.logger.log_tool_call("store_context", {
                "key": key,
                "category": category,
                "value_length": len(value) if value else 0
            })
            
            try:
                self.logger.log_thinking(f"Attempting to parse and store context for key '{key}'")
                value_dict = json.loads(value) if value else {}
                
                self.logger.log_step("Parsed JSON value successfully", {
                    "parsed_type": type(value_dict).__name__,
                    "has_content": bool(value_dict)
                })
                
                success = self.context_memory.store_context(key, value_dict, category)
                
                if success:
                    result = f"Context stored successfully in {category} category"
                    self.logger.log_tool_result("store_context", result)
                    return result
                else:
                    error_result = "Failed to store context"
                    self.logger.log_tool_result("store_context", error_result)
                    return error_result
            except json.JSONDecodeError as e:
                error_result = f"Error parsing JSON value: {str(e)}"
                self.logger.log_error(e, "store_context JSON parsing")
                self.logger.log_tool_result("store_context", error_result)
                return error_result
            except Exception as e:
                error_result = f"Error storing context: {str(e)}"
                self.logger.log_error(e, "store_context")
                self.logger.log_tool_result("store_context", error_result)
                return error_result

        @function_tool  
        def retrieve_context(key: str, category: str = "general") -> str:
            """Retrieve information from context memory
            
            Args:
                key: Context key to retrieve
                category: Context category to search in
            """
            self.logger.log_tool_call("retrieve_context", {
                "key": key,
                "category": category
            })
            
            try:
                self.logger.log_thinking(f"Searching for context key '{key}' in category '{category}'")
                value = self.context_memory.get_context(key, category=category)
                
                if value:
                    self.logger.log_step("Context found successfully", {
                        "found": True,
                        "value_type": type(value).__name__
                    })
                    
                    result = json.dumps(value, indent=2)
                    self.logger.log_tool_result("retrieve_context", f"Found context with {len(result)} characters")
                    return result
                else:
                    result = f"No context found for key '{key}' in category '{category}'"
                    self.logger.log_step("Context not found", {
                        "found": False,
                        "key": key,
                        "category": category
                    })
                    self.logger.log_tool_result("retrieve_context", result)
                    return result
            except Exception as e:
                error_result = f"Error retrieving context: {str(e)}"
                self.logger.log_error(e, "retrieve_context")
                self.logger.log_tool_result("retrieve_context", error_result)
                return error_result

        return [store_context, retrieve_context]
    
    def _create_agent_tools(self) -> List:
        """Create agent tools using custom Runner.run implementation"""
        
        self.logger.log_step("Creating agent tools using custom Runner.run pattern")
        
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
                    max_turns=3
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
        
        # Log query start
        self.logger.log_query_start(user_query, user_context)
        self.logger.log_thinking("Starting query analysis and planning...")
        
        try:
            # Store the original query
            self.logger.log_step("Storing query in context memory", {
                "query_id": query_id
            })
            
            self.context_memory.store_context("original_query", {
                "query": user_query,
                "context": user_context,
                "timestamp": self.context_memory.created_at
            })
            
            # Prepare the user message
            message = f"Process this user query and generate the appropriate database changeset:\n\nQuery: {user_query}"
            
            if user_context:
                message += f"\n\nAdditional context: {json.dumps(user_context, indent=2)}"
                self.logger.log_step("Added user context to message")
            
            self.logger.log_thinking("Preparing message for LLM agent...")
            log_json_pretty(self.logger, "MESSAGE TO AGENT", {"message": message}, "DEBUG")
            
            # Use the OpenAI Agents SDK Runner to process the message
            self.logger.log_step("Calling Runner.run_sync with agent", {
                "agent_name": self.agent.name,
                "model": self.model
            })
            
            result = Runner.run_sync(
                self.agent,
                input=message
            )
            
            # Log detailed result structure for debugging
            result_attrs = [attr for attr in dir(result) if not attr.startswith('_')]
            self.logger.log_step("Received result from agent", {
                "has_final_output": hasattr(result, 'final_output') and bool(result.final_output),
                "has_messages": hasattr(result, 'messages') and bool(result.messages),
                "result_type": type(result).__name__,
                "available_attributes": result_attrs
            })
            
            # Log result details for debugging
            if hasattr(result, 'messages'):
                self.logger.log_step("Result messages details", {
                    "message_count": len(result.messages) if result.messages else 0,
                    "message_types": [type(msg).__name__ for msg in (result.messages or [])]
                })
            
            # Extract the result - the agents SDK provides final_output
            if hasattr(result, 'final_output') and result.final_output:
                content = str(result.final_output)
                
                self.logger.log_thinking("Processing agent response...")
                log_json_pretty(self.logger, "AGENT RESPONSE", {"content": content}, "DEBUG")
                
                # Try to parse as JSON changeset
                try:
                    self.logger.log_step("Attempting to parse JSON changeset from response")
                    import re
                    json_pattern = r'\{[^}]*(?:\{[^}]*\}[^}]*)*\}'
                    json_matches = re.findall(json_pattern, content, re.DOTALL)
                    
                    self.logger.log_step("Found potential JSON matches", {
                        "match_count": len(json_matches)
                    })
                    
                    for i, match in enumerate(json_matches):
                        try:
                            self.logger.log_step(f"Attempting to parse JSON match {i+1}")
                            changeset = json.loads(match)
                            
                            # Validate it looks like a proper changeset
                            is_changeset = any(key in changeset for key in ['insert', 'update', 'delete']) or any(isinstance(v, dict) and any(op in v for op in ['insert', 'update', 'delete']) for v in changeset.values())
                            
                            if is_changeset:
                                self.logger.log_step("Valid changeset found!", {
                                    "changeset_tables": list(changeset.keys())
                                })
                                
                                result_dict = {
                                    "success": True,
                                    "changeset": changeset,
                                    "query_id": query_id
                                }
                                
                                self.logger.log_query_end(result_dict, True)
                                return result_dict
                            else:
                                self.logger.log_step(f"JSON match {i+1} is not a valid changeset")
                        except json.JSONDecodeError as e:
                            self.logger.log_step(f"JSON match {i+1} failed to parse", {
                                "error": str(e)
                            })
                            continue
                            
                except Exception as e:
                    self.logger.log_error(e, "JSON parsing")
                
                # Return the response content
                self.logger.log_thinking("No valid changeset found, returning raw response")
                result_dict = {
                    "response": content,
                    "query_id": query_id,
                    "message": "Agent response - may contain clarification questions or analysis"
                }
                
                self.logger.log_query_end(result_dict, True)
                return result_dict
                
            else:
                error_dict = {"error": "No response received from agent"}
                self.logger.log_query_end(error_dict, False)
                return error_dict
            
        except Exception as e:
            self.logger.log_error(e, "process_query")
            error_dict = {"error": f"Query processing failed: {str(e)}"}
            self.logger.log_query_end(error_dict, False)
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
        self.logger.log_step("Handling clarification response", {
            "query_id": query_id,
            "answer_count": len(answers)
        })
        
        try:
            # Get the original clarification Q&A
            self.logger.log_thinking("Retrieving original clarification data...")
            qa_data = self.context_memory.get_clarification_qa(query_id)
            
            if not qa_data:
                error_result = {"error": "Original query not found"}
                self.logger.log_step("Original query not found in memory", {
                    "query_id": query_id
                })
                return error_result
            
            self.logger.log_step("Found original clarification data", {
                "original_question_count": len(qa_data.get("questions", []))
            })
            
            # Update with answers
            qa_data["answers"] = answers
            qa_data["status"] = "answered"
            self.context_memory.store_clarification_qa(query_id, qa_data)
            
            self.logger.log_step("Updated clarification data with answers")
            
            # Build enriched context
            enriched_context = {
                "clarification_provided": True,
                "questions_and_answers": [
                    {"question": q["question"], "answer": a}
                    for q, a in zip(qa_data["questions"], answers)
                ]
            }
            
            log_json_pretty(self.logger, "ENRICHED CONTEXT", enriched_context, "DEBUG")
            
            # Reprocess the original query with enriched context
            self.logger.log_thinking("Reprocessing original query with clarification answers...")
            self.logger.log_agent_handoff("MasterAgent", "MasterAgent", "Reprocessing with clarifications")
            
            return self.process_query(qa_data["original_query"], enriched_context)
            
        except Exception as e:
            self.logger.log_error(e, "handle_clarification_response")
            return {"error": f"Failed to handle clarification response: {str(e)}"}

    def get_memory_summary(self) -> Dict:
        """Get a summary of stored context memory"""
        return self.context_memory.get_memory_summary()


def create_master_agent(model="gpt-4", db_path="data/forms.sqlite", verbose_logging=True) -> MasterAgent:
    """Factory function to create a configured master LLM agent"""
    return MasterAgent(model=model, db_path=db_path, verbose_logging=verbose_logging)