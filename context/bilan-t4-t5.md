# Bilan T4 + T5 : réponse, preuves, incident et DORA

**Branche :** `Adam-(T4,-T5)` sur `MelissaAbider/Secure_horizons`, poussée sur GitHub (non mergée dans `main`).
**Référence :** TASKS.md, sections 2.8 (matrice), 2.9 (API), 2.10 (branchements), fiches T4 et T5.
**État :** T4 et T5 sont terminées et testées hors ligne (dry-run, sans chaîne ni AWS). Il ne reste que l'intégration réelle, qui attend T1, T2 et T3.

---

## 1. Ce que fait ma partie, en une phrase

Quand la surveillance (T3) lève une alerte, **T4** décide quoi faire selon une table de règles fixe, met l'argent à l'abri, prévient l'équipe et scelle une preuve vérifiable de la décision. **T5** transforme ensuite cette décision en incident suivi, propose sa classification DORA, calcule les délais légaux et prépare le rapport qu'un humain soumet.

```
Alerte (T3) → T4 Responder : matrice → 8 actions → preuve (hash + ancrage) → Discord
            → T5 IncidentManager : incident → classification DORA → délais → rapport (MD / PDF / mail)
```

---

## 2. T4 · Réponse et preuves

| Livrable | Fichier | Ce qu'il fait |
|---|---|---|
| Playbook | `backend/config/playbook.yaml` | Table gravité → actions : critical, high, warning, info, plus la règle « exposition < 1 000 $ » |
| Planificateur | `backend/responder.py` (`assess`, `plan_actions`) | Fonctions pures : alertes + snapshot → liste d'actions, positions concernées sans double comptage, case de la matrice |
| Responder | `backend/responder.py` (`Responder`) | Une décision par snapshot (`DEC-<réseau>-<bloc>-<n>`), idempotent, n'envoie jamais d'exception au moteur, appelle T5 |
| Exécuteur | `backend/executor.py` | `DryRunExecutor` (hash `0xdry…`, aucune transaction) et `Web3Executor` (clé guardian pour pause et retraits, clé owner pour la réouverture). Un revert passe l'action en `failed` avec la raison, les actions suivantes continuent |
| Notifications | `backend/notify.py` | Log systématique. Webhook et SNS dans un thread séparé, sans jamais retarder les retraits. **Message Discord formaté** (encadré coloré, 8 actions, `record_hash`, mentions désactivées) |
| Preuves | `backend/evidence.py` | `data/evidence/<id>.json`, `inputs_hash` et `record_hash` (keccak du JSON canonique), ancrage dans `EvidenceRegistry` (simulé en dry-run), `verify` qui rejoue la décision |
| CLI | `backend/cli.py` | `verify` (MATCH, code 0 / MISMATCH, code 1 / id inconnu, code 2), `tamper`, `restore`, `demo` |
| API | `backend/api/response.py` | `GET /api/decisions`, `POST /api/decisions/{id}/approve` (200 / 400 / 404 / 409 / 422), `POST /api/verify/{id}` |
| Make | `mk/t4.mk` | `verify`, `tamper`, `restore`, `decision-demo`, `discord-test`, `test-t4` |

