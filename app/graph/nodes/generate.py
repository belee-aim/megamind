from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from ..state import AgentState

def generate_node(state: AgentState):
    """
    Generates a response using the Google Generative AI LLM based on the retrieved documents and conversation history.
    """
    print("---GENERATE NODE---")
    messages = state["messages"]
    
    # Extract documents from ToolMessage in the state
    documents = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            # Assuming the content of the ToolMessage is the list of Documents
            # This might need adjustment based on the exact output format of the ToolNode
            if isinstance(msg.content, list) and all(isinstance(d, Document) for d in msg.content):
                documents.extend(msg.content)
            elif isinstance(msg.content, str):
                # If the tool returns a string, wrap it in a Document
                documents.append(Document(page_content=msg.content))
            # Add more robust parsing if the tool output is more complex
    
    # If no documents were found in ToolMessages, check the 'documents' key in state
    if not documents:
        documents = state.get("documents", [])

    # Create a prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI assistant. Use the following documents to answer the user's question:\n\n{documents}"),
        ("human", "{question}")
    ])

    # Format the documents for the prompt
    document_context = "\n".join([doc.page_content for doc in documents])

    # Get the latest human message as the question
    question = ""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            question = message.content
            break

    # Create the LLM instance (replace with actual API key handling)
    # from app.config import settings # Assuming settings object has google_api_key
    # llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-05-20", google_api_key=settings.google_api_key, streaming=True)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-05-20", streaming=True) # Placeholder for API key

    # Create the chain and invoke it
    chain = prompt | llm

    # Stream the response
    response = ""
    for chunk in chain.stream({"documents": document_context, "question": question}):
        response += str(chunk.content)
        yield str(chunk.content) # Yield each chunk for streaming

    # Update the state with the final response (optional, depending on graph structure)
    # state["messages"].append(("ai", response))
    # return state # Or return the final response in a different key if needed
