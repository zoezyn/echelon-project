from typing import Dict, Any, List, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
import json

from ..utils.logger import setup_logger
from ..utils.database import DatabaseManager
from .query_parser import QueryParser
from .change_generator import ChangeGenerator
from .validator import ChangeValidator


class ChatState(TypedDict):
    """State for the chatbot conversation"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_query: str
    parsed_query: Any
    database_context: Dict[str, Any]
    change_set: Any
    validation_errors: List[str]
    needs_clarification: bool
    clarification_questions: List[str]


class FormManagementChatbot:
    """LangGraph-based chatbot for form management"""
    
    def __init__(self, model_provider: str = "openai"):
        self.logger = setup_logger("FormManagementChatbot")
        self.db = DatabaseManager()
        self.query_parser = QueryParser(model_provider)
        self.change_generator = ChangeGenerator(model_provider)
        self.validator = ChangeValidator()
        
        # Build the graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph chatbot workflow"""
        
        workflow = StateGraph(ChatState)
        
        # Add nodes
        workflow.add_node("analyze_query", self.analyze_query)
        workflow.add_node("ask_clarification", self.ask_clarification)
        workflow.add_node("get_database_context", self.get_database_context)
        workflow.add_node("generate_changes", self.generate_changes)
        workflow.add_node("validate_changes", self.validate_changes)
        workflow.add_node("format_response", self.format_response)
        
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
        
        workflow.add_edge("ask_clarification", END)
        workflow.add_edge("get_database_context", "generate_changes")
        workflow.add_edge("generate_changes", "validate_changes")
        workflow.add_edge("validate_changes", "format_response")
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    def analyze_query(self, state: ChatState) -> ChatState:
        """Analyze the user's latest message"""
        self.logger.info("Analyzing user query")
        
        # Get the latest human message
        human_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
        if human_messages:
            state["user_query"] = human_messages[-1].content
            self.logger.debug(f"User query: {state['user_query']}")
            
            # Get available forms for context
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title FROM forms WHERE status = 'published'")
                available_forms = [row[0] for row in cursor.fetchall()]
            
            context = {"available_forms": available_forms}
            parsed_query = self.query_parser.parse_query(state["user_query"], context)
            
            state["parsed_query"] = parsed_query
            state["needs_clarification"] = parsed_query.needs_clarification
            state["clarification_questions"] = parsed_query.clarification_questions
            
            self.logger.info(f"Parsed intent: {parsed_query.intent}")
        
        return state
    
    def ask_clarification(self, state: ChatState) -> ChatState:
        """Ask clarification questions"""
        self.logger.info("Asking for clarification")
        
        if state["clarification_questions"]:
            # Create clarification message
            clarification_text = "I need more information to help you:\n\n"
            for i, question in enumerate(state["clarification_questions"], 1):
                clarification_text += f"{i}. {question}\n"
            clarification_text += "\nPlease provide more details so I can assist you better."
            
            ai_message = AIMessage(content=clarification_text)
            state["messages"] = state["messages"] + [ai_message]
            
            self.logger.info(f"Added clarification message with {len(state['clarification_questions'])} questions")
        
        return state
    
    def get_database_context(self, state: ChatState) -> ChatState:
        """Get relevant database context"""
        self.logger.info("Getting database context")
        
        if state["parsed_query"]:
            context = self.query_parser.get_database_context(state["parsed_query"])
            state["database_context"] = context
            
            # Enhance parsed query with context
            state["parsed_query"] = self.query_parser.enhance_with_context(
                state["parsed_query"], context
            )
            
            # Check if we need clarification after getting context
            if state["parsed_query"].needs_clarification:
                state["needs_clarification"] = True
                state["clarification_questions"] = state["parsed_query"].clarification_questions
        
        return state
    
    def generate_changes(self, state: ChatState) -> ChatState:
        """Generate database changes"""
        self.logger.info("Generating database changes")
        
        if state["parsed_query"] and not state["needs_clarification"]:
            try:
                change_set = self.change_generator.generate_changes(
                    state["parsed_query"],
                    state["database_context"]
                )
                state["change_set"] = change_set
                self.logger.info("Changes generated successfully")
                
            except Exception as e:
                self.logger.error(f"Error generating changes: {str(e)}")
                state["validation_errors"] = state["validation_errors"] + [f"Error generating changes: {str(e)}"]
        
        return state
    
    def validate_changes(self, state: ChatState) -> ChatState:
        """Validate the generated changes"""
        self.logger.info("Validating changes")
        
        if state["change_set"]:
            validation_errors = self.validator.validate_changes(
                state["change_set"].to_dict(),
                state["database_context"]
            )
            state["validation_errors"] = validation_errors
            
            if validation_errors:
                self.logger.warning(f"Found {len(validation_errors)} validation errors")
            else:
                self.logger.info("Changes validation passed")
        
        return state
    
    def format_response(self, state: ChatState) -> ChatState:
        """Format the final response"""
        self.logger.info("Formatting response")
        
        if state["validation_errors"]:
            # Error response
            error_text = "I encountered some issues while processing your request:\n\n"
            for i, error in enumerate(state["validation_errors"], 1):
                error_text += f"{i}. {error}\n"
            error_text += "\nPlease check your request and try again."
            
            ai_message = AIMessage(content=error_text)
            
        elif state["change_set"]:
            # Success response with changes
            changes_dict = state["change_set"].to_dict()
            
            # Create a user-friendly summary
            summary_text = "✅ I've generated the database changes for your request:\n\n"
            
            for table_name, operations in changes_dict.items():
                if operations.get('insert'):
                    summary_text += f"**{table_name}** - Adding {len(operations['insert'])} new record(s)\n"
                if operations.get('update'):
                    summary_text += f"**{table_name}** - Updating {len(operations['update'])} record(s)\n"
                if operations.get('delete'):
                    summary_text += f"**{table_name}** - Deleting {len(operations['delete'])} record(s)\n"
            
            summary_text += f"\n**Raw JSON Output:**\n```json\n{json.dumps(changes_dict, indent=2)}\n```"
            
            ai_message = AIMessage(content=summary_text)
            
        else:
            # Fallback response
            ai_message = AIMessage(content="I'm sorry, I couldn't process your request. Please try rephrasing your question.")
        
        state["messages"] = state["messages"] + [ai_message]
        self.logger.info("Response formatted and added to messages")
        
        return state
    
    def _should_clarify(self, state: ChatState) -> str:
        """Determine if clarification is needed"""
        if state["needs_clarification"] and state["clarification_questions"]:
            return "clarify"
        return "continue"
    
    def process_message(self, user_message: str, conversation_history: List[BaseMessage] = None) -> Dict[str, Any]:
        """Process a user message and return the response"""
        
        try:
            # Initialize state with conversation history
            initial_state = ChatState(
                messages=conversation_history or [],
                user_query="",
                parsed_query=None,
                database_context={},
                change_set=None,
                validation_errors=[],
                needs_clarification=False,
                clarification_questions=[]
            )
            
            # Add the new user message
            human_message = HumanMessage(content=user_message)
            initial_state["messages"] = initial_state["messages"] + [human_message]
            
            # Run the workflow
            result = self.workflow.invoke(initial_state)
            
            # Return the updated conversation state
            return {
                "messages": result["messages"],
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
            
            # Create error message
            error_message = AIMessage(content=f"I'm sorry, I encountered an error: {str(e)}")
            
            return {
                "messages": (conversation_history or []) + [HumanMessage(content=user_message), error_message],
                "success": False,
                "error": str(e)
            }