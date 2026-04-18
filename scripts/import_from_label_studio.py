#!/usr/bin/env python3
"""
Import d'annotations depuis un export JSON Label Studio → XLSX gold_flat.

Lit un fichier JSON exporté de Label Studio (format standard), réaligne
les annotations span-level avec le fichier XLSX source, puis produit
un nouveau XLSX avec :
  - les colonnes contextuelles conservées (idx, ID, NAME, HATE, etc.)
  - les annotations mises à jour : spans_json, n_spans, span*_text/cat/mode
  - les 19 colonnes binaires recalculées (12 émotions, 4 modes, Emo, Base, Complexe)

Usage :
    python import_from_label_studio.py \\
        --json obésité_gold_new.json \\
        --xlsx obésité_annotations_gold_flat.xlsx

    python import_from_label_studio.py \\
        --json obésité_gold_new.json \\
        --xlsx obésité_annotations_gold_flat.xlsx \\
        --output obésité_annotations_gold_flat_updated.xlsx
"""

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ── Forcer UTF-8 sur Windows (évite les erreurs cp1252) ──
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════

# 12 catégories émotionnelles canoniques
EMOTION_ORDER = [
    "Colère", "Dégoût", "Joie", "Peur", "Surprise", "Tristesse",
    "Admiration", "Culpabilité", "Embarras", "Fierté", "Jalousie", "Autre",
]

# 4 modes d'expression
MODE_ORDER = ["Comportementale", "Désignée", "Montrée", "Suggérée"]

# Émotions de base vs complexes
BASE_EMOTIONS = {"Colère", "Dégoût", "Joie", "Peur", "Surprise", "Tristesse"}
COMPLEX_EMOTIONS = {"Admiration", "Culpabilité", "Embarras", "Fierté", "Jalousie"}

# ── Remapping Label Studio (sans accents) → noms XLSX (avec accents) ──
LS_MODE_REMAP = {
    "Comportementale": "Comportementale",
    "Designee":        "Désignée",
    "Montree":         "Montrée",
    "Suggeree":        "Suggérée",
}

# Toutes les valeurs qui sont des modes (côté Label Studio)
LS_MODE_VALUES = set(LS_MODE_REMAP.keys())

# Toutes les valeurs qui sont des émotions canoniques (côté Label Studio)
LS_EMOTION_VALUES = set(EMOTION_ORDER)

# Mapping labels fins → catégories canoniques (identique à gold_flat.py)
FINE_TO_CANONICAL = {
    # Colère
    "Agacement": "Colère", "Contestation": "Colère", "Désaccord": "Colère",
    "Désapprobation": "Colère", "Énervement": "Colère", "Fureur": "Colère",
    "Rage": "Colère", "Indignation": "Colère", "Insatisfaction": "Colère",
    "Irritation": "Colère", "Mécontentement": "Colère", "Réprobation": "Colère",
    "Révolte": "Colère",
    # Dégoût
    "Lassitude": "Dégoût", "Répulsion": "Dégoût",
    # Joie
    "Amusement": "Joie", "Enthousiasme": "Joie", "Exaltation": "Joie",
    "Plaisir": "Joie",
    # Peur
    "Angoisse": "Peur", "Appréhension": "Peur", "Effroi": "Peur",
    "Horreur": "Peur", "Inquiétude": "Peur", "Méfiance": "Peur",
    "Stress": "Peur",
    # Surprise
    "Étonnement": "Surprise", "Stupeur": "Surprise",
    # Tristesse
    "Blues": "Tristesse", "Chagrin": "Tristesse", "Déception": "Tristesse",
    "Désespoir": "Tristesse", "Peine": "Tristesse", "Souffrance": "Tristesse",
    # Embarras
    "Gêne": "Embarras", "Honte": "Embarras", "Humiliation": "Embarras",
    # Fierté
    "Orgueil": "Fierté",
    # Timidité → Peur ET Embarras (double mapping)
    "Timidité": "Peur",
    # Autre
    "Amour": "Autre", "Courage": "Autre", "Curiosité": "Autre",
    "Désir": "Autre", "Détermination": "Autre", "Envie": "Autre",
    "Espoir": "Autre", "Haine": "Autre", "Impuissance": "Autre",
    "Mépris": "Autre", "Soulagement": "Autre",
}

