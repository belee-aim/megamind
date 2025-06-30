from llama_cloud_services import LlamaParse

from megamind.utils.config import settings


class Parser:
    def __init__(self):
        self.parser = LlamaParse(
            api_key=settings.llama_cloud_api_key,
            num_workers=4,
            result_type="markdown",
            verbose=True,
        )

    def parse_file(self, file_path: str) -> dict:
        """
        Parse a file and return its content.
        """
        result = self.parser.parse(file_path)
        markdown_nodes = result.get_markdown_documents(split_by_page=True)
        langchain_documents = [
            markdown_node.to_langchain_format() for markdown_node in markdown_nodes
        ]

        return langchain_documents
