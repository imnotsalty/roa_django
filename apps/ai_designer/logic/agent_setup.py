# agent_setup.py
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

# Import the single tool and api_services to fetch designs on startup
from .agent_tools import generate_marketing_image
from . import api_services

load_dotenv()

AI_MODEL = "gemini-2.0-flash"

# --- FETCH AVAILABLE DESIGNS ON STARTUP ---
# This makes the agent aware of designs without needing a tool call.
try:
    API_KEY = os.environ["BANNERBEAR_API_KEY"]
    TEMPLATES = api_services.fetch_all_template_details(API_KEY)
    AVAILABLE_DESIGNS = "\n".join([f"- {t['name']}" for t in TEMPLATES])
except Exception as e:
    print(f"CRITICAL: Could not fetch BannerBear templates on startup. Error: {e}")
    AVAILABLE_DESIGNS = "Could not load designs. There might be a configuration issue."

# --- NEW, HIGHLY-DIRECTIVE PROMPT ---
prompt = ChatPromptTemplate.from_messages([
    ("system", f"""
    You are a professional and highly capable design assistant for Realty of America. Your purpose is to help real estate agents create marketing materials by generating images.

    **Your Workflow:**
    Your goal is to collect three pieces of information from the user before you can act:
    1. The design they want to create.
    2. The property's MLS Listing ID.
    3. The property's 3-digit regional MLS ID.

    **Available Designs:**
    Here are the marketing designs you can create:
    {AVAILABLE_DESIGNS}

    ---
    **CRITICAL CONVERSATION RULES:**

    1.  **GATHER INFORMATION FIRST:** Your primary job is to gather the three required pieces of information (Design Name, MLS Listing ID, MLS ID). Ask for them conversationally. If the user provides everything at once, great. If not, ask for the missing pieces. For example, if they only provide an MLS ID, ask them which design they'd like and what the MLS Listing ID is.

    2.  **DO NOT USE A TOOL UNTIL READY:** You have one tool: `generate_marketing_image`. You MUST NOT call this tool until you have all three pieces of information.

    3.  **DO NOT ASK FOR PROPERTY DETAILS:** Never ask for the property address, price, photos, or features. The tool gets all of that automatically from the MLS IDs.

    """),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# --- AGENT SETUP WITH A SINGLE TOOL ---
tools = [generate_marketing_image]

llm = ChatGoogleGenerativeAI(model=AI_MODEL, temperature=0.1)

agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True, 
    handle_parsing_errors=True, 
    return_intermediate_steps=True
)


# --- CONVERSATION RUNNER (No changes needed, but simplified internally) ---
def run_agent_conversation(user_input: str, history_list: list, agent_context: dict) -> (str, dict):
    """
    Runs a single turn of the conversation with the LangChain agent.
    This function is STATELESS. It receives context and returns updated context.
    """
    chat_history = []
    for msg in history_list:
        if msg.get("role") == "user":
            chat_history.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            # If the assistant's last message was a request for info,
            # we must also include the tool's context in the history for the LLM.
            # This is a more advanced (but correct) way to handle multi-step tool use.
            content = msg["content"]
            if "context" in msg:
                 content += f"\n\n[Internal Note: The current context is {msg['context']}]"
            chat_history.append(AIMessage(content=content))

    try:
        # The agent_context from the previous turn contains the necessary details
        # for the 'user_provided_data' argument in the follow-up tool call.
        # We merge it with the user input to help the agent make the right call.
        # This helps the agent remember the context from the `needs_info` step.
        invoke_input = {"input": user_input, "chat_history": chat_history}
        if agent_context:
            invoke_input['input'] += f"\n\n[Internal Context for Tool Call: {json.dumps(agent_context)}]"


        response = agent_executor.invoke(invoke_input)

        # Intercept tool output to handle custom responses ("needs_info", "image_generated", etc.)
        if "intermediate_steps" in response and response["intermediate_steps"]:
            last_tool_output = response["intermediate_steps"][-1][1]

            if isinstance(last_tool_output, dict) and "message_for_user" in last_tool_output:
                message = last_tool_output["message_for_user"]
                # Persist the context if the tool needs more info
                new_context = last_tool_output.get("context", {}) 
                return (message, new_context)

        # If no special tool output, return the agent's final answer.
        message = response.get("output", "I'm sorry, I had trouble processing that.")
        return (message, {}) # Clear context after a successful final response

    except Exception as e:
        print(f"A critical error occurred in the agent executor: {e}")
        return ("I've encountered a serious technical issue. Please try again later.", {})