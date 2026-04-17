import pandas as pd
import json
import uuid
import os

def load_data(file_path):
    return pd.read_excel(file_path)

def process_file(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
        
    print(f"Processing {file_path}...")
    df = load_data(file_path)
    tasks = []
    
    for idx, row in df.iterrows():
        text = str(row['TEXT'])
        if pd.isna(text) or text.strip() == "" or text == "nan":
            continue
            
        task = {
            "data": {
                "text": text,
                "source": os.path.basename(file_path)
            },
            "predictions": []
        }
        results = []
        
        for i in range(1, 4):
            span_col = f'span{i}_text'
            cat_col = f'span{i}_cat'
            mode_col = f'span{i}_mode'
            
            if span_col in df.columns:
                span_text = row[span_col]
                if pd.notna(span_text) and str(span_text).strip() != "":
                    span_text = str(span_text)
                    start_idx = text.find(span_text)
                    
                    if start_idx != -1:
                        end_idx = start_idx + len(span_text)
                        
                        labels = []
                        if cat_col in df.columns and pd.notna(row[cat_col]) and str(row[cat_col]).strip() != "":
                            labels.append(str(row[cat_col]).strip())
                        if mode_col in df.columns and pd.notna(row[mode_col]) and str(row[mode_col]).strip() != "":
                            labels.append(str(row[mode_col]).strip())
                            
                        if labels:
                            result = {
                                "id": str(uuid.uuid4())[:8],
                                "from_name": "label",
                                "to_name": "text",
                                "type": "labels",
                                "value": {
                                    "start": start_idx,
                                    "end": end_idx,
                                    "text": span_text,
                                    "labels": labels
                                }
                            }
                            results.append(result)
                    else:
                        print(f"Warning: Span '{span_text}' not found in original text for row {idx} in {file_path}.")
                        
        # Même s'il n'y a pas de prédictions, on peut importer la tâche pour l'avoir dans Label Studio.
        if results:
            task["predictions"].append({
                "model_version": "gold_annotations",
                "result": results
            })
        
        tasks.append(task)
        
    output_file = file_path.replace(".xlsx", "_import.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully exported {len(tasks)} tasks to {output_file}")

if __name__ == "__main__":
    files = [
        "religion_annotations_gold_flat.xlsx",
        "racisme_annotations_gold_flat.xlsx",
        "obésité_annotations_gold_flat.xlsx",
        "homophobie_annotations_gold_flat.xlsx"
    ]
    
    for f in files:
        process_file(f)
