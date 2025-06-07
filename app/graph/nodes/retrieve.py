from langchain_core.messages import HumanMessage
from langchain_core.documents import Document

from ..state import AgentState
from ..tools.retriever import get_retriever_tool

def retrieve_node(state: AgentState):
    """
    Retrieves relevant documents using the retriever tool based on the latest human message.
    """
    print("---RETRIEVE NODE---")
    last_message = state["messages"][-1]
    docs = []
    if isinstance(last_message, HumanMessage):
        query = last_message.content
        print(f"Retrieving documents for query: {query}")
        retriever_tool = get_retriever_tool()
        # The retriever tool expects a dictionary with 'query'
        tool_input = {"query": query}
        docs = retriever_tool.invoke(tool_input)
        print(f"Retrieved {len(docs)} documents.")
    return {"documents": docs}
