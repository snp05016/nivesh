import logging
"""
Offline Calibration Report Generator

Generates a markdown report summarizing model calibration, pillar performance,
and proposed fusion weights. Run this periodically to review if confidence
fusion logic needs updating.
"""
import os
from datetime import datetime

from services.prediction_calibration_service import (
    get_calibration_metrics,
    get_calibration_health,
    get_fusion_weight_recommendations
)

def generate_report():
    logging.info("Generating calibration report...")
    health = get_calibration_health()
    metrics = get_calibration_metrics()
    recommendations = get_fusion_weight_recommendations()
    
    report_lines = []
    report_lines.append("# Nivesh Prediction Calibration Report")
    report_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"**Total Predictions:** {health['total_predictions']}")
    report_lines.append("")
    
    report_lines.append("## 1. Data Readiness")
    report_lines.append(f"- **Matured 7d:** {health.get('matured_7d', 0)}")
    report_lines.append(f"- **Matured 30d:** {health.get('matured_30d', 0)}")
    report_lines.append(f"- **Matured 90d:** {health.get('matured_90d', 0)}")
    report_lines.append(f"- **Ready for Calibration:** {'✅ Yes' if health.get('is_ready_for_calibration') else '❌ No'}")
    
    if health.get('warnings'):
        report_lines.append("\n**Warnings:**")
        for w in health['warnings']:
            report_lines.append(f"- {w}")
    report_lines.append("")
    
    report_lines.append("## 2. Calibration Errors (Overall)")
    ece = metrics.get('expected_calibration_error')
    mce = metrics.get('max_calibration_error')
    report_lines.append(f"- **Expected Calibration Error (ECE):** {ece if ece is not None else 'N/A'}")
    report_lines.append(f"- **Max Calibration Error (MCE):** {mce if mce is not None else 'N/A'}")
    report_lines.append("")
    
    report_lines.append("## 3. Recommended Fusion Weights")
    rec_weights = recommendations.get('recommended_weights', {})
    for k, v in rec_weights.items():
        report_lines.append(f"- **{k}:** {v:.4f}")
    if recommendations.get('warnings'):
        report_lines.append("\n**Warnings:**")
        for w in recommendations['warnings']:
            report_lines.append(f"- {w}")
    report_lines.append("\n> Note: These weights are advisory. Manually update `confidence_fusion.py` if you choose to apply them.")
    report_lines.append("")
    
    # Write report
    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/calibration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
        
    logging.info(f"Report successfully saved to {report_path}")

if __name__ == "__main__":
    generate_report()
