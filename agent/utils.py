import logging
import os
from typing import Dict, Any, List

# Configure logger
logger = logging.getLogger("Family_law_chat")

# Swedish UI text dictionary
# SWEDISH_UI_TEXT = {
#     "processing_question": "Bearbetar din fråga...",
#     "understanding_context": "Förstår din fråga i sammanhanget...",
#     "searching": "Söker efter relevant juridisk information...",
#     "processing_files": "Bearbetar uppladdade filer...",
#     "retrieved_docs": "Hämtade dokument",
#     "error_processing": "Fel vid bearbetning av fil",
#     "unsupported_file": "Filtyp stöds inte",
#     "supported_formats": "Format som stöds är",
#     "settings_updated": "Inställningarna har uppdaterats",
#     "processed": "Bearbetade",
#     "files": "filer",
#     "extracted": "extraherade",
#     "text_chunks": "textavsnitt",
#     "error_initializing": "Fel vid initialisering av kunskapsbasen"
# }
#
# def get_ui_text(key: str) -> str:
#     """Get UI text in Swedish"""
#     # Return the requested text or a placeholder if key not found
#     return SWEDISH_UI_TEXT.get(key, f"[Saknad text: {key}]")
#
# def format_document_for_display(doc: Dict[str, Any], index: int) -> str:
#     """Format a document for display in the UI (Swedish only)"""
#     doc_content = f"**Dokument {index+1}**\n\n"
#     if 'title' in doc.metadata:
#         doc_content += f"**Titel:** {doc.metadata['title']}\n\n"
#     if 'law_name' in doc.metadata:
#         doc_content += f"**Lagnamn:** {doc.metadata['law_name']}\n\n"
#     doc_content += f"**Innehållsutdrag:** {doc.page_content[:300]}...\n\n"
#
#     return doc_content



def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("swedish_law_chat.log"),
            logging.StreamHandler()
        ]
    )
    logger.info("Loggning initialiserad")
