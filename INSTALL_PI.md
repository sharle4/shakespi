# Guide d'Installation sur Raspberry Pi

Ce guide vous explique étape par étape comment installer Shakespi sur un Raspberry Pi neuf.

## Matériel Requis
- Un Raspberry Pi 4B (2 Go de RAM ou plus) avec Raspberry Pi OS Lite (64 bits) installé sur la carte SD.
- Une connexion Internet configurée (Wi-Fi ou Ethernet).
- Une souris USB à 5 boutons (branchée).
- Une carte son USB ou un micro/enceinte reconnus par le système.

## Étape 1 : Transférer les fichiers

Copiez tout le dossier `shakespi` sur votre Raspberry Pi, dans le répertoire `/home/shakespi/shakespi`.
(Vous pouvez utiliser `scp` depuis votre PC : `scp -r shakespi shakespi@adresse_ip:/home/shakespi/`)

## Étape 2 : Exécuter le script d'installation automatique

Connectez-vous au Raspberry Pi via SSH (ou avec un clavier temporaire branché dessus), puis lancez :

```bash
cd /home/shakespi/shakespi
chmod +x scripts/setup_pi.sh
./scripts/setup_pi.sh
```

Ce script va installer Python, créer l'environnement virtuel, installer les dépendances et télécharger les voix Piper.

## Étape 3 : Configurer l'Audio

L'application utilise `sounddevice` qui s'appuie sur ALSA.
Testez que votre micro fonctionne :
```bash
arecord -d 5 test.wav
aplay test.wav
```
Si vous n'entendez rien, vérifiez vos périphériques avec `aplay -l` et `arecord -l`, et ajustez les niveaux avec `alsamixer`.
Si vous avez besoin de forcer un périphérique spécifique, vous pourrez indiquer son index dans le fichier de configuration.

## Étape 4 : Configurer les clés API

Ouvrez le fichier de configuration :
```bash
nano config/config.yaml
```
Remplacez `YOUR_GEMINI_API_KEY_HERE` par votre clé API Google Gemini (AI Studio).
Remplacez `YOUR_GROQ_API_KEY_HERE` par votre clé API Groq (pour Whisper).
Sauvegardez (`Ctrl+O`, `Entrée`, `Ctrl+X`).

## Étape 5 : Tester le mapping de la souris

Afin d'être sûr que les boutons de votre souris correspondent aux actions attendues :
Lancez l'application manuellement une première fois :
```bash
source venv/bin/activate
python main.py
```
Testez les clics. Si un clic ne fait pas ce qu'il devrait (ex: le bouton latéral ne fait rien), vous pouvez utiliser l'utilitaire `evtest` pour trouver le code exact du bouton de votre souris et le mettre à jour dans le code (`core/input_handler.py`).

## Étape 6 : Activer le démarrage automatique (Service Systemd)

Une fois que tout fonctionne, configurez Shakespi pour démarrer tout seul à l'allumage :

```bash
sudo cp systemd/shakespi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shakespi.service
sudo systemctl start shakespi.service
```

Vous pouvez voir les logs en temps réel avec :
```bash
tail -f data/shakespi.log
# ou
journalctl -u shakespi.service -f
```

C'est prêt ! Débranchez l'écran et le clavier (si vous en utilisiez), Shakespi est maintenant un boîtier autonome.
