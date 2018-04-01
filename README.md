# Troll Doc - Générateur de documentation html pour des modèles Troll


## 1. Prérequis

* Avoir `python 3.5` (ou >) sur son ordinateur : 
voir la [Doc officielle d'installation](https://wiki.python.org/moin/BeginnersGuide/Download)
et le [Hitchiker's guide to Python](http://docs.python-guide.org/en/latest/starting/installation/).

* Avoir Python disponible dans l'invite de commandes Windows (voir le hitchikers' guide - 
partie sur le Path).

* Avoir `pip` (le gestionnaire de paquets python) : le plus facile 
est d'utiliser le script `get-pip.py` [disponible ici](https://pip.pypa.io/en/stable/installing/).

* Recommandé : avoir un bon éditeur python (moi c'est 
[PyCharm - Community (ie gratuit)](https://www.jetbrains.com/pycharm/) mais [chacun ses goûts](https://wiki.python.org/moin/IntegratedDevelopmentEnvironments).) 

## 2. Installation 

1. Cloner le dépôt git ou le copier.

1. Ouvrir un terminal (Linux) ou une invite de commandes (Windows), naviguer jusqu'au 
répertoire d'installation du projet. 

1. Installer les dépendances du projet, qui se trouvent dans le fichier `requirements.txt` :  

```
pip install -r requirements.txt
``` 

## 3. Utilisation

1. Ouvrir un terminal (Linux) ou une invite de commandes (Windows), naviguer jusqu'au 
répertoire d'installation du projet. 

1. Lancer le programme `modeldoc.py` :  

```
python modeldoc.py -i <troll_input_file.inp> -p <param_file.csv> -l <legend_file.csv> -o <documentation_file.html> [-v]

        -i : troll input file (mandatory)
        -p : csv input file (mandatory)
        -l : csv legend file (mandatory)
        -o : html output file (mandatory)
        -v : verbose, prints debug information
```

Par exemple, la commande peut s'écrire:
python modeldoc.py -i frbdf_v0.inp -p paramexport.csv -l lexique.csv -o frbdf_v0_documentation.html

1. Le fichier indiqué dans l'option -o est généré. Il suffit ensuite de l'ouvrir dans 
un navigateur. 


## 4. Le code : principes de base

Le programme `modeldoc.py` fait essentiellement 5 choses :

* Il parse le fichier d'entrée Troll et en extrait les équations du modèle. 
Pour chaque équation, il lit le nom de l'équation, qui doit être le nom de la 
variable endogène que l'on détermine dans l'équation, et aussi l'équation complète.
Pour cela il utilise le module python `pyparsing`.
Il convertit aussi tout en minuscules.  

* Il remplace les paramètres par leur valeur

* Il ajoute les légendes de chaque équation (nom en français de la variable expliquée)

* Il cherche les variables endogènes dans chaque équation et, pour chacune, ajoute 
dans le corps de l'équation un lien html qui pointe vers l'équation déterminant cette variable.
Il cherche aussi les liens inverses: dans quelles autres équations la variable principale apparaît-elle ? 
  
* Il génère le fichier html, à partir d'un template. Pour cela il utilise le module 'jinja2'.