**Résultat sur le scénario** (alerte R1 critique au bloc 45 201 812) :
- la décision `DEC-fuji-45201812-1` contient 8 actions : NOTIFY, PAUSE_DEPOSITS, 4 × EMERGENCY_WITHDRAW, OPEN_INCIDENT, UNPAUSE_DEPOSITS (en attente d'un humain) ;
- les 4 retraits, dans l'ordre : lend-eth 400 000 USDC, lend-eth 150 WETH, lend-avax 300 000 USDC, lend-avax 100 WETH, soit 1 325 000 $ rapatriés ;
- la case de la matrice est `critical|exposure>=1k|exit_possible` ;
- `verify` donne MATCH. `tamper` sur `actions.2.params.asset = DAI` donne MISMATCH, avec les différences `action[2]` et `record_hash`. `restore` redonne MATCH.

---

## 3. T5 · Incident et DORA

| Livrable | Fichier | Ce qu'il fait |
|---|---|---|
| Gestionnaire d'incident | `backend/incidents.py` | Ouvre un incident sur `OPEN_INCIDENT`, rattache les décisions et alertes suivantes, calcule montants (en entiers), statut (`contained` après 10 snapshots calmes) et chronologie. Le recalcul part toujours du store |
| Classification DORA | `backend/dora.py` | Seuils de l'Art. 9 du RTS 2024/1772 (comparaisons strictes), règle « majeur » de l'Art. 8(1), délais du règlement 2025/301 |
| Rapport | `backend/dora.py` | Brouillon markdown en 8 sections, sans `None`, `nan` ni `TODO` |
| IA optionnelle | `backend/llm.py` | Bedrock dans un thread séparé, au plus 1 appel par seconde, avec cache. Repli sur un texte fixe en cas d'erreur, pour que rien ne reste bloqué |
| Profil et tiers | `backend/config/dora_profile.yaml`, `dependencies.yaml` | Entité synthétique, registre de 9 tiers avec un statut ok / degraded / down / unknown |
| **PDF** | `backend/dora_pdf.py` | Rapport DORA en PDF (3 pages : badges, 8 sections, tableau des critères, signature, annexe chronologie) |
| **Mail** | `backend/mailer.py` | Envoie le PDF par mail (Gmail via SMTP). Adresses autorisées, 3 envois par minute au plus, mot de passe jamais affiché. C'est un brouillon pour relecture, **pas** la soumission au régulateur |
| API | `backend/api/incidents.py` | `/api/incidents`, `/api/incidents/{id}`, `/report.md`, `POST /submit` (200 puis 409), `/api/dependencies` |
| Make | `mk/t5.mk` | `test-t5`, `dora-demo`, `dora-report`, `dora-pdf`, `dora-pdf-demo`, `dora-email` |

**Résultat sur le scénario** :
- l'incident `INC-20261011-001` passe à `contained` à 08:01:04 UTC (bloc 45 201 832) ;
- montants : 1 325 000 $ sauvés, 0 $ à risque ;
- classification : **majeur** (Art. 8(1)(b), seuils 9(1) et 9(4)) ;
- délais : notification initiale le 11/10 à 12:00:26 UTC, puis +72 h, puis +30 jours ;
- sur la série sans réaction : statut `open`, 375 000 $ à risque, seuils 9(1), 9(4) et 9(6) (345 000 €) ;
- registre des tiers : rsETH `down`, lend-eth `degraded`, lend-avax `ok`.

---

## 4. Ajouts pour pouvoir tout tester seul

**Shim T0 (provisoire)**
Le squelette T0 n'est pas encore sur `main`. J'ai donc ajouté le minimum pour faire tourner T4 et T5 ensemble : `store.py`, `chain.py`, un `engine.py` sans détection, `main.py` avec le câblage engine → responder → incidents, un `Makefile` racine et `mk/t0.mk`. Chaque fichier porte l'en-tête « T0 SHIM ». Ils seront remplacés par le vrai T0 (CR-004).

**Démo guidée** (`make t4t5-ui`, puis `http://localhost:8000/demo`)
- 8 étapes expliquées pour un jury non spécialiste : contexte, journée normale, attaque, réponse automatique, vidage du marché, preuve, validation humaine, incident et DORA, tiers et récap.
- Un tableau compare notre trésorerie (1 325 000 $ à l'abri) à une trésorerie passive (375 000 $ bloqués).
- Un panneau coche **chaque exigence de mes fiches T4 et T5** au moment où l'API la démontre.
- Envoi vers Discord, rapport PDF et mail sont accessibles depuis la page.
- Tout est simulé (dry-run, données synthétiques).

**Sécurité**
- Les secrets (webhook Discord, SMTP) sont uniquement dans `.env`, qui est ignoré par git.
- `backend/tests/conftest.py` coupe Discord, SNS, S3 et Bedrock pendant les tests.

---

## 5. Tests

| Suite | Résultat |
|---|---|
| `make test-t0` (shim) | 21 passés, 2 skippés |
| `make test-t4` | 26 passés, 1 skippé (T4-25 attend anvil) |
| `make test-t5` | 48 passés |
| `make t4t5-e2e` | T4 + T5 de bout en bout via le câblage : 4 passés |

Vérifié en réel : le message Discord est bien reçu (HTTP 204), et le PDF se génère et se télécharge depuis la démo.
Pas encore vérifié en réel : l'envoi du mail, qui attend le mot de passe d'application Gmail dans `.env`.

---

## 6. Ce qui reste, et de qui ça dépend

| Point | Dépend de |
|---|---|
| T4-25 : vrais retraits, pause et ancrage sur anvil, puis `make verify` qui donne MATCH | T1 (contrats), T2 (`make seed`) |
| E2E-1 : `make attack SEED=42` avec le vrai moteur, et un seul incident `contained` | T1, T2, T3 |
| Démo sur Fuji : décision ancrée et lien snowtrace | T1 (déploiement Fuji), T8 |
| Remplacer le shim T0 par le vrai T0, puis rebaser | T0 |
| Valider les demandes CR-001 à CR-005 (models, settings, `.gitignore`, shim, `fpdf2==2.8.9` et variables SMTP) | T0 |
| Secrets SNS, S3, Bedrock et SMTP sur AWS (SSM) | T8 |

**Points d'attention**
- Les routes `approve` et `submit` n'ont pas d'authentification : c'est acceptable en local, mais pas pour une URL publique.
- Le dossier `demo/t4t5/` et `mk/t4t5_demo.mk` sont hors de l'arborescence officielle (1.5). Ils servent à présenter, pas au produit : le vrai dashboard est celui de T6.
- Le webhook Discord est à régénérer avant tout partage d'écran.
