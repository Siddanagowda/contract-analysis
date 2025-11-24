import os
import json
import logging
from typing import Dict, List, Any
from pathlib import Path
import torch
from transformers import AutoModel, AutoTokenizer
from PIL import Image
import fitz
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class DeepSeekOCR:
    """DeepSeek OCR for contract analysis with visual understanding."""
    
    def __init__(self, model_name: str = "deepseek-ai/DeepSeek-OCR"):
        """Initialize DeepSeek OCR model."""
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Loading DeepSeek model on {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, 
            trust_remote_code=True
        )
        self.model = AutoModel.from_pretrained(
            model_name,
            _attn_implementation='flash_attention_2' if self.device == "cuda" else 'eager',
            trust_remote_code=True,
            use_safetensors=True,
            torch_dtype=torch.bfloat16 if self.device == "cuda" else torch.float32
        )
        self.model = self.model.eval().to(self.device)
        logger.info("DeepSeek model loaded successfully")

    def pdf_to_images(self, pdf_path: str, base_size: int = 1024) -> List[Image.Image]:
        """Convert PDF pages to images."""
        try:
            pdf_document = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                
                # Resize to base_size
                img.thumbnail((base_size, base_size), Image.Resampling.LANCZOS)
                images.append(img)
            
            pdf_document.close()
            logger.info(f"Converted {len(images)} pages to images")
            return images
            
        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}")
            raise

    def extract_fields(
        self,
        pdf_path: str,
        doc_type: str,
        fields_to_extract: List[str]
    ) -> List[Dict[str, Any]]:
        """Extract fields from contract using DeepSeek OCR."""
        try:
            # Convert PDF to images
            images = self.pdf_to_images(pdf_path)
            
            results = []
            
            for page_num, image in enumerate(images):
                logger.info(f"Processing page {page_num + 1}/{len(images)}")
                
                # Create extraction prompt
                fields_str = ", ".join(fields_to_extract)
                prompt = f"""<image>\n<|grounding|>Extract the following contract fields from this {doc_type} document:
{fields_str}

Return as JSON with format:
{{
    "field_name": "extracted_value",
    "confidence": 0.95,
    "reasoning": "why this value",
    "proof": "evidence from text"
}}"""
                
                # Extract using DeepSeek
                page_results = self._extract_page_fields(
                    image=image,
                    prompt=prompt,
                    page_num=page_num + 1,
                    doc_type=doc_type
                )
                
                results.extend(page_results)
            
            logger.info(f"Extracted {len(results)} field instances from document")
            return results
            
        except Exception as e:
            logger.error(f"Error extracting fields: {str(e)}")
            raise

    def _extract_page_fields(
        self,
        image: Image.Image,
        prompt: str,
        page_num: int,
        doc_type: str
    ) -> List[Dict[str, Any]]:
        """Extract fields from a single page."""
        try:
            with torch.no_grad():
                output = self.model.infer(
                    self.tokenizer,
                    prompt=prompt,
                    image_file=image,
                    base_size=1024,
                    image_size=640,
                    crop_mode=True,
                    save_results=False,
                    test_compress=True
                )
            
            # Parse output
            results = self._parse_extraction_output(
                output,
                page_num=page_num,
                doc_type=doc_type
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error extracting page fields: {str(e)}")
            return []

    def _parse_extraction_output(
        self,
        output: str,
        page_num: int,
        doc_type: str
    ) -> List[Dict[str, Any]]:
        """Parse DeepSeek extraction output."""
        results = []
        
        try:
            # Try to parse JSON from output
            json_start = output.find('{')
            json_end = output.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = output[json_start:json_end]
                extracted_data = json.loads(json_str)
                
                for field_name, value in extracted_data.items():
                    if isinstance(value, dict):
                        field_value = value.get('value', value.get('extracted_value', ''))
                        confidence = value.get('confidence', 0.8)
                        reasoning = value.get('reasoning', '')
                        proof = value.get('proof', '')
                    else:
                        field_value = str(value)
                        confidence = 0.85
                        reasoning = 'Extracted by DeepSeek OCR'
                        proof = field_value
                    
                    results.append({
                        'field': field_name,
                        'value': {
                            'field_value': field_value,
                            'page_number': str(page_num),
                            'confidence': confidence,
                            'reasoning': reasoning,
                            'proof': proof
                        }
                    })
        
        except json.JSONDecodeError:
            # Fallback: return raw output
            logger.warning(f"Could not parse JSON from DeepSeek output for page {page_num}")
            results.append({
                'field': 'raw_output',
                'value': {
                    'field_value': output,
                    'page_number': str(page_num),
                    'confidence': 0.5,
                    'reasoning': 'Raw DeepSeek output',
                    'proof': output
                }
            })
        
        except Exception as e:
            logger.error(f"Error parsing extraction output: {str(e)}")
        
        return results

    def extract_all_fields(
        self,
        pdf_path: str,
        doc_type: str = "SOW"
    ) -> List[Dict[str, Any]]:
        """Extract all contract fields."""
        # Define fields by document type
        if doc_type.upper() == "SOW":
            fields = [
                "client_company_name", "currency", "start_date", "end_date",
                "cola", "credit_period", "inclusive_or_exclusive_gst",
                "sow_value", "sow_no", "type_of_billing", "po_number",
                "amendment_no", "billing_unit_type_and_rate_cost", "particular_role_rate"
            ]
        else:  # MSA
            fields = [
                "client_company_name", "currency", "start_date", "end_date",
                "info_security", "limitation_of_liability", "data_processing_agreement",
                "insurance_required", "type_of_insurance_required",
                "is_cyber_insurance_required", "cyber_insurance_amount",
                "is_workman_compensation_insurance_required",
                "workman_compensation_insurance_amount",
                "other_insurance_required", "other_insurance_amount"
            ]
        
        return self.extract_fields(pdf_path, doc_type, fields)


def extract_contract_fields(pdf_path: str, doc_type: str = "SOW") -> List[Dict[str, Any]]:
    """Convenience function to extract fields from contract."""
    ocr = DeepSeekOCR()
    return ocr.extract_all_fields(pdf_path, doc_type)

