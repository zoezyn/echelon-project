from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
import os

from ..utils.models import ParsedQuery, QueryIntent
from ..utils.database import DatabaseManager
from ..utils.logger import setup_logger

class QueryParser:
    def __init__(self, model_provider: str = "openai"):
        self.logger = setup_logger("QueryParser")
        self.db = DatabaseManager()
        
        if model_provider == "openai":
            self.llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0,
                api_key=os.getenv('OPENAI_API_KEY')
            )
        else:
            self.llm = ChatAnthropic(
                model="claude-3-haiku-20240307",
                temperature=0,
                api_key=os.getenv('ANTHROPIC_API_KEY')
            )
        
        self.parser = JsonOutputParser(pydantic_object=ParsedQuery)
        
        self.system_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at parsing natural language queries about form management operations.

Your task is to analyze user queries and extract structured information about what they want to do with forms, fields, options, or logic rules.

Available query intents:
- CREATE_FORM: Creating entirely new forms
- UPDATE_FORM: Modifying form properties
- DELETE_FORM: Removing forms    
- ADD_FIELD: Adding new fields to forms
- UPDATE_FIELD: Modifying existing field properties
- DELETE_FIELD: Removing fields from forms      
- ADD_OPTIONS: Adding new options to dropdown/radio fields
- UPDATE_OPTIONS: Modifying existing option values/labels
- DELETE_OPTIONS: Removing options from fields
- ADD_LOGIC: Adding conditional logic rules
- UPDATE_LOGIC: Modifying existing logic rules
- DELETE_LOGIC: Removing logic rules

- UNKNOWN: Query intent unclear

Form context database tables:
- forms: id, slug, title, description, status, category_id
- form_fields: id, form_id, page_id, type_id, code, label, position, required, visible_by_default
- option_sets: id, form_id, name
- option_items: id, option_set_id, value, label, position, is_active
- logic_rules: id, form_id, name, trigger, scope, priority, enabled
- logic_conditions: id, rule_id, lhs_ref, operator, rhs, bool_join, position
- logic_actions: id, rule_id, action, target_ref, params, position

Field types available:
1=short_text, 2=long_text, 3=dropdown, 4=radio, 5=checkbox, 6=tags, 7=date, 8=number, 9=file_upload, 10=email

Analyze the query and return JSON with:
- intent: The primary intent (enum value)
- form_identifier: Form name, slug, or ID mentioned
- field_code: Field code/name mentioned
- target_entities: List of specific items mentioned (option values, field names, etc.)
- parameters: Additional parameters extracted (field types, labels, positions, etc.)
- confidence: Confidence score 0-1
- needs_clarification: Boolean if more info needed
- clarification_questions: List of questions to ask if clarification needed

Examples:

Query: "update the dropdown options for the destination field in the travel request form: 1. add a paris option, 2. change tokyo to wuhan"
Response:
{{
  "intent": "update_options",
  "form_identifier": "travel request form",
  "field_code": "destination",
  "target_entities": ["paris", "tokyo", "wuhan"],
  "parameters": {{"operations": [{{"type": "add", "value": "paris"}}, {{"type": "update", "from": "tokyo", "to": "wuhan"}}]}},
  "confidence": 0.95,
  "needs_clarification": false,
  "clarification_questions": []
}}

Query: "I want the employment-demo form to require university_name when employment_status is Student"
Response:
{{
  "intent": "add_logic",
  "form_identifier": "employment-demo",
  "field_code": "university_name",
  "target_entities": ["university_name", "employment_status", "Student"],
  "parameters": {{"condition_field": "employment_status", "condition_value": "Student", "action": "require", "target_field": "university_name"}},
  "confidence": 0.9,
  "needs_clarification": false,
  "clarification_questions": []
}}

Query: "create a new form for snack requests"
Response:
{{
  "intent": "create_form",
  "form_identifier": "snack requests",
  "field_code": null,
  "target_entities": ["snack requests"],
  "parameters": {{"form_title": "snack requests", "form_type": "new"}},
  "confidence": 0.8,
  "needs_clarification": true,
  "clarification_questions": ["What fields should be included in the snack request form?", "Should this form have multiple pages?"]
}}

