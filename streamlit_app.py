"""
Interactive Streamlit Chatbot for Enterprise Form Management System

This Streamlit app provides a conversational interface to interact with the
enterprise form management system using natural language queries.
"""

import streamlit as st
import json
import traceback
from datetime import datetime
from typing import Dict, Any

# Import the master agent
from src.agent.master_agent import create_master_agent

# Configure page
st.set_page_config(
    page_title="Form Management Chatbot",
    page_icon=">",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
    
    .user-message {
        background-color: #e8f4fd;
        border-left-color: #1f77b4;
    }
    
    .assistant-message {
        background-color: #f0f2f6;
        border-left-color: #ff7f0e;
    }
    
    .error-message {
        background-color: #ffe6e6;
        border-left-color: #d62728;
    }
    
    .success-message {
        background-color: #e6ffe6;
        border-left-color: #2ca02c;
    }
    
    .changeset-display {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
        font-family: monospace;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "master_agent" not in st.session_state:
        st.session_state.master_agent = None
    
    if "agent_initialized" not in st.session_state:
        st.session_state.agent_initialized = False

def initialize_agent(model: str, db_path: str, verbose_logging: bool = False) -> bool:
    """Initialize the master agent"""
    try:
        with st.spinner("Initializing agent system..."):
            st.session_state.master_agent = create_master_agent(
                model=model,
                db_path=db_path,
                verbose_logging=verbose_logging
            )
            st.session_state.agent_initialized = True
            st.success(" Agent system initialized successfully!")
            return True
    except Exception as e:
        st.error(f"L Failed to initialize agent system: {str(e)}")
        st.session_state.agent_initialized = False
        return False

def display_message(role: str, content: str, message_type: str = "normal"):
    """Display a chat message with appropriate styling"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if role == "user":
        css_class = "chat-message user-message"
        icon = "=d"
    else:
        if message_type == "error":
            css_class = "chat-message error-message"
            icon = "L"
        elif message_type == "success":
            css_class = "chat-message success-message"
            icon = ""
        else:
            css_class = "chat-message assistant-message"
            icon = ">"
    
    st.markdown(f"""
    <div class="{css_class}">
        <strong>{icon} {role.title()} ({timestamp})</strong><br>
        {content}
    </div>
    """, unsafe_allow_html=True)

def format_changeset_display(changeset: Dict[str, Any]) -> str:
    """Format changeset for better display"""
    try:
        return f"""
```json
{json.dumps(changeset, indent=2)}
```
"""
    except Exception:
        return f"```\n{str(changeset)}\n```"

def process_user_query(query: str) -> Dict[str, Any]:
    """Process user query through the master agent"""
    try:
        # Fix for Streamlit: create new event loop if none exists
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Process the query
        result = st.session_state.master_agent.process_query(query)
        return result
    except Exception as e:
        return {
            "error": f"Failed to process query: {str(e)}",
            "traceback": traceback.format_exc()
        }

def main():
    """Main Streamlit app"""
    # Initialize session state
    initialize_session_state()
    
    # Header
    st.markdown('<div class="main-header">> Enterprise Form Management Chatbot</div>', 
                unsafe_allow_html=True)
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("� Configuration")
        
        # Model selection
        model = st.selectbox(
            "Select AI Model",
            ["gpt-4o", "gpt-4", "gpt-3.5-turbo"],
            index=0,
            help="Choose the AI model for the agent system"
        )
        
        # Database path
        db_path = st.text_input(
            "Database Path",
            value="data/forms.sqlite",
            help="Path to the SQLite database file"
        )
        
        # Verbose logging
        verbose_logging = st.checkbox(
            "Enable Verbose Logging",
            value=False,
            help="Enable detailed logging for debugging"
        )
        
        # Initialize/Reinitialize button
        if st.button("= Initialize Agent System", type="primary"):
            st.session_state.agent_initialized = False
            st.session_state.master_agent = None
            initialize_agent(model, db_path, verbose_logging)
        
        # Status indicator
        if st.session_state.agent_initialized:
            st.success(" Agent System Ready")
        else:
            st.warning("� Agent System Not Initialized")
        
        # Separator
        st.markdown("---")
        
        # Clear chat button
        if st.button("=� Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
        
        # Example queries
        st.markdown("### =� Example Queries")
        example_queries = [
            "Create a new form for vacation requests with fields for start date, end date, and reason",
            "Add a priority field to the contact form with options: Low, Medium, High, Urgent",
            "Update the employment form to require university name when status is Student",
            "Show me all forms in the database",
            "Create logic rules to hide certain fields based on user selections"
        ]
        
        for i, example in enumerate(example_queries):
            if st.button(f"=� Example {i+1}", key=f"example_{i}", help=example):
                st.session_state.messages.append({"role": "user", "content": example})
                st.rerun()
    
    # Main chat interface
    st.header("=� Chat Interface")
    
    # Auto-initialize agent if not done
    if not st.session_state.agent_initialized:
        if initialize_agent(model, db_path, verbose_logging):
            st.rerun()
    
    # Display chat messages
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.messages:
            display_message(
                message["role"], 
                message["content"],
                message.get("type", "normal")
            )
    
    # User input
    if st.session_state.agent_initialized:
        # Use form to handle Enter key properly
        with st.form(key="chat_form", clear_on_submit=True):
            user_input = st.text_area(
                "Enter your message:",
                placeholder="Ask me to create forms, add fields, modify options, or any other form management task...",
                height=100,
                key="user_input"
            )
            
            submit_button = st.form_submit_button("Send 📤", type="primary")
            
            if submit_button and user_input.strip():
                # Add user message
                st.session_state.messages.append({
                    "role": "user", 
                    "content": user_input
                })
                
                # Process the query
                with st.spinner("> Processing your request..."):
                    result = process_user_query(user_input)
                
                # Handle different types of responses
                if "error" in result:
                    # Error response
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"**Error:** {result['error']}",
                        "type": "error"
                    })
                elif "changeset" in result:
                    # Successful changeset
                    changeset_display = format_changeset_display(result["changeset"])
                    response_content = f"""
** Changeset Generated Successfully!**

The following database operations will be performed:

{changeset_display}

*This changeset represents the database modifications needed to fulfill your request.*
"""
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_content,
                        "type": "success"
                    })
                elif "response" in result:
                    # Agent response (clarification, analysis, etc.)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result["response"]
                    })
                else:
                    # Unexpected response format
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"**Response:** {json.dumps(result, indent=2)}",
                        "type": "normal"
                    })
                
                # Rerun to show new messages
                st.rerun()
    
    else:
        st.warning("� Please initialize the agent system using the sidebar configuration.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem;">
        > Enterprise Form Management Chatbot | Powered by OpenAI Agents SDK
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()