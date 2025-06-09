# Codebase Overview

## High-Level Architecture

This application is a FastAPI-based microservice designed to interact with AI models. It uses `langgraph` to create a stateful, multi-actor system that processes user requests in a structured manner. The core of the application is a graph-based state machine that orchestrates the flow of data and logic, from receiving a user's chat message to generating a final response.

The application is designed to be modular, with clear separation of concerns between the API layer, the graph definition, and the individual nodes that make up the graph. This allows for easier maintenance and extension of the application's capabilities.
## Detailed Component Breakdown

### `app/main.py`

This file serves as the entry point for the application. It initializes the FastAPI application and defines the API endpoints.

-   **`@app.post("/v1/chat")`**: This is the primary endpoint for interacting with the AI. It receives a `ChatRequest` object containing the user's prompt. The endpoint is responsible for:
    1.  Building the `langgraph` by calling the `build_graph()` function.
    2.  Invoking the graph with the user's message.
    3.  Streaming the response back to the client using `StreamingResponse`.
### `app/graph/builder.py`

This file is responsible for constructing the `langgraph` state machine.

-   **`build_graph()`**: This function defines the structure of the graph, including its nodes and edges.
    -   **Nodes**: The graph consists of three main nodes:
        -   `agent`: The entry point of the graph, which decides the next step.
        -   `retrieve`: A `ToolNode` that uses a retriever to fetch relevant information.
        -   `generate`: A node that generates the final response.
    -   **Edges**: The function defines the conditional edges that control the flow between the nodes based on the output of the `agent` node.
### `app/graph/state.py`

This file defines the state object for the agent.

-   **`AgentState`**: A `TypedDict` that represents the state of the graph. It contains a `messages` field, which is a list of messages that are passed between the nodes. This state is updated by each node as the graph is executed.
### `app/graph/nodes/`

This directory contains the functions that define the logic for each node in the graph.

-   **`agent.py`**: The `agent_node` function is the brain of the agent. It uses a language model to decide whether to call a tool or to respond directly to the user.
-   **`generate.py`**: The `generate_node` function is responsible for generating the final response. It takes the retrieved documents and the conversation history as input and uses a language model to generate a coherent and contextually relevant answer.
### `app/graph/tools/retriever.py`

This file defines the tool that the agent can use to retrieve information.

-   **`get_retriever_tool()`**: This function creates a retriever tool that can search for information within a set of documents. It initializes an in-memory vector store with a small set of dummy documents and creates a retriever that can query this vector store.
## Visual Representation

```mermaid
graph TD
    A[User Request: /v1/chat] --> B{app/main.py};
    B --> C{app/graph/builder.py: build_graph()};
    C --> D[StateGraph];
    D -- Entry Point --> E{agent_node};
    E -- Has Tool Call? --> F{Yes};
    E -- No Tool Call? --> G{End};
    F --> H{retrieve (ToolNode)};
    H --> I{generate_node};
    I --> G;
```