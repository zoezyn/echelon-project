"""
Context Memory - Persistent Context Storage for Agent System

This module provides context memory capabilities to save plans, history messages,
and other context that needs to persist across agent interactions.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

class ContextMemory:
    """
    Context Memory system for storing and retrieving agent context
    
    This class provides persistent storage for:
    - User queries and clarification Q&A
    - Database exploration context
    - Validation results
    - Agent plans and strategies
    - Conversation history
    """
    
    def __init__(self):
        """Initialize the context memory system"""
        self.memory = {}
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now().isoformat()

    def store_context(self, key: str, value: Any, category: str = "general") -> bool:
        """
        Store context information with optional categorization
        
        Args:
            key: Unique identifier for the context
            value: The context data to store
            category: Category for organizing context (e.g., 'plan', 'history', 'exploration')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if category not in self.memory:
                self.memory[category] = {}
            
            self.memory[category][key] = {
                "value": value,
                "timestamp": datetime.now().isoformat(),
                "session_id": self.session_id
            }
            
            return True
        except Exception as e:
            return False
    
    def get_context(self, key: str, default: Any = None, category: str = "general") -> Any:
        """
        Retrieve context information
        
        Args:
            key: The context key to retrieve
            default: Default value if key not found
            category: Category to search in
        
        Returns:
            The stored context value or default
        """
        try:
            if category in self.memory and key in self.memory[category]:
                return self.memory[category][key]["value"]
            return default
        except Exception:
            return default
    
    def get_context_with_metadata(self, key: str, category: str = "general") -> Optional[Dict]:
        """
        Retrieve context with metadata (timestamp, session_id)
        
        Args:
            key: The context key to retrieve
            category: Category to search in
        
        Returns:
            Dictionary with value, timestamp, and session_id or None
        """
        try:
            if category in self.memory and key in self.memory[category]:
                return self.memory[category][key]
            return None
        except Exception:
            return None
    
    def store_plan(self, plan_id: str, plan_data: Dict) -> bool:
        """
        Store agent execution plan
        
        Args:
            plan_id: Unique identifier for the plan
            plan_data: Plan information including steps, strategy, etc.
        
        Returns:
            True if successful
        """
        return self.store_context(plan_id, plan_data, "plans")
    
    def get_plan(self, plan_id: str) -> Optional[Dict]:
        """
        Retrieve a stored plan
        
        Args:
            plan_id: The plan identifier
        
        Returns:
            Plan data or None if not found
        """
        return self.get_context(plan_id, None, "plans")
    
    def store_history_message(self, message_id: str, message_data: Dict) -> bool:
        """
        Store conversation history message
        
        Args:
            message_id: Unique identifier for the message
            message_data: Message content, role, timestamp, etc.
        
        Returns:
            True if successful
        """
        return self.store_context(message_id, message_data, "history")
    
    def get_conversation_history(self, limit: int = 50) -> List[Dict]:
        """
        Get recent conversation history
        
        Args:
            limit: Maximum number of messages to return
        
        Returns:
            List of message dictionaries ordered by timestamp
        """
        try:
            if "history" not in self.memory:
                return []
            
            messages = []
            for message_id, message_data in self.memory["history"].items():
                messages.append({
                    "id": message_id,
                    "timestamp": message_data["timestamp"],
                    **message_data["value"]
                })
            
            # Sort by timestamp and limit
            messages.sort(key=lambda x: x["timestamp"])
            return messages[-limit:]
            
        except Exception:
            return []
    
    def store_database_context(self, context_id: str, context_data: Dict) -> bool:
        """
        Store database exploration context
        
        Args:
            context_id: Unique identifier for the context
            context_data: Database exploration results
        
        Returns:
            True if successful
        """
        return self.store_context(context_id, context_data, "database")
    
    def get_database_context(self, context_id: str) -> Optional[Dict]:
        """
        Retrieve database exploration context
        
        Args:
            context_id: The context identifier
        
        Returns:
            Database context or None if not found
        """
        return self.get_context(context_id, None, "database")
    
    def store_validation_result(self, changeset_id: str, validation_data: Dict) -> bool:
        """
        Store validation results
        
        Args:
            changeset_id: Unique identifier for the changeset
            validation_data: Validation results and metadata
        
        Returns:
            True if successful
        """
        return self.store_context(changeset_id, validation_data, "validation")
    
    def get_validation_result(self, changeset_id: str) -> Optional[Dict]:
        """
        Retrieve validation results
        
        Args:
            changeset_id: The changeset identifier
        
        Returns:
            Validation results or None if not found
        """
        return self.get_context(changeset_id, None, "validation")
    
    def store_clarification_qa(self, query_id: str, qa_data: Dict) -> bool:
        """
        Store clarification questions and answers
        
        Args:
            query_id: Unique identifier for the original query
            qa_data: Questions, answers, and metadata
        
        Returns:
            True if successful
        """
        return self.store_context(query_id, qa_data, "clarification")
    
    def get_clarification_qa(self, query_id: str) -> Optional[Dict]:
        """
        Retrieve clarification Q&A
        
        Args:
            query_id: The query identifier
        
        Returns:
            Clarification Q&A or None if not found
        """
        return self.get_context(query_id, None, "clarification")
    
    def list_categories(self) -> List[str]:
        """
        List all context categories
        
        Returns:
            List of category names
        """
        return list(self.memory.keys())
    
    def list_keys_in_category(self, category: str) -> List[str]:
        """
        List all keys in a specific category
        
        Args:
            category: The category to list
        
        Returns:
            List of keys in the category
        """
        if category in self.memory:
            return list(self.memory[category].keys())
        return []
    
    def clear_category(self, category: str) -> bool:
        """
        Clear all context in a specific category
        
        Args:
            category: The category to clear
        
        Returns:
            True if successful
        """
        try:
            if category in self.memory:
                self.memory[category] = {}
            return True
        except Exception:
            return False
    
    def clear_all(self) -> bool:
        """
        Clear all stored context
        
        Returns:
            True if successful
        """
        try:
            self.memory = {}
            return True
        except Exception:
            return False
    
    def get_memory_summary(self) -> Dict:
        """
        Get a summary of stored context
        
        Returns:
            Dictionary with category counts and metadata
        """
        summary = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "categories": {}
        }
        
        for category, contexts in self.memory.items():
            summary["categories"][category] = {
                "count": len(contexts),
                "keys": list(contexts.keys())[:5]  # First 5 keys as preview
            }
        
        return summary
    
    def export_context(self, category: Optional[str] = None) -> Dict:
        """
        Export context data for persistence or analysis
        
        Args:
            category: Specific category to export, or None for all
        
        Returns:
            Dictionary containing the context data
        """
        if category:
            return {
                "category": category,
                "data": self.memory.get(category, {}),
                "session_id": self.session_id,
                "exported_at": datetime.now().isoformat()
            }
        else:
            return {
                "all_categories": self.memory,
                "session_id": self.session_id,
                "exported_at": datetime.now().isoformat()
            }
    
    def import_context(self, context_data: Dict) -> bool:
        """
        Import context data from export
        
        Args:
            context_data: Context data from export_context()
        
        Returns:
            True if successful
        """
        try:
            if "all_categories" in context_data:
                # Import all categories
                self.memory.update(context_data["all_categories"])
            elif "category" in context_data and "data" in context_data:
                # Import specific category
                category = context_data["category"]
                self.memory[category] = context_data["data"]
            else:
                return False
            
            return True
        except Exception:
            return False