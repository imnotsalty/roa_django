import os
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from .agent_tools import generate_marketing_image, complete_marketing_image, list_available_designs

load_dotenv()

# ... (prompt definition remains the same) ...
prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are a professional and highly capable design assistant for Realty of America...
    """),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

tools = [generate_marketing_image, complete_marketing_image, list_available_designs]
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.1, convert_system_message_to_human=True)
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

def run_agent_conversation(user_input: str, history_list: list, agent_context: dict) -> (str, dict):
    """
    Runs a single turn of the conversation with the LangChain agent.
    This function is now STATELESS. It receives context and returns updated context.

    Args:
        user_input: The latest message from the user.
        history_list: A list of dicts representing the conversation history.
        agent_context: The context from the previous turn (if any).

    Returns:
        A tuple containing: (agent's response string, updated agent_context dictionary)
    """
    chat_history = []
    for msg in history_list:
        if msg.get("role") == "user":
            chat_history.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            chat_history.append(AIMessage(content=msg["content"]))
    
    # The agent needs the previous context for the complete_marketing_image tool.
    # We can pass it as part of the input. A more robust way would be to inject it
    # into a custom tool or modify the prompt, but this is a direct way.
    # For this implementation, the logic in the view will handle the context passing.
    
    try:
        response = agent_executor.invoke({
            "input": user_input,
            "chat_history": chat_history,
            "agent_context": agent_context # Pass context to the agent
        })
        
        output = response.get("output", "I'm sorry, I had trouble processing that.")
        new_context = {} # Default to clearing context

        if isinstance(output, dict):
            if output.get("status") == "needs_info":
                new_context = output.get("context", {}) # Save context for the next turn
                message = output["message_for_user"]
            elif "message_for_user" in output:
                 message = output["message_for_user"]
            elif output.get("success") and "designs" in output:
                 designs = "\n".join([f"- {name}" for name in output.get("designs", [])])
                 message = f"I can create the following designs for you:\n\n{designs}"
            else:
                message = f"I encountered an issue: {output.get('error', 'Unknown error')}"
        else:
            message = output
            
        return (message, new_context)
            
    except Exception as e:
        print(f"A critical error occurred in the agent executor: {e}")
        return ("I've encountered a serious technical issue. Please try again later.", {})