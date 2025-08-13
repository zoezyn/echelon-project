from typing import Annotated, Dict, List, Any, Optional, Sequence, Union
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class QueryIntent(str, Enum):
    ADD_OPTIONS = "add_options"
    UPDATE_OPTIONS = "update_options"
    DELETE_OPTIONS = "delete_options"
    ADD_FIELD = "add_field"
    UPDATE_FIELD = "update_field"
    DELETE_FIELD = "delete_field"
    ADD_LOGIC = "add_logic"
    UPDATE_LOGIC = "update_logic"
    DELETE_LOGIC = "delete_logic"
    CREATE_FORM = "create_form"
    UPDATE_FORM = "update_form"
    DELETE_FORM = "delete_form"
    UNKNOWN = "unknown"

class DatabaseOperation(BaseModel):
    insert: List[Dict[str, Any]] = Field(default_factory=list)
    update: List[Dict[str, Any]] = Field(default_factory=list)
    delete: List[Dict[str, Any]] = Field(default_factory=list)

class ChangeSet(BaseModel):
    changes: Dict[str, DatabaseOperation] = Field(default_factory=dict)
    
    def add_insert(self, table: str, record: Dict[str, Any]):
        if table not in self.changes:
            self.changes[table] = DatabaseOperation()
        self.changes[table].insert.append(record)
    
    def add_update(self, table: str, record: Dict[str, Any]):
        if table not in self.changes:
            self.changes[table] = DatabaseOperation()
        self.changes[table].update.append(record)
    
    def add_delete(self, table: str, record: Dict[str, Any]):
        if table not in self.changes:
            self.changes[table] = DatabaseOperation()
        self.changes[table].delete.append(record)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for table, ops in self.changes.items():
            table_ops = {}
            if ops.insert:
                table_ops["insert"] = ops.insert
            if ops.update:
                table_ops["update"] = ops.update  
            if ops.delete:
                table_ops["delete"] = ops.delete
            if table_ops:
                result[table] = table_ops
        return result

class ParsedQuery(BaseModel):
    intent: QueryIntent
    form_identifier: Optional[str] = None
    field_code: Optional[str] = None
    target_entities: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_questions: List[str] = Field(default_factory=list)

class AgentState(BaseModel):
    user_query: str
    parsed_query: Optional[ParsedQuery] = None
    form_data: Optional[Dict[str, Any]] = None
    database_context: Dict[str, Any] = Field(default_factory=dict)
    change_set: Optional[ChangeSet] = None
    clarification_history: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    final_output: Optional[Dict[str, Any]] = None
    next_action: str = "analyze_query"
    pending_clarification_questions: List[str] = Field(default_factory=list)
    needs_user_input: bool = False

class FormResponse(BaseModel):
    """Pydantic model for validating the final JSON output format"""
    success: bool
    message: Optional[str] = None
    changes: Optional[Dict[str, Dict[str, List[Dict[str, Any]]]]] = None
    
    @field_validator('changes')
    @classmethod
    def validate_changes_structure(cls, v):
        """Validate that changes follow the expected table->operation->records structure"""
        if v is None:
            return v
        
        valid_operations = {'insert', 'update', 'delete'}
        
        for table_name, operations in v.items():
            if not isinstance(operations, dict):
                raise ValueError(f"Operations for table {table_name} must be a dictionary")
            
            for op_type, records in operations.items():
                if op_type not in valid_operations:
                    raise ValueError(f"Invalid operation type '{op_type}'. Must be one of: {valid_operations}")
                
                if not isinstance(records, list):
                    raise ValueError(f"Records for {table_name}.{op_type} must be a list")
                
                for record in records:
                    if not isinstance(record, dict):
                        raise ValueError(f"Each record in {table_name}.{op_type} must be a dictionary")
        
        return v
    
    def to_json_output(self) -> Dict[str, Any]:
        """Convert to clean JSON output format"""
        if self.success and self.changes:
            return self.changes
        else:
            return {
                "error": self.message or "An error occurred",
                "success": False
            }

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
    clarification_source: str