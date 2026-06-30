"""
WhatsApp Alert Formatter
Formats alerts and notifications for WhatsApp messages.
"""

def format_whatsapp_alert(alert_data: dict) -> str:
    """
    Formats a dictionary of alert data into a string suitable for a WhatsApp message.
    """
    if not alert_data:
        return "New Alert: No details provided."
    
    title = alert_data.get("title", "Alert")
    message = alert_data.get("message", "")
    
    formatted_message = f"*{title}*\n\n{message}"
    return formatted_message
