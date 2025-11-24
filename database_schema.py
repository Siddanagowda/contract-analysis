from typing import Dict, List

# Common table schema for SOW detailed results
SOW_DETAILED_SCHEMA = {
    'db_id': 'INTEGER NOT NULL',
    'field_name': 'TEXT NOT NULL',
    'field_value': 'TEXT',
    'page_number': 'TEXT',
    'confidence': 'REAL',
    'reasoning': 'TEXT',
    'proof': 'TEXT',
    'file_name': 'TEXT NOT NULL',
    'verified': 'INTEGER DEFAULT 0',
    'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
}

# Common table schema for MSA detailed results
MSA_DETAILED_SCHEMA = {
    'db_id': 'INTEGER NOT NULL',
    'field_name': 'TEXT NOT NULL',
    'field_value': 'TEXT',
    'page_number': 'TEXT',
    'confidence': 'REAL',
    'reasoning': 'TEXT',
    'proof': 'TEXT',
    'file_name': 'TEXT NOT NULL',
    'verified': 'INTEGER DEFAULT 0',
    'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
}

# Schema for SOW simple results (transposed format)
SOW_FIELDS = [
    'client_company_name',
    'currency',
    'start_date',
    'end_date',
    'cola',
    'credit_period',
    'inclusive_or_exclusive_gst',
    'sow_value',
    'sow_no',
    'type_of_billing',
    'po_number',
    'amendment_no',
    'particular_role_rate',
    'billing_unit_type_and_rate_cost'
]

# Schema for MSA simple results (transposed format)
MSA_FIELDS = [
    'client_company_name',
    'currency',
    'start_date',
    'end_date',
    'credit_period',
    'insurance_required',
    'type_of_insurance_required',
    'is_cyber_insurance_required',
    'cyber_insurance_amount',
    'is_workman_compensation_insurance_required',
    'workman_compensation_insurance_amount',
    'other_insurance_required',
    'other_insurance_details',
    'data_processing_agreement',
    'limitation_of_liability'
]

# Create dynamic schema for simple tables based on fields
def create_simple_schema(fields):
    schema = {
        'db_id': 'INTEGER NOT NULL PRIMARY KEY',
        'file_name': 'TEXT NOT NULL',
        'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
    }
    for field in fields:
        schema[field] = 'TEXT'
    return schema

SOW_SIMPLE_SCHEMA = create_simple_schema(SOW_FIELDS)
MSA_SIMPLE_SCHEMA = create_simple_schema(MSA_FIELDS)

# Document metadata schema
DOCUMENT_METADATA_SCHEMA = {
    'db_id': 'INTEGER NOT NULL',  # Added db_id
    'doc_type': 'TEXT NOT NULL',
    'file_name': 'TEXT NOT NULL',
    'processed_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
    'PRIMARY KEY': '(db_id, doc_type, file_name)'  # Modified primary key to include db_id
}

def get_create_table_sql(table_name: str, schema: Dict[str, str]) -> str:
    """Generate CREATE TABLE SQL statement from schema dictionary."""
    columns = [f"{col_name} {col_type}" for col_name, col_type in schema.items() if col_name != 'PRIMARY KEY']
    primary_key = schema.get('PRIMARY KEY', '')
    if primary_key:
        columns.append(f'PRIMARY KEY {primary_key}')
    return f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {', '.join(columns)}
    )
    """

def get_table_names(doc_type: str) -> Dict[str, str]:
    """Get table names for a specific document type."""
    doc_type = doc_type.lower()
    return {
        'detailed': f'{doc_type}_detailed_results',
        'simple': f'{doc_type}_simple_results',
        'metadata': 'document_metadata'
    }

# Index definitions for better query performance
INDEX_DEFINITIONS = {
    'idx_file_name': 'CREATE INDEX IF NOT EXISTS {table_name}_file_name_idx ON {table_name} (file_name)',
    'idx_created_at': 'CREATE INDEX IF NOT EXISTS {table_name}_created_at_idx ON {table_name} (created_at)',
    'idx_doc_type': 'CREATE INDEX IF NOT EXISTS document_metadata_doc_type_idx ON document_metadata (doc_type)',
    'idx_db_id': 'CREATE INDEX IF NOT EXISTS {table_name}_db_id_idx ON {table_name} (db_id)'  # Added index for db_id
}

# Specific index definitions for detailed tables
DETAILED_INDEX_DEFINITIONS = {
    'idx_field_name': 'CREATE INDEX IF NOT EXISTS {table_name}_field_name_idx ON {table_name} (field_name)'
}
