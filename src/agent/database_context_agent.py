"""
Database Context Agent - LLM-Based Database Explorer

This agent specializes in exploring and understanding the current database state,
providing context needed for intelligent decision making about form modifications.
"""

import sqlite3
import json
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any
from agents import Agent, function_tool, Runner

class DatabaseContextAgent:
    """
    LLM-powered agent that explores database structure and content
    
    This agent has tools to explore schema, relationships, sample data,
    and can discover existing forms, fields, options, and logic rules
    to provide context needed for intelligent decision making.
    """
    
    def __init__(self, model="gpt-5", db_path="data/forms.sqlite"):
        self.db_path = db_path
        self.model = model
        
        # Create function tools
        self.tools = self._create_tools()
        
        self.agent = Agent(
            name="DatabaseContextAgent",
            model=model,
            instructions=self._get_instructions(),
            tools=self.tools
        )
        
    def _get_instructions(self):
        return """# Database Context Agent

You are a specialized LLM agent for exploring and understanding enterprise form system databases. Your job is to gather relevant context about the current database state to inform decision making.

## Your Expertise

You have access to tools that can explore:
- Database schema and table structures
- Foreign key relationships between tables
- Sample data from any table
- Existing forms, fields, options, and logic rules
- High-level database context and patterns

## Database Schema Knowledge
The database contains these key tables:

### Core Form Structure

- **forms**: Top-level form definitions (id, slug, title, status, etc.)
- **form_pages**: Form sections that organize fields (id, form_id, title, position) - REQUIRED for field organization
- **form_fields**: Individual input elements (id, form_id, page_id, type_id, code, label, position, required, etc.)
- **field_types**: Available field types (text, dropdown, checkbox, etc.)

### Choice/Option System

- **option_sets**: Collections of choices for dropdowns/radios (id, name, form_id)
- **option_items**: Individual choice options (id, option_set_id, value, label, position, is_active)
- **field_option_binding**: Links fields to their option sets (field_id, option_set_id) - CRITICAL for dropdowns

### Dynamic Logic System

- **logic_rules**: Conditional behavior definitions (id, form_id, name, trigger, scope, priority)
- **logic_conditions**: When rules should fire (id, rule_id, lhs_ref, operator, rhs, bool_join)
- **logic_actions**: What happens when conditions met (id, rule_id, action, target_ref, params)

## COMPLETE FORM CREATION WORKFLOW

When asked to explore form creation, you MUST examine ALL these tables:
1. **forms** - for form metadata structure
2. **form_pages** - forms need pages to organize fields 
3. **form_fields** - field structure and requirements
4. **field_types** - available field types (especially text=1, dropdown=4, etc.)
5. **option_sets** - for dropdown field choices
6. **option_items** - individual dropdown options  
7. **field_option_binding** - how fields connect to option sets

## Available Tools

### For finding forms, fields, options, and logic rules:
- **get_forms**: Get information about existing forms
- **get_fields**: Get information about form fields. You should call this tool ONLY after finding a form to explore its fields and use the `form_id` parameter to filter by specific form.
- **get_options**: Get information about option sets and items
- **get_logic_rules**: Get information about logic rules and conditions

### For exploring database structure and content:
- **discover_relationships**: Find foreign key relationships

### For general information: (Only use them when necessary)
- **get_db_schema**: Get complete database schema with tables and columns
- **list_tables**: List all tables in the database

## Core Responsibilities

1. **Explore efficiently**: Use tools strategically to gather relevant information
2. **Provide context**: Return comprehensive information about database state
3. **Identify patterns**: Recognize naming conventions and data patterns
4. **Map relationships**: Understand how entities connect to each other
5. **Sample intelligently**: Get representative data samples when needed
6. **Follow foreign keys**: Always discover ALL related tables through foreign key relationships
7. **Complete table coverage**: Find all intermediate tables that connect entities

## Return the EXACT table that are necessary with ALL REQUIRED FIELDS

This is essential because the master agent needs complete information to generate valid changesets with:
- ALL REQUIRED FIELDS populated correctly
- Proper column types and constraints
- Complete foreign key references

## Guidelines

- Use tools proactively to understand the current state before making recommendations
- When finding forms, fields, or options by name, find the most relevant match
- When exploring for a specific query, prioritize gathering information that directly relates to the user's request
- You should always return the results and the EXACT table rows that are relevant to the query in JSON format, with clear keys for each piece of information
- ALWAYS include complete row data - never summarize or truncate database records
- Include table names as keys in your response so the master agent knows which tables to modify
- When asked to find specific records, return the full record data with all columns

For complex queries, you should generate a list plan steps first and execute them sequentially to gather all necessary context.


DO NOT abbreviate, filter, or summarize the schema information. Return the complete output for the requested tables.

"""

    def _create_tools(self) -> List:
        """Create function tools using @function_tool decorator"""
        
        @function_tool
        def get_db_schema() -> str:
            """Get the complete database schema with all tables and columns"""
            try:
                result = self.get_db_schema()
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error getting schema: {str(e)}"
        
        @function_tool
        def list_tables() -> str:
            """List all tables in the database"""
            try:
                result = self.list_tables()
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing tables: {str(e)}"
        
        # @function_tool
        # def get_table_sample(table_name: str, limit: int = 5) -> str:
        #     """Get sample rows from a specific table
            
        #     Args:
        #         table_name: Name of the table to sample
        #         limit: Number of rows to return (default 5)
        #     """
        #     try:
        #         result = self.get_table_sample(table_name, limit)
        #         return json.dumps(result, indent=2)
        #     except Exception as e:
        #         return f"Error getting table sample: {str(e)}"
        
        @function_tool
        def discover_relationships() -> str:
            """Discover foreign key relationships in the database"""
            try:
                result = self.discover_relationships()
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error discovering relationships: {str(e)}"
        
        @function_tool
        def get_forms(form_id: str = None, form_name: str = None, limit: int = 10) -> str:
            """Get information about existing forms
            
            Args:
                form_id: Specific form ID (optional)
                form_name: Form name for fuzzy matching (optional)
                limit: Number of forms to return (default 10)
            """
            try:
                result = self.get_forms(form_id, form_name, limit)
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error getting forms: {str(e)}"
        
        @function_tool
        def get_fields(form_id: str = None, field_type: str = None, limit: int = 20) -> str:
            """Get information about form fields
            
            Args:
                form_id: Filter by form ID (optional)
                field_type: Filter by field type (optional)
                limit: Number of fields to return (default 20)
            """
            try:
                result = self.get_fields(form_id, field_type, limit)
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error getting fields: {str(e)}"
        
        @function_tool
        def get_options(form_id: str = None, option_set_id: str = None) -> str:
            """Get information about option sets and items
            
            Args:
                form_id: Filter by form ID (optional)
                option_set_id: Specific option set ID (optional)
            """
            try:
                result = self.get_options(form_id, option_set_id)
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error getting options: {str(e)}"
        
        @function_tool
        def get_logic_rules(form_id: str = None, rule_id: str = None) -> str:
            """Get information about logic rules, conditions, and actions
            
            Args:
                form_id: Filter by form ID (optional)
                rule_id: Specific rule ID (optional)
            """
            try:
                result = self.get_logic_rules(form_id, rule_id)
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error getting logic rules: {str(e)}"
        
        # @function_tool
        # def describe_db_context() -> str:
        #     """Get a high-level description of the database content and patterns"""
        #     try:
        #         result = self.describe_db_context()
        #         return json.dumps(result, indent=2)
        #     except Exception as e:
        #         return f"Error describing context: {str(e)}"
        
        return [
            get_db_schema, list_tables, discover_relationships,
            get_forms, get_fields, get_options, get_logic_rules
        ]

    def _get_db_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two strings using SequenceMatcher"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def find_similar_forms(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Find forms with semantic similarity to the query"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM forms WHERE status = 'published'")
            
            # Get column names
            cursor.execute("PRAGMA table_info(forms)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Get form data
            cursor.execute("SELECT * FROM forms WHERE status = 'published'")
            rows = cursor.fetchall()
            all_forms = [dict(zip(columns, row)) for row in rows]
        
        # Calculate similarity scores
        form_similarities = []
        for form in all_forms:
            # Check similarity against title, slug, and description
            title_sim = self._calculate_similarity(query, form['title'] or '')
            slug_sim = self._calculate_similarity(query, form['slug'] or '')
            desc_sim = self._calculate_similarity(query, form['description'] or '') if form.get('description') else 0
            
            # Use the highest similarity score
            max_sim = max(title_sim, slug_sim, desc_sim)
            
            if max_sim > 0.3:  # Only include if similarity is above threshold
                form_similarities.append((form, max_sim))
        
        # Sort by similarity score and return top results
        form_similarities.sort(key=lambda x: x[1], reverse=True)
        return [form for form, _ in form_similarities[:limit]]

    def get_db_schema(self) -> Dict:
        """Get complete database schema"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                schema = {}
                for (table_name,) in tables:
                    # Get table info
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    
                    # Get foreign keys
                    cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                    foreign_keys = cursor.fetchall()
                    
                    schema[table_name] = {
                        "columns": [
                            {
                                "name": col[1],
                                "type": col[2],
                                "not_null": bool(col[3]),
                                "primary_key": bool(col[5])
                            } for col in columns
                        ],
                        "foreign_keys": [
                            {
                                "column": fk[3],
                                "references_table": fk[2],
                                "references_column": fk[4]
                            } for fk in foreign_keys
                        ]
                    }
                
                return {"schema": schema}
                
        except Exception as e:
            return {"error": f"Failed to get schema: {str(e)}"}

    def list_tables(self) -> Dict:
        """List all tables in the database"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                return {"tables": tables}
        except Exception as e:
            return {"error": f"Failed to list tables: {str(e)}"}

    def get_table_sample(self, table_name: str, limit: int = 5) -> Dict:
        """Get sample rows from a table"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
                rows = cursor.fetchall()
                
                # Get column names
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [col[1] for col in cursor.fetchall()]
                
                # Convert to dict format
                sample_data = []
                for row in rows:
                    sample_data.append(dict(zip(columns, row)))
                
                return {"table": table_name, "sample_data": sample_data, "count": len(sample_data)}
                
        except Exception as e:
            return {"error": f"Failed to get sample from {table_name}: {str(e)}"}

    def discover_relationships(self) -> Dict:
        """Discover all foreign key relationships"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                relationships = []
                for table in tables:
                    cursor.execute(f"PRAGMA foreign_key_list({table})")
                    foreign_keys = cursor.fetchall()
                    
                    for fk in foreign_keys:
                        relationships.append({
                            "from_table": table,
                            "from_column": fk[3],
                            "to_table": fk[2],
                            "to_column": fk[4]
                        })
                
                return {"relationships": relationships}
                
        except Exception as e:
            return {"error": f"Failed to discover relationships: {str(e)}"}

    def get_forms(self, form_id: str = None, form_name: str = None, limit: int = 10) -> Dict:
        """Get information about forms"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get column names first
                cursor.execute("PRAGMA table_info(forms)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if form_id:
                    cursor.execute("SELECT * FROM forms WHERE id = ?", (form_id,))
                    rows = cursor.fetchall()
                elif form_name:
                    # Use similarity matching for better form finding
                    similar_forms = self.find_similar_forms(form_name, limit)
                    
                    # Convert back to the format expected by the rest of the method
                    rows = []
                    for form in similar_forms:
                        row = tuple(form.get(col) for col in columns)
                        rows.append(row)
                else:
                    cursor.execute("SELECT * FROM forms LIMIT ?", (limit,))
                    rows = cursor.fetchall()
                
                forms = [dict(zip(columns, row)) for row in rows]
                return {"forms": forms}
                
        except Exception as e:
            return {"error": f"Failed to get forms: {str(e)}"}

    def get_fields(self, form_id: str = None, field_type: str = None, limit: int = 20) -> Dict:
        """Get information about form fields"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT ff.*, ft.key as field_type_key, ft.has_options, ft.allows_multiple
                    FROM form_fields ff
                    JOIN field_types ft ON ff.type_id = ft.id
                """
                params = []
                
                if form_id:
                    query += " WHERE ff.form_id = ?"
                    params.append(form_id)
                
                if field_type:
                    if params:
                        query += " AND ft.key = ?"
                    else:
                        query += " WHERE ft.key = ?"
                    params.append(field_type)
                
                query += f" LIMIT {limit}"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Get column names - need to handle the JOIN
                columns = [desc[0] for desc in cursor.description]
                
                fields = [dict(zip(columns, row)) for row in rows]
                return {"fields": fields}
                
        except Exception as e:
            return {"error": f"Failed to get fields: {str(e)}"}

    def get_options(self, form_id: str = None, option_set_id: str = None) -> Dict:
        """Get information about option sets and items"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get option sets
                if option_set_id:
                    cursor.execute("SELECT * FROM option_sets WHERE id = ?", (option_set_id,))
                elif form_id:
                    cursor.execute("SELECT * FROM option_sets WHERE form_id = ?", (form_id,))
                else:
                    cursor.execute("SELECT * FROM option_sets LIMIT 20")
                
                option_sets = cursor.fetchall()
                cursor.execute("PRAGMA table_info(option_sets)")
                os_columns = [col[1] for col in cursor.fetchall()]
                
                option_sets_data = []
                for os_row in option_sets:
                    os_dict = dict(zip(os_columns, os_row))
                    
                    # Get items for this option set
                    cursor.execute("SELECT * FROM option_items WHERE option_set_id = ? ORDER BY position", (os_dict['id'],))
                    items = cursor.fetchall()
                    
                    cursor.execute("PRAGMA table_info(option_items)")
                    item_columns = [col[1] for col in cursor.fetchall()]
                    
                    os_dict['items'] = [dict(zip(item_columns, item)) for item in items]
                    option_sets_data.append(os_dict)
                
                return {"option_sets": option_sets_data}
                
        except Exception as e:
            return {"error": f"Failed to get options: {str(e)}"}

    def get_logic_rules(self, form_id: str = None, rule_id: str = None) -> Dict:
        """Get information about logic rules"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get logic rules
                if rule_id:
                    cursor.execute("SELECT * FROM logic_rules WHERE id = ?", (rule_id,))
                elif form_id:
                    cursor.execute("SELECT * FROM logic_rules WHERE form_id = ?", (form_id,))
                else:
                    cursor.execute("SELECT * FROM logic_rules LIMIT 20")
                
                rules = cursor.fetchall()
                cursor.execute("PRAGMA table_info(logic_rules)")
                rule_columns = [col[1] for col in cursor.fetchall()]
                
                rules_data = []
                for rule_row in rules:
                    rule_dict = dict(zip(rule_columns, rule_row))
                    
                    # Get conditions for this rule
                    cursor.execute("SELECT * FROM logic_conditions WHERE rule_id = ? ORDER BY position", (rule_dict['id'],))
                    conditions = cursor.fetchall()
                    cursor.execute("PRAGMA table_info(logic_conditions)")
                    cond_columns = [col[1] for col in cursor.fetchall()]
                    rule_dict['conditions'] = [dict(zip(cond_columns, cond)) for cond in conditions]
                    
                    # Get actions for this rule
                    cursor.execute("SELECT * FROM logic_actions WHERE rule_id = ? ORDER BY position", (rule_dict['id'],))
                    actions = cursor.fetchall()
                    cursor.execute("PRAGMA table_info(logic_actions)")
                    action_columns = [col[1] for col in cursor.fetchall()]
                    rule_dict['actions'] = [dict(zip(action_columns, action)) for action in actions]
                    
                    rules_data.append(rule_dict)
                
                return {"logic_rules": rules_data}
                
        except Exception as e:
            return {"error": f"Failed to get logic rules: {str(e)}"}

    # def describe_db_context(self) -> Dict:
    #     """Get high-level database description"""
    #     try:
    #         with self._get_db_connection() as conn:
    #             cursor = conn.cursor()
                
    #             context = {}
                
    #             # Count records in each table
    #             tables = ['forms', 'form_pages', 'form_fields', 'option_sets', 'option_items', 'logic_rules']
    #             for table in tables:
    #                 try:
    #                     cursor.execute(f"SELECT COUNT(*) FROM {table}")
    #                     context[f"{table}_count"] = cursor.fetchone()[0]
    #                 except:
    #                     context[f"{table}_count"] = 0
                
    #             # Get form categories
    #             cursor.execute("SELECT COUNT(*) FROM categories")
    #             context['categories_count'] = cursor.fetchone()[0]
                
    #             # Get field types
    #             cursor.execute("SELECT key, COUNT(*) as usage_count FROM field_types ft LEFT JOIN form_fields ff ON ft.id = ff.type_id GROUP BY ft.key")
    #             field_types = cursor.fetchall()
    #             context['field_types'] = [{"type": ft[0], "usage_count": ft[1]} for ft in field_types]
                
    #             # Get recent activity (last 10 forms by updated_at)
    #             cursor.execute("SELECT id, title, status, updated_at FROM forms ORDER BY updated_at DESC LIMIT 10")
    #             recent_forms = cursor.fetchall()
    #             context['recent_forms'] = [
    #                 {"id": f[0], "title": f[1], "status": f[2], "updated_at": f[3]} 
    #                 for f in recent_forms
    #             ]
                
    #             return {"context": context}
                
        except Exception as e:
            return {"error": f"Failed to describe context: {str(e)}"}

    # def get_database_context(self, exploration_type: str, parameters: Dict = None) -> Dict:
    #     """Main method for exploring database - called by master agent"""
    #     if parameters is None:
    #         parameters = {}
            
    #     try:
    #         if exploration_type == "get_schema":
    #             return self.get_db_schema()
    #         elif exploration_type == "get_forms":
    #             return self.get_forms(
    #                 form_id=parameters.get("form_id"),
    #                 limit=parameters.get("limit", 10)
    #             )
    #         elif exploration_type == "get_fields":
    #             return self.get_fields(
    #                 form_id=parameters.get("form_id"),
    #                 field_type=parameters.get("field_type"),
    #                 limit=parameters.get("limit", 20)
    #             )
    #         elif exploration_type == "get_options":
    #             return self.get_options(
    #                 form_id=parameters.get("form_id"),
    #                 option_set_id=parameters.get("option_set_id")
    #             )
    #         elif exploration_type == "get_logic_rules":
    #             return self.get_logic_rules(
    #                 form_id=parameters.get("form_id"),
    #                 rule_id=parameters.get("rule_id")
    #             )
    #         elif exploration_type == "sample_data":
    #             table_name = parameters.get("table_name", "forms")
    #             return self.get_table_sample(table_name, parameters.get("limit", 5))
    #         elif exploration_type == "describe_context":
    #             return self.describe_db_context()
    #         elif exploration_type == "discover_relationships":
    #             return self.discover_relationships()
    #         else:
    #             return {"error": f"Unknown exploration type: {exploration_type}"}
                
    #     except Exception as e:
    #         return {"error": f"Database exploration failed: {str(e)}"}