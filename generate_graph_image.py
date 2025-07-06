import os
import asyncio
import sys
from src.megamind.graph.builder import build_graph
from IPython.display import Image, display

async def main():
    # Get the query from the command-line arguments
    query = sys.argv[1] if len(sys.argv) > 1 else ""

    # Build the graph
    graph = await build_graph(query=query)

    # Generate the mermaid PNG image
    try:
        image_bytes = graph.get_graph().draw_mermaid_png()

        # Define the output path and create the directory if it doesn't exist
        output_path = "images/graph.png"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save the image to the file
        with open(output_path, "wb") as f:
            f.write(image_bytes)

        print(f"Graph image saved to {output_path}")

        # Display the image
        display(Image(data=image_bytes))

    except Exception as e:
        print(f"Error generating or saving graph image: {e}")

if __name__ == "__main__":
    asyncio.run(main())
