from typing import Dict, Any, Literal, List, Sequence, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing_extensions import TypedDict
import json

from ..utils.models import AgentState
from ..utils.database import DatabaseManager
from ..utils.logger import setup_logger
from .query_parser import QueryParser
from .change_generator import ChangeGenerator
from .validator import ChangeValidator


class ChatState(TypedDict):
    """State for chatbot conversations with message history"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_query: str
    parsed_query: Any
    database_context: Dict[str, Any]
    change_set: Any
    validation_errors: List[str]
    needs_clarification: bool
    clarification_questions: List[str]

class FormAgentWorkflow:
    def __init__(self, model_provider: str = "openai"):
        self.logger = setup_logger("FormAgentWorkflow")
        self.db = DatabaseManager()
        self.query_parser = QueryParser(model_provider)
        self.change_generator = ChangeGenerator(model_provider)
        self.validator = ChangeValidator()
        
        # Build the unified workflow
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the unified LangGraph workflow"""
        
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
        
        workflow.add_conditional_edges(
            "get_database_context",
            self._should_clarify,
            {
                "clarify": "ask_clarification",
                "continue": "generate_changes"
            }
        )
        
        workflow.add_edge("generate_changes", "validate_changes")
        workflow.add_edge("validate_changes", "format_response")
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    def analyze_query(self, state: ChatState) -> ChatState:
        """Analyze the user's latest message with conversation context"""
        self.logger.info("Analyzing user query")
        
        # Get the latest human message or use existing user_query
        if state["messages"]:
            human_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
            if human_messages:
                latest_message = human_messages[-1].content
                
                # Check if there's conversation history (multiple messages total, not just human)
                if len(state["messages"]) > 1:
                    # Get the conversation context from previous messages
                    conversation_context = []
                    for msg in state["messages"][:-1]:  # Exclude the latest message
                        if isinstance(msg, HumanMessage):
                            conversation_context.append(f"User: {msg.content}")
                        elif isinstance(msg, AIMessage):
                            # Check if this is a clarification request
                            if "I need more information" in msg.content or "I couldn't find" in msg.content:
                                conversation_context.append(f"Assistant: {msg.content}")
                    
                    # If we have meaningful conversation context, include it
                    if conversation_context:
                        combined_query = f"""Previous conversation:
{chr(10).join(conversation_context)}

Current request: {latest_message}

Please analyze this current request in the context of the previous conversation. The user may be providing clarification or additional details about their original request."""
                        
                        state["user_query"] = combined_query
                        self.logger.debug(f"Using conversation context with {len(conversation_context)} previous messages")
                    else:
                        state["user_query"] = latest_message
                else:
                    state["user_query"] = latest_message
        
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
    
    def get_database_context(self, state: ChatState) -> ChatState:
        """Get relevant database context"""
        self.logger.info("Getting database context")
        
        if state["parsed_query"]:
            context = self.query_parser.get_database_context(state["parsed_query"])
            state["database_context"] = context
            
            # Enhance parsed query with context
            enhanced_query = self.query_parser.enhance_with_context(
                state["parsed_query"], context
            )
            state["parsed_query"] = enhanced_query
            
            self.logger.debug(f"Enhanced query needs_clarification: {enhanced_query.needs_clarification}")
            self.logger.debug(f"Enhanced query clarification_questions: {enhanced_query.clarification_questions}")
            
            # Check if we need clarification after getting context
            if enhanced_query.needs_clarification:
                state["needs_clarification"] = True
                state["clarification_questions"] = enhanced_query.clarification_questions
                self.logger.info("Setting needs_clarification=True due to enhanced query")
            else:
                self.logger.info("No clarification needed after database context")
        
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
    
    
    def generate_changes(self, state: ChatState) -> ChatState:
        """Generate database changes"""
        self.logger.info("Generating database changes")
        self.logger.debug(f"Has parsed_query: {bool(state['parsed_query'])}")
        self.logger.debug(f"Needs clarification: {state['needs_clarification']}")
        
        if state["parsed_query"] and not state["needs_clarification"]:
            try:
                self.logger.info("Calling change_generator.generate_changes")
                change_set = self.change_generator.generate_changes(
                    state["parsed_query"],
                    state["database_context"]
                )
                state["change_set"] = change_set
                self.logger.info(f"Changes generated successfully: {change_set.to_dict() if change_set else 'Empty changeset'}")
                
            except Exception as e:
                self.logger.error(f"Error generating changes: {str(e)}")
                import traceback
                traceback.print_exc()
                state["validation_errors"] = state["validation_errors"] + [f"Error generating changes: {str(e)}"]
        else:
            self.logger.warning("Skipping change generation - either no parsed query or needs clarification")
        
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
            # Error response - check if it's a single natural error message
            if len(state["validation_errors"]) == 1 and not state["validation_errors"][0].startswith("Error generating changes:"):
                # Single natural error message - use it directly
                ai_message = AIMessage(content=state["validation_errors"][0])
            else:
                # Multiple errors or technical errors - format them
                error_text = ""
                for i, error in enumerate(state["validation_errors"], 1):
                    # Remove technical prefixes for natural display
                    clean_error = error
                    if clean_error.startswith("Error generating changes: "):
                        clean_error = clean_error[26:]  # Remove "Error generating changes: "
                    error_text += f"{i}. {clean_error}\n"
                # error_text += "\nPlease check your request and try again."
                
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
    
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """Process a user query through the workflow (CLI compatibility)"""
        
        # For CLI, create a simple human message and extract the final response
        result = self.process_message(user_query, [])
        
        if result["success"]:
            # Extract the AI response for CLI compatibility
            ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                latest_response = ai_messages[-1].content
                
                # Try to parse JSON from the response if it contains JSON
                import re
                json_match = re.search(r'```json\n(.*?)\n```', latest_response, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except:
                        pass
                
                # Return as clarification needed or simple message
                if "I need more information" in latest_response:
                    questions = []
                    for line in latest_response.split('\n'):
                        if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith('•')):
                            questions.append(line.strip())
                    return {
                        "clarification_needed": True,
                        "questions": questions
                    }
                else:
                    return {"message": latest_response}
            
            return {"error": "No response generated"}
        else:
            return {"error": result.get("error", "Unknown error")}
    
    
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
            
            # Run the unified workflow
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
    
