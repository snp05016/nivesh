"""
Parser for daily FII/DII sectoral derivative activity reports.
"""

import pandas as pd
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SectoralActivityResponse(BaseModel):
    buy_value: float
    sell_value: float

class AggregatedActivityResponse(BaseModel):
    total_fii_buy: float = 0.0
    total_fii_sell: float = 0.0
    total_dii_buy: float = 0.0
    total_dii_sell: float = 0.0
    sectoral_breakdown: Optional[Dict[str, SectoralActivityResponse]] = None

class FiiDiiPipelineResponse(BaseModel):
    status: str
    raw_data_shape: Optional[tuple] = None
    aggregated_data: Optional[AggregatedActivityResponse] = None
    report_summary: Optional[str] = None
    message: Optional[str] = None

def parse_fii_dii_report(file_path: str) -> pd.DataFrame:
    """
    Parses a raw FII/DII derivative activity report into a pandas DataFrame.
    
    Args:
        file_path (str): The path to the daily report file (CSV/Excel).
        
    Returns:
        pd.DataFrame: Cleaned and structured data.
    """
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format. Please provide a CSV or Excel file.")
            
        df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
        logger.info(f"Successfully parsed FII/DII report from {file_path}")
        return df
    except Exception as e:
        logger.error(f"Error parsing FII/DII report: {e}")
        raise

def aggregate_sectoral_activity(df: pd.DataFrame) -> AggregatedActivityResponse:
    """
    Aggregates FII/DII derivative activity by sector and instrument type.
    
    Args:
        df (pd.DataFrame): Cleaned FII/DII activity dataframe.
        
    Returns:
        AggregatedActivityResponse: Aggregated data metrics.
    """
    if df.empty:
        return AggregatedActivityResponse()

    summary_args = {
        'total_fii_buy': float(df[df.get('client_type', '') == 'FII'].get('buy_value', pd.Series(dtype=float)).sum()),
        'total_fii_sell': float(df[df.get('client_type', '') == 'FII'].get('sell_value', pd.Series(dtype=float)).sum()),
        'total_dii_buy': float(df[df.get('client_type', '') == 'DII'].get('buy_value', pd.Series(dtype=float)).sum()),
        'total_dii_sell': float(df[df.get('client_type', '') == 'DII'].get('sell_value', pd.Series(dtype=float)).sum()),
    }
    
    if 'sector' in df.columns:
        sector_group = df.groupby('sector')
        sectoral_dict = sector_group.agg({
            'buy_value': 'sum', 
            'sell_value': 'sum'
        }).to_dict(orient='index')
        summary_args['sectoral_breakdown'] = {k: SectoralActivityResponse(**v) for k, v in sectoral_dict.items()}
        
    return AggregatedActivityResponse(**summary_args)

def generate_daily_summary(aggregated_data: AggregatedActivityResponse) -> str:
    """
    Generates a human-readable summary report from aggregated data.
    
    Args:
        aggregated_data (AggregatedActivityResponse): The aggregated FII/DII data.
        
    Returns:
        str: Textual summary report.
    """
    if not aggregated_data or (aggregated_data.total_fii_buy == 0.0 and aggregated_data.total_dii_buy == 0.0 and not aggregated_data.sectoral_breakdown):
        return "No data available for daily summary."
        
    fii_net = aggregated_data.total_fii_buy - aggregated_data.total_fii_sell
    dii_net = aggregated_data.total_dii_buy - aggregated_data.total_dii_sell
    
    report_lines = [
        "📊 FII/DII Daily Derivative Activity Summary",
        "=" * 45,
        f"FII Net Activity: {'Bullish (Net Long)' if fii_net > 0 else 'Bearish (Net Short)'} (₹ {fii_net:,.2f})",
        f"DII Net Activity: {'Bullish (Net Long)' if dii_net > 0 else 'Bearish (Net Short)'} (₹ {dii_net:,.2f})",
        ""
    ]
    
    sectoral = aggregated_data.sectoral_breakdown or {}
    if sectoral:
        report_lines.append("Sectoral Highlights:")
        report_lines.append("-" * 20)
        for sector, values in sectoral.items():
            net = values.buy_value - values.sell_value
            report_lines.append(f" - {sector.title()}: {'Positive' if net > 0 else 'Negative'} (Net: ₹ {net:,.2f})")
            
    return "\n".join(report_lines)

def fii_dii_summarization_pipeline(file_path: str) -> FiiDiiPipelineResponse:
    """
    End-to-end pipeline to parse, aggregate, and summarize FII/DII daily sectoral derivative reports.
    
    Args:
        file_path (str): Path to the input report file.
        
    Returns:
        FiiDiiPipelineResponse: A structured object containing the raw df info, aggregated dict, and text report.
    """
    logger.info("Starting FII/DII summarization pipeline...")
    
    try:
        df = parse_fii_dii_report(file_path)
        aggregated_data = aggregate_sectoral_activity(df)
        report_text = generate_daily_summary(aggregated_data)
        
        logger.info("Pipeline executed successfully.")
        
        return FiiDiiPipelineResponse(
            status='success',
            raw_data_shape=df.shape,
            aggregated_data=aggregated_data,
            report_summary=report_text
        )
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return FiiDiiPipelineResponse(
            status='error',
            message=str(e)
        )
