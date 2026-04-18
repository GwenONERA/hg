# Pipeline d'Annotation : SitEmo → Gold Flat → Label Studio

Ce dépôt contient un pipeline pour traiter les annotations d'émotions et de modes d'expression (SitEmo), de les aplatir, de les exporter vers Label Studio pour révision humaine, puis de les réintégrer.

L'objectif est de gérer rigoureusement des jeux de données annotés (thèmes : racisme, obésité, religion, homophobie) pour évaluer et entraîner le modèle EMOTYC.

## Structure du Dépôt

L'arborescence est organisée pour séparer les données selon leur état d'avancement, et les scripts du reste :

```text
.
├── config/
│   └── label_studio_config.xml           # Configuration UI (Setup) pour Label Studio
├── data/
│   ├── 01_raw/                           # Données sources initiales (ex: JSONL) [PAS UTILISÉ]
│   ├── 02_gold_flat/                     # Fichiers XLSX avec les gold labels aplatis (span-level → phrase-level)
│   ├── 03_label_studio/
│   │   ├── imports/                      # Fichiers JSON générés prêts à être importés dans Label Studio
│   │   └── exports/                      # Fichiers JSON exportés depuis Label Studio après révision
│   └── 04_final/                         # Fichiers XLSX finaux, reconstruits et mis à jour après la révision
├── scripts/
│   ├── export_to_label_studio.py         # (Étape 1) Convertit les XLSX gold_flat en JSON importable
│   └── import_from_label_studio.py       # (Étape 2) Reconstruit les XLSX à partir des JSON exportés de Label Studio
└── README.md
```

## Taxonomie (Schéma d'Annotation)

Le pipeline gère **19 labels** (compatibles avec le modèle EMOTYC) :
- **12 Émotions** : Admiration, Culpabilité, Embarras, Fierté, Jalousie, Autre, Colère, Dégoût, Joie, Peur, Surprise, Tristesse.
- **4 Modes d'expression** : Comportementale, Désignée, Montrée, Suggérée.
- **3 Méta-catégories** : Emo (caractère émotionnel), Base (émotion de base présente), Complexe (émotion complexe présente).

## Mode d'Emploi

### Étape 1 : Export vers Label Studio
Pour chaque fichier XLSX (déjà au format `gold_flat`) que vous souhaitez réviser manuellement, générez un JSON d'import pour Label Studio.

```bash
python scripts/export_to_label_studio.py \
    --input data/02_gold_flat/obésité_annotations_gold_flat.xlsx \
    --output data/03_label_studio/imports/obésité_annotations_gold_flat_import.json
```
*(Si `--output` est omis, le fichier sera créé dans le même dossier que l'entrée avec le suffixe `_import.json`)*.

### Étape 1bis : Révision dans Label Studio
1. Créez un nouveau projet dans Label Studio.
2. Allez dans **Settings > Labeling Interface**, basculez en mode **Code**, collez le contenu du fichier `config/label_studio_config.xml`, puis sauvegardez.
3. Cliquez sur **Import** et uploadez votre fichier généré (ex: `data/03_label_studio/imports/obésité_annotations_gold_flat_import.json`).
4. Révisez les annotations (ajustement des spans, ajout/suppression de labels).
5. Une fois terminé, cliquez sur **Export** au format **JSON** et sauvegardez le fichier dans `data/03_label_studio/exports/` (ex: `obésité_gold_new.json`).

### Étape 2 : Réintégration (Import depuis Label Studio)
Reconstruisez le fichier XLSX d'origine en y intégrant vos révisions Label Studio. Le script mettra à jour la colonne `spans_json`, les colonnes `span*_text/cat/mode`, et recalculera l'ensemble des 19 colonnes binaires. Toutes les autres colonnes contextuelles (linguistiques, metadata) sont conservées intactes.

```bash
python scripts/import_from_label_studio.py \
    --json data/03_label_studio/exports/obésité_gold_new.json \
    --xlsx data/02_gold_flat/obésité_annotations_gold_flat.xlsx \
    --output data/04_final/obésité_annotations_gold_flat_updated.xlsx
```
*(Si `--output` est omis, le fichier sera créé dans le même dossier que le XLSX d'entrée avec le suffixe `_updated.xlsx`)*.

Le fichier final généré dans `data/04_final/` est prêt à être utilisé pour évaluer ou entraîner les modèles.
