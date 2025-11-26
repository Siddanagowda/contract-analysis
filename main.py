from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any
from json.decoder import JSONDecodeError
import os
import sys
import asyncio
import logging
import traceback
from database_handler import DatabaseHandler
from sqlite_rag import SQLiteOpenAIRAG
from chunking import CustomChunking
from batch_embedding import AsyncEmbeddingGenerator
from result_database import ResultDatabase
from rag_chatbot import RAGChatbot
from deepseek_ocr import DeepSeekOCR
import sqlite3
import glob
import json

# Configure logging

# Common CORS headers for all responses
def get_cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*",
    }

# Initialize FastAPI app
app = FastAPI()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400
)

# Add OPTIONS endpoints for preflight requests
@app.options("/rag-chat")
async def options_rag_chat():
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400"
        }
    )

@app.options("/extracted-data/{db_id}")
async def options_extracted_data(db_id: int):
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400"
        }
    )

@app.options("/verify-data")
async def options_verify_data():
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400"
        }
    )

# Add error handling middleware
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        
        # Ensure CORS headers are present in all responses
        if "Access-Control-Allow-Origin" not in response.headers:
            response.headers["Access-Control-Allow-Origin"] = "*"
        if "Access-Control-Allow-Methods" not in response.headers:
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        if "Access-Control-Allow-Headers" not in response.headers:
            response.headers["Access-Control-Allow-Headers"] = "*"
        
        return response
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('contract_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Note: CORS middleware is already configured above

class EditValueRequest(BaseModel):
    doc_type: str
    field_name: str
    updated_value: str

# Removing Pydantic model temporarily for debugging

class UpdateFieldRequest(BaseModel):
    db_id: int
    field: str
    value: str
    page_number: str
    doc_type: str

def sow_transform_response(response: list) -> list:
    field_mapping = {
        'start_date': 'sow_start_date',
        'end_date': 'sow_end_date'
    }
    
    transformed = []
    for entry in response:
        original_field = entry['field']
        # Rename fields
        field = field_mapping.get(original_field, original_field)

        # Extract value and page number from the value dictionary
        value_dict = entry['value']
        value = value_dict.get('field_value', '')
        page_number = value_dict.get('page_number', '') if value_dict.get('page_number', '') not in ['', None] else '0'

        # Also preserve the confidence, reasoning, and proof
        confidence = value_dict.get('confidence', None)
        reasoning = value_dict.get('reasoning', None)
        proof = value_dict.get('proof', None)

        # -- Perform your custom transformations on `value` --
        if field == 'currency' and value == 'Rs':
            value = 'INR'
        elif field == 'billing_unit_type_and_rate_cost':
            if isinstance(value, dict):
                per_sample = value.get('per_sample', 0)
                per_item = value.get('per_item', 0)
                value = f"Per-Sample : {per_sample}, Per-Item : {per_item}"
            else:
                if value is not None:
                    value = str(value).replace('{', '').replace('}', '').replace("'", "")
                else:
                    value = 'null'
        elif field == 'particular_role_rate' and isinstance(value, list):
            roles = [f"{r['role'].split('/')[0].strip()} - {r['rate']}" for r in value]
            value = ', '.join(roles)
        elif value in ['', None]:
            value = 'null'

        # Convert numeric to string
        if isinstance(value, (int, float)):
            value = str(value)

        # Final check to ensure value is ALWAYS a string
        if not isinstance(value, str):
            value = str(value)

        # Build the final dictionary
        transformed.append({
            'field': field,
            'value': value,
            'page_number': page_number,
            'confidence': confidence,
            'reasoning': reasoning,
            'proof': proof
        })
    return transformed
    
def format_other_insurance_amount(insurance_data: str | dict) -> str:
    """Format other insurance amount data into a readable string."""
    try:
        # If input is string, try to parse it as JSON
        if isinstance(insurance_data, str):
            try:
                insurance_data = json.loads(insurance_data)
            except json.JSONDecodeError:
                return ''

        # Extract insurance details
        details = insurance_data.get('insurance_details', [])
        if not details:
            return ''

        # Format each insurance type and amount pair
        formatted_pairs = []
        for detail in details:
            if isinstance(detail, dict):
                ins_type = detail.get('insurance_type', '')
                amount = detail.get('amount', 0)
                if ins_type:
                    formatted_pairs.append(f"{ins_type}: {amount}")

        return ', '.join(formatted_pairs)
    except Exception as e:
        logger.error(f"Error formatting other insurance amount: {str(e)}")
        return ''

def transform_insurance_data(insurance_data: dict) -> dict:
    """Transform nested insurance structure into individual fields for MSA."""
    try:
        if isinstance(insurance_data, str):
            try:
                insurance_data = json.loads(insurance_data)
            except json.JSONDecodeError:
                insurance_data = {}

        # Format other_insurance_amount specially
        other_insurance_amount = insurance_data.get('other_insurance_amount', {'insurance_details': []})
        formatted_other_amount = format_other_insurance_amount(other_insurance_amount)

        # Extract values with proper defaults
        return {
            'insurance_required': insurance_data.get('insurance_required', 'NO'),
            'type_of_insurance_required': ', '.join(insurance_data.get('type_of_insurance_required', [])),
            'is_cyber_insurance_required': insurance_data.get('is_cyber_insurance_required', 'NO'),
            'cyber_insurance_amount': str(insurance_data.get('cyber_insurance_amount', 0)),
            'is_workman_compensation_insurance_required': insurance_data.get('is_workman_compensation_insurance_required', 'NO'),
            'workman_compensation_insurance_amount': str(insurance_data.get('workman_compensation_insurance_amount', 0)),
            'other_insurance_required': ', '.join(insurance_data.get('other_insurance_required', [])),
            'other_insurance_amount': formatted_other_amount
        }
    except Exception as e:
        logger.error(f"Error transforming insurance data: {str(e)}")
        return {
            'insurance_required': 'NO',
            'type_of_insurance_required': '',
            'is_cyber_insurance_required': 'NO',
            'cyber_insurance_amount': '0',
            'is_workman_compensation_insurance_required': 'NO',
            'workman_compensation_insurance_amount': '0',
            'other_insurance_required': '',
            'other_insurance_amount': ''
        }

def msa_transform_response(response: list) -> list:
    field_mapping = {
        'start_date': 'msa_start_date',
        'end_date': 'msa_end_date'
    }
    
    transformed = []
    for entry in response:
        original_field = entry['field']
        # Rename fields
        field = field_mapping.get(original_field, original_field)

        # Extract value and page number from the value dictionary
        value_dict = entry['value']
        value = value_dict.get('field_value', '')
        page_number = value_dict.get('page_number', '') if value_dict.get('page_number', '') not in ['', None] else '0'

        # Also preserve the confidence, reasoning, and proof
        confidence = value_dict.get('confidence', None)
        reasoning = value_dict.get('reasoning', None)
        proof = value_dict.get('proof', None)

        # -- Perform your custom transformations on `value` --
        if field == 'currency' and value == 'Rs':
            value = 'INR'
        elif field == 'billing_unit_type_and_rate_cost':
            if isinstance(value, dict):
                per_sample = value.get('per_sample', 0)
                per_item = value.get('per_item', 0)
                value = f"Per-Sample : {per_sample}, Per-Item : {per_item}"
            else:
                if value is not None:
                    value = str(value).replace('{', '').replace('}', '').replace("'", "")
                else:
                    value = 'null'
        elif field == 'particular_role_rate' and isinstance(value, list):
            roles = [f"{r['role'].split('/')[0].strip()} - {r['rate']}" for r in value]
            value = ', '.join(roles)
        elif field == 'insurance_required':
            # Transform insurance data and add all fields
            insurance_data = transform_insurance_data(value)
            
            # Add the main insurance field
            transformed.append({
                'field': 'insurance_required',
                'value': insurance_data['insurance_required'],
                'page_number': page_number,
                'confidence': confidence,
                'reasoning': reasoning,
                'proof': proof
            })
            
            # Add all other insurance fields
            for ins_field, ins_value in insurance_data.items():
                if ins_field != 'insurance_required':
                    transformed.append({
                        'field': ins_field,
                        'value': ins_value,
                        'page_number': page_number,
                        'confidence': confidence,
                        'reasoning': reasoning,
                        'proof': proof
                    })
            continue
        elif value in ['', None]:
            value = 'null'

        # Convert numeric to string
        if isinstance(value, (int, float)):
            value = str(value)

        # Final check to ensure value is ALWAYS a string
        if not isinstance(value, str):
            value = str(value)

        # Build the final dictionary (skip if it's an insurance field that was already added)
        if not field.startswith(('type_of_insurance', 'is_cyber', 'cyber_insurance', 'is_workman', 'workman_compensation', 'other_insurance')):
            transformed.append({
                'field': field,
                'value': value,
                'page_number': page_number,
                'confidence': confidence,
                'reasoning': reasoning,
                'proof': proof
            })
    return transformed


@app.get("/")
async def root():
    return JSONResponse(
        content={"message": "Contract Extraction API v2 - CORS Update 2025-02-07 10:16"},
        headers=get_cors_headers()
    )

@app.options("/upload")
async def options_upload():
    """Handle preflight requests for the upload endpoint"""
    return JSONResponse(
        content={"message": "OK"},
        headers=get_cors_headers()
    )

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    pdfType: str = Form(...),
    use_deepseek: bool = Form(default=False)
):
    try:
        # Create contract_file directory if it doesn't exist
        os.makedirs("contract_file", exist_ok=True)

        # make sure contract_file directory is empty
        for f in os.listdir("contract_file"):
            file_path = os.path.join("contract_file", f)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        # Save uploaded file
        file_path = os.path.join("contract_file", file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        db = ResultDatabase()
        logger.info(f"Processing {pdfType} document: {file.filename}")

        # Use DeepSeek OCR if requested
        if use_deepseek:
            logger.info("Using DeepSeek OCR for extraction")
            try:
                ocr = DeepSeekOCR()
                results = ocr.extract_all_fields(file_path, doc_type=pdfType)
            except Exception as e:
                logger.error(f"DeepSeek extraction failed: {str(e)}")
                logger.info("Falling back to OpenAI extraction")
                results = await _extract_with_openai(file_path, pdfType)
        else:
            logger.info("Using OpenAI extraction")
            results = await _extract_with_openai(file_path, pdfType)

        db_id = db.store_results(results, doc_type=pdfType, file_name=file.filename)
        logger.info(f"Stored results in database with db_id: {db_id}")
        
        # Transform response based on document type
        if pdfType == "SOW":
            transformed_data = sow_transform_response(results)
        else:
            transformed_data = msa_transform_response(results)

        # add db_id to the response
        transformed_data = {'db_id': db_id, 'extracted_data': transformed_data}
        logger.info(f"Returning transformed data with db_id: {db_id}")
        
        # Return response with CORS headers
        return JSONResponse(
            content=transformed_data,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Content-Type": "application/json"
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        print(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _extract_with_openai(file_path: str, pdfType: str):
    """Extract fields using OpenAI (original method)."""
    rag = SQLiteOpenAIRAG()
    chunker = CustomChunking(overlap_words=50)
    
    chunked_docs = chunker.load_documents(file_path)
    if not chunked_docs:
        logger.error(f"Failed to load document: {file_path}")
        raise ValueError("Failed to load document")

    conn = sqlite3.connect(rag.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM document_chunks')
    count = cursor.fetchone()[0]

    embedding_generator = AsyncEmbeddingGenerator()
    embedded_docs = await embedding_generator.embed_chunks(chunked_docs)
    
    if count == 0 and chunked_docs:
        rag.db_handler.store_chunked_docs(embedded_docs)
    elif chunked_docs:
        cursor.execute('DELETE FROM document_chunks;')
        conn.commit()
        rag.db_handler.store_chunked_docs(embedded_docs)

    conn.close()
    logger.info(f"Stored {len(chunked_docs)} chunks in SQLite database")

    results = await rag.extract_all_fields(doc_type=pdfType)
    logger.info(f"Extracted {len(results)} fields from document")
    
    return results
        
@app.post("/update")
async def update_field(request: UpdateFieldRequest):
    """Update a field value in both detailed and simple tables."""
    try:
        db = ResultDatabase()
        success = db.update_sow_msa_detailed_simple_table(            
            db_id=request.db_id,
            field=request.field,
            value=request.value,
            page_number=request.page_number,
            doc_type=request.doc_type
        )
        
        if success:
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "Field updated successfully"},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type"
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to update field")
            
    except Exception as e:
        print(f"Error updating field: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/extracted-data/{db_id}")
async def get_extracted_data(db_id: int):
    """Retrieve extracted data for a specific document by db_id."""
    try:
        db = ResultDatabase()
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        # Get document metadata to determine doc type
        cursor.execute(
            "SELECT db_id, doc_type FROM document_metadata WHERE db_id = ?",
            (db_id,)
        )
        metadata = cursor.fetchone()
        
        if not metadata:
            return JSONResponse(
                status_code=404,
                content={"error": "Document not found"},
                headers=get_cors_headers()
            )
        
        doc_type = metadata[1]
        tables = {"sow": "sow_detailed_results", "msa": "msa_detailed_results"}
        table = tables.get(doc_type, "msa_detailed_results")
        
        # Get all fields for this document
        cursor.execute(
            f"""
            SELECT field_name, field_value, page_number, confidence, reasoning, proof
            FROM {table}
            WHERE db_id = ?
            ORDER BY field_name
            """,
            (db_id,)
        )
        
        results = cursor.fetchall()
        conn.close()
        
        extracted_data = [
            {
                "field": row[0],
                "value": row[1],
                "page_number": row[2],
                "confidence": row[3],
                "reasoning": row[4],
                "proof": row[5]
            }
            for row in results
        ]
        
        return JSONResponse(
            content={
                "db_id": db_id,
                "doc_type": doc_type,
                "extracted_data": extracted_data
            },
            headers=get_cors_headers()
        )
        
    except Exception as e:
        logger.error(f"Error retrieving extracted data: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
            headers=get_cors_headers()
        )

@app.post("/verify-data")
async def verify_data(request: Request):
    """Mark extracted data as verified."""
    try:
        data = await request.json()
        db_id = data.get("db_id")
        verified_fields = data.get("verified_fields", [])
        
        if not db_id:
            return JSONResponse(
                status_code=400,
                content={"error": "db_id is required"},
                headers=get_cors_headers()
            )
        
        db = ResultDatabase()
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        # Get document metadata to determine doc type
        cursor.execute(
            "SELECT doc_type FROM document_metadata WHERE db_id = ?",
            (db_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return JSONResponse(
                status_code=404,
                content={"error": "Document not found"},
                headers=get_cors_headers()
            )
        
        doc_type = result[0]
        table = f"{doc_type}_detailed_results"
        
        # Update verified status for specified fields
        for field in verified_fields:
            cursor.execute(
                f"""
                UPDATE {table}
                SET verified = 1
                WHERE db_id = ? AND field_name = ?
                """,
                (db_id, field)
            )
        
        conn.commit()
        conn.close()
        
        return JSONResponse(
            content={"success": True, "message": "Data marked as verified"},
            headers=get_cors_headers()
        )
        
    except Exception as e:
        logger.error(f"Error verifying data: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
            headers=get_cors_headers()
        )

@app.post("/rag-chat")
async def rag_chat(request: Request):
    print("Received request to /rag-chat")
    print(f"Request headers: {dict(request.headers)}")
    
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "*"
    }
    
    try:
        # Parse JSON body
        try:
            data = await request.json()
            print(f"Received data: {data}")
        except JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JSONResponse(
                content={"error": "Invalid JSON format"},
                status_code=400,
                headers=cors_headers
            )
        
        # Validate fields
        if not data.get("query"):
            return JSONResponse(
                content={"error": "query field is required"},
                status_code=400,
                headers=cors_headers
            )
        
        query = data["query"]
        session_id = data.get("session_id")
        
        print(f"Processing chat request - query: {query}, session_id: {session_id}")
        
        chatbot = RAGChatbot()
        
        if session_id == "first_session":
            print("First session, resetting conversation")
            session_id = None
            chatbot._delete_conversation_db()
        
        response = chatbot.chat(query)
        print(f"Generated response: {response}")
        
        return JSONResponse(
            content={
                "response": response,
                "session_id": session_id
            },
            headers=cors_headers
        )
        
    except Exception as e:
        print(f"Error in rag_chat: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error traceback: {traceback.format_exc()}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
            headers=cors_headers
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
