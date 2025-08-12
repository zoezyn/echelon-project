import uuid
import json
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
import os

from ..utils.models import ParsedQuery, QueryIntent, ChangeSet
from ..utils.database import DatabaseManager
from ..utils.logger import setup_logger

class ChangeGenerator:
    def __init__(self, model_provider: str = "openai"):
        self.logger = setup_logger("ChangeGenerator")
        self.db = DatabaseManager()
        
        if model_provider == "openai":
            self.llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0,
                api_key=os.getenv('OPENAI_API_KEY')
            )
        else:
            self.llm = ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0,
                api_key=os.getenv('ANTHROPIC_API_KEY')
            )
    
    def generate_changes(self, parsed_query: ParsedQuery, context: Dict[str, Any]) -> ChangeSet:
        """Generate database changes based on parsed query and context"""
        
        self.logger.debug(f"generate_changes called with intent: {parsed_query.intent}")
        self.logger.debug(f"Context keys: {list(context.keys())}")
        
        change_set = ChangeSet()
        
        if parsed_query.intent == QueryIntent.UPDATE_OPTIONS or parsed_query.intent == QueryIntent.ADD_OPTIONS:
            self.logger.info("Calling _handle_update_options")
            try:
                result = self._handle_update_options(parsed_query, context, change_set)
                self.logger.debug(f"_handle_update_options returned: {result.to_dict()}")
                return result
            except ValueError as e:
                # Let ValueError (user-facing errors) propagate to show meaningful messages
                self.logger.error(f"User-facing error in _handle_update_options: {e}")
                raise e
            except Exception as e:
                # Log and re-raise other exceptions
                self.logger.error(f"Unexpected error in _handle_update_options: {e}")
                import traceback
                traceback.print_exc()
                raise e
        elif parsed_query.intent == QueryIntent.ADD_FIELD:
            try:
                return self._handle_add_field(parsed_query, context, change_set)
            except ValueError as e:
                self.logger.error(f"User-facing error in _handle_add_field: {e}")
                raise e
            except Exception as e:
                self.logger.error(f"Unexpected error in _handle_add_field: {e}")
                raise e
        elif parsed_query.intent == QueryIntent.ADD_LOGIC:
            try:
                return self._handle_add_logic(parsed_query, context, change_set)
            except ValueError as e:
                self.logger.error(f"User-facing error in _handle_add_logic: {e}")
                raise e
            except Exception as e:
                self.logger.error(f"Unexpected error in _handle_add_logic: {e}")
                raise e
        elif parsed_query.intent == QueryIntent.CREATE_FORM:
            try:
                return self._handle_create_form(parsed_query, context, change_set)
            except ValueError as e:
                self.logger.error(f"User-facing error in _handle_create_form: {e}")
                raise e
            except Exception as e:
                self.logger.error(f"Unexpected error in _handle_create_form: {e}")
                raise e
        else:
            # Use LLM for complex cases
            return self._generate_with_llm(parsed_query, context)
    
    def _handle_update_options(self, parsed_query: ParsedQuery, context: Dict[str, Any], change_set: ChangeSet) -> ChangeSet:
        """Handle updating dropdown/radio options"""
        
        self.logger.error(f"DEBUG: Context keys: {list(context.keys())}")
        self.logger.error(f"DEBUG: Parsed query parameters: {parsed_query.parameters}")
        
        if not context.get('target_field'):
            self.logger.error("Target field not found in context")
            raise ValueError("Target field not found in context")
        
        field = context['target_field']
        self.logger.debug(f"Target field: {field}")
        
        option_set_id = self.db.get_option_set_by_field_code(context['form']['id'], field['code'])
        self.logger.debug(f"Option set ID: {option_set_id}")
        
        if not option_set_id:
            raise ValueError(f"No option set found for field {field['code']}")
        
        operations = parsed_query.parameters.get('operations', [])
        self.logger.debug(f"Operations: {operations}")
        
        for op in operations:
            if op['type'] == 'add':
                # Add new option
                position = self.db.get_max_position('option_items', 'option_set_id', option_set_id)
                new_option = {
                    "id": f"$opt_{op['value'].lower().replace(' ', '_')}",
                    "option_set_id": option_set_id,
                    "value": op['value'].title(),
                    "label": op['value'].title(),
                    "position": position,
                    "is_active": 1
                }
                change_set.add_insert('option_items', new_option)
                
            elif op['type'] == 'update':
                # Update existing option
                self.logger.error(f"DEBUG: Updating option from '{op['from']}' to '{op['to']}'")
                self.logger.error(f"DEBUG: Option set ID: {option_set_id}")
                existing_option = self.db.get_existing_option_by_value(option_set_id, op['from'])
                self.logger.error(f"DEBUG: Found existing option: {existing_option}")
                if existing_option:
                    updated_option = {
                        "id": existing_option['id'],
                        "value": op['to'].title(),
                        "label": op['to'].title()
                    }
                    self.logger.error(f"DEBUG: Adding update operation: {updated_option}")
                    change_set.add_update('option_items', updated_option)
                else:
                    self.logger.error(f"DEBUG: No existing option found with value '{op['from']}'")
                    
                    # Try semantic search for similar options
                    similar_options = self.db.find_similar_field_options(option_set_id, op['from'])
                    
                    if similar_options:
                        # Found similar options - ask for confirmation
                        similar_names = [opt['value'] for opt in similar_options]
                        error_msg = f"I couldn't find an option called '{op['from']}' in the {field['code']} field.\n\nDid you mean one of these similar options?\n• " + "\n• ".join(similar_names)
                    else:
                        # No similar options found - show all available options
                        with self.db.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT value FROM option_items WHERE option_set_id = ? ORDER BY position", (option_set_id,))
                            available_options = [row[0] for row in cursor.fetchall()]
                        
                        error_msg = f"I couldn't find an option called '{op['from']}' in the {field['code']} field.\n\nThe available options are:\n• " + "\n• ".join(available_options) + f"\n\nDid you mean one of these instead?"
                    
                    raise ValueError(error_msg)
        
        return change_set
    
    def _handle_add_field(self, parsed_query: ParsedQuery, context: Dict[str, Any], change_set: ChangeSet) -> ChangeSet:
        """Handle adding new field to form"""
        
        if not context.get('form'):
            raise ValueError("Form not found in context")
        
        form = context['form']
        pages = context.get('form_pages', [])
        
        # Use first page if available, otherwise the form page will be None
        page_id = pages[0]['id'] if pages else None
        
        field_type = parsed_query.parameters.get('field_type', 'short_text')
        type_id = self.db.get_field_type_id(field_type)
        
        if not type_id:
            type_id = 1  # Default to short_text
        
        position = self.db.get_max_position('form_fields', 'form_id', form['id'])
        
        new_field = {
            "id": f"$fld_{parsed_query.field_code}",
            "form_id": form['id'],
            "page_id": page_id,
            "type_id": type_id,
            "code": parsed_query.field_code,
            "label": parsed_query.parameters.get('label', parsed_query.field_code.replace('_', ' ').title()),
            "position": position,
            "required": parsed_query.parameters.get('required', 0),
            "read_only": 0,
            "placeholder": parsed_query.parameters.get('placeholder'),
            "visible_by_default": parsed_query.parameters.get('visible_by_default', 1)
        }
        
        change_set.add_insert('form_fields', new_field)
        return change_set
    
    def _handle_add_logic(self, parsed_query: ParsedQuery, context: Dict[str, Any], change_set: ChangeSet) -> ChangeSet:
        """Handle adding conditional logic rules"""
        
        if not context.get('form'):
            raise ValueError("Form not found in context")
        
        form = context['form']
        condition_field = parsed_query.parameters.get('condition_field')
        condition_value = parsed_query.parameters.get('condition_value')
        action = parsed_query.parameters.get('action')
        target_field = parsed_query.parameters.get('target_field', parsed_query.field_code)
        
        # Find the condition field ID
        condition_field_info = next(
            (f for f in context.get('form_fields', []) if f['code'] == condition_field),
            None
        )
        
        if not condition_field_info:
            raise ValueError(f"Condition field '{condition_field}' not found")
        
        # Create logic rule
        rule_id = f"$rule_{target_field}_{action}"
        logic_rule = {
            "id": rule_id,
            "form_id": form['id'],
            "name": f"{target_field.title()} {action} rule",
            "trigger": "on_change",
            "scope": "form",
            "priority": 10,
            "enabled": 1
        }
        change_set.add_insert('logic_rules', logic_rule)
        
        # Create condition
        condition = {
            "id": f"$cond_{condition_field}_{condition_value}",
            "rule_id": rule_id,
            "lhs_ref": json.dumps({"type": "field", "field_id": condition_field_info['id'], "property": "value"}),
            "operator": "=",
            "rhs": json.dumps(condition_value),
            "bool_join": "AND",
            "position": 1
        }
        change_set.add_insert('logic_conditions', condition)
        
        # Create actions
        if action == "require":
            # First show the field
            show_action = {
                "id": f"$act_show_{target_field}",
                "rule_id": rule_id,
                "action": "show",
                "target_ref": json.dumps({"type": "field", "field_id": f"$fld_{target_field}"}),
                "params": None,
                "position": 1
            }
            change_set.add_insert('logic_actions', show_action)
            
            # Then require it
            require_action = {
                "id": f"$act_require_{target_field}",
                "rule_id": rule_id,
                "action": "require",
                "target_ref": json.dumps({"type": "field", "field_id": f"$fld_{target_field}"}),
                "params": None,
                "position": 2
            }
            change_set.add_insert('logic_actions', require_action)
        
        return change_set
    
    def _handle_create_form(self, parsed_query: ParsedQuery, context: Dict[str, Any], change_set: ChangeSet) -> ChangeSet:
        """Handle creating a new form"""
        
        form_title = parsed_query.parameters.get('form_title', parsed_query.form_identifier)
        form_slug = form_title.lower().replace(' ', '-').replace('_', '-')
        
        # Create form
        form_id = f"$form_{form_slug}"
        new_form = {
            "id": form_id,
            "slug": form_slug,
            "title": form_title.title(),
            "description": parsed_query.parameters.get('description', f"Form for {form_title}"),
            "status": "draft"
        }
        change_set.add_insert('forms', new_form)
        
        # Create default page
        page_id = f"$page_{form_slug}_1"
        new_page = {
            "id": page_id,
            "form_id": form_id,
            "title": "Page 1",
            "position": 1
        }
        change_set.add_insert('form_pages', new_page)
        
        # Add fields if specified
        fields = parsed_query.parameters.get('fields', [])
        for i, field_info in enumerate(fields):
            field_id = f"$fld_{field_info['code']}"
            type_id = self.db.get_field_type_id(field_info.get('type', 'short_text')) or 1
            
            new_field = {
                "id": field_id,
                "form_id": form_id,
                "page_id": page_id,
                "type_id": type_id,
                "code": field_info['code'],
                "label": field_info.get('label', field_info['code'].replace('_', ' ').title()),
                "position": i + 1,
                "required": field_info.get('required', 0),
                "read_only": 0,
                "visible_by_default": 1
            }
            change_set.add_insert('form_fields', new_field)
            
            # Add option set if needed
            if field_info.get('options'):
                option_set_id = f"$opt_set_{field_info['code']}"
                option_set = {
                    "id": option_set_id,
                    "form_id": form_id,
                    "name": f"{field_info['label']} Options"
                }
                change_set.add_insert('option_sets', option_set)
                
                # Add option items
                for j, option in enumerate(field_info['options']):
                    option_item = {
                        "id": f"$opt_{field_info['code']}_{j}",
                        "option_set_id": option_set_id,
                        "value": option,
                        "label": option,
                        "position": j + 1,
                        "is_active": 1
                    }
                    change_set.add_insert('option_items', option_item)
                
                # Bind field to option set
                binding = {
                    "field_id": field_id,
                    "option_set_id": option_set_id
                }
                change_set.add_insert('field_option_binding', binding)
        
        return change_set
    
    def _generate_with_llm(self, parsed_query: ParsedQuery, context: Dict[str, Any]) -> ChangeSet:
        """Use LLM to generate complex changes"""
        
        system_prompt = """You are a database change generator for a form management system.

Given a parsed query and database context, generate the appropriate database changes in JSON format.

Database schema:
- forms: id, slug, title, description, status, category_id
- form_pages: id, form_id, title, position
- form_fields: id, form_id, page_id, type_id, code, label, position, required, visible_by_default
- option_sets: id, form_id, name
- option_items: id, option_set_id, value, label, position, is_active
- field_option_binding: field_id, option_set_id
- logic_rules: id, form_id, name, trigger, scope, priority, enabled
- logic_conditions: id, rule_id, lhs_ref, operator, rhs, bool_join, position
- logic_actions: id, rule_id, action, target_ref, params, position

Field types: 1=short_text, 2=long_text, 3=dropdown, 4=radio, 5=checkbox, 6=tags, 7=date, 8=number, 9=file_upload, 10=email

Rules for change generation:
1. Use placeholder IDs starting with $ for new records that other records reference
2. For updates/deletes, use exact existing IDs from the database context
3. Include all required fields for inserts
4. Maintain referential integrity
5. Use appropriate positioning for ordered items

Return a JSON object with table names as keys and insert/update/delete arrays as values.
Only include non-empty operations."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", """
Parsed Query: {parsed_query}

