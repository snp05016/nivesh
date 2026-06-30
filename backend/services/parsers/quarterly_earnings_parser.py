"""
Quarterly Earnings Parser
Extracts tabular financial data from quarterly earnings PDF reports.
"""

import os
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class TableDataResponse(BaseModel):
    page: int
    table_index: int
    data: List[List[Any]]

class ProcessEarningsResponse(BaseModel):
    status: str
    file: str
    tables_extracted: Optional[int] = None
    data: Optional[List[TableDataResponse]] = None
    message: Optional[str] = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    
def parse_pdf_tables(file_path: str) -> List[TableDataResponse]:
    """
    Extracts tables from a PDF file.
    
    Args:
        file_path (str): The path to the PDF file.
        
    Returns:
        List[TableDataResponse]: A list of objects representing the extracted tables.
    """
    if pdfplumber is None:
        raise ImportError("pdfplumber is required to parse PDF files. Please install it using 'pip install pdfplumber'.")
        
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    extracted_tables = []
    
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table_num, table in enumerate(tables, start=1):
                extracted_tables.append(TableDataResponse(
                    page=page_num,
                    table_index=table_num,
                    data=table
                ))
                
    return extracted_tables


def clean_tabular_data(raw_tables: List[TableDataResponse]) -> List[TableDataResponse]:
    """
    Cleans the extracted tabular data by removing empty rows and columns,
    and normalizing whitespace.
    
    Args:
        raw_tables (List[TableDataResponse]): The raw extracted tables.
        
    Returns:
        List[TableDataResponse]: The cleaned tables.
    """
    cleaned_tables = []
    
    for table_info in raw_tables:
        raw_data = table_info.data
        cleaned_data = []
        
        for row in raw_data:
            # Skip empty rows
            if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                continue
                
            # Clean cells
            cleaned_row = [
                re.sub(r'\s+', ' ', str(cell).strip()) if cell is not None else ""
                for cell in row
            ]
            cleaned_data.append(cleaned_row)
            
        if cleaned_data:
            cleaned_tables.append(TableDataResponse(
                page=table_info.page,
                table_index=table_info.table_index,
                data=cleaned_data
            ))
            
    return cleaned_tables


def process_earnings_report(file_path: str) -> ProcessEarningsResponse:
    """
    Main pipeline function to process a quarterly earnings report.
    
    Args:
        file_path (str): The path to the earnings report PDF.
        
    Returns:
        ProcessEarningsResponse: An object containing the processed financial data.
    """
    try:
        raw_tables = parse_pdf_tables(file_path)
        cleaned_tables = clean_tabular_data(raw_tables)
        
        return ProcessEarningsResponse(
            status="success",
            file=os.path.basename(file_path),
            tables_extracted=len(cleaned_tables),
            data=cleaned_tables
        )
    except Exception as e:
        return ProcessEarningsResponse(
            status="error",
            file=os.path.basename(file_path),
            message=str(e)
        )
