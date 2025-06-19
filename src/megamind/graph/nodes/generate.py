from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from megamind import prompts
from megamind.configuration import Configuration
from megamind.graph.tools import frappe_retriever
from megamind.utils import get_human_message

from ..states import AgentState

def generate_node(state: AgentState, config: RunnableConfig):
    """
    Generates a response using the Google Generative AI LLM based on the retrieved documents and conversation history.
    """
    logger.info("---GENERATE NODE---")
    configurable = Configuration.from_runnable_config(config)
    human_message = get_human_message(state)

    if not human_message:
        raise ValueError("No human message found in the state.")
    
    documents = state.get("documents", [])
    
    # Create a prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompts.generate_node_instructions),
        ("human", "{question}"),
    ])

    document_context = "\n".join([doc.page_content for doc in documents])

    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model) 
    llm.bind_tools([frappe_retriever])
    chain = prompt | llm

    response = chain.invoke({"documents": document_context, "question": human_message.content})

    return {"messages": [response]}
