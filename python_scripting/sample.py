import pandas as pd
from datetime import datetime

def load_data(source_file):
    """Load raw data from CSV/Excel."""
    if source_file.endswith(".csv"):
        return pd.read_csv(source_file)
    elif source_file.endswith(".xlsx"):
        return pd.read_excel(source_file)
    else:
        raise ValueError("Unsupported file type")

def generate_report(df):
    """Process and create a summary report."""
    report = {
        "total_rows": len(df),
        "column_summary": df.describe(include='all').to_dict(),
        "generated_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return report

def save_report(report, output_file="report.xlsx"):
    """Save the report as an Excel file."""
    writer = pd.ExcelWriter(output_file, engine="xlsxwriter")
    
    # Save summary table
    summary_df = pd.DataFrame({
        "Metric": report.keys(),
        "Value": report.values()
    })
    summary_df.to_excel(writer, sheet_name="Summary", index=False)

    writer.close()
    print("Report successfully generated:", output_file)

if __name__ == "__main__":
    data = load_data("sample.csv")    # sample input file
    report = generate_report(data)
    save_report(report, "final_report.xlsx")
