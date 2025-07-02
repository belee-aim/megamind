# Megamind of AIMLink

The main dependency manager of this project is uv.

Follow uv's official [website](https://docs.astral.sh/uv/getting-started/installation/) to install it.

To get started create a virtual env and download the dependencies

```bash
uv venv
uv sync
```

Then, run the fastapi server in development mode by running below script. 

```bash
uv run fastapi dev src/megamind/main.py
```

If you want to see the graph in visual mode run the scripts below.

```bash
uv pip install -e .
langgraph dev
```


To generate image of the graph  

```bash
 python generate_graph_image.py
```