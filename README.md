# AI Park for Swift Trader

To get started create a virtual env and download the dependencies

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -U
```

Run the server in dev mode

```bash
fastapi dev app/main.py
```

To generate image of the graph  

```bash
 python app/utils/generate_graph_image.py
```