from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing_extensions import TypedDict
import json
from ..utils.database import DatabaseManager
from ..utils.logger import setup_logger
from .query_parser import QueryParser
from .change_generator import ChangeGenerator
from .validator import ChangeValidator
from ..utils.models import ChatState, FormResponse

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
        workflow.add_node("replan", self.replan)
        # workflow.add_node("validate_guardrails", self.validate_guardrails)
        workflow.add_node("ask_clarification", self.ask_clarification)
        workflow.add_node("get_database_context", self.get_database_context)
        workflow.add_node("generate_changes", self.generate_changes)
        workflow.add_node("validate_changes", self.validate_changes)
        workflow.add_node("format_response", self.format_response)
        
        # Define the flow
        workflow.set_entry_point("analyze_query")
        
        workflow.add_conditional_edges(
            "analyze_query",
        #     self._should_clarify,
        #     {
        #         "clarify": "ask_clarification",
        #         "continue": "validate_guardrails"
        #     }
        # )
        
        # workflow.add_conditional_edges(
        #     "validate_guardrails",
            self._should_clarify,
            {
                "clarify": "ask_clarification",
                "continue": "get_database_context"
            }
        )
        
        # After clarification, go to replan or back to original source
        workflow.add_conditional_edges(
            "ask_clarification",
            self._clarification_router,
            {
                "replan": "replan",
                "generate_changes": "generate_changes", 
                "default": "replan"
            }
        )
        
        # From replan, either ask for more clarification or continue to get_database_context
        workflow.add_conditional_edges(
            "replan",
            self._should_clarify,
            {
                "clarify": "ask_clarification",
                "continue": "get_database_context"
            }
        )
        
        workflow.add_conditional_edges(
            "get_database_context",
            self._should_clarify,
            {
                "clarify": "ask_clarification",
                "continue": "generate_changes"
            }
        )
        
        workflow.add_conditional_edges(
            "generate_changes",
            self._should_clarify,
            {
                "clarify": "ask_clarification",
                "continue": "validate_changes"
            }
        )
        
        workflow.add_edge("validate_changes", "format_response")
        workflow.add_edge("format_response", END)
        
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)
    
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
                            # Check if this is a clarification request or error message
                            if ("I need more information" in msg.content or 
                                "I couldn't find" in msg.content or
                                "Did you mean" in msg.content):
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
            # TODO: Add slug to the available forms
            cursor.execute("SELECT title FROM forms WHERE status = 'published'")
            available_forms = [row[0] for row in cursor.fetchall()]
        
        context = {"available_forms": available_forms}
        parsed_query = self.query_parser.parse_query(state["user_query"], context)
        
        state["parsed_query"] = parsed_query
        state["needs_clarification"] = parsed_query.needs_clarification
        state["clarification_questions"] = parsed_query.clarification_questions
        
        # Set clarification source for routing decisions
        if parsed_query.needs_clarification:
            state["clarification_source"] = "analyze_query"
        
        self.logger.info(f"Parsed intent: {parsed_query.intent}")
        
        return state
    
    def replan(self, state: ChatState) -> ChatState:
        """Replan and update ParsedQuery based on user clarification response"""
        self.logger.info("Replanning based on user clarification")
        
        if not state.get("parsed_query"):
            self.logger.error("No parsed query found in state for replanning")
            return state
        
        # Get the last human message (user's clarification response)
        human_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
        if len(human_messages) < 2:  # Need at least original query + clarification response
            self.logger.error("Not enough human messages for replanning")
            return state
        
        user_clarification = human_messages[-1].content.strip()
        original_parsed_query = state["parsed_query"]
        
        self.logger.info(f"User clarification: {user_clarification}")
        self.logger.info(f"Original parsed query intent: {original_parsed_query.intent}")
        
        # Use LLM to update the ParsedQuery based on user clarification
        self._update_parsed_query_with_llm(state, user_clarification)
        
        return state
    
    def _update_parsed_query_with_llm(self, state: ChatState, user_clarification: str) -> None:
        """Use LLM to update the ParsedQuery based on user clarification"""
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        from ..utils.models import ParsedQuery
        
        original_parsed_query = state["parsed_query"]
        clarification_questions = state.get("clarification_questions", [])
        
        self.logger.info("Using LLM to update ParsedQuery based on clarification")
        
        # Create a simple prompt to update the ParsedQuery
        update_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at updating ParsedQuery objects based on user clarifications.

