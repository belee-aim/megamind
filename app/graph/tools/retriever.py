import os
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.tools.retriever import create_retriever_tool
from langchain_core.documents import Document # Added import for Document

load_dotenv()

def get_retriever_tool():
    """
    Initializes the vector store with dummy text and creates a retriever tool.
    """
    dummy_text = [
        "LangChain is a framework for developing applications powered by large language models (LLMs).",
        "It enables applications that are context-aware and can reason.",
        "LangChain provides tools for data loading, text splitting, embeddings, and vector stores.",
        "It supports various LLMs and integrates with many external services.",
        "LangGraph is a library for building stateful, multi-actor applications with LLMs, built on LangChain.",
        "LangGraph allows defining agentic systems as graphs with nodes and edges.",
        "Streaming is a key feature in both LangChain and LangGraph for real-time responses.",
        "Tools in LangChain allow LLMs to interact with external environments.",
        "Memory management is crucial for conversational AI applications in LangChain and LangGraph.",
        "The framework is designed for building complex AI agents and RAG systems."
    ]

    docs_list = [Document(page_content=text) for text in dummy_text]

    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=100, chunk_overlap=20 # Adjusted chunk_overlap for smaller chunks
    )
    doc_splits = text_splitter.split_documents(docs_list)

    vectorstore = InMemoryVectorStore.from_documents(
        documents=doc_splits, embedding=GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    )

    retriever = vectorstore.as_retriever()

    retriever_tool = create_retriever_tool(
        retriever,
        "langchain_info_retriever",
        "Retrieve information about LangChain.",
    )

    return retriever_tool