FINE_DUAL_MAP = {
    "Timidité": ["Peur", "Embarras"],
}


def _resolve_category(label: str) -> List[str]:
    """Résout un label (canonique ou fin) vers la/les catégorie(s) canonique(s)."""
    if label in LS_EMOTION_VALUES:
        return [label]
    if label in FINE_DUAL_MAP:
        return FINE_DUAL_MAP[label]
    canonical = FINE_TO_CANONICAL.get(label)
    if canonical:
        return [canonical]
    return []


# ═══════════════════════════════════════════════════════════════════════════
#  CHARGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def load_label_studio_json(path: str) -> List[Dict[str, Any]]:
    """Charge le JSON exporté de Label Studio."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f"✗ Le JSON n'est pas une liste de tâches.", file=sys.stderr)
        sys.exit(1)
    return data


def load_source_xlsx(path: str) -> pd.DataFrame:
    """Charge le XLSX source."""
    if not os.path.isfile(path):
        print(f"✗ Fichier introuvable : {path}", file=sys.stderr)
        sys.exit(1)
    return pd.read_excel(path)


# ═══════════════════════════════════════════════════════════════════════════
#  PARSING DES ANNOTATIONS LABEL STUDIO
# ═══════════════════════════════════════════════════════════════════════════

def parse_task_annotations(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse une tâche Label Studio et extrait les annotations structurées.

    Retourne un dict avec :
        text        — texte de la tâche
        inner_id    — inner_id Label Studio
        spans       — liste de dicts {span_text, start, end, mode, categorie, categorie2}
        n_spans     — nombre de spans
    """
    text = task.get("data", {}).get("text", "")
    inner_id = task.get("inner_id")

    # Prendre la dernière annotation (la plus récente)
    annotations = task.get("annotations", [])
    if not annotations:
        return {"text": text, "inner_id": inner_id, "spans": [], "n_spans": 0}

    # Prendre la première annotation (il n'y en a qu'une par tâche dans ce setup)
    annotation = annotations[0]
    results = annotation.get("result", [])

    if not results:
        return {"text": text, "inner_id": inner_id, "spans": [], "n_spans": 0}

    # ── Regrouper les results par span (start, end) ──
    # Un même span peut avoir plusieurs result entries avec des labels différents
    span_groups: Dict[Tuple[int, int, str], List[str]] = {}

    for res in results:
        if res.get("type") != "labels":
            continue
        value = res.get("value", {})
        start = value.get("start", 0)
        end = value.get("end", 0)
        span_text = value.get("text", "")
        labels = value.get("labels", [])

        key = (start, end, span_text)
        if key not in span_groups:
            span_groups[key] = []
        span_groups[key].extend(labels)

    # ── Convertir chaque groupe en span structuré ──
    spans = []
    for (start, end, span_text), labels in sorted(span_groups.items()):
        # Séparer modes et émotions
        modes = []
        emotions = []

        for label in labels:
            if label in LS_MODE_VALUES:
                modes.append(LS_MODE_REMAP[label])
            elif label in LS_EMOTION_VALUES:
                emotions.append(label)
            else:
                # Label fin → résoudre en canonique
                resolved = _resolve_category(label)
                if resolved:
                    emotions.extend(resolved)
                else:
                    print(f"  ⚠ Label inconnu ignoré : '{label}' (span: '{span_text}')",
                          file=sys.stderr)

        # Dédupliquer
        modes = list(dict.fromkeys(modes))
        emotions = list(dict.fromkeys(emotions))

        # Construire le(s) span(s) — un par mode×émotions si besoin
        # Format attendu : chaque span a un seul mode et jusqu'à 2 catégories
        mode = modes[0] if modes else None

        if not emotions:
            # Span avec mode seul (ne devrait pas arriver normalement)
            spans.append({
                "span_text": span_text,
                "start": start,
                "end": end,
                "mode": mode,
                "categorie": None,
                "categorie2": None,
            })
        elif len(emotions) == 1:
            spans.append({
                "span_text": span_text,
                "start": start,
                "end": end,
                "mode": mode,
                "categorie": emotions[0],
                "categorie2": None,
            })
        elif len(emotions) == 2:
            spans.append({
                "span_text": span_text,
                "start": start,
                "end": end,
                "mode": mode,
                "categorie": emotions[0],
                "categorie2": emotions[1],
            })
        else:
            # Plus de 2 émotions sur le même span : categorie + categorie2 pour
            # les deux premières, puis un span additionnel pour les suivantes
            spans.append({
                "span_text": span_text,
                "start": start,
                "end": end,
                "mode": mode,
                "categorie": emotions[0],
                "categorie2": emotions[1],
            })
            for extra_emo in emotions[2:]:
                spans.append({
                    "span_text": span_text,
                    "start": start,
                    "end": end,
                    "mode": mode,
                    "categorie": extra_emo,
                    "categorie2": None,
                })

    return {
        "text": text,
        "inner_id": inner_id,
        "spans": spans,
        "n_spans": len(spans),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  MATCHING TÂCHES ↔ LIGNES XLSX
# ═══════════════════════════════════════════════════════════════════════════

def _normalize(s: str) -> str:
    """Normalise un texte pour le matching."""
    return s.strip().lower()


def match_tasks_to_rows(
    tasks: List[Dict[str, Any]],
    df: pd.DataFrame,
) -> Dict[int, Dict[str, Any]]:
    """
    Associe chaque tâche Label Studio à un index de ligne du DataFrame.

    Stratégie :
    1. Match par inner_id (inner_id - 1 == row index)
       avec vérification que le texte correspond
    2. Fallback : match exact sur TEXT
    3. Fallback : match normalisé sur TEXT

    Retourne : {row_idx: parsed_task_dict}
    """
    parsed_tasks = [parse_task_annotations(t) for t in tasks]

    # Index pour les fallbacks
    text_to_row = {}
    norm_to_row = {}
    for i, row in df.iterrows():
        txt = str(row.get("TEXT", ""))
        if txt and txt != "nan":
            text_to_row[txt] = i
            norm_to_row[_normalize(txt)] = i

    mapping = {}
    n_by_inner_id = 0
    n_by_exact = 0
    n_by_norm = 0
    n_unmatched = 0

    for pt in parsed_tasks:
        inner_id = pt.get("inner_id")
        text = pt.get("text", "")
        matched_idx = None

        # 1. Match par inner_id
        if inner_id is not None:
            candidate_idx = inner_id - 1  # inner_id est 1-indexed
            if 0 <= candidate_idx < len(df):
                row_text = str(df.iloc[candidate_idx].get("TEXT", ""))
                if row_text == text:
                    matched_idx = candidate_idx
                    n_by_inner_id += 1

        # 2. Fallback : match exact
        if matched_idx is None and text in text_to_row:
            matched_idx = text_to_row[text]
            n_by_exact += 1

        # 3. Fallback : match normalisé
        if matched_idx is None:
            norm = _normalize(text)
            if norm in norm_to_row:
                matched_idx = norm_to_row[norm]
                n_by_norm += 1

        if matched_idx is not None:
            if matched_idx in mapping:
                print(f"  ⚠ Doublon : ligne {matched_idx} déjà assignée "
                      f"(inner_id={inner_id}, texte='{text[:40]}…')",
                      file=sys.stderr)
            mapping[matched_idx] = pt
        else:
            n_unmatched += 1
            print(f"  ✗ Non matché : inner_id={inner_id}, texte='{text[:60]}…'",
                  file=sys.stderr)

    print(f"\n  Matching : {len(mapping)}/{len(parsed_tasks)} tâches assignées")
    print(f"    par inner_id : {n_by_inner_id}")
    print(f"    par exact     : {n_by_exact}")
    print(f"    par normalisé : {n_by_norm}")
    if n_unmatched:
        print(f"    ✗ non matchés : {n_unmatched}")

    return mapping


# ═══════════════════════════════════════════════════════════════════════════
#  FLATTENING (OR logique) — identique à gold_flat.py
# ═══════════════════════════════════════════════════════════════════════════

def flatten_spans(spans: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Aplatit une liste de spans en vecteurs binaires phrase-level via OR logique.

    Retourne un dict avec les 19 labels :
        12 émotions + 4 modes + Emo + Base + Complexe
    """
    emotions = {e: 0 for e in EMOTION_ORDER}
    modes = {m: 0 for m in MODE_ORDER}

    for span in spans:
        # OR sur les catégories émotionnelles
        for cat_key in ("categorie", "categorie2"):
            cat = span.get(cat_key)
            if not cat:
                continue
            resolved = _resolve_category(cat)
            for r in resolved:
                if r in emotions:
                    emotions[r] = 1

        # OR sur les modes
        mode = span.get("mode")
        if mode and mode in modes:
            modes[mode] = 1

    # Emo : 1 si au moins un span
    emo = 1 if spans else 0

    # Base / Complexe
    base = 1 if any(emotions[e] for e in BASE_EMOTIONS) else 0
    complexe = 1 if any(emotions[e] for e in COMPLEX_EMOTIONS) else 0

    result = {}
    result.update(emotions)
    result.update(modes)
    result["Emo"] = emo
    result["Base"] = base
    result["Complexe"] = complexe

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  RECONSTRUCTION DU DATAFRAME
# ═══════════════════════════════════════════════════════════════════════════

MAX_SPAN_COLS = 4  # span1..span4


def rebuild_dataframe(
    df: pd.DataFrame,
    mapping: Dict[int, Dict[str, Any]],
) -> pd.DataFrame:
    """
    Met à jour le DataFrame avec les nouvelles annotations.

    Pour chaque ligne matchée :
    - Remplace spans_json, n_spans
    - Remplace span{1..4}_text, span{1..4}_cat, span{1..4}_mode
    - Recalcule les 19 colonnes binaires
    """
    df = df.copy()

    n_updated = 0
    for row_idx, parsed in mapping.items():
        spans = parsed["spans"]
        n_spans = parsed["n_spans"]

        # ── spans_json ──
        spans_for_json = []
        for sp in spans:
            spans_for_json.append({
                "span_text": sp["span_text"],
                "mode": sp["mode"],
                "categorie": sp["categorie"],
                "categorie2": sp["categorie2"],
                "justification": None,
            })

        if spans_for_json:
            df.at[row_idx, "spans_json"] = json.dumps(
                spans_for_json, ensure_ascii=False
            )
        else:
            df.at[row_idx, "spans_json"] = None

        df.at[row_idx, "n_spans"] = n_spans if n_spans > 0 else 0

        # ── span{1..4}_text / _cat / _mode ──
        for i in range(MAX_SPAN_COLS):
            col_text = f"span{i+1}_text"
            col_cat = f"span{i+1}_cat"
            col_mode = f"span{i+1}_mode"

            if i < len(spans):
                sp = spans[i]
                if col_text in df.columns:
                    df.at[row_idx, col_text] = sp["span_text"]
                if col_cat in df.columns:
                    cats = [sp["categorie"]]
                    if sp["categorie2"]:
                        cats.append(sp["categorie2"])
                    df.at[row_idx, col_cat] = " + ".join(
                        c for c in cats if c
                    ) if cats[0] else None
                if col_mode in df.columns:
                    df.at[row_idx, col_mode] = sp["mode"]
            else:
                if col_text in df.columns:
                    df.at[row_idx, col_text] = None
                if col_cat in df.columns:
                    df.at[row_idx, col_cat] = None
                if col_mode in df.columns:
                    df.at[row_idx, col_mode] = None

        # ── Recalcul des 19 colonnes binaires ──
        flat = flatten_spans(spans)
        for label, value in flat.items():
            if label in df.columns:
                df.at[row_idx, label] = value

        n_updated += 1

    print(f"\n  {n_updated} lignes mises à jour sur {len(df)} lignes totales.")
    return df


# ═══════════════════════════════════════════════════════════════════════════
#  STATISTIQUES
# ═══════════════════════════════════════════════════════════════════════════

def print_label_distribution(df: pd.DataFrame, title: str):
    """Affiche la distribution des labels binaires."""
    all_labels = [l for l in EMOTION_ORDER + MODE_ORDER + ["Emo", "Base", "Complexe"]
                  if l in df.columns]
    print(f"\n  {title}")
    print(f"  {'Label':<20s} {'#1':>5s} {'#0':>5s} {'%':>7s}")
    print(f"  {'-'*40}")
    for label in all_labels:
        col = df[label]
        n1 = int(col.sum())
        n0 = len(df) - n1
        pct = n1 / len(df) * 100 if len(df) > 0 else 0
        print(f"  {label:<20s} {n1:>5d} {n0:>5d} {pct:>6.1f}%")


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Import d'annotations Label Studio → XLSX gold_flat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--json", required=True,
                   help="Chemin vers le JSON exporté de Label Studio")
    p.add_argument("--xlsx", required=True,
                   help="Chemin vers le XLSX source original (gold_flat)")
    p.add_argument("--output", default=None,
                   help="Chemin de sortie XLSX (défaut : <xlsx>_updated.xlsx)")
    return p.parse_args()


def main():
    args = parse_args()

    # ── Résolution du chemin de sortie ──
    json_path = os.path.abspath(args.json)
    xlsx_path = os.path.abspath(args.xlsx)

    if args.output:
        output_path = os.path.abspath(args.output)
    else:
        base, ext = os.path.splitext(xlsx_path)
        output_path = f"{base}_updated{ext}"

    # ── 1. Chargement ─────────────────────────────────────────────────
    print(f"{'═' * 60}")
    print(f"  IMPORT LABEL STUDIO → XLSX")
    print(f"{'═' * 60}")

    tasks = load_label_studio_json(json_path)
    print(f"\n✓ JSON chargé : {json_path}")
    print(f"  {len(tasks)} tâches")

    df = load_source_xlsx(xlsx_path)
    print(f"\n✓ XLSX chargé : {xlsx_path}")
    print(f"  {len(df)} lignes, {len(df.columns)} colonnes")

    # Vérification rapide
    n_annotated = sum(
        1 for t in tasks
        if t.get("annotations") and t["annotations"][0].get("result")
    )
    n_empty = sum(
        1 for t in tasks
        if t.get("annotations") and not t["annotations"][0].get("result")
    )
    print(f"\n  Tâches avec annotations : {n_annotated}")
    print(f"  Tâches sans annotations : {n_empty}")

    # ── 2. Distribution AVANT ─────────────────────────────────────────
    print_label_distribution(df, "Distribution AVANT (XLSX source) :")

    # ── 3. Matching ───────────────────────────────────────────────────
    print("\n▸ Matching tâches JSON ↔ lignes XLSX…")
    mapping = match_tasks_to_rows(tasks, df)

    # ── 4. Reconstruction ─────────────────────────────────────────────
    print("\n▸ Reconstruction du DataFrame…")
    df_out = rebuild_dataframe(df, mapping)

    # ── 5. Distribution APRÈS ─────────────────────────────────────────
    print_label_distribution(df_out, "Distribution APRÈS (XLSX mis à jour) :")

    # ── 6. Validation ─────────────────────────────────────────────────
    assert len(df_out) == len(df), (
        f"Nombre de lignes modifié : {len(df)} → {len(df_out)}"
    )
    assert list(df_out.columns) == list(df.columns), (
        "Colonnes modifiées !"
    )

    # ── 7. Export ─────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    df_out.to_excel(output_path, index=False, engine="openpyxl")

    print(f"\n{'═' * 60}")
    print(f"  EXPORT TERMINÉ")
    print(f"{'═' * 60}")
    print(f"  Entrée JSON  : {json_path}")
    print(f"  XLSX source  : {xlsx_path}")
    print(f"  XLSX sortie  : {output_path}")
    print(f"  Lignes       : {len(df_out)}")
    print(f"  Colonnes     : {len(df_out.columns)}")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()
