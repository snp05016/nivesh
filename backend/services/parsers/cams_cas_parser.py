"""
Parser for CAMS/KFintech Consolidated Account Statement (CAS) PDFs.
"""

import re
from typing import Dict, Any, List, Optional
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class InvestorInfoResponse(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    pan: Optional[str] = None
    address: Optional[str] = None

class PortfolioSummaryResponse(BaseModel):
    total_value: Optional[float] = None

class TransactionResponse(BaseModel):
    date: Optional[str] = None
    scheme: Optional[str] = None
    amount: Optional[float] = None
    units: Optional[float] = None

class CamsCasResponse(BaseModel):
    investor_info: InvestorInfoResponse
    portfolio_summary: PortfolioSummaryResponse
    transactions: List[TransactionResponse]

def extract_text_from_pdf(file_path: str, password: Optional[str] = None) -> str:
    """
    Extracts raw text from an encrypted or unencrypted CAS PDF file.

    Args:
        file_path (str): The path to the PDF file.
        password (str, optional): The password for the PDF, if encrypted.

    Returns:
        str: The extracted text from the PDF.
    """
    logger.info(f"Extracting text from {file_path}")
    text = ""
    try:
        import PyPDF2
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            if reader.is_encrypted and password:
                reader.decrypt(password)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
    return text

def parse_investor_info(text: str) -> InvestorInfoResponse:
    """
    Parses investor information from the CAS text.

    Args:
        text (str): The extracted text from the CAS PDF.

    Returns:
        InvestorInfoResponse: Object containing investor details (e.g., name, email, PAN, address).
    """
    info = InvestorInfoResponse()

    email_match = re.search(r"Email\s*ID\s*:\s*([^\n\s]+)", text, re.IGNORECASE)
    if email_match:
        info.email = email_match.group(1).strip()

    pan_match = re.search(r"PAN\s*:\s*([A-Z]{5}[0-9]{4}[A-Z]{1})", text, re.IGNORECASE)
    if pan_match:
        info.pan = pan_match.group(1).strip()

    name_match = re.search(r"Name\s*:\s*([^\n]+)", text, re.IGNORECASE)
    if name_match:
        info.name = name_match.group(1).strip()

    return info

def parse_portfolio_summary(text: str) -> PortfolioSummaryResponse:
    """
    Parses the portfolio valuation summary from the CAS text.

    Args:
        text (str): The extracted text from the CAS PDF.

    Returns:
        PortfolioSummaryResponse: Object containing portfolio summary details.
    """
    summary = PortfolioSummaryResponse()

    val_match = re.search(r"Total\s*Value\s*.*?([\d,]+\.\d{2})", text, re.IGNORECASE)
    if val_match:
        try:
            summary.total_value = float(val_match.group(1).replace(",", ""))
        except ValueError:
            pass

    return summary

def parse_transactions(text: str) -> List[TransactionResponse]:
    """
    Parses individual mutual fund transactions from the CAS text.

    Args:
        text (str): The extracted text from the CAS PDF.

    Returns:
        List[TransactionResponse]: A list of transaction objects (date, scheme, amount, units, etc.).
    """
    transactions = []
    lines = text.split('\n')
    current_scheme = None

    for line in lines:
        if "Folio No" in line or "Scheme" in line:
            current_scheme = line.strip()

        txn_match = re.search(r"(\d{2}-[a-zA-Z]{3}-\d{4})\s+.*?\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{3,4})", line)
        if txn_match and current_scheme:
            try:
                amount = float(txn_match.group(2).replace(",", ""))
                units = float(txn_match.group(3).replace(",", ""))
                transactions.append(TransactionResponse(
                    date=txn_match.group(1),
                    scheme=current_scheme,
                    amount=amount,
                    units=units
                ))
            except ValueError:
                continue

    return transactions

def parse_cams_cas(file_path: str, password: Optional[str] = None) -> CamsCasResponse:
    """
    Main function to parse a CAMS CAS PDF file and return structured data.

    Args:
        file_path (str): The path to the CAS PDF file.
        password (str, optional): The password for the PDF, if encrypted.

    Returns:
        CamsCasResponse: A structured object containing all extracted data from the CAS.
    """
    try:
        text = extract_text_from_pdf(file_path, password)

        return CamsCasResponse(
            investor_info=parse_investor_info(text),
            portfolio_summary=parse_portfolio_summary(text),
            transactions=parse_transactions(text)
        )
    except Exception as e:
        logger.error(f"Error parsing CAS file {file_path}: {str(e)}")
        raise
