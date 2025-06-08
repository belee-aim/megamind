import os
from app.graph.builder import build_graph
from IPython.display import Image, display

if __name__ == "__main__":
    # Build the graph
    graph = build_graph()

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
