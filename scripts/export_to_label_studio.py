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

import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Convertit un XLSX gold_flat en JSON importable dans Label Studio.")
    parser.add_argument("--input", required=True, help="Chemin vers le fichier XLSX source")
    parser.add_argument("--output", default=None, help="Chemin du fichier JSON de sortie (défaut: <input>_import.json)")
    return parser.parse_args()

def main():
    args = parse_args()
    input_file = os.path.abspath(args.input)
    
    if args.output:
        output_file = os.path.abspath(args.output)
    else:
        output_file = input_file.replace(".xlsx", "_import.json")
        
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return
        
    print(f"Processing {input_file}...")
    df = load_data(input_file)
    tasks = []
    
    for idx, row in df.iterrows():
        text = str(row.get('TEXT', ''))
        if pd.isna(text) or text.strip() == "" or text == "nan":
            continue
            
        task = {
            "data": {
                "text": text,
                "source": os.path.basename(input_file)
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
                        print(f"Warning: Span '{span_text}' not found in original text for row {idx} in {input_file}.")
            except Exception as e:
                print(f"Error parsing spans_json for row {idx}: {e}")
                        
        if results:
            task["predictions"].append({
                "model_version": "gold_annotations",
                "result": results
            })
        
        tasks.append(task)
        
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully exported {len(tasks)} tasks to {output_file}")

if __name__ == "__main__":
    main()