Database Context: {context}

Generate the appropriate database changes as JSON:
""")
        ])
        
        chain = prompt | self.llm
        
        try:
            response = chain.invoke({
                "parsed_query": parsed_query.model_dump(),
                "context": json.dumps(context, default=str)
            })
            
            self.logger.debug(f"LLM Response: {response.content}")
            
            if not response.content or response.content.strip() == "":
                self.logger.warning("Empty response from LLM")
                return ChangeSet()
            
            # Strip markdown code blocks if present
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.startswith("```"):
                content = content[3:]   # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove trailing ```
            content = content.strip()
            
            changes_dict = json.loads(content)
            self.logger.debug(f"Parsed changes dict: {changes_dict}")
            
            # Convert to ChangeSet
            change_set = ChangeSet()
            for table, operations in changes_dict.items():
                for op_type in ['insert', 'update', 'delete']:
                    if op_type in operations:
                        for record in operations[op_type]:
                            if op_type == 'insert':
                                change_set.add_insert(table, record)
                            elif op_type == 'update':
                                change_set.add_update(table, record)
                            elif op_type == 'delete':
                                change_set.add_delete(table, record)
            
            return change_set
            
        except Exception as e:
            self.logger.error(f"Error generating changes with LLM: {e}")
            return ChangeSet()