import streamlit as st
from google import genai
from google.genai.types import HttpOptions
from google.oauth2 import service_account
import modal
import html
import json
import os
# Page config - Wide layout

os.environ["MODAL_TOKEN_ID"] = st.secrets["token_id"]
os.environ["MODAL_TOKEN_SECRET"] = st.secrets["token_secret"]

st.set_page_config(
    page_title="Query Expansion & Topic Tagging",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)
# Custom CSS - Dark themed professional style
st.markdown("""
<style>
    /* Main container */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 1200px;
    }

    /* Chat message styling - compact */
    .stChatMessage {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        margin-bottom: 0rem !important;
    }

    .stChatMessage > div {
        padding: 0 !important;
    }

    /* User message container */
    .user-message-container {
        position: relative;
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    /* Top row: message text and topic tags */
    .message-top-row {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        width: 100%;
    }

    /* Message text area */
    .message-text-area {
        flex: 1;
        color: #ffffff;
        font-size: 0.9rem;
        line-height: 1.5;
        padding: 0;
        min-width: 0;
    }

    /* Topic tag - top right corner */
    .topic-tag-container {
        display: flex;
        align-items: center;
        gap: 4px;
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 0.7rem;
        flex-shrink: 0;
    }

    .topic-badge {
        background: #2d2d2d;
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 500;
        white-space: nowrap;
    }

    .topic-badge.active {
        background: #2563eb;
        color: #ffffff;
    }

    .topic-sep {
        color: #666;
        font-size: 0.7rem;
        margin: 0 2px;
    }

    /* Expanded query - large highlighted box */
    .expanded-query-container {
        width: 100%;
        padding: 5px 16px;
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 6px;
        border-left: 4px solid #4a9eff;
        margin-top: 0px;
    }

    .expanded-query-label {
        font-size: 0.7rem;
        font-weight: 700;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }

    .expanded-query-value {
        color: #ffffff;
        font-size: 0.9rem;
        line-height: 1.5;
        font-weight: 400;
    }

    /* Header */
    .main-header {
        text-align: center;
        padding: 0.5rem 0 1.5rem 0;
        border-bottom: 1px solid #333;
        margin-bottom: 1rem;
    }

    .main-header h1 {
        font-size: 1.5rem;
        font-weight: 600;
        margin: 0;
    }

    .main-header p {
        color: #888;
        font-size: 0.875rem;
        margin: 4px 0 0 0;
    }

    /* Status badge */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
    }

    .status-badge.success {
        background: #1a3d1a;
        color: #4ade80;
    }

    .status-badge.warning {
        background: #3d2e1a;
        color: #fbbf24;
    }

    /* Suggestion button */
    button[kind="secondary"]:has(p:first-child) {
        font-size: 0.85rem !important;
    }

    /* Dismiss X button - target by key */
    button[data-testid="baseButton-secondary"] {
        background: transparent !important;
        border: 1px solid #ef4444 !important;
        color: #ef4444 !important;
        padding: 2px 8px !important;
        min-height: unset !important;
        font-size: 0.8rem !important;
    }

    button[data-testid="baseButton-secondary"]:hover {
        background: rgba(239, 68, 68, 0.15) !important;
    }
</style>
""", unsafe_allow_html=True)

# System instruction
SYSTEM_INSTRUCTION = """You are a helpful AI assistant. Engage in natural conversation with the user.
Keep your responses concise but informative. Be friendly and helpful."""

# Topic hierarchy
TOPIC_HIERARCHY = {
    "Politics": ["India", "UK", "USA", "China", "Russia", "Global"],
    "Sports": ["Cricket", "Football", "Basketball", "Tennis", "Olympics"],
    "Technology": ["Artificial Intelligence", "Machine Learning", "Software Development", "Cybersecurity", "Blockchain"],
    "Business": ["Startups", "Finance", "Stock Market", "Economy", "E-commerce"],
    "Entertainment": ["Movies", "TV Shows", "Music", "Celebrities", "OTT Platforms"],
    "Science": ["Physics", "Biology", "Space", "Climate", "Research"],
    "Health": ["Fitness", "Nutrition", "Mental Health", "Diseases", "Medicine"],
    "Education": ["Exams", "Universities", "Online Courses", "Careers", "Research"],
    "General": ["Chitchat", "Greetings", "Meta", "Clarification", "Other"]
}


