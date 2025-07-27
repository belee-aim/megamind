import os
import asyncio
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from megamind.graph.workflows.stock_movement_graph import build_stock_movement_graph
from megamind.graph.workflows.document_graph import build_rag_graph

async def main():
    # Get the workflow from the command-line arguments
    workflow_name = sys.argv[1] if len(sys.argv) > 1 else "stock_movement"

    # Build the graph based on the workflow name
    if workflow_name == "stock_movement":
        graph = await build_stock_movement_graph()
        output_path = "images/stock_movement_graph.png"
    elif workflow_name == "document":
        graph = await build_rag_graph()
        output_path = "images/document_graph.png"
    else:
        print(f"Unknown workflow: {workflow_name}")
        return

    # Generate the mermaid PNG image
    try:
        image_bytes = graph.get_graph().draw_mermaid_png()

        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save the image to the file
        with open(output_path, "wb") as f:
            f.write(image_bytes)

        print(f"Graph image saved to {output_path}")

    except Exception as e:
        print(f"Error generating or saving graph image: {e}")

if __name__ == "__main__":
    asyncio.run(main())
