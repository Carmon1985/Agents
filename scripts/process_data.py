import json
import pandas as pd
from datetime import datetime
import os

def load_json_data(file_path):
    """Load JSON data from file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_master_file(data, output_dir):
    """Create master.xlsx with employee data."""
    df = pd.DataFrame(data['Master_data'])
    
    # Convert date columns
    df['Seniority Date'] = pd.to_datetime(df['Seniority Date'])
    
    # Calculate additional metrics
    df['Years of Service'] = (datetime.now() - df['Seniority Date']).dt.days / 365.25
    
    # Save to Excel
    output_file = os.path.join(output_dir, 'master.xlsx')
    df.to_excel(output_file, index=False)
    print(f"Created {output_file}")

def create_charged_hours_file(data, output_dir):
    """Create charged_hours.xlsx with utilization data."""
    # Create sample charged hours data based on master data
    charged_hours_data = []
    
    for employee in data['Master_data']:
        if employee['Status'] == 'ACTIVE':
            # Generate sample data for last 12 months
            for month in range(1, 13):
                charged_hours_data.append({
                    'GPN': employee['GPN'],
                    'Person_Name': employee['Person_Name'],
                    'Year': 2024,
                    'Month': month,
                    'Charged_Hours': 160,  # Standard monthly hours
                    'Capacity_Hours': 176,  # Standard capacity
                    'Location': employee['Location'],
                    'Competency': employee['Competency'],
                    'Level': employee['Level']
                })
    
    df = pd.DataFrame(charged_hours_data)
    output_file = os.path.join(output_dir, 'charged_hours.xlsx')
    df.to_excel(output_file, index=False)
    print(f"Created {output_file}")

def create_targets_file(data, output_dir):
    """Create targets.xlsx with utilization targets."""
    # Extract unique combinations of relevant fields
    unique_segments = set()
    for employee in data['Master_data']:
        unique_segments.add((
            employee['Person Segment'],
            employee['Employee Category'],
            employee['Level Group']
        ))
    
    # Create targets data
    targets_data = []
    for segment, category, level_group in unique_segments:
        targets_data.append({
            'Person Segment': segment,
            'Employee Category': category,
            'Level Group': level_group,
            'Target Utilization': 0.85,  # 85% standard target
            'Year': 2024,
            'Quarter': 'Q1'
        })
        targets_data.append({
            'Person Segment': segment,
            'Employee Category': category,
            'Level Group': level_group,
            'Target Utilization': 0.85,
            'Year': 2024,
            'Quarter': 'Q2'
        })
    
    df = pd.DataFrame(targets_data)
    output_file = os.path.join(output_dir, 'targets.xlsx')
    df.to_excel(output_file, index=False)
    print(f"Created {output_file}")

def main():
    # Create output directory if it doesn't exist
    output_dir = 'data/excel'
    os.makedirs(output_dir, exist_ok=True)
    
    # Load JSON data
    json_file = 'data/agentic_poland_data.json'
    data = load_json_data(json_file)
    
    # Create Excel files
    create_master_file(data, output_dir)
    create_charged_hours_file(data, output_dir)
    create_targets_file(data, output_dir)

if __name__ == '__main__':
    main() 