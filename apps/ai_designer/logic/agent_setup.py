import os
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from .agent_tools import generate_marketing_image, complete_marketing_image, list_available_designs

# Load environment variables
load_dotenv()

# Check for critical environment variables on startup
if not all(k in os.environ for k in ["GOOGLE_API_KEY", "BANNERBEAR_API_KEY", "REALTY_API_ENDPOINT"]):
    raise EnvironmentError("Missing critical environment variables. Please check your .env file.")

prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are a professional and highly capable design assistant for Realty of America. Your purpose is to help real estate agents create marketing materials.
    Your Primary Goal is to generate a marketing image. The process is as follows:
    1.  Understand the user's intent (e.g., "a just listed ad") and the property's MLS ID.
    2.  Once you have both, use the `generate_marketing_image` tool.
    Handling Missing Information (A Two-Step Process):
    - STEP 1: Initial Call. If `generate_marketing_image` needs more info, it will return `status: 'needs_info'`. Relay the `message_for_user` directly to the user and wait.
    - STEP 2: Follow-up Call. After the user responds, you MUST call `complete_marketing_image` with the original context and the new `user_provided_data`.
    Other Tools: Use `list_available_designs` if the user asks what you can create.
    Always maintain a friendly, professional, and conversational tone.
    """),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

tools = [generate_marketing_image, complete_marketing_image, list_available_designs]
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.1, convert_system_message_to_human=True)
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# WARNING: This global context holder is NOT thread-safe and is unsuitable for production with concurrent users.
# For production, replace this with a more robust state management solution like Django sessions or a cache (e.g., Redis).
_agent_context = {}

def run_agent_conversation(user_input: str, history_list: list) -> str:
    global _agent_context
    chat_history = []
    for msg in history_list:
        if msg.get("role") == "user":
            chat_history.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            chat_history.append(AIMessage(content=msg["content"]))
    try:
        response = agent_executor.invoke({
            "input": user_input,
            "chat_history": chat_history
        })
        output = response.get("output", "I'm sorry, I had trouble processing that.")
        if isinstance(output, dict):
            if output.get("status") == "needs_info":
                _agent_context = output.get("context", {})
                return output["message_for_user"]
            elif "message_for_user" in output:
                 _agent_context = {}
                 return output["message_for_user"]
            elif output.get("success") and "designs" in output:
                 designs = "\n".join([f"- {name}" for name in output.get("designs", [])])
                 return f"I can create the following designs for you:\n\n{designs}"
            else:
                return f"I encountered an issue: {output.get('error', 'Unknown error')}"
        else:
            _agent_context = {}
            return output
    except Exception as e:
        print(f"A critical error occurred in the agent executor: {e}")
        return "I've encountered a serious technical issue. Please try again later."