Given the original ParsedQuery and user clarification, update ONLY the fields that need to be changed based on the user's input.

Original ParsedQuery structure:
- intent: The operation intent (keep unchanged unless user explicitly changes it)
- form_identifier: Form name/slug/title
- field_code: Field code/name
- target_entities: List of entities involved
- parameters: Operation parameters
- confidence: Confidence level
- needs_clarification: Whether clarification is needed
- clarification_questions: List of questions

Rules:
1. Only update fields that the user clarification addresses
2. Keep the original intent unless explicitly changed
3. Set needs_clarification to false after incorporating clarification
4. Clear clarification_questions after update
5. Maintain the same confidence level unless you're certain about the correction
6. Return the complete updated ParsedQuery as JSON

Format the response as a valid ParsedQuery JSON object."""),
            ("user", """Original ParsedQuery:
{original_query}

Clarification Questions that were asked:
{clarification_questions}

User's clarification response:
{user_clarification}

Please update the ParsedQuery to incorporate the user's clarification:""")
        ])

        parser = JsonOutputParser(pydantic_object=ParsedQuery)
        
        # Use the query parser's LLM since FormAgentWorkflow doesn't have its own
        llm = self.query_parser.llm
        chain = update_prompt | llm | parser

        try:
            invoke_params = {
                "original_query": original_parsed_query.model_dump(),
                "clarification_questions": clarification_questions,
                "user_clarification": user_clarification
            }
            self.logger.info(f"Chain invoke parameters: {invoke_params}")
            
            self.logger.info("📞 Calling chain.invoke() now...")
            updated_query = chain.invoke(invoke_params)
            self.logger.info("📞 chain.invoke() completed!")
            
            self.logger.info(f"LLM returned: {updated_query}")
            self.logger.info(f"LLM response type: {type(updated_query)}")
            
            # Convert back to ParsedQuery object
            if isinstance(updated_query, dict):
                self.logger.info("Converting dict to ParsedQuery object")
                updated_parsed_query = ParsedQuery(**updated_query)
            else:
                self.logger.info("Using ParsedQuery object directly")
                updated_parsed_query = updated_query
            
            self.logger.info(f"Converted ParsedQuery: {updated_parsed_query.model_dump()}")
            
            # Compare and log only changed attributes
            original_dict = original_parsed_query.model_dump()
            updated_dict = updated_parsed_query.model_dump()
            
            changes = {}
            for key, new_value in updated_dict.items():
                old_value = original_dict.get(key)
                if old_value != new_value:
                    changes[key] = {"old": old_value, "new": new_value}
            
            # Update the state with the corrected query
            state["parsed_query"] = updated_parsed_query
            state["needs_clarification"] = updated_parsed_query.needs_clarification
            state["clarification_questions"] = updated_parsed_query.clarification_questions
            
            if changes:
                self.logger.info("✅ Successfully updated ParsedQuery with LLM")
                for key, change in changes.items():
                    self.logger.info(f"📝 New {key}: {change['old']} → {change['new']}")
            else:
                self.logger.info("✅ ParsedQuery processed by LLM (no changes needed)")
            
        except Exception as e:
            self.logger.error(f"Error updating ParsedQuery with LLM: {e}")
            # Fallback: clear clarification flags to continue workflow
            state["needs_clarification"] = False
            state["clarification_questions"] = []
            self.logger.warning("Fallback: cleared clarification flags to continue workflow")
    
    # def validate_guardrails(self, state: ChatState) -> ChatState:
    #     """Validate query against guardrails"""
    #     self.logger.info("Validating query against guardrails")
        
    #     if state["parsed_query"]:
    #         violations = self.guardrails.validate_query(
    #             state["parsed_query"], 
    #             state.get("database_context", {})
    #         )
            
    #         if violations:
    #             # Check for critical violations
    #             if self.guardrails.has_critical_violations(violations):
    #                 state["needs_clarification"] = True
    #                 violation_message = self.guardrails.format_violations(violations)
    #                 state["clarification_questions"] = [violation_message]
    #                 self.logger.warning(f"Critical guardrail violations found: {len(violations)}")
    #             else:
    #                 # Just warnings - log them but continue
    #                 violation_message = self.guardrails.format_violations(violations)
    #                 self.logger.warning(f"Guardrail warnings: {violation_message}")
    #         else:
    #             self.logger.info("No guardrail violations found")
        
    #     return state
    
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
                state["clarification_source"] = "get_database_context"
                self.logger.info("Setting needs_clarification=True due to enhanced query")
            else:
                self.logger.info("No clarification needed after database context")
        
        return state
    
    def ask_clarification(self, state: ChatState) -> ChatState:
        """Ask clarification questions"""
        self.logger.info("Asking for clarification")
        self.logger.debug(f"Clarification questions: {state['clarification_questions']}")
        self.logger.debug(f"Current messages count: {len(state['messages'])}")
        
        if state["clarification_questions"]:
            # Create clarification message
            clarification_text = "I need more information to help you:\n\n"
            for i, question in enumerate(state["clarification_questions"], 1):
                clarification_text += f"{i}. {question}\n"
            clarification_text += "\nPlease provide more details so I can assist you better."
            
            self.logger.debug(f"About to call interrupt with text: {clarification_text}")
            
            # Use interrupt to wait for human input - this will raise GraphInterrupt
            self.logger.info(f"Calling interrupt with clarification: {clarification_text}")
            user_response = interrupt(clarification_text)
            
            # This code will only execute if the interrupt is resumed
            self.logger.debug(f"interrupt() returned: {user_response}")
            
            # Add both the clarification and user response to messages
            ai_message = AIMessage(content=clarification_text)
            human_message = HumanMessage(content=user_response)
            state["messages"] = state["messages"] + [ai_message, human_message]
            
            # Process the user response to update the parsed query
            self.logger.info(f"Processing clarification response: {user_response}")
            self._process_clarification_response(state, user_response)
            
            # Reset clarification flags since we got the input
            state["needs_clarification"] = False
            state["clarification_questions"] = []
            
            self.logger.info(f"Received user response: {user_response}")
        else:
            self.logger.warning("ask_clarification called but no clarification_questions found")
        
        self.logger.debug(f"Returning state with {len(state['messages'])} messages")
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
                
                # Convert error to clarification request
                error_message = str(e)
                state["needs_clarification"] = True
                state["clarification_questions"] = [error_message]
                state["clarification_source"] = "generate_changes"
        else:
            self.logger.warning("Skipping change generation - either no parsed query or needs clarification")
        
        return state
    
    def validate_changes(self, state: ChatState) -> ChatState:
        """Validate the generated changes"""
        self.logger.info("Validating changes")
        self.logger.debug(f"validate_changes - needs_clarification: {state.get('needs_clarification')}")
        
        if state["change_set"]:
            self.logger.info("Validating changes2")
            # Comprehensive guardrail validation (includes technical + policy validation)
            validation_errors = self.validator.validate_changes(
                state["change_set"].to_dict(),
                state["database_context"]
            )
            self.logger.info("Validating changes3")
            # Convert violations to error messages
            # validation_errors = [violation.message for violation in guardrail_violations]
            state["validation_errors"] = validation_errors
            self.logger.info("Validating changes4")
            if validation_errors:
                self.logger.warning(f"Found {len(validation_errors)} validation errors")
                # # Check if there are critical guardrail violations
                # critical_violations = [v for v in guardrail_violations if v.severity == 'critical']
                # if critical_violations:
                #     state["needs_clarification"] = True
                #     violation_message = self.guardrails.format_violations(guardrail_violations)
                #     state["clarification_questions"] = [violation_message]
            else:
                self.logger.info("Changes validation passed")
                # # Increment daily change counter on successful validation
                # self.guardrails.increment_daily_changes()
        
        # self.logger.debug(f"validate_changes completed - needs_clarification: {state.get('needs_clarification')}")
        return state
    
    def format_response(self, state: ChatState) -> ChatState:
        """Format the final response with Pydantic validation"""
        self.logger.info("Formatting response")
        
        try:
            if state["validation_errors"]:
                # Error response - validate structure
                error_message = ""
                if len(state["validation_errors"]) == 1 and not state["validation_errors"][0].startswith("Error generating changes:"):
                    # Single natural error message - use it directly
                    error_message = state["validation_errors"][0]
                else:
                    # Multiple errors or technical errors - format them
                    error_text = ""
                    for i, error in enumerate(state["validation_errors"], 1):
                        # Remove technical prefixes for natural display
                        clean_error = error
                        if clean_error.startswith("Error generating changes: "):
                            clean_error = clean_error[26:]  # Remove "Error generating changes: "
                        error_text += f"{i}. {clean_error}\n"
                    error_message = error_text
                
                # Create validated error response
                form_response = FormResponse(
                    success=False,
                    message=error_message,
                    changes=None
                )
                
                ai_message = AIMessage(content=error_message)
                
            elif state["change_set"]:
                # Success response with changes - validate structure
                changes_dict = state["change_set"].to_dict()
                
                # Validate using Pydantic model
                form_response = FormResponse(
                    success=True,
                    message="Database changes generated successfully",
                    changes=changes_dict
                )
                
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
                form_response = FormResponse(
                    success=False,
                    message="I'm sorry, I couldn't process your request. Please try rephrasing your question.",
                    changes=None
                )
                
                ai_message = AIMessage(content="I'm sorry, I couldn't process your request. Please try rephrasing your question.")
            
            # Store the validated response for potential API usage
            state["final_output"] = form_response.model_dump()
            
        except Exception as validation_error:
            self.logger.error(f"Error validating response format: {validation_error}")
            # Fallback to unvalidated response
            ai_message = AIMessage(content="I encountered an error while formatting the response. Please try again.")
        
        state["messages"] = state["messages"] + [ai_message]
        self.logger.info("Response formatted and added to messages")
        self.logger.debug(f"format_response completed with {len(state['messages'])} total messages")
        
        return state
    
    def _should_clarify(self, state: ChatState) -> str:
        """Determine if clarification is needed"""
        needs_clarification = state["needs_clarification"]
        has_questions = bool(state["clarification_questions"])
        
        self.logger.debug(f"_should_clarify: needs_clarification={needs_clarification}, has_questions={has_questions}")
        
        if needs_clarification and has_questions:
            self.logger.info("_should_clarify returning 'clarify'")
            return "clarify"
        else:
            self.logger.info("_should_clarify returning 'continue'")
            return "continue"
    
    def _process_clarification_response(self, state: ChatState, user_response: str) -> None:
        """Process user's clarification response and update the parsed query accordingly"""
        clarification_source = state.get("clarification_source", "")
        
        self.logger.info(f"Processing clarification for source: {clarification_source}")
        
        if clarification_source == "generate_changes" and state.get("parsed_query"):
            # For generate_changes errors, typically the user is providing the corrected value
            parsed_query = state["parsed_query"]
            
            # If this is an update_options intent and the user provided a single response,
            # assume they're correcting the "from" value
            if (hasattr(parsed_query, 'intent') and 
                parsed_query.intent.value == 'update_options' and 
                hasattr(parsed_query, 'parameters') and 
                parsed_query.parameters.get('operations')):
                
                operations = parsed_query.parameters['operations']
                if operations and len(operations) > 0:
                    # Update the "from" value with the user's clarification
                    old_from = operations[0].get('from', '')
                    operations[0]['from'] = user_response.strip()
                    
                    # Also update target_entities if they exist
                    if hasattr(parsed_query, 'target_entities'):
                        # Replace the old value with the new one
                        target_entities = list(parsed_query.target_entities)
                        if old_from in target_entities:
                            idx = target_entities.index(old_from)
                            target_entities[idx] = user_response.strip()
                            parsed_query.target_entities = target_entities
                    
                    self.logger.info(f"Updated parsed_query: from '{old_from}' to '{user_response.strip()}'")
                    self.logger.debug(f"Updated operations: {operations}")

    def _clarification_router(self, state: ChatState) -> str:
        """Route back to the appropriate node after clarification"""
        source = state.get("clarification_source", "")
        self.logger.info(f"Clarification router called with source: '{source}'")
        self.logger.debug(f"Full state clarification_source: {state.get('clarification_source')}")
        
        # If clarification came from generate_changes, go back there directly
        # (these are usually specific value corrections that don't need replanning)
        if source == "generate_changes":
            self.logger.info("Routing back to generate_changes")
            return "generate_changes"
        elif source == "get_database_context" or source == "replan" or source == "analyze_query":
            self.logger.info("Routing back to replan")
            return "replan"
        else:
            # For analyze_query clarifications or unknown sources, go to replan
            # This handles field/form name corrections and query refinements
            self.logger.info(f"Clarification source '{source}', routing to replan")
            return "replan"
    
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """Process a user query through the workflow (CLI compatibility)"""
        
        # For CLI, create a simple human message and extract the final response
        result = self.process_message(user_query, [])
        
        if result["success"]:
            # Try to get final_output from the current workflow state
            try:
                config = {"configurable": {"thread_id": "default"}}
                current_state = self.workflow.get_state(config)
                if current_state and current_state.values.get("final_output"):
                    # Use the validated Pydantic output
                    final_output = current_state.values["final_output"]
                    
                    if final_output.get("success") and final_output.get("changes"):
                        # Return the clean JSON structure for successful operations
                        return final_output["changes"]
                    else:
                        # Return error information
                        return {
                            "error": final_output.get("message", "Unknown error"),
                            "success": False
                        }
            except Exception as e:
                self.logger.debug(f"Could not retrieve final_output from state: {e}")
            
            # Fallback to existing logic if no validated output
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
        """Process a user message and return the response - handles both new conversations and resume from interrupts"""
        
        import threading
        thread_id = threading.current_thread().ident
        self.logger.info(f"process_message called with message: {user_message} (thread: {thread_id})")
        self.logger.debug(f"Conversation history length: {len(conversation_history) if conversation_history else 0}")
        
        try:
            config = {"configurable": {"thread_id": "default"}}
            
            # Check if there's an existing interrupted workflow state
            try:
                current_state = self.workflow.get_state(config)
                is_interrupted = current_state and hasattr(current_state, 'next') and current_state.next
                self.logger.info(f"Existing workflow state found. Is interrupted: {is_interrupted}")
                
                if is_interrupted:
                    self.logger.info("Resuming from interrupted workflow")
                    # This is a resume scenario - use Command(resume=...)
                    result_state = None
                    
                    event_count = 0
                    for event in self.workflow.stream(Command(resume=user_message), config, stream_mode="updates"):
                        event_count += 1
                        self.logger.info(f"Resume event #{event_count}: {list(event.keys()) if isinstance(event, dict) else event}")
                        self.logger.debug(f"Resume event #{event_count} full: {event}")
                        
                        if "__interrupt__" in event:
                            # Another interrupt occurred
                            interrupt_info = event["__interrupt__"][0]
                            interrupt_value = interrupt_info.value
                            
                            self.logger.info(f"Another interrupt occurred during resume: {interrupt_value}")
                            
                            # Get current state to build proper response
                            current_state = self.workflow.get_state(config)
                            ai_message = AIMessage(content=interrupt_value)
                            return {
                                "messages": current_state.values["messages"] + [ai_message],
                                "success": True,
                                "interrupted": True,
                                "thread_id": config["configurable"]["thread_id"]
                            }
                        else:
                            # Update with the latest state
                            for node_name, node_state in event.items():
                                self.logger.info(f"Resume processing node {node_name} (event #{event_count})")
                                if node_state is not None:
                                    result_state = node_state
                    
                    self.logger.info(f"Resume stream completed after {event_count} events")
                    self.logger.debug(f"Final result_state: {result_state}")
                    self.logger.debug(f"Result_state type: {type(result_state)}")
                    if result_state:
                        self.logger.debug(f"Result_state has messages: {'messages' in result_state if hasattr(result_state, '__contains__') else 'not dict-like'}")
                    
                    # Return the final result from resume
                    if result_state and "messages" in result_state:
                        self.logger.info("Resume completed successfully with result_state")
                        self.logger.debug(f"Final result_state keys: {result_state.keys() if hasattr(result_state, 'keys') else 'not dict'}")
                        return {
                            "messages": result_state["messages"],
                            "success": True
                        }
                    else:
                        # Get current state if no result_state
                        current_state = self.workflow.get_state(config)
                        self.logger.info("Resume completed, using current workflow state")
                        self.logger.debug(f"Current state: {current_state}")
                        return {
                            "messages": current_state.values.get("messages", []),
                            "success": True
                        }
                        
            except Exception as state_check_error:
                self.logger.debug(f"No existing state or error checking state: {state_check_error}")
                is_interrupted = False
            
            if not is_interrupted:
                self.logger.info("Starting new workflow - no interrupted state detected")
                # This is a new conversation - initialize fresh state
                initial_state = ChatState(
                    messages=conversation_history or [],
                    user_query="",
                    parsed_query=None,
                    database_context={},
                    change_set=None,
                    validation_errors=[],
                    needs_clarification=False,
                    clarification_questions=[],
                    clarification_source=""
                )
                
                # Add the new user message
                human_message = HumanMessage(content=user_message)
                initial_state["messages"] = initial_state["messages"] + [human_message]
                
                # Use stream to handle interrupts properly
                result_state = None
                
                self.logger.debug(f"Starting new workflow stream with config: {config}")
                
                for event in self.workflow.stream(initial_state, config, stream_mode="updates"):
                    self.logger.debug(f"New workflow event: {event}")
                    
                    if "__interrupt__" in event:
                        # Extract the interrupt value (clarification question)
                        interrupt_info = event["__interrupt__"][0]
                        interrupt_value = interrupt_info.value
                        
                        self.logger.info(f"New workflow interrupted with value: {interrupt_value}")
                        
                        # Return the interrupt as a clarification request
                        ai_message = AIMessage(content=interrupt_value)
                        return {
                            "messages": initial_state["messages"] + [ai_message],
                            "success": True,
                            "interrupted": True,
                            "thread_id": config["configurable"]["thread_id"]
                        }
                    else:
                        # Update with the latest state
                        for node_name, node_state in event.items():
                            self.logger.debug(f"New workflow processing node {node_name}")
                            if node_state is not None:
                                result_state = node_state
                
                # If no interrupt occurred, return the final result
                if result_state and "messages" in result_state:
                    return {
                        "messages": result_state["messages"],
                        "success": True
                    }
                else:
                    return {
                        "messages": initial_state["messages"],
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
    
