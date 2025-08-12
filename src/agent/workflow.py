from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END

from ..utils.models import AgentState
from ..utils.database import DatabaseManager
from ..utils.logger import setup_logger
from .query_parser import QueryParser
from .change_generator import ChangeGenerator
from .validator import ChangeValidator

class FormAgentWorkflow:
    def __init__(self, model_provider: str = "openai"):
        self.logger = setup_logger("FormAgentWorkflow")
        self.db = DatabaseManager()
        self.query_parser = QueryParser(model_provider)
        self.change_generator = ChangeGenerator(model_provider)
        self.validator = ChangeValidator()
        
        # Build the graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("analyze_query", self.analyze_query)
        workflow.add_node("ask_clarification", self.ask_clarification)
        workflow.add_node("get_database_context", self.get_database_context)
        workflow.add_node("generate_changes", self.generate_changes)
        workflow.add_node("validate_changes", self.validate_changes)
        workflow.add_node("format_output", self.format_output)
        
        # Define the flow
        workflow.set_entry_point("analyze_query")
        
        workflow.add_conditional_edges(
            "analyze_query",
            self._should_clarify,
            {
                "clarify": "ask_clarification",
                "continue": "get_database_context"
            }
        )
        
        workflow.add_edge("ask_clarification", "analyze_query")
        
        workflow.add_edge("get_database_context", "generate_changes")
        
        workflow.add_edge("generate_changes", "validate_changes")
        
        workflow.add_conditional_edges(
            "validate_changes",
            self._has_validation_errors,
            {
                "retry": "generate_changes",
                "continue": "format_output"
            }
        )
        
        workflow.add_edge("format_output", END)
        
        return workflow.compile()
    
    def analyze_query(self, state: AgentState) -> AgentState:
        """Analyze the user query and extract intent"""
        self.logger.info("Analyzing user query")
        self.logger.debug(f"Query: {state.user_query}")
        
        # Get available forms for context
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM forms WHERE status = 'published'")
            available_forms = [row[0] for row in cursor.fetchall()]
        
        context = {"available_forms": available_forms}
        parsed_query = self.query_parser.parse_query(state.user_query, context)
        
        self.logger.info(f"Parsed intent: {parsed_query.intent}")
        self.logger.debug(f"Parsed query: {parsed_query}")
        
        state.parsed_query = parsed_query
        state.next_action = "get_database_context"
        
        return state
    
    def get_database_context(self, state: AgentState) -> AgentState:
        """Get relevant database context for the query"""
        self.logger.info("Getting database context")
        
        if not state.parsed_query:
            self.logger.warning("No parsed query available, returning to analyze_query")
            state.next_action = "analyze_query"
            return state
        
        context = self.query_parser.get_database_context(state.parsed_query)
        state.database_context = context
        
        self.logger.debug(f"Database context: {context.keys() if context else 'None'}")
        
        # Enhance parsed query with context
        state.parsed_query = self.query_parser.enhance_with_context(
            state.parsed_query, 
            context
        )
        
        state.next_action = "check_clarification"
        return state
    
    def ask_clarification(self, state: AgentState) -> AgentState:
        """Ask clarification questions and get user response"""
        self.logger.info("Asking for clarification")
        
        if state.parsed_query and state.parsed_query.clarification_questions:
            self.logger.info(f"Clarification questions: {state.parsed_query.clarification_questions}")
            
            # Store the clarification questions
            state.clarification_history.extend(state.parsed_query.clarification_questions)
            
            # In a real interactive system, this would pause and wait for user input
            # For now, we'll append the clarification info to the original query
            clarification_context = " ".join(state.clarification_history)
            state.user_query = f"{state.user_query} Additional context: {clarification_context}"
            
            # Reset parsed query to force re-analysis
            state.parsed_query = None
            state.next_action = "analyze_query"
        
        return state
    
    def generate_changes(self, state: AgentState) -> AgentState:
        """Generate database changes"""
        self.logger.info("Generating database changes")
        
        if not state.parsed_query:
            self.logger.error("No parsed query available")
            state.validation_errors.append("No parsed query available")
            state.next_action = "format_output"
            return state
        
        try:
            change_set = self.change_generator.generate_changes(
                state.parsed_query,
                state.database_context
            )
            state.change_set = change_set
            state.next_action = "validate_changes"
            
            self.logger.info("Changes generated successfully")
            self.logger.debug(f"Change set: {change_set.to_dict()}")
            
        except Exception as e:
            self.logger.error(f"Error generating changes: {str(e)}")
            state.validation_errors.append(f"Error generating changes: {str(e)}")
            state.next_action = "format_output"
        
        return state
    
    def validate_changes(self, state: AgentState) -> AgentState:
        """Validate the generated changes"""
        self.logger.info("Validating changes")
        
        if not state.change_set:
            self.logger.warning("No changes generated")
            state.validation_errors.append("No changes generated")
            state.next_action = "format_output"
            return state
        
        validation_errors = self.validator.validate_changes(
            state.change_set.to_dict(),
            state.database_context
        )
        
        state.validation_errors = validation_errors
        
        if validation_errors:
            self.logger.warning(f"Found {len(validation_errors)} validation errors: {validation_errors}")
            state.next_action = "retry"
        else:
            self.logger.info("Changes validation passed")
            state.next_action = "format_output"
        
        return state
    
    def format_output(self, state: AgentState) -> AgentState:
        """Format the final output"""
        self.logger.info("Formatting output")
        
        if state.validation_errors:
            self.logger.warning("Formatting output with validation errors")
            state.final_output = {
                "error": "Validation failed",
                "errors": state.validation_errors
            }
        elif state.parsed_query and state.parsed_query.needs_clarification:
            self.logger.info("Formatting output for clarification needed")
            state.final_output = {
                "clarification_needed": True,
                "questions": state.parsed_query.clarification_questions
            }
        elif state.change_set:
            self.logger.info("Formatting successful change set output")
            state.final_output = state.change_set.to_dict()
        else:
            self.logger.error("Unable to process query - no changes or clarification")
            state.final_output = {
                "error": "Unable to process query"
            }
        
        self.logger.debug(f"Final output: {state.final_output}")
        return state
    
    def _should_clarify(self, state: AgentState) -> Literal["clarify", "continue"]:
        """Determine if clarification is needed"""
        if state.parsed_query and state.parsed_query.needs_clarification:
            return "clarify"
        return "continue"
    
    def _has_validation_errors(self, state: AgentState) -> Literal["retry", "continue"]:
        """Check if there are validation errors"""
        if state.validation_errors:
            # For now, don't retry automatically to avoid infinite loops
            return "continue"
        return "continue"
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """Process a user query through the workflow"""
        
        initial_state = AgentState(user_query=user_query)
        
        try:
            result = self.workflow.invoke(initial_state)
            # Handle both AgentState object and dictionary results
            if hasattr(result, 'final_output'):
                return result.final_output or {"error": "No output generated"}
            else:
                return result.get('final_output', {"error": "No output generated"})
            
        except Exception as e:
            self.logger.error(f"Error in workflow: {e}")
            import traceback
            traceback.print_exc()
            return {
                "error": f"Workflow error: {str(e)}"
            }