import matplotlib.pyplot as plt
import seaborn as sns
import os
import json

def get_accuracy_from_trace(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        scores = [
            d['human_preference_agreement'][0] 
            for d in data 
            if 'human_preference_agreement' in d 
            and isinstance(d['human_preference_agreement'], list) 
            and len(d['human_preference_agreement']) > 0
        ]
        return (sum(scores) / len(scores)) * 100.0 if scores else 0.0
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0.0

def create_calibration_chart():
    # Base directory
    base_dir = '/mnt/nvme0n1p4/Projects/Programming_Projects/Skripsi/Eval_Data/Articles/Calibration'
    
    # Read dynamic data
    hhem_acc = get_accuracy_from_trace(os.path.join(base_dir, 'Trace_Calibration_HHEM2.1.json'))
    bespoke_acc = get_accuracy_from_trace(os.path.join(base_dir, 'Trace_Calibration_BespokeMiniCheck7B.json'))

    # Data from calibration and RAGAS article (Table 1: Faithfulness Agreement)
    models = ['RAGAS (GPT-3.5) Baseline\n(Article)', 'Vectara HHEM-2.1-Open\n(Local Eval)', 'Bespoke-MiniCheck-7B\n(Local Eval)']
    accuracy = [95.0, hhem_acc, bespoke_acc]
    
    # Setup style
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(10, 6))
    
    # Plotting
    colors = ['#4A90E2', '#F39C12', '#2ECC71']
    bars = plt.bar(models, accuracy, color=colors, width=0.6)
    
    # Add labels
    plt.title('Faithfulness Agreement Rate on WikiEval Dataset\nComparison: Official Ragas Baseline vs Local Evaluators', pad=20, fontsize=14, fontweight='bold')
    plt.ylabel('Human Preference Agreement (%)', fontsize=12)
    plt.ylim(0, 110)
    
    # Value text on bars
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 1.5, f'{yval:.1f}%', ha='center', va='bottom', fontsize=12, fontweight='bold')
        
    plt.tight_layout()
    
    # Save chart
    output_dir = '/mnt/nvme0n1p4/Projects/Programming_Projects/Skripsi/Eval_Data/Articles/Calibration'
    output_path = os.path.join(output_dir, 'Calibration_Comparison_Chart.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Chart saved to {output_path}")

if __name__ == "__main__":
    create_calibration_chart()
