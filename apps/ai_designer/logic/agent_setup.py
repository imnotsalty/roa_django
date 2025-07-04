import os
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from .agent_tools import generate_marketing_image, complete_marketing_image, list_available_designs

load_dotenv()

# --- PROMPT REMAINS THE SAME ---
prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are a professional and highly capable design assistant for Realty of America. Your purpose is to help real estate agents create marketing materials by generating images.

    **Your Primary Goal:**
    Your main goal is to generate a marketing image. The user will provide their intent (e.g., "a just listed ad"), the property MLS Listing ID, and the regional property MLS ID.

    ---
    **CRITICAL WORKFLOW RULE: DO NOT ASK FOR PROPERTY DETAILS**
    If you are given an MLS Listing ID and an MLS ID, you MUST NOT ask the user for property details like price, address, photos, or key features.
    The `generate_marketing_image` tool is designed to automatically fetch all of this information from the database using the MLS Listing ID and MLS ID.
    Your ONLY job is to take the user's intent, the MLS Listing ID, and the MLS ID and immediately call the `generate_marketing_image` tool.
    ---

    **Handling Missing Information (The ONLY time you ask questions):**
    Some designs require information that is impossible to know from property data (like a date for an 'Open House').

    - **STEP 1: Initial Call**
      - When you call `generate_marketing_image`, it will check if more information is needed.
      - If it IS needed, the tool will return a `status: 'needs_info'` and a pre-formatted `message_for_user`.
      - **Your job is to simply relay this `message_for_user` directly to the user and then wait for their response.** Do not change it.

    - **STEP 2: Follow-up Call**
      - After the user responds with the requested information (e.g., "The open house is Saturday from 2-4 PM").
      - You **MUST** then call the `complete_marketing_image` tool to finalize the image.

    **Other Tools:**
    - If the user asks what you can create, use the `list_available_designs` tool.
    """),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

tools = [generate_marketing_image, complete_marketing_image, list_available_designs]

# --- CORRECTED ORDER OF DEFINITIONS ---
# 1. Define the LLM
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.1, convert_system_message_to_human=True)

# 2. Create the agent (which needs the llm and tools)
agent = create_tool_calling_agent(llm, tools, prompt)

# 3. Create the agent executor (which needs the agent and tools)
agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True, 
    handle_parsing_errors=True, 
    return_intermediate_steps=True
)

# --- UPDATED CONVERSATION RUNNER (No changes here) ---
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
            chat_history.append(AIMessage(content=msg["content"]))

    try:
        response = agent_executor.invoke({
            "input": user_input,
            "chat_history": chat_history
        })

        # *** NEW LOGIC TO INTERCEPT TOOL OUTPUT ***
        # Check if a tool was run and returned our specific dictionary structure.
        if "intermediate_steps" in response and response["intermediate_steps"]:
            # The tool's output is the second item in the last tuple of intermediate_steps
            last_tool_output = response["intermediate_steps"][-1][1]

            if isinstance(last_tool_output, dict) and "message_for_user" in last_tool_output:
                # If it's our structured output, use it directly!
                message = last_tool_output["message_for_user"]
                new_context = last_tool_output.get("context", {})
                return (message, new_context)
            
            elif isinstance(last_tool_output, dict) and last_tool_output.get("success"):
                 # Handle the list_available_designs tool output
                 designs = "\n".join([f"- {name}" for name in last_tool_output.get("designs", [])])
                 message = f"I can create the following designs for you:\n\n{designs}"
                 return (message, {})

        # If no tool was run or it didn't return our specific format, fall back to the agent's final answer.
        message = response.get("output", "I'm sorry, I had trouble processing that.")
        return (message, {})

    except Exception as e:
        print(f"A critical error occurred in the agent executor: {e}")
        return ("I've encountered a serious technical issue. Please try again later.", {})