from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

from megamind.configuration import Configuration

from ..states import AgentState

def generate_node(state: AgentState, config: RunnableConfig):
    """
    Generates a response using the Google Generative AI LLM based on the retrieved documents and conversation history.
    """
    print("---GENERATE NODE---")
    configurable = Configuration.from_runnable_config(config)
    question = state["question"]

    # Placeholder for retriever
    # In a real implementation, you would use the vector_store to retrieve relevant documents
    # For now, we'll just use the documents from the state
    documents = state.get("documents", [])
    
    # Create a prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI assistant. Only use the following documents to answer the user's question:\n\n{documents}"),
        ("human", "{question}")
    ])

    # Format the documents for the prompt
    document_context = "\n".join([doc.page_content for doc in documents])

    # Create the LLM instance (replace with actual API key handling)
    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model) 

    # Create the chain and invoke it
    chain = prompt | llm

    # Invoke the chain to get the complete response
    response = chain.invoke({"documents": document_context, "question": question})

    # Return a dictionary to update the state with the final response
    return {"messages": [AIMessage(content=response.content)]}
