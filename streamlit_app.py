import streamlit as st
import sys
import os
from typing import List

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.agent.workflow import FormAgentWorkflow
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# Page config
st.set_page_config(
    page_title="Form Management AI Agent",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent" not in st.session_state:
    st.session_state.agent = None

# Sidebar configuration
st.sidebar.title("⚙️ Configuration")

# Model provider selection
model_provider = st.sidebar.selectbox(
    "Choose Model Provider",
    ["openai", "anthropic"],
    index=0,
    help="Select which AI model to use for processing"
)

# Initialize agent if not exists or provider changed
if (st.session_state.agent is None or 
    getattr(st.session_state, 'current_provider', None) != model_provider):
    
    try:
        with st.sidebar:
            with st.spinner("Initializing agent..."):
                st.session_state.agent = FormAgentWorkflow(model_provider=model_provider)
                st.session_state.current_provider = model_provider
        st.sidebar.success("✅ Agent initialized!")
    except Exception as e:
        st.sidebar.error(f"❌ Error initializing agent: {str(e)}")
        st.sidebar.info("Please check your API keys in the .env file")

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.markdown("### 📖 What I can help with:")
st.sidebar.markdown("""
- **Forms**: Create, update, delete forms
- **Fields**: Add, modify, remove form fields  
- **Options**: Manage dropdown/radio options
- **Logic Rules**: Add conditional logic
- **Validation**: Check form constraints
""")

st.sidebar.markdown("### 💡 Example queries:")
st.sidebar.markdown("""
- "Add a Paris option to destinations field in travel request form"
- "Create a new procurement form"
""")

# Clear chat button
if st.sidebar.button("🗑️ Clear Chat", type="secondary"):
    st.session_state.messages = []
    st.rerun()

# Main interface
st.title("🔧 Form Management AI Agent")
st.markdown("**Natural language interface for enterprise form management**")

# Display chat messages
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        if isinstance(message, HumanMessage):
            with st.chat_message("user"):
                st.markdown(message.content)
        elif isinstance(message, AIMessage):
            with st.chat_message("assistant"):
                st.markdown(message.content)

# Chat input
if prompt := st.chat_input("Describe what you want to do with your forms..."):
    if st.session_state.agent is None:
        st.error("Please wait for the agent to initialize or check your API keys.")
    else:
        # Add user message to chat history
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Process the message
        with st.chat_message("assistant"):
            with st.spinner("Processing your request..."):
                try:
                    # Process the message through the agent
                    result = st.session_state.agent.process_message(
                        prompt, 
                        st.session_state.messages
                    )
                    
                    if result["success"]:
                        # Update session state with new messages
                        st.session_state.messages = result["messages"]
                        
                        # Display the latest AI response
                        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
                        if ai_messages:
                            latest_response = ai_messages[-1].content
                            st.markdown(latest_response)
                        
                    else:
                        st.error(f"Error: {result.get('error', 'Unknown error occurred')}")
                        
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.info("Please check your API keys and try again.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.8em;'>
    🤖 Powered by LangGraph • Built with Streamlit
</div>
""", unsafe_allow_html=True)

# Show current state in expander (for debugging)
if st.sidebar.checkbox("🐛 Debug Mode", value=False):
    with st.expander("Debug Information", expanded=False):
        st.json({
            "total_messages": len(st.session_state.messages),
            "model_provider": model_provider,
            "agent_initialized": st.session_state.agent is not None
        })
        
        if st.session_state.messages:
            st.subheader("Message History")
            for i, msg in enumerate(st.session_state.messages):
                st.text(f"{i}: {type(msg).__name__} - {msg.content[:100]}...")