{format_instructions}"""),
            ("user", "{query}")
        ])
        
    def parse_query(self, query: str, context: Dict[str, Any] = None) -> ParsedQuery:
        """Parse a natural language query into structured format"""
        
        self.logger.info("Parsing natural language query")
        self.logger.info(f"Input query: {query}")
        
        # Add database context if available
        context_str = ""
        if context and 'available_forms' in context:
            context_str = f"\nAvailable forms in database: {', '.join(context['available_forms'])}"
            self.logger.info(f"Added context: {context_str}")
        
        # Prepare the full query that will be sent to LLM
        full_query = query + context_str
        self.logger.info(f"Full query sent to LLM: {full_query}")
        
        prompt = self.system_prompt.partial(
            format_instructions=self.parser.get_format_instructions()
        )
        
        # Log the prompt template being used
        self.logger.debug(f"Using prompt template with format instructions")
        
        chain = prompt | self.llm | self.parser
        
        try:
            # First get the raw LLM response before parsing
            llm_chain = prompt | self.llm
            raw_response = llm_chain.invoke({"query": full_query})
            self.logger.info(f"Raw LLM response: {raw_response.content}")
            
            # Now parse the response
            parsed_result = self.parser.invoke(raw_response)
            self.logger.info(f"Parsed JSON result: {parsed_result}")
            
            parsed_query = ParsedQuery(**parsed_result)
            self.logger.info(f"Successfully created ParsedQuery with intent: {parsed_query.intent}")
            self.logger.info(f"Form identifier: {parsed_query.form_identifier}")
            self.logger.info(f"Field code: {parsed_query.field_code}")
            self.logger.info(f"Target entities: {parsed_query.target_entities}")
            self.logger.info(f"Confidence: {parsed_query.confidence}")
            self.logger.info(f"Needs clarification: {parsed_query.needs_clarification}")
            if parsed_query.clarification_questions:
                self.logger.info(f"Clarification questions: {parsed_query.clarification_questions}")
            
            return parsed_query
        except Exception as e:
            self.logger.error(f"Error parsing query: {e}")
            # Return a default unknown intent
            return ParsedQuery(
                intent=QueryIntent.UNKNOWN,
                confidence=0.0,
                needs_clarification=True,
                clarification_questions=["I couldn't understand your request. Could you please rephrase what you'd like to do with the form?"]
            )
    
    def get_database_context(self, parsed_query: ParsedQuery) -> Dict[str, Any]:
        """Get relevant database context for the parsed query"""
        self.logger.info("Getting database context for parsed query")
        self.logger.error(f"DEBUG: parsed_query.field_code = {parsed_query.field_code}")
        context = {}
        
        # Get form information if form identifier is provided
        if parsed_query.form_identifier:
            self.logger.debug(f"Looking for form: {parsed_query.form_identifier}")
            form_result = self.db.find_form_by_identifier(parsed_query.form_identifier, include_similar=True)
            form = form_result['exact_match']
            if form:
                self.logger.info(f"Found form: {form['title']}")
                context['form'] = form
                context['form_fields'] = self.db.get_form_fields(form['id'])
                context['form_pages'] = self.db.get_form_pages(form['id'])
                
                # Get field-specific context
                if parsed_query.field_code:
                    self.logger.error(f"DEBUG: Looking for field_code: {parsed_query.field_code}")
                    self.logger.error(f"DEBUG: Available fields: {[f['code'] for f in context['form_fields']]}")
                    field_info = next(
                        (f for f in context['form_fields'] if f['code'] == parsed_query.field_code),
                        None
                    )
                    if field_info:
                        self.logger.error(f"DEBUG: Found target field: {field_info['code']}")
                        context['target_field'] = field_info
                        if field_info.get('has_options'):
                            context['field_options'] = self.db.get_field_options(field_info['id'])
                    else:
                        self.logger.error(f"DEBUG: Field '{parsed_query.field_code}' not found in form fields")
                else:
                    self.logger.error("DEBUG: No field_code to look up")
            else:
                self.logger.warning(f"Form not found: {parsed_query.form_identifier}")
                # Use semantic search results
                context['similar_forms'] = form_result['similar_matches']
        
        self.logger.debug(f"Database context keys: {list(context.keys())}")
        return context
    
    def enhance_with_context(self, parsed_query: ParsedQuery, context: Dict[str, Any]) -> ParsedQuery:
        """Enhance parsed query with database context"""
        
        # If form wasn't found but we have similar forms, flag for clarification
        if parsed_query.form_identifier and 'similar_forms' in context and not context.get('form'):
            parsed_query.needs_clarification = True
            if context['similar_forms']:
                form_names = [f['title'] for f in context['similar_forms']]
                parsed_query.clarification_questions.append(
                    f"I couldn't find a form called '{parsed_query.form_identifier}'. Did you mean one of these?\n• " + "\n• ".join(form_names)
                )
            else:
                parsed_query.clarification_questions.append(
                    f"I couldn't find a form matching '{parsed_query.form_identifier}'. Could you check the form name?"
                )
        
        # If field wasn't found, flag for clarification
        if parsed_query.field_code and context.get('form') and not context.get('target_field'):
            available_fields = [f['code'] for f in context.get('form_fields', [])]
            parsed_query.needs_clarification = True
            parsed_query.clarification_questions.append(
                f"I couldn't find field '{parsed_query.field_code}' in the form. Available fields: {', '.join(available_fields)}"
            )
        
        return parsed_query