@st.cache_data
def load_templates():
    """Load conversation templates from jsonl file."""
    templates = []
    template_path = os.path.join(os.path.dirname(__file__), 'templete.jsonl')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    templates.append(json.loads(line))
    except Exception as e:
        st.error(f"Failed to load templates: {e}")
    return templates


def load_template_to_chat(template: dict):
    """Load a template into the chat session, with last user message as suggestion."""
    messages = template.get('messages', [])

    # Build the session messages (all except the last user message)
    st.session_state.messages = []
    st.session_state.suggestion = None

    for i, msg in enumerate(messages):
        # If this is the last message and it's from user, store as suggestion
        if i == len(messages) - 1 and msg['role'] == 'user':
            st.session_state.suggestion = msg['content']
        else:
            st.session_state.messages.append({
                'role': msg['role'],
                'content': msg['content']
            })


@st.cache_resource
def get_modal_service():
    """Get the Modal service for query expansion and topic tagging."""
    try:
        QueryExpansionService = modal.Cls.from_name(
            "query-expansion-topic-tagging",  # app name
            "QueryExpansionService"           # class name
        )
        return QueryExpansionService()
    except Exception as e:
        # Return None silently - error will be handled in get_query_analysis
        return None


def get_query_analysis(messages: list) -> dict:
    """
    Get expanded query and topic classification from Modal service.

    Args:
        messages: List of message dicts with 'role' and 'content' keys

    Returns:
        dict with 'expanded_query', 'topic' (level_1, level_2), and optional 'error'
    """
    service = get_modal_service()
    if service is None:
        # Return empty strings with error - do not display topic tags and expanded query
        return {
            'expanded_query': '',
            'topic': {},
            'error': "Modal instance is not running. Please start the Modal service."
        }

    try:
        # Call modal service with chat history
        result = service.infer.remote(messages=messages)

        # Check for errors
        if isinstance(result, dict) and 'error' in result:
            # Check if error indicates Modal instance is not running
            error_msg = result.get('error', '').lower()
            if 'not running' in error_msg or 'not found' in error_msg or 'connection' in error_msg:
                # Return empty strings with error - do not display topic tags and expanded query
                return {
                    'expanded_query': '',
                    'topic': {},
                    'error': "Modal instance is not running. Please start the Modal service."
                }
            else:
                # For other errors, use fallback with warning
                fallback = get_fallback_analysis(messages)
                fallback['warning'] = f"Modal service error: {result.get('error')}"
                if 'raw_output' in result:
                    fallback['raw_output'] = result['raw_output'][:100]
                return fallback

        # Extract labels from result
        # Result should have 'labels' key with 'expanded_query' and 'topic'
        labels = result.get('labels', {})
        if not labels:
            # If no labels, try to extract from the result directly
            if 'expanded_query' in result:
                labels = result
            else:
                fallback = get_fallback_analysis(messages)
                fallback['warning'] = "Modal service returned unexpected format"
                return fallback

        expanded_query = labels.get('expanded_query', '')
        if not expanded_query and messages:
            expanded_query = messages[-1].get('content', '')

        topic = labels.get('topic', {})
        if not topic or 'level_1' not in topic:
            topic = {'level_1': 'General', 'level_2': 'Other'}

        return {
            'expanded_query': expanded_query,
            'topic': topic
        }
    except Exception as e:
        # Check if exception indicates Modal instance is not running
        error_str = str(e).lower()
        if 'not running' in error_str or 'not found' in error_str or 'connection' in error_str or 'timeout' in error_str:
            # Return empty strings with error - do not display topic tags and expanded query
            return {
                'expanded_query': '',
                'topic': {},
                'error': "Modal instance is not running. Please start the Modal service."
            }
        else:
            fallback = get_fallback_analysis(messages)
            fallback['warning'] = f"Error calling Modal service: {str(e)}"
            return fallback


