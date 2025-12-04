import re
import os
import time
import logging
from typing import Optional, List, Dict
from pypdf import PdfReader

# Try to import DeepSeek OCR
try:
    from deepseek_ocr import get_deepseek_ocr
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False
    logging.warning("DeepSeek OCR not available. Using pypdf for text extraction.")

class CustomChunking:
    def __init__(self, overlap_words: int = 50, use_deepseek: bool = False):
        """
        Initializes the CustomChunking class with a specified number of overlap words.

        Args:
            overlap_words (int): Number of words to overlap from previous and next pages.
            use_deepseek (bool): Whether to use DeepSeek OCR for text extraction (default: False)
        """
        self.overlap_words = overlap_words
        self.use_deepseek = use_deepseek and DEEPSEEK_AVAILABLE
        self.deepseek_ocr = None
        
        if self.use_deepseek:
            try:
                self.deepseek_ocr = get_deepseek_ocr()
                if self.deepseek_ocr.is_available():
                    logging.info("DeepSeek OCR initialized successfully")
                else:
                    logging.warning("DeepSeek OCR failed to initialize, falling back to pypdf")
                    self.use_deepseek = False
            except Exception as e:
                logging.error(f"Error initializing DeepSeek OCR: {str(e)}")
                self.use_deepseek = False

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Cleans and preprocesses the input text by removing unnecessary whitespace,
        newline characters, and specific unicode escape sequences.

        Args:
            text (str): The raw text to be cleaned.

        Returns:
            str: The cleaned and stripped text.
        """
        # Replace multiple whitespace characters (spaces, tabs, newlines) with a single space
        cleaned_text = re.sub(r'\s+', ' ', text)
        
        # Remove newline characters
        cleaned_text = re.sub(r'\\n', ' ', cleaned_text)
        
        # Remove unicode escape sequences
        cleaned_text = re.sub(r'\\u[a-zA-Z0-9]{4}', '', cleaned_text)
        cleaned_text = re.sub(r'\\uf0b7', '', cleaned_text)
        
        # Remove any remaining backslashes
        cleaned_text = re.sub(r'\\', '', cleaned_text)
        
        return cleaned_text.strip()

    def load_documents(self, file_path: str) -> Optional[List[Dict]]:
        """
        Loads and processes a PDF document from the specified file path.

        Args:
            file_path (str): The path to the PDF file.

        Returns:
            Optional[List[Dict]]: A list of dictionaries containing page numbers and cleaned text,
                                  or None if an error occurs.
        """
        print(f"------------------------------Loading document from '{file_path}'------------------------------")

        if not os.path.exists(file_path):
            print(f"------------------------------Error: The file '{file_path}' does not exist.------------------------------")
            return None

        if not file_path.lower().endswith(".pdf"):
            print(f"------------------------------Error: The file '{file_path}' is not a PDF.------------------------------")
            return None

        try:
            return self.read_pdf(file_path)
        except Exception as e:
            print(f"------------------------------Error loading '{file_path}': {str(e)}------------------------------")
            return None

    def read_pdf(self, file_name: str) -> List[Dict]:
        """
        Reads and extracts text from each page of a PDF file, cleaning the text before storage.

        Args:
            file_name (str): The name of the PDF file to read.

        Returns:
            List[Dict]: A list of dictionaries with page numbers and their corresponding cleaned text.
        """
        # Use DeepSeek OCR if enabled
        if self.use_deepseek and self.deepseek_ocr:
            try:
                print(f"Using DeepSeek OCR for {file_name}")
                results = self.deepseek_ocr.process_pdf(file_name)
                if results:
                    # Clean text for consistency
                    for page in results:
                        page['text'] = self.clean_text(page['text'])
                    return results
                else:
                    print("DeepSeek OCR returned no results, falling back to pypdf")
            except Exception as e:
                print(f"DeepSeek OCR failed: {str(e)}, falling back to pypdf")

        # Fallback to pypdf
        reader = PdfReader(file_name)
        page_contents = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text:
                cleaned_text = self.clean_text(text)  # Clean the text before adding it to the list
                page_contents.append({"page_number": page_number, "text": cleaned_text})

        return page_contents

    def get_last_n_words(self, text: str, n: int) -> str:
        """
        Retrieves the last n words from the given text.

        Args:
            text (str): The text to extract words from.
            n (int): Number of words to extract.

        Returns:
            str: The last n words.
        """
        words = text.split()
        return ' '.join(words[-n:]) if len(words) >= n else ' '.join(words)

    def get_first_n_words(self, text: str, n: int) -> str:
        """
        Retrieves the first n words from the given text.

        Args:
            text (str): The text to extract words from.
            n (int): Number of words to extract.

        Returns:
            str: The first n words.
        """
        words = text.split()
        return ' '.join(words[:n]) if len(words) >= n else ' '.join(words)

    def chunk_documents(self, pages: List[Dict]) -> List[Dict]:
        """
        Chunks the document pages with overlapping words from previous and next pages.

        Args:
            pages (List[Dict]): List of dictionaries containing page numbers and text.

        Returns:
            List[Dict]: List of dictionaries with page numbers and their corresponding chunked text.
        """
        chunked_pages = []
        total_pages = len(pages)

        for i, page in enumerate(pages):
            chunk_text = ""

            # Add last n words from previous page if not the first page
            if i > 0:
                prev_page_text = pages[i - 1]['text']
                overlap_prev = self.get_last_n_words(prev_page_text, self.overlap_words)
                chunk_text += overlap_prev + ' '

            # Add current page text
            chunk_text += page['text'] + ' '

            # Add first n words from next page if not the last page
            if i < total_pages - 1:
                next_page_text = pages[i + 1]['text']
                overlap_next = self.get_first_n_words(next_page_text, self.overlap_words)
                chunk_text += overlap_next

            # Clean up any extra whitespace
            chunk_text = chunk_text.strip()

            # Append to the chunked_pages list with the current page number
            chunked_pages.append({
                "page_number": page['page_number'],
                "text": chunk_text
            })

        return chunked_pages

    def process_file(self, file_path: str) -> Optional[List[Dict]]:
        """
        End-to-end processing of the PDF file: loading, cleaning, and chunking.

        Args:
            file_path (str): The path to the PDF file.

        Returns:
            Optional[List[Dict]]: The chunked document as a list of dictionaries, or None if an error occurs.
        """
        pages = self.load_documents(file_path)
        if pages is None:
            return None

        chunked_pages = self.chunk_documents(pages)
        return chunked_pages

    @staticmethod
    def print_clean_chunked_document(chunked_document: List[Dict]) -> None:
        """
        Prints the chunked document in a clean and readable format.
        Args:
            chunked_document (List[Dict]): The chunked document as a list of dictionaries,
                                           each containing 'page_number' and 'text'.
        """
        if not chunked_document:
            print("No document to display.")
            return
        for chunk in chunked_document:
            page_number = chunk.get("page_number", "Unknown")
            text = chunk.get("text", "")
            print(f"--- Page {page_number} ---")
            print(text)
            print("\n" + "-" * 50 + "\n")