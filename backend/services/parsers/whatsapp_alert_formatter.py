"""
WhatsApp Alert Formatter
Formats alerts and notifications for WhatsApp messages.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel

class WhatsappAlertResponse(BaseModel):
    formatted_message: str

def format_whatsapp_alert(alert_data: dict) -> WhatsappAlertResponse:
    """
    Formats a dictionary of alert data into a string suitable for a WhatsApp message.
    """
    if not alert_data:
        return WhatsappAlertResponse(formatted_message="New Alert: No details provided.")
    
    title = alert_data.get("title", "Alert")
    message = alert_data.get("message", "")
    
    formatted_message = f"*{title}*\n\n{message}"
    return WhatsappAlertResponse(formatted_message=formatted_message)