def get_fallback_analysis(messages: list) -> dict:
    """Fallback analysis if Modal service is unavailable."""
    if not messages:
        return {
            'expanded_query': '',
            'topic': {'level_1': 'General', 'level_2': 'Other'}
        }
    
    last_message = messages[-1]
    query = last_message.get('content', '')
    
    # Simple fallback logic
    q = query.lower()
    if any(word in q for word in ['movie', 'film', 'actor']):
        topic = {'level_1': 'Entertainment', 'level_2': 'Movies'}
    elif any(word in q for word in ['football', 'soccer', 'goal', 'cricket']):
        topic = {'level_1': 'Sports', 'level_2': 'Football'}
    elif any(word in q for word in ['code', 'programming', 'software']):
        topic = {'level_1': 'Technology', 'level_2': 'Software Development'}
    elif any(word in q for word in ['health', 'doctor', 'medicine']):
        topic = {'level_1': 'Health', 'level_2': 'Medicine'}
    elif any(word in q for word in ['pm', 'minister', 'election', 'government']):
        topic = {'level_1': 'Politics', 'level_2': 'India'}
    elif any(word in q for word in ['ai', 'machine learning', 'technology']):
        topic = {'level_1': 'Technology', 'level_2': 'Artificial Intelligence'}
    else:
        topic = {'level_1': 'General', 'level_2': 'Chitchat'}
    
    # Simple expanded query (just return the query as-is for fallback)
    expanded_query = query
    
    return {
        'expanded_query': expanded_query,
        'topic': topic
    }


