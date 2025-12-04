"""
DeepSeek OCR Module
Simplified implementation for PDF to text extraction using DeepSeek-OCR
"""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path
import base64
from io import BytesIO

try:
    from transformers import AutoModel, AutoTokenizer
    import torch
    from PIL import Image
    from pdf2image import convert_from_path
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False
    logging.warning("DeepSeek-OCR dependencies not installed. Using fallback mode.")

logger = logging.getLogger(__name__)


class DeepSeekOCR:
    """
    DeepSeek OCR for document processing
    Uses the tiny model (512x512) for efficient processing
    """
    
    def __init__(
        self,
        model_name: str = "deepseek-ai/DeepSeek-OCR",
        base_size: int = 512,
        image_size: int = 512,
        device: str = None
    ):
        """
        Initialize DeepSeek OCR
        
        Args:
            model_name: HuggingFace model name
            base_size: Base resolution for processing (tiny: 512, small: 640, base: 1024)
            image_size: Image size for processing
            device: Device to use (cuda/cpu), auto-detected if None
        """
        self.model_name = model_name
        self.base_size = base_size
        self.image_size = image_size
        
        if not DEEPSEEK_AVAILABLE:
            logger.warning("DeepSeek-OCR not available. Install required packages.")
            self.model = None
            self.tokenizer = None
            return
        
        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Initializing DeepSeek-OCR on {self.device}")
        
        try:
            # Load model and tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True
            )
            
            # Load model with appropriate settings
            if self.device == "cuda":
                self.model = AutoModel.from_pretrained(
                    model_name,
                    trust_remote_code=True,
                    torch_dtype=torch.bfloat16,
                    device_map="auto",
                    low_cpu_mem_usage=True
                )
            else:
                self.model = AutoModel.from_pretrained(
                    model_name,
                    trust_remote_code=True,
                    device_map="cpu",
                    low_cpu_mem_usage=True
                )
            
            self.model.eval()
            logger.info("DeepSeek-OCR model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load DeepSeek-OCR model: {str(e)}")
            self.model = None
            self.tokenizer = None
    
    def is_available(self) -> bool:
        """Check if DeepSeek-OCR is available and loaded"""
        return DEEPSEEK_AVAILABLE and self.model is not None and self.tokenizer is not None
    
    def pdf_to_images(self, pdf_path: str, dpi: int = 200) -> List[Image.Image]:
        """
        Convert PDF to images
        
        Args:
            pdf_path: Path to PDF file
            dpi: DPI for conversion (higher = better quality but slower)
            
        Returns:
            List of PIL Images
        """
        try:
            logger.info(f"Converting PDF to images: {pdf_path}")
            images = convert_from_path(pdf_path, dpi=dpi)
            logger.info(f"Converted {len(images)} pages")
            return images
        except Exception as e:
            error_msg = str(e)
            if "poppler" in error_msg.lower() or "pdfinfo" in error_msg.lower():
                logger.error("Poppler is not installed or not in PATH. Please install Poppler for Windows.")
                logger.error("Download from: https://github.com/oschwartz10612/poppler-windows/releases/")
                logger.error("Extract and add the 'bin' folder to your system PATH.")
            logger.error(f"Error converting PDF to images: {error_msg}")
            return []
    
    def extract_text_from_image(
        self,
        image: Image.Image,
        prompt: str = "<image>\\nFree OCR."
    ) -> str:
        """
        Extract text from a single image using DeepSeek-OCR
        
        Args:
            image: PIL Image
            prompt: Prompt for OCR (default: Free OCR for simple text extraction)
            
        Returns:
            Extracted text
        """
        if not self.is_available():
            logger.warning("DeepSeek-OCR not available, returning empty string")
            return ""
        
        try:
            # Convert image to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save image temporarily
            temp_image_path = os.path.abspath("temp_ocr_image.jpg")
            image.save(temp_image_path)
            
            # Create temporary output directory
            temp_output_dir = os.path.abspath("temp_ocr_output")
            os.makedirs(temp_output_dir, exist_ok=True)
            
            # Run inference
            result = self.model.infer(
                self.tokenizer,
                prompt=prompt,
                image_file=temp_image_path,
                output_path=temp_output_dir,
                base_size=self.base_size,
                image_size=self.image_size,
                crop_mode=False,
                save_results=False,
                test_compress=False
            )
            
            # Clean up temp files
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
            
            # Extract text from result
            if isinstance(result, dict) and 'text' in result:
                return result['text']
            elif isinstance(result, str):
                return result
            else:
                logger.warning(f"Unexpected result type: {type(result)}")
                return str(result)
                
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            return ""
    
    def process_pdf(
        self,
        pdf_path: str,
        prompt: str = "<image>\\nFree OCR.",
        dpi: int = 200
    ) -> List[Dict[str, any]]:
        """
        Process entire PDF and extract text from each page
        
        Args:
            pdf_path: Path to PDF file
            prompt: Prompt for OCR
            dpi: DPI for PDF to image conversion
            
        Returns:
            List of dictionaries with page_number and text
        """
        if not self.is_available():
            logger.warning("DeepSeek-OCR not available, returning empty list")
            return []
        
        logger.info(f"Processing PDF with DeepSeek-OCR: {pdf_path}")
        
        # Convert PDF to images
        images = self.pdf_to_images(pdf_path, dpi=dpi)
        
        if not images:
            logger.error("No images extracted from PDF")
            return []
        
        # Process each page
        results = []
        for page_num, image in enumerate(images, start=1):
            logger.info(f"Processing page {page_num}/{len(images)}")
            
            text = self.extract_text_from_image(image, prompt=prompt)
            
            results.append({
                "page_number": page_num,
                "text": text.strip()
            })
        
        logger.info(f"Completed processing {len(results)} pages")
        return results


# Singleton instance
_deepseek_ocr_instance = None


def get_deepseek_ocr(
    base_size: int = None,
    image_size: int = None
) -> DeepSeekOCR:
    """
    Get or create DeepSeek OCR singleton instance
    
    Args:
        base_size: Base resolution (default from env or 512)
        image_size: Image size (default from env or 512)
        
    Returns:
        DeepSeekOCR instance
    """
    global _deepseek_ocr_instance
    
    if _deepseek_ocr_instance is None:
        # Get settings from environment or use defaults
        if base_size is None:
            base_size = int(os.getenv("DEEPSEEK_OCR_BASE_SIZE", "512"))
        if image_size is None:
            image_size = int(os.getenv("DEEPSEEK_OCR_IMAGE_SIZE", "512"))
        
        _deepseek_ocr_instance = DeepSeekOCR(
            base_size=base_size,
            image_size=image_size
        )
    
    return _deepseek_ocr_instance
