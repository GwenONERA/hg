# Segmentation des Émotions et Modes d'Expression - Export Label Studio

Ce dépôt contient un script et une configuration permettant la conversion de jeux de données d'annotations ("Gold Standard") depuis un format Excel structuré vers le format JSON compatible avec la plateforme d'annotation Label Studio.

L'objectif est d'importer des annotations expertes préexistantes (concernant des thèmes tels que le racisme, l'obésité, la religion, et l'homophobie) afin de les visualiser et de les éditer facilement sous Label Studio.

## Structure du dépôt

- `export_to_label_studio.py` : Le script Python principal qui traite fichiers `.xlsx` et extrait les colonnes pré-annotées (`spans_json`, comportant le texte segmenté, et ses étiquettes/modes) pour les convertir en listes de tâches importables (`*_import.json`).
- `label_studio_config.xml` : La configuration de l'interface graphique de segmentation à coller dans les paramètres ("Setup") de votre projet Label Studio.
- `*_annotations_gold_flat.xlsx` : Les jeux de données sources bruts sous format Excel.
- `*_annotations_gold_flat_import.json` : Les jeux de données finaux traités par le script et prêts à être importés dans Label Studio.

## Configuration des classes sous Label Studio

Le fichier XML fournit une taxonomie de **12 émotions** (Admiration, Culpabilité, Embarras, Fierté, Jalousie, Autre, Colère, Dégoût, Joie, Peur, Surprise, Tristesse) et de **4 modes d'expression** (Comportementale, Désignée, Montrée, Suggérée).

Veillez à configurer le projet en copiant le contenu de `label_studio_config.xml` dans les balises de configuration du projet.

## Mode d'emploi

### 1. Génération des fichiers JSON 

Assurez-vous d'avoir Python installé ainsi que la librairie `pandas`.
Lancez simplement le script depuis la racine du projet :

```bash
python export_to_label_studio.py
```

Le script lira chaque fichier `.xlsx` identifié dans son code source et produira les fichiers `<nom_fichier>_import.json` correspondants.

### 2. Importation dans Label Studio

1. Créez un nouveau projet dans Label Studio.
2. Allez dans *Settings > Labeling Interface*, basculez en mode *Code* et collez le contenu du fichier `label_studio_config.xml`. Sauvegardez.
3. Importez les données : Cliquez sur le bouton *Import*, puis uploadez un ou plusieurs des fichiers JSON nouvellement générés (ex: `homophobie_annotations_gold_flat_import.json`).
4. Vos textes apparaîtront et les annotations existantes seront affichées sous forme de pré-annotations prêtes à être confirmées, éditées ou corrigées !
