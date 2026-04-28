import logging
from pathlib import Path
from typing import Optional

# Using local import to allow the rest of the system to run 
# even if markitdown is not yet installed in the environment.
try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None

class DocumentConverter:
    """
    Service to convert various document formats (PDF, Word, Excel, etc.) to Markdown.
    Uses Microsoft's MarkItDown as the primary engine.
    """
    
    def __init__(self):
        if MarkItDown is None:
            logging.warning("MarkItDown not installed. Document conversion will be unavailable.")
            self.md_engine = None
        else:
            self.md_engine = MarkItDown()

    def convert_to_markdown(self, source_path: Path) -> Optional[str]:
        """
        Convert a single file to markdown.
        """
        if self.md_engine is None:
            logging.error(f"Cannot convert {source_path}: MarkItDown engine not available.")
            return None
            
        if not source_path.exists():
            logging.error(f"Source file not found: {source_path}")
            return None

        try:
            # markitdown.convert returns a conversion result object
            result = self.md_engine.convert(str(source_path))
            return result.text_content
        except Exception as e:
            logging.error(f"Failed to convert {source_path} to markdown: {e}")
            return None

    def save_markdown(self, source_path: Path, output_dir: Path) -> Optional[Path]:
        """
        Convert and save as a .md file in the output directory.
        """
        text = self.convert_to_markdown(source_path)
        if text is None:
            return None
            
        output_path = output_dir / f"{source_path.stem}.md"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
            
        return output_path
