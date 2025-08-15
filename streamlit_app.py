import streamlit as st
import sys
import os
import json
import asyncio
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.agent.master_agent import create_master_agent

# Page config
st.set_page_config(
    page_title="Enterprise Form Management Agent (Dynamic, built with openai agents sdk)",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent" not in st.session_state:
    st.session_state.agent = None

if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = f"streamlit_{uuid.uuid4().hex[:8]}"

# Sidebar configuration
st.sidebar.title("⚙️ Configuration")

# Model selection
model_provider = st.sidebar.selectbox(
    "Choose AI Model",
    ["gpt-4o"],
    index=0,
    help="Select which OpenAI model to use for processing"
)

# Database path
db_path = st.sidebar.text_input(
    "Database Path",
    value="data/forms.sqlite",
    help="Path to the SQLite database file"
)

# Verbose logging option
verbose_logging = st.sidebar.checkbox(
    "Enable Verbose Logging",
    value=True,
    help="Enable detailed logging for debugging"
)

# Initialize agent if not exists or settings changed
current_config = f"{model_provider}_{db_path}_{verbose_logging}"
if (st.session_state.agent is None or 
    getattr(st.session_state, 'current_config', None) != current_config):
    
    try:
        with st.sidebar:
            with st.spinner("Initializing agent system..."):
                st.session_state.agent = create_master_agent(
                    model=model_provider,
                    db_path=db_path,
                    verbose_logging=verbose_logging,
                    session_id=st.session_state.session_id
                )
                st.session_state.current_config = current_config
        st.sidebar.success("✅ Agent system ready!")
    except Exception as e:
        st.sidebar.error(f"❌ Error initializing agent: {str(e)}")
        st.sidebar.info("Please check your API keys and database path")

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.markdown("### 📖 What I can help with:")
st.sidebar.markdown("""
- **Forms**: Create, update, delete forms
- **Fields**: Add, modify, remove form fields  
- **Options**: Manage dropdown/radio options
- **Logic Rules**: Add conditional logic
- **Validation**: Check form constraints
- **Database Operations**: Query and modify form data
""")

st.sidebar.markdown("### 💡 Example queries:")
st.sidebar.markdown("""
- "Add a Paris option to destinations field in travel request form"
- "Create a new procurement form with vendor and budget fields"
- "Update the employment form to require university when status is Student"
- "Show me all forms in the database"
""")

# Agent status
if st.session_state.agent:
    st.sidebar.success(f"🤖 Agent Ready (Session: {st.session_state.session_id[:8]})")
    
    # Show Langfuse status if available
    try:
        langfuse_status = st.session_state.agent.get_langfuse_status()
        if langfuse_status.get("enabled"):
            st.sidebar.success("📊 Langfuse tracking enabled")
        else:
            st.sidebar.info("📊 Langfuse tracking disabled")
    except:
        pass

# Clear chat button
if st.sidebar.button("🗑️ Clear Chat", type="secondary"):
    st.session_state.messages = []
    st.rerun()

# Main interface
st.title("🚀 Enterprise Form Management Agent (Dynamic, built with openai agents sdk)")
st.markdown("**Natural language interface for enterprise form management**")

# Display chat messages
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        elif message["role"] == "assistant":
            with st.chat_message("assistant"):
                if message.get("type") == "error":
                    st.error(message["content"])
                elif message.get("type") == "success":
                    st.success(message["content"])
                elif message.get("changeset"):
                    st.success("✅ **Changeset Generated Successfully!**")
                    st.markdown("The following database operations will be performed:")
                    st.json(message["changeset"])
                else:
                    st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Describe what you want to do with your forms..."):
    if st.session_state.agent is None:
        st.error("Please wait for the agent to initialize or check your API keys.")
    else:
        # Add user message to chat history
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt,
            "timestamp": datetime.now().isoformat()
        })
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Process the message
        with st.chat_message("assistant"):
            with st.spinner("🤖 Processing your request..."):
                try:
                    # Fix for Streamlit: create new event loop if none exists
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Process the message through the master agent
                    result = st.session_state.agent.process_query(prompt)
                    
                    if result.get("success") and result.get("changeset"):
                        # Successful changeset generation
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "Changeset generated successfully!",
                            "changeset": result["changeset"],
                            "type": "success",
                            "query_id": result.get("query_id"),
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        st.success("✅ **Changeset Generated Successfully!**")
                        st.markdown("The following database operations will be performed:")
                        st.json(result["changeset"])
                        
                    elif result.get("error"):
                        # Error response
                        error_content = f"**Error:** {result['error']}"
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": error_content,
                            "type": "error",
                            "timestamp": datetime.now().isoformat()
                        })
                        st.error(error_content)
                        
                    elif result.get("response"):
                        # Agent response (clarification, analysis, etc.)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": result["response"],
                            "type": "normal",
                            "query_id": result.get("query_id"),
                            "timestamp": datetime.now().isoformat()
                        })
                        st.markdown(result["response"])
                        
                    else:
                        # Unexpected response format
                        response_content = f"**Response:** {json.dumps(result, indent=2)}"
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response_content,
                            "type": "normal",
                            "timestamp": datetime.now().isoformat()
                        })
                        st.markdown(response_content)
                        
                except Exception as e:
                    error_msg = f"An error occurred: {str(e)}"
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"**Error:** {error_msg}",
                        "type": "error",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.error(error_msg)
                    st.info("Please check your API keys and database configuration.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.8em;'>
    🚀 Enterprise Form Management Agent • Powered by OpenAI Agents SDK • Built with Streamlit
</div>
""", unsafe_allow_html=True)

# Show current state in expander (for debugging)
if st.sidebar.checkbox("🐛 Debug Mode", value=False):
    with st.expander("Debug Information", expanded=False):
        debug_info = {
            "total_messages": len(st.session_state.messages),
            "model": model_provider,
            "db_path": db_path,
            "session_id": st.session_state.session_id,
            "agent_initialized": st.session_state.agent is not None,
            "verbose_logging": verbose_logging
        }
        
        # Add agent status if available
        if st.session_state.agent:
            try:
                debug_info["langfuse_status"] = st.session_state.agent.get_langfuse_status()
                debug_info["memory_summary"] = st.session_state.agent.get_memory_summary()
            except:
                pass
        
        st.json(debug_info)
        
        if st.session_state.messages:
            st.subheader("Message History")
            for i, msg in enumerate(st.session_state.messages):
                st.text(f"{i}: {msg['role']} - {msg['content'][:100]}...")
                
        # Test Langfuse connection button
        if st.button("🧪 Test Langfuse Connection"):
            if st.session_state.agent:
                try:
                    langfuse_status = st.session_state.agent.get_langfuse_status()
                    st.json(langfuse_status)
                except Exception as e:
                    st.error(f"Langfuse test failed: {e}")