import pandas as pd
import json
import uuid
import os

def load_data(file_path):
    return pd.read_excel(file_path)

mode_map = {
    "comportementale": "Comportementale",
    "désignée": "Designee",
    "designée": "Designee",
    "designee": "Designee",
    "montrée": "Montree",
    "montree": "Montree",
    "suggérée": "Suggeree",
    "suggeree": "Suggeree"
}

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
        
        if 'spans_json' in df.columns and pd.notna(row['spans_json']):
            try:
                spans = json.loads(row['spans_json'])
                for span_info in spans:
                    span_text = span_info.get('span_text', '')
                    if not span_text or span_text.strip() == "":
                        continue
                    
                    start_idx = text.find(span_text)
                    if start_idx != -1:
                        end_idx = start_idx + len(span_text)
                        
                        labels = []
                        cat = span_info.get('categorie')
                        if cat and str(cat).strip() != "":
                            labels.append(str(cat).strip())
                            
                        cat2 = span_info.get('categorie2')
                        if pd.notna(cat2) and cat2 and str(cat2).strip() != "":
                            labels.append(str(cat2).strip())
                            
                        mode = span_info.get('mode')
                        if mode and str(mode).strip() != "":
                            m_clean = str(mode).strip().lower()
                            # Normalise vers les étiquettes sans accents attendues par l'XML Label Studio
                            labels.append(mode_map.get(m_clean, str(mode).strip()))
                            
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
            except Exception as e:
                print(f"Error parsing spans_json for row {idx}: {e}")
                        
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