@st.cache_resource
def get_genai_client():
    use_vertex = st.secrets.get('GOOGLE_GENAI_USE_VERTEXAI', 'false').lower() == 'true'

    if use_vertex and 'gcp_service_account' in st.secrets:
        credentials = service_account.Credentials.from_service_account_info(
            dict(st.secrets['gcp_service_account']),
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        client = genai.Client(
            http_options=HttpOptions(api_version="v1"),
            vertexai=True,
            project=st.secrets.get('GOOGLE_CLOUD_PROJECT', 'stone-column-425217-n6'),
            location=st.secrets.get('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            credentials=credentials
        )
    else:
        api_key = st.secrets.get('GOOGLE_API_KEY', '')
        if api_key:
            client = genai.Client(
                api_key=api_key,
                http_options=HttpOptions(api_version="v1")
            )
        else:
            return None
    return client


def get_gemini_response(messages: list) -> str:
    client = get_genai_client()
    if client is None:
        raise Exception("Gemini client not configured. Check secrets.toml")

    contents = [
        {'role': 'user' if m['role'] == 'user' else 'model', 'parts': [{'text': m['content']}]}
        for m in messages
    ]

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents,
        config={
            'system_instruction': SYSTEM_INSTRUCTION,
            'temperature': 0.7,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 1024,
        }
    )
    return response.text


def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>Query Expansion & Topic Tagging</h1>
    </div>
    """, unsafe_allow_html=True)

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    # Sidebar - Templates
    with st.sidebar:
        st.markdown("### Templates")

        templates = load_templates()

        if templates:
            for i, template in enumerate(templates):
                if st.button(f"Template {i + 1}", key=f"template_{i}", use_container_width=True):
                    load_template_to_chat(template)
                    st.rerun()
        else:
            st.caption("No templates found")

        st.divider()
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.suggestion = None
            st.rerun()

    # Chat area
    for msg in st.session_state.messages:
        if msg['role'] == 'user':
            analysis = msg.get('analysis')
            # Display error/warning for this message if any
            if analysis and analysis.get('error'):
                st.error(analysis['error'])
            if analysis and analysis.get('warning'):
                st.warning(analysis['warning'])
            with st.chat_message("user", avatar="👦"):
                if analysis:
                    # Build topic tags HTML only if topic exists and has valid values
                    topic_html = ""
                    topic = analysis.get('topic')
                    if topic and isinstance(topic, dict) and topic.get('level_1') and topic.get('level_2'):
                        topic_html = f'<div class="topic-tag-container"><span class="topic-badge">{html.escape(str(topic["level_1"]))}</span><span class="topic-sep">›</span><span class="topic-badge active">{html.escape(str(topic["level_2"]))}</span></div>'

                    # Build expanded query HTML only if expanded_query exists and is not empty
                    expanded_query_html = ""
                    expanded_query = analysis.get('expanded_query')
                    if expanded_query and expanded_query != "":
                        expanded_query_html = f'<div class="expanded-query-container"><div class="expanded-query-label">EXPANDED QUERY</div><div class="expanded-query-value">{html.escape(str(expanded_query))}</div></div>'

                    # Only show formatted message if we have at least topic or expanded query
                    has_topic = bool(topic_html)
                    has_expanded = bool(expanded_query_html)

                    if has_topic or has_expanded:
                        # Build the HTML structure conditionally
                        html_content = f'<div class="user-message-container"><div class="message-top-row"><div class="message-text-area">{html.escape(str(msg["content"]))}</div>{topic_html if has_topic else ""}</div>{expanded_query_html if has_expanded else ""}</div>'
                        st.markdown(html_content, unsafe_allow_html=True)
                    else:
                        st.write(msg['content'])
                else:
                    st.write(msg['content'])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.write(msg['content'])

    # Show suggestion if available
    if 'suggestion' in st.session_state and st.session_state.suggestion:
        suggestion_text = st.session_state.suggestion
        col1, col2, _ = st.columns([0.55, 0.05, 0.4])
        with col1:
            if st.button(f"💬 {suggestion_text}", key="suggestion_btn"):
                st.session_state.suggestion = None
                st.session_state.pending_prompt = suggestion_text
                st.rerun()
        with col2:
            if st.button("✕", key="dismiss_suggestion", type="secondary"):
                st.session_state.suggestion = None
                st.rerun()

    # Handle pending prompt from suggestion
    prompt = None
    if 'pending_prompt' in st.session_state and st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    # Chat input - always show the input box
    chat_input = st.chat_input("Type your message...")
    
    # Use chat input if no pending prompt, otherwise use pending prompt
    if not prompt:
        prompt = chat_input

    if prompt:
        # Add user message first (without analysis)
        user_message = {
            'role': 'user',
            'content': prompt
        }
        st.session_state.messages.append(user_message)
        
        # Get analysis from Modal service with full chat history
        with st.spinner("Analyzing query..."):
            analysis = get_query_analysis(st.session_state.messages)

        # Display error or warning messages from analysis
        if analysis.get('error'):
            st.error(analysis['error'])
        if analysis.get('warning'):
            st.warning(analysis['warning'])
            if analysis.get('raw_output'):
                st.caption(f"Raw output: {analysis['raw_output']}...")

        # Update the user message with analysis
        st.session_state.messages[-1]['analysis'] = analysis

        with st.chat_message("user", avatar="🐿️"):
            # Build topic tags HTML only if topic exists and has valid values
            topic_html = ""
            if analysis:
                topic = analysis.get('topic')
                if topic and isinstance(topic, dict) and topic.get('level_1') and topic.get('level_2'):
                    topic_html = f'<div class="topic-tag-container"><span class="topic-badge">{html.escape(str(topic["level_1"]))}</span><span class="topic-sep">›</span><span class="topic-badge active">{html.escape(str(topic["level_2"]))}</span></div>'
                
                # Build expanded query HTML only if expanded_query exists and is not empty
                expanded_query_html = ""
                expanded_query = analysis.get('expanded_query')
                if expanded_query and expanded_query != "":
                    expanded_query_html = f'<div class="expanded-query-container"><div class="expanded-query-label">EXPANDED QUERY</div><div class="expanded-query-value">{html.escape(str(expanded_query))}</div></div>'
            
            # Only show formatted message if we have at least topic or expanded query
            has_topic = bool(topic_html)
            has_expanded = bool(expanded_query_html)
            
            if has_topic or has_expanded:
                # Build the HTML structure conditionally
                html_content = f'<div class="user-message-container"><div class="message-top-row"><div class="message-text-area">{html.escape(str(prompt))}</div>{topic_html if has_topic else ""}</div>{expanded_query_html if has_expanded else ""}</div>'
                st.markdown(html_content, unsafe_allow_html=True)
            else:
                st.write(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking..."):
                try:
                    response = get_gemini_response(st.session_state.messages)
                    st.write(response)
                    st.session_state.messages.append({
                        'role': 'assistant',
                        'content': response
                    })
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        'role': 'assistant',
                        'content': error_msg
                    })


if __name__ == "__main__":
    main()
