import sqlite3
from typing import Dict, List, Any, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv('DATABASE_PATH', 'data/forms.sqlite')
        
    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_schema(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get database schema information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            schema = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = []
                for col in cursor.fetchall():
                    columns.append({
                        'name': col[1],
                        'type': col[2],
                        'not_null': bool(col[3]),
                        'default_value': col[4],
                        'primary_key': bool(col[5])
                    })
                schema[table] = columns
                
            return schema
    
    def find_form_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Find form by ID or slug"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM forms 
                WHERE id = ? OR slug = ? OR title LIKE ?
            """, (identifier, identifier, f"%{identifier}%"))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_form_fields(self, form_id: str) -> List[Dict[str, Any]]:
        """Get all fields for a form"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ff.*, ft.key as field_type_key, ft.has_options
                FROM form_fields ff
                JOIN field_types ft ON ff.type_id = ft.id
                WHERE ff.form_id = ?
                ORDER BY ff.position
            """, (form_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_field_options(self, field_id: str) -> List[Dict[str, Any]]:
        """Get options for a field"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT oi.* FROM option_items oi
                JOIN field_option_binding fob ON oi.option_set_id = fob.option_set_id
                WHERE fob.field_id = ?
                ORDER BY oi.position
            """, (field_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_option_set_by_field_code(self, form_id: str, field_code: str) -> Optional[str]:
        """Get option set ID for a field by code"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fob.option_set_id
                FROM form_fields ff
                JOIN field_option_binding fob ON ff.id = fob.field_id
                WHERE ff.form_id = ? AND ff.code = ?
            """, (form_id, field_code))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def get_field_type_id(self, type_key: str) -> Optional[int]:
        """Get field type ID by key"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM field_types WHERE key = ?", (type_key,))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def get_form_pages(self, form_id: str) -> List[Dict[str, Any]]:
        """Get all pages for a form"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM form_pages 
                WHERE form_id = ? 
                ORDER BY position
            """, (form_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_existing_option_by_value(self, option_set_id: str, value: str) -> Optional[Dict[str, Any]]:
        """Find existing option by value"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM option_items 
                WHERE option_set_id = ? AND (value = ? OR label = ?)
            """, (option_set_id, value, value))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_max_position(self, table: str, parent_field: str, parent_id: str) -> int:
        """Get the maximum position value for ordering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT MAX(position) FROM {table} WHERE {parent_field} = ?
            """, (parent_id,))
            result = cursor.fetchone()[0]
            return (result or 0) + 1
    
    def search_forms(self, query: str) -> List[Dict[str, Any]]:
        """Search forms by title or description"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM forms 
                WHERE title LIKE ? OR description LIKE ? OR slug LIKE ?
            """, (f"%{query}%", f"%{query}%", f"%{query}%"))
            return [dict(row) for row in cursor.fetchall()]
    
    def validate_foreign_keys(self, changes: Dict[str, Any]) -> List[str]:
        """Validate that foreign key references exist"""
        errors = []
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for table, operations in changes.items():
                for operation in ['insert', 'update']:
                    if operation not in operations:
                        continue
                        
                    for record in operations[operation]:
                        # Check form_id references
                        if 'form_id' in record:
                            form_id = record['form_id']
                            if not form_id.startswith('$'):  # Skip placeholder references
                                cursor.execute("SELECT 1 FROM forms WHERE id = ?", (form_id,))
                                if not cursor.fetchone():
                                    errors.append(f"Form ID {form_id} does not exist")
                        
                        # Check option_set_id references
                        if 'option_set_id' in record:
                            option_set_id = record['option_set_id']
                            if not option_set_id.startswith('$'):
                                cursor.execute("SELECT 1 FROM option_sets WHERE id = ?", (option_set_id,))
                                if not cursor.fetchone():
                                    errors.append(f"Option set ID {option_set_id} does not exist")
                        
                        # Check type_id references
                        if 'type_id' in record:
                            type_id = record['type_id']
                            cursor.execute("SELECT 1 FROM field_types WHERE id = ?", (type_id,))
                            if not cursor.fetchone():
                                errors.append(f"Field type ID {type_id} does not exist")
        
        return errors