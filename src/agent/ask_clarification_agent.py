"""
Ask Clarification Agent - LLM-Based Intelligent Question Generation

This agent specializes in analyzing ambiguous user queries and generating 
targeted clarification questions to gather missing information needed for 
precise database operations.
"""

from typing import Dict, List, Optional, Any
from agents import Agent, Runner
from ..utils.logger import get_agent_logger, log_json_pretty


class AskClarificationAgent:
    """
    LLM-powered agent that generates intelligent clarification questions
    
    This agent uses advanced reasoning to identify gaps in user queries and
    generate targeted questions that help collect the specific information
    needed to proceed with database operations.
    """
    
    def __init__(self, model="gpt-4"):
        self.model = model
        
        # Initialize logging
        self.logger = get_agent_logger("AskClarificationAgent", "DEBUG")
        self.logger.log_step("Initializing AskClarificationAgent", {"model": model})
        
        self.agent = Agent(
            name="AskClarificationAgent",
            model=model,
            instructions=self._get_instructions(),
            tools=[]  # This agent doesn't need external tools, just reasoning
        )
        
        self.logger.log_step("AskClarificationAgent initialized successfully")
        
    def _get_instructions(self):
        return """# Ask Clarification Agent

You are a specialized LLM agent for analyzing user queries about enterprise form systems and generating targeted clarification questions when information is missing or ambiguous.

## Your Expertise

You understand the complete form system architecture:
- **Forms**: Containers with categories, titles, descriptions, and status
- **Pages**: Logical sections within forms that group related fields
- **Fields**: Input elements with types (text, dropdown, checkbox, etc.), labels, validation rules
- **Option Sets**: Collections of choices for dropdown/radio fields
- **Logic Rules**: Dynamic behavior with conditions and actions

## Core Responsibilities

1. **Analyze queries** for missing critical information
2. **Identify ambiguities** that could lead to incorrect operations
3. **Generate targeted questions** that efficiently gather needed details
4. **Categorize question types** for better user experience
5. **Provide context** explaining why each question is necessary

## Question Categories

### form_selection
When the user hasn't specified which form to work with:
- "Which specific form should I modify?"
- "Are you referring to [Form A] or [Form B]?"

### field_specification  
When field references are unclear:
- "Which field should I add the validation to?"
- "Should this be a new field or modify the existing 'Email' field?"

### option_details
When option set modifications need clarification:
- "What options should be available in this dropdown?"
- "Should these replace existing options or be added to them?"

### logic_clarification
When business logic requirements are ambiguous:
- "When should this field be hidden/shown?"
- "What conditions should trigger this validation?"

## Question Generation Strategy

Generate questions that are:
- **Specific**: Target exact missing information
- **Contextual**: Reference existing system elements when possible
- **Efficient**: Minimize back-and-forth exchanges
- **User-friendly**: Use clear, non-technical language

## Response Format

Always return structured response with:
- needs_clarification: boolean indicating if questions are needed
- questions: array of question objects with question, type, context, and optional suggestions
- reasoning: explanation of what's missing and why clarification is needed
- priority: how critical these questions are (low/medium/high)

## Guidelines

- Only ask questions when truly necessary for accurate operations
- Prioritize questions that could prevent incorrect database modifications
- Group related questions logically
- Provide helpful context without being verbose
- Consider user intent and try to infer reasonable defaults when possible

Analyze the provided query and generate appropriate clarification questions if needed."""

    def generate_questions(self, query: str, context: Dict = None) -> Dict:
        """Generate targeted clarification questions for an ambiguous query"""
        
        self.logger.log_step("Starting question generation", {
            "query_length": len(query),
            "has_context": bool(context)
        })
        
        self.logger.log_thinking("Analyzing query for ambiguities and missing information...")
        log_json_pretty(self.logger, "INPUT QUERY", {"query": query, "context": context}, "DEBUG")
        
        messages = [
            {"role": "user", "content": f"Analyze this user query for clarity and generate clarification questions if needed:\n\nQuery: {query}"}
        ]
        
        if context:
            messages.append({
                "role": "user", 
                "content": f"Additional context: {context}"
            })
            self.logger.log_step("Added context to analysis")
            
        try:
            self.logger.log_step("Calling LLM for clarification analysis")
            
            result = Runner.run_sync(
                self.agent,
                messages=messages
            )
            
            self.logger.log_step("Received response from LLM", {
                "has_messages": hasattr(result, 'messages') and bool(result.messages)
            })
            
            # Extract response content
            if hasattr(result, 'messages') and result.messages:
                content = result.messages[-1].content if hasattr(result.messages[-1], 'content') else str(result.messages[-1])
                
                self.logger.log_thinking("Processing clarification response...")
                log_json_pretty(self.logger, "LLM RESPONSE", {"content": content}, "DEBUG")
                
                # Parse the response to extract structured information
                parsed_result = self._parse_clarification_response(content)
                
                self.logger.log_step("Clarification analysis complete", {
                    "needs_clarification": parsed_result.get("needs_clarification", False),
                    "question_count": len(parsed_result.get("questions", []))
                })
                
                return parsed_result
            else:
                error_result = {"error": "No response received"}
                self.logger.log_step("No response received from LLM")
                return error_result
            
        except Exception as e:
            self.logger.log_error(e, "generate_questions")
            return {
                "error": f"Clarification agent error: {str(e)}",
                "needs_clarification": False,
                "questions": []
            }
    
    def _parse_clarification_response(self, response_content: str) -> Dict:
        """Parse the agent's response into structured format"""
        
        # For now, we'll use a simple approach to determine if clarification is needed
        # In a production system, you might want to use structured outputs or function calling
        
        needs_clarification_keywords = [
            "unclear", "ambiguous", "missing", "specify", "which", "what", "clarification", 
            "need more information", "not clear", "question"
        ]
        
        response_lower = response_content.lower()
        needs_clarification = any(keyword in response_lower for keyword in needs_clarification_keywords)
        
        if needs_clarification:
            # Extract questions from the response
            lines = response_content.split('\n')
            questions = []
            
            for line in lines:
                line = line.strip()
                if line.endswith('?') and len(line) > 10:  # Basic question detection
                    question_type = self._categorize_question(line)
                    questions.append({
                        "question": line,
                        "type": question_type,
                        "context": "This information is needed to proceed accurately"
                    })
            
            return {
                "needs_clarification": True,
                "questions": questions[:5],  # Limit to 5 questions max
                "reasoning": "The query contains ambiguous or missing information that could lead to incorrect operations.",
                "priority": "medium"
            }
        else:
            return {
                "needs_clarification": False,
                "questions": [],
                "reasoning": "Query appears clear and actionable"
            }
    
    def _categorize_question(self, question: str) -> str:
        """Categorize a question into one of the predefined types"""
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['form', 'which form']):
            return "form_selection"
        elif any(word in question_lower for word in ['field', 'column', 'input']):
            return "field_specification"
        elif any(word in question_lower for word in ['option', 'choice', 'dropdown', 'select']):
            return "option_details"
        elif any(word in question_lower for word in ['rule', 'condition', 'logic', 'when', 'if']):
            return "logic_clarification"
        else:
            return "general"

    def analyze_query_completeness(self, query: str) -> Dict:
        """Analyze if a query has sufficient information without generating questions"""
        
        messages = [
            {"role": "user", "content": f"Analyze this query for completeness. Is there enough information to proceed with database operations? Just provide a brief analysis:\n\nQuery: {query}"}
        ]
        
        try:
            result = Runner.run_sync(
                self.agent,
                messages=messages
            )
            
            if hasattr(result, 'messages') and result.messages:
                content = result.messages[-1].content if hasattr(result.messages[-1], 'content') else str(result.messages[-1])
            else:
                content = ""
            
            # Simple heuristics for completeness
            is_complete = not any(word in content for word in [
                "incomplete", "missing", "unclear", "ambiguous", "need more", 
                "not enough", "insufficient", "lacks"
            ])
            
            return {
                "is_complete": is_complete,
                "analysis": content
            }
            
        except Exception as e:
            return {
                "is_complete": False,
                "analysis": f"Error analyzing query: {str(e)}"
            }