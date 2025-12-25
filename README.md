# Megamind of AIMLink

Welcome to megamind of aim. This project serves as the main agentic ai for aim projects.

## Getting Started

The main dependency manager of this project is uv.

Follow uv's official [website](https://docs.astral.sh/uv/getting-started/installation/) to install it.

For initial setup create a virtual environment using python

```bash
python -m venv .venv
source .venv/bin/activate
```

Then install `uv`

```bash
pip install uv
```

If you have uv installed, create a virtual env and download the dependencies

Create virtual env using uv (Optional if you created virtual env using python)

```bash
uv venv
```

Install dependencies using uv

```bash
uv sync
```

After that, copy the environment variable and set it

```bash
cp .env.example .env
```

Then, run the fastapi server in development mode by running below script.

```bash
uv run fastapi dev src/megamind/main.py
```

## Frappe MCP Server setup

Clone the frappe mcp server outside this project, and build it

```bash
git clone git@github.com:AIMlink-team/frappe_mcp_server.git
cd frappe_mcp_server
npm install -g typescript # If you don't have typescript installed
npm install -g yarn # If you don't have yarn dependency manager
yarn # Install the dependencies
yarn build
```

Copy the `[project-path]/frappe_mcp_server/build/index.js` path into `FRAPPE_MCP_SERVER_PATH` Environment variable

## Repository or Websites used for inspiration

- [Github - Gemini Langchain](https://github.com/google-gemini/gemini-fullstack-langgraph-quickstart)
- [Google Langgraph example](https://ai.google.dev/gemini-api/docs/langgraph-example)
- [Langgraph documentation](https://langchain-ai.github.io/langgraph/agents/agents/)
- [Langchain V1 (Middleware)](https://reference.langchain.com/python/langchain/middleware/#middleware-classes)
- [Deepagents by Langchain](https://github.com/langchain-ai/deepagents)
