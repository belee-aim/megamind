# Megamind of AIMLink

To get started create a virtual env and download the dependencies

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install poetry
poetry install
```

Run the server in dev mode

```bash
fastapi dev src/megamind/main.py
```

To generate image of the graph  

```bash
 python generate_graph_image.py
```