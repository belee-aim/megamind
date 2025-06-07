from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage

from ..state import AgentState
from ..tools.retriever import get_retriever_tool

def agent_node(state: AgentState):
    """
    Calls the LLM to decide whether to use a tool (retriever) or respond directly.
    """
    print("---AGENT NODE---")
    messages = state["messages"]
    # Log messages for debugging
    for i, message in enumerate(messages):
        print(f"Message {i}: {message}")
    
    # Initialize LLM with tools
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-05-20")
    retriever_tool = get_retriever_tool()
    llm_with_tools = llm.bind_tools([retriever_tool])

    # Invoke the LLM with the current messages
    response = llm_with_tools.invoke(messages)
    print(f"LLM response: {response}")
    
    return {"messages": [response]}
