# MVP « Surveillance de trésorerie DeFi » : plan des tâches

> Document de référence de l'équipe. Chaque tâche (T0 à T9) se lance **de son côté, avec son propre Claude Code**.
> 1. Lis d'abord **« Les tâches en clair »** juste en dessous : une fiche courte et concrète par tâche, pour choisir la tienne.
> 2. Donne ensuite à ton Claude Code la section 1 (contexte), la section 2 (contrat d'interface) et **ta fiche détaillée** de la section 3.
> 3. La section 2 est **figée** : personne ne la modifie seul (voir 2.12).

---

## Les tâches en clair

Dix tâches, chacune lancée par une personne avec son propre Claude Code. Cette partie dit **concrètement** ce que chaque tâche construit, ce qui doit marcher à la fin et comment on sait que c'est fini. Le reste du document (contrat d'interface, fiches détaillées) est surtout destiné aux Claude Code.

**Ordre :** T0 d'abord (tout le monde part de ce commit), puis tout le reste en parallèle sur des maquettes. T2 attend juste que les contrats de T1 se déploient en local.

| Tâche | Ce qu'elle livre | A besoin de (maquette en attendant) | Débloque |
|---|---|---|---|
| **T0** Fondations | squelette du repo, modèles, helpers, store, stubs, API sur fixtures, fixtures, Makefile, garde-fous | rien | tout le monde |
| **T1** Contrats on-chain | jetons, bridge rsETH avec sa faille, oracle, 2 protocoles de prêt, coffre avec guardian, registre de preuves ; déploiement local et Fuji ; ABIs ; financement des rôles en AVAX de test | T0 | T2, T3, T4, T7, T8, T9 |
| **T2** Scénario | seed, attaque (3 variantes, graine aléatoire), trafic normal, reset, vérité terrain des runs, routes de démo | T1 (chaîne locale dès que `make deploy` marche) | T3, T4, T5, T6, T7 |
| **T3** Surveillance | collecteur, règles R1 à R5, moteur, routes d'état | T1/T2 (séries `fixtures/snapshots_*.jsonl`) | T4, T5, T6, T7 |
| **T4** Réponse et preuves | matrice, exécution on-chain, notifications, preuves ancrées, `verify`, approbations | T3 (alertes construites à la main), T1 (dry-run) | T5, T6, T7, T9 |
| **T5** Incident et DORA | incidents, chronologie, classification DORA, rapport, registre des dépendances | T4 (décisions construites à la main) | T6, T9 |
| **T6** Dashboard | toutes les vues, démo pilotable | T3, T4, T5, T2, T7 (fixtures, puis squelette T0) | T9 (captures, vidéo) |
| **T7** Évaluation | métriques simples sur runs synthétiques, rapport | T2, T3, T4 (chaîne locale) | T6, T9 |
| **T8** AWS et CI | images, compose, EC2, SNS, S3, Bedrock, CI, plan de repli | T0 (puis tout le reste pour la mise en ligne) | E2E-3, T9 |
| **T9** Livrables | README, playbook, conformité, defense sheet, deck, vidéo, pitch | tout (chiffres provisoires marqués en attendant) | la soumission |

---

### T0 · Fondations : le squelette du repo que tout le monde clone

**En une phrase.** Le premier commit mergé sur `main` : un repo où chaque route de l'API répond déjà avec des données d'exemple (les « fixtures »), pour que chaque tâche démarre seule sans attendre personne.

**Profil conseillé.** Python (FastAPI, Pydantic) avec un peu de TypeScript et de Makefile. Pas besoin de connaître la blockchain : les helpers suivent la spec de la section 2.

**Concrètement, tu construis :**
- le **contrat de données en code** : `backend/models.py` (modèles Pydantic de 2.6) et son miroir exact `frontend/src/types.ts` ;
- les **briques communes** : `settings.py` (variables de `.env`, clés de test dérivées de la mnémonique publique d'anvil, la chaîne locale), `chain.py` (lire et envoyer des transactions), `store.py` (mémoire + fichiers JSONL) ;
- les **stubs** (coquilles vides qui « ne font rien ») d'`Engine`, `Responder`, `Executor`, `IncidentManager`, que T3, T4 et T5 remplaceront ;
- l'**API** `backend/main.py` avec 5 routeurs qui servent les fixtures sur toutes les routes de 2.9 ;
- les **fixtures** qui racontent l'attaque, régénérables par `python -m fixtures._generate` ;
- l'**outillage** : `Makefile`, `.env.example`, `.gitignore`, gitleaks (détecteur de secrets) en pre-commit, `CLAUDE.md`, `docs/contract-requests.md`.

**À la fin, on doit pouvoir :**
1. lancer `make backend` puis `curl -s localhost:8000/api/state` et recevoir la fixture `state.json` ; `localhost:8000/docs` liste toutes les routes de 2.9 ;
2. lancer `make test-t0` et tout voir vert ;
3. lancer `make help` et voir au moins `setup backend demo test test-t0` ;
4. lire dans les fixtures l'histoire de l'attaque : alerte `R1_BRIDGE_INVARIANT` critique au bloc 45 201 812, exposition 1 325 000 $, décision `DEC-fuji-45201812-1`, 250 WETH + 700 000 USDC rapatriés, `at_risk_usd = 0`, incident `INC-20261011-001`, `verify` = MATCH.

**Specs clés.**
- Décision `DEC-fuji-45201812-1` : exactement 8 actions dans cet ordre, `NOTIFY`, `PAUSE_DEPOSITS`, 4 × `EMERGENCY_WITHDRAW` (lend-eth USDC, lend-eth WETH, lend-avax USDC, lend-avax WETH), `OPEN_INCIDENT`, `UNPAUSE_DEPOSITS` (en attente d'approbation humaine).
- `snapshots_attack.jsonl` et `snapshots_normal.jsonl` : 41 lignes chacune, chaque ligne valide en `Snapshot`.
- Store thread-safe, au plus 2 000 snapshots en mémoire ; `reset()` vide tout et incrémente `generation`.
- `send()` : verrou par expéditeur, gas estimé × 1,3, timeout 120 s, compatible web3.py 6 et 7.
- `get_executor()` renvoie toujours la même instance ; dry-run (simulation sans transaction réelle) si `DRY_RUN_ACTIONS=true`.
- Un seul worker uvicorn ; moteur lancé seulement si `ENGINE_ENABLED=true`. Aucune cible make ne fixe `NETWORK`.
- Aucune logique métier dans les stubs ; aucune clé dans un fichier versionné.

**Livrables.** `backend/models.py`, `settings.py`, `chain.py`, `store.py`, `fixtures.py`, `main.py`, stubs et `backend/config/*.yaml`, `fixtures/*`, `frontend/src/types.ts`, `Makefile`, `mk/t0.mk`, `CLAUDE.md`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `requirements.txt`, tests `backend/tests/test_t0_*.py`. Un seul commit `T0: repo foundations`.

**Tests d'acceptation (ceux qui comptent).**
- T0-01 / T0-02 : chaque fixture se valide avec son modèle et raconte l'histoire (`incident.saved_usd == 1325000.0`, `state.positions == []`, `verify.stored_hash` = `record_hash` de la décision R1).
- T0-03 : recalculer keccak256 (une empreinte cryptographique) du JSON canonique de la décision R1 redonne `record_hash`.
- T0-04 : avec `USE_FIXTURES=true`, toutes les routes répondent 200 ; `GET /api/incidents/UNKNOWN` → 404 ; `approve` renvoie `approved`.
- T0-05 : en `local` sans clé, `deployer` = `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266`, 3 bots ; en `fuji` sans clé, `private_key("guardian")` lève `RuntimeError`.
- T0-07 : `main.py` importe et le câblage `engine` → `responder` → `incidents` est en place.
- T0-10 / T0-11 : gitleaks ne trouve aucun secret ; `types.ts` compile en `--strict`.

**En attendant les autres.** Rien à attendre : T0 ne dépend de personne, sa seule entrée est la section 2 de ce document. Ensuite, T0 valide les demandes de changement du contrat (2.12) et coordonne l'intégration.

**Détails pour Claude Code.** Fiche détaillée T0, section 3 de ce document.

---

### T1 · Contrats : le mini-monde on-chain du scénario

**En une phrase.** Écrire, tester et déployer (chaîne locale anvil puis testnet Avalanche Fuji) les 7 contrats Solidity (programmes stockés sur la blockchain) qui reproduisent le scénario Kelp/Aave : jetons, bridge rsETH, oracle de prix, deux protocoles de prêt, le coffre et le registre de preuves.

**Profil conseillé.** Solidity + Foundry (`forge`, `anvil`), un peu de Python et de bash pour les scripts.

**Concrètement, tu construis :**
- les **jetons** `MockERC20` (USDC 6 décimales, WETH 18) et `RsETH`, plus `MockBridge` qui simule la route cross-chain rsETH, dont `forgedRelease` libère du rsETH **sans verrouillage/burn source canonique et sans contrôle d'accès** (c'est la faille), et `MockOracle` (prix en dollars × 1e8) ;
- `MiniLend`, un protocole de prêt simplifié (dépôt, garantie, emprunt, retrait, gel, pause, modèle de taux), déployé deux fois : `lend-eth` et `lend-avax` ;
- `TreasuryVault`, le coffre : le guardian (notre robot de réponse) peut mettre en pause les dépôts et faire un `emergencyWithdraw` qui renvoie toujours les fonds au coffre ; `EvidenceRegistry` stocke les empreintes (`anchor`) ;
- `script/Deploy.s.sol` + scripts annexes : écrit `deployments/<network>.json`, exporte les ABIs (la description des fonctions que le backend utilise pour appeler les contrats), finance les rôles Fuji.

**À la fin, on doit pouvoir :**
1. `make chain` puis `make deploy` sur anvil neuf → `deployments/local.json` valide, avec les 9 adresses identiques à celles des fixtures (USDC `0x5FbD…0aa3`, …, EvidenceRegistry `0x2279…eBe6`) ;
2. lire sur chaque `MiniLend` : prix USDC `1e8`, WETH et rsETH `2500e8` ; `getAssets()` = `[USDC, WETH, rsETH]` ; LTV (part de la garantie empruntable) 8000 / 8000 / 7500 ; aucun jeton minté par T1 ;
3. rejouer l'attaque : `forgedRelease` de 5000 rsETH produit `conservationGap() == 5000e18`, `destinationNonce == sourceNonce + 1` et un ratio d'affichage de `1935` bps ; un guardian qui sort avant le vidage récupère `150e18` WETH et `400_000e6` USDC (100 %), un déposant passif récupère `0` après ;
4. `make test-t1` vert ; sur Fuji, `deployments/fuji.json` + `fuji.md` commités, les 8 rôles ont ≥ 0,5 AVAX, et `make deploy` est refusé sans `FORCE=1`.

**Specs clés.**
- Signatures, events et **messages de revert exacts** de la section 2.2 (ex. `"MiniLend: frozen"`, `"Vault: only guardian or owner"`) ; ordre des champs de `ReserveData` à la lettre.
- `liquidity = totalSupplied - totalBorrowed` (comptable) ; la garantie est un solde séparé, jamais empruntable ; contrôle de liquidité **avant** contrôle de santé.
- Retrait autorisé si réserve `frozen`, tout bloqué si `paused` ; `withdraw(max)` = `min(position, liquidité)`, `0` sans revert si rien à retirer.
- Taux (u en bps → supply/borrow) : 6000 → 165/325 ; 5500 → 143/306 ; 10000 → 6715/7900.
- Ordre de déploiement imposé (nonces 0 à 8), prix fixés **après** les 9 déploiements ; fichier écrit en `.pending.json`, promu après vérification du code on-chain ; aucune clé dans le repo ni les logs.

**Livrables.** `contracts/**` (`src/` 7 contrats, `script/`, `test/`), `abi/<Contrat>.json` ×7 commités, `deployments/local.json`, `fuji.json`, `fuji.md`, `history/`, `mk/t1.mk` (`chain`, `deploy`, `abi`, `fund-roles`, `test-t1`, `t1-*`), `backend/tests/test_t1_deployment.py`.

**Tests d'acceptation (ceux qui comptent).**
- T1-06 : dépôt 1200 + émission forgée 5000 → supply `6200e18`, ratio `1935`.
- T1-26 : le seed de 2.2 passe **sans toucher aux prix** ; `lend-eth` WETH à 6000 bps (165/325), `lend-avax` à 5500 (143/306) ; marge restante 195 WETH exactement.
- T1-27 : vidage sans réaction → liquidité 0, `6715`/`7900`, tranche suivante `"MiniLend: insufficient liquidity"`, `emergencyWithdraw` retourne `0`.
- T1-28 : guardian sort avant le vidage → `150e18` et `400_000e6` récupérés, bot passif → `0`.
- T1-37 : les 9 adresses de déploiement = celles des fixtures.
- T1-38 à T1-41 : `local.json` au bon format, code présent aux adresses, 7 ABIs, config on-chain et rôles corrects.

**En attendant les autres.** T1 n'attend personne : tout se fait sur **anvil local** avec les comptes publics (mnémonique `test test … junk`), sans clé à écrire ; avant le squelette T0, lancer `NETWORK=local make -f mk/t1.mk <cible>`. Livrer vite les 7 ABIs et un `make deploy` local pour débloquer T2, T3, T4 ; Fuji ensuite, dès que la clé `DEPLOYER_PK` est financée.

**Détails pour Claude Code.** Fiche détaillée T1, section 3 de ce document.

---

### T2 · Scénario : préparer la chaîne, jouer l'attaque, remettre à zéro

**En une phrase.** Les scripts qui mettent la chaîne de test dans l'état de départ, rejouent l'attaque Kelp/Aave de façon reproductible, produisent du trafic normal et remettent tout à zéro, en écrivant à chaque run la « vérité terrain » (`RunRecord`) qui sert à l'évaluation (T7).

**Profil conseillé.** Python. Pas besoin d'être expert blockchain : envoyer une transaction et lire un bloc passent par `backend/chain.py`.

**Concrètement, tu construis :**
- `seed` : les dépôts et emprunts des bots et les positions du coffre qui donnent l'état de référence ; il ne fait rien si l'état est déjà en place ;
- `attack` : émission forgée de rsETH (un jeton émis sans contrepartie), dépôt en garantie, emprunts par tranches, ruée des bots, gel par le guardian du protocole ; réglable par variante (`default`, `slow`, `usdc`) et par graine (`seed`, pour rejouer un tirage) ;
- `normal` : du trafic bénin aléatoire mais sans danger (dépôts, retraits, emprunts, remboursements) ;
- `reset` : redéploie les contrats (`make deploy FORCE=1`) puis relance le seed ;
- le `RunRecord` : un JSON par run dans `data/runs/`, avec le bloc de chaque phase de l'attaque ;
- l'API `/api/demo/*` : boutons « Run attack » et « Reset » du dashboard (T6).

**À la fin, on doit pouvoir :**
1. `make reset && make attack` sur local : couverture du rsETH à 1 935 bps (~19 %), 6 emprunts de 100 WETH (600 WETH), lend-eth WETH fourni 1 800 / emprunté 1 800 / disponible 0, rsETH gelé sur lend-eth seulement, lend-avax intact ;
2. `make seed` deux fois de suite : la 2e n'envoie aucune transaction (`already_seeded`) ;
3. `make attack SEED=42` puis `SEED=43` : paramètres différents et deux `data/runs/*.json` valides ;
4. `make normal MINUTES=2` : tourne sans exception, rend la main et écrit un `RunRecord` label `normal` ;
5. `curl -X POST :8000/api/demo/attack -H 'content-type: application/json' -d '{"seed": null}'` : un `DemoRun` avec une graine dans [1 ; 999999], qui passe `done` avec ses logs ; un 2e appel pendant le run renvoie 409.

**Specs clés.**

| Sujet | Règle |
|---|---|
| État après seed | lend-eth WETH 2 000 fournis / 1 200 empruntés, USDC 3 000 000 / 1 800 000 ; lend-avax WETH 1 000 / 550, USDC 2 000 000 / 1 100 000 ; rsETH 1 200, couverture 10 000 bps |
| Coffre après seed | 150 WETH + 400 000 USDC sur lend-eth, 100 WETH + 300 000 USDC sur lend-avax, 0 en attente |
| Attaque `default` | 5 000 rsETH forgés, tranches de 100 WETH toutes les 1 s (local) / 8 s (fuji), retraits de bots après les emprunts 4 et 5 |
| Graine | `0` = paramètres par défaut exacts ; `≥ 1` = tirage déterministe ; `null` = l'API tire une graine |
| Trafic normal | utilisation ≤ 8 500 bps, montant ≤ 10 % du disponible ; jamais d'opération sur le coffre, et l'emprunteur historique (`bots[1]`) n'emprunte pas |

- Prix de l'oracle jamais modifiés (aucun `setPriceE8`) ; le collatéral USDC est déposé avant les emprunts.
- `seed` et `reset` tournent sous `data/runtime/<network>/maintenance.flag`, supprimé dans un `finally` même en cas d'échec.
- Non-circularité : aucun paramètre d'attaque choisi en regardant les seuils des règles.

**Livrables.** `scenario/common.py`, `params.py`, `seed.py`, `attack.py`, `normal.py`, `reset.py`, `testing.py`, `backend/api/demo.py`, `mk/t2.mk` (`seed`, `attack`, `normal`, `reset`, `test-t2`), tests `backend/tests/test_t2_*.py`.

**Tests d'acceptation (ceux qui comptent).**
- T2-30 : attaque par défaut → `conservationGap() == 5000e18`, `destinationNonce() == sourceNonce() + 1`, ratio d'affichage `backingRatioBps() == 1935`, lend-eth WETH disponible 0, collatéral rsETH 5 900, lend-avax WETH disponible 450.
- T2-31 : `RunRecord` avec 5 phases dans l'ordre `forged_release < collateral_deposit < first_borrow < liquidity_zero < protocol_freeze` et les 4 positions du coffre au départ.
- T2-32 : CLI `--json` → 6 `borrow`, 2 `bot_withdraw` ok et 1 `blocked` (le déposant coincé).
- T2-22 : seed relancé → `{"status": "already_seeded"}`, aucun nonce modifié.
- T2-40 : trafic normal → utilisation ≤ 8 500 à chaque bloc, couverture toujours 10 000.
- T2-54 : API → 404 run inconnu, 409 run concurrent, 422 pour `variant="foo"` ou `seed=-1`.

**En attendant les autres.** Sans contrats (T1), on code et teste ce qui ne touche pas la chaîne : paramètres, trafic planifié, `RunRecord`, API avec un faux runner ; les tests chaîne se mettent en skip tout seuls. Helpers manquants de T0 : shim `scenario/_compat.py`.

**Détails pour Claude Code.** Fiche détaillée T2, section 3 de ce document.

---

### T3 · Surveillance : lire la chaîne et lever des alertes

**En une phrase.** Un programme qui, à chaque nouveau bloc (un « bloc » = une page de transactions ajoutée à la chaîne), lit l'état des marchés où le coffre a de l'argent et lève une alerte dès qu'un des cinq indicateurs franchit son seuil.

**Profil conseillé.** Python (FastAPI, asyncio). Pas besoin de connaître la blockchain : `backend/chain.py` fournit les adresses et les ABI (la description des fonctions de chaque contrat) pour faire les lectures.

**Concrètement, tu construis :**
- le **collecteur** (`collector.py`) : lit les deux marchés de prêt `lend-eth` et `lend-avax`, le bridge rsETH, l'oracle (le prix) et le coffre, et renvoie une photo de l'état (`Snapshot`), environ 20 lectures par photo ;
- les **5 règles** R1 à R5 (`rules.py`) : des fonctions pures qui regardent les 20 dernières photos et renvoient des `Alert` avec une phrase chiffrée en anglais ;
- l'**anti-doublon** (`AlertLatch`) : une alerte n'est émise qu'une fois par gravité, sauf si elle monte en gravité ;
- le **moteur** (`engine.py`) : boucle toutes les 2 s, collecte, applique les règles, stocke, et passe les nouvelles alertes à la réponse (T4) une à la fois, sans bloquer l'API ; RPC de secours après 3 erreurs ; pause pendant la maintenance ;
- les **routes d'état** (`api/state.py`) : `/api/health`, `/api/state`, `/api/series`, `/api/alerts`, avec totaux en dollars et niveau de risque.

**À la fin, on doit pouvoir :**
1. `make replay-t3` : imprime exactement 7 alertes (R1 critical au bloc 45 201 812, R2 critical au premier snapshot suivant le dépôt du rsETH volé, R5 critical au bloc 45 201 878) ; `make replay-t3 FILE=fixtures/snapshots_normal.jsonl` n'imprime rien ;
2. `make monitor-once` sur anvil (chaîne locale de test) après `make seed` : un `Snapshot` JSON avec les 4 positions du coffre (150 WETH + 400 000 USDC sur `lend-eth`, 100 WETH + 300 000 USDC sur `lend-avax`), toutes 100 % retirables, total 1 325 000 $ ;
3. `ENGINE_ENABLED=true USE_FIXTURES=false make backend` puis `make attack` (T2) : R1 apparaît dans `/api/alerts` au plus 2 polls après l'émission forgée ;
4. après l'attaque, sans la réponse de T4 branchée, `/api/state` donne `value_usd` 1 325 000, `withdrawable_usd` 950 000, `at_risk_usd` 375 000, `risk_level` `"critical"` ;
5. lancer `make seed` pendant que le moteur tourne : aucune alerte ; avec une mauvaise `RPC_URL`, `/api/health` passe `degraded` et le moteur continue sur `RPC_FALLBACK_URL`.

**Specs clés.**

| Règle | Ce qu'elle regarde | Seuil | Gravité |
|---|---|---|---|
| R1 | conservation et nonces du bridge rsETH | gap > 0 ou nonce destination > source | critical |
| R2 | hausse du rsETH déposé en garantie vs baseline sur 20 snapshots | ≥ 50 % / ≥ 200 % | high / critical |
| R3 | baisse de liquidité d'une réserve où le coffre est exposé | ≥ 30 % / ≥ 60 % | high / critical |
| R4 | part réellement retirable d'une position du coffre | < 80 % / < 50 % | high / critical |
| R5 | activation on-chain d'un confinement bridge/réserve | transition | high / critical selon l'exitabilité |

- Seuils dans `backend/config/rules.yaml` (copie exacte de 2.7) ; `rules_version` = `"sha256:"` + empreinte du fichier (71 caractères).
- La fenêtre = les 20 derniers **snapshots** (pas des blocs).
- Mode maintenance : tant que `data/runtime/<network>/maintenance.flag` existe, aucune règle évaluée ; fenêtre vidée à sa disparition, et aussi si `store.generation` change ou si la chaîne recule.
- `/api/state` sans snapshot → `503 {"detail": "no snapshot yet"}` ; `value_usd` inclut l'argent rapatrié dans le coffre (`idle_usd`), `at_risk_usd` ne compte que les positions.

**Livrables.** `backend/collector.py`, `backend/rules.py`, `backend/engine.py`, `backend/config/rules.yaml`, `backend/api/state.py`, tests `backend/tests/test_t3_*.py`, `mk/t3.mk` (`test-t3`, `monitor-once`, `monitor`, `replay-t3`).

**Tests d'acceptation (ceux qui comptent).**
- Série d'attaque (41 snapshots) : 7 alertes dans l'ordre R1 bridge critical (812), R2 collateral critical (814), R3 liquidity high (826), R3 liquidity critical (832), R4 exitability high (836), R4 exitability critical (838), R5 containment critical (878) ; aucun doublon ; R3/R4 uniquement sur `lend-eth/WETH`.
- Série normale : 0 alerte.
- R1 au bloc 45 201 812 : `conservation_gap == 5000`, destination nonce 308 > source nonce 307 ; l'explication mentionne l'absence de backing source canonique.
- Maintenance : 0 alerte tant que le fichier existe, puis R1 dès le premier snapshot après sa suppression.
- Abonnés lents : `/api/health` répond en moins de 0,5 s pendant qu'un handler dort, jamais deux appels simultanés.

**En attendant les autres.** Pas besoin de la chaîne pour commencer : règles, moteur et API se développent sur `fixtures/snapshots_attack.jsonl` et `snapshots_normal.jsonl`, avec une `MemStore` locale aux tests si `backend/store.py` manque. Le test du collecteur reste en `skip` jusqu'à ce que T1 (déploiement) et T2 (`make seed`) soient prêts.

**Détails pour Claude Code.** Fiche détaillée T3, section 3 de ce document.

---

### T4 · Réponse et preuves : décider, mettre l'argent à l'abri, prouver

**En une phrase.** À partir des alertes de T3, le programme prend **une** décision fixée par une table de règles (la « matrice »), pause les nouveaux dépôts, rapatrie dans le coffre ce qui est encore retirable, prévient les humains, puis enregistre et ancre une empreinte de la décision sur la chaîne pour qu'un auditeur puisse la vérifier avec `verify`.

**Profil conseillé.** Python. Pas besoin d'être spécialiste blockchain : `backend/chain.py` envoie les transactions (opérations signées sur la chaîne), et tout se développe d'abord en dry-run (simulation, aucune transaction).

**Concrètement, tu construis :**
- le **playbook** `backend/config/playbook.yaml` : la matrice gravité → actions (automatiques ou soumises à approbation humaine) ;
- le **planificateur** : des fonctions pures (`assess`, `plan_actions`) qui transforment alertes + snapshot (photo de l'état) en liste d'actions ;
- l'**exécuteur** : `Web3Executor` (vraies transactions avec la clé guardian) et `DryRunExecutor` (factice, hash `0xdry…`) ;
- les **notifications** : log toujours, webhook et SNS si configurés, sans jamais bloquer les retraits ;
- les **preuves** : fichier `data/evidence/<id>.json`, empreintes `inputs_hash` et `record_hash` (hash keccak), ancrage dans `EvidenceRegistry`, et la commande `verify` (+ `tamper`/`restore` pour la démo) ;
- les **routes** `GET /api/decisions`, `POST /api/decisions/{id}/approve`, `POST /api/verify/{decision_id}`.

**À la fin, on doit pouvoir :**
1. passer une alerte R1 critique au bloc 45 201 812 et obtenir la décision `DEC-fuji-45201812-1` : 8 actions, exposition 1 325 000 $, case `critical|exposure>=1k|exit_possible`, 4 retraits d'urgence exécutés (400 000 USDC et 150 WETH sur `lend-eth`, 300 000 USDC et 100 WETH sur `lend-avax`) ;
2. lancer `make verify ID=DEC-fuji-45201812-1` et lire `MATCH` (code de sortie 0) ;
3. falsifier la preuve avec `make tamper` (ex. `decision.actions.2.params.asset` = `DAI`) puis `make verify` : `MISMATCH` (code 1) avec les différences lisibles ; `make restore` remet `MATCH` ;
4. sur anvil (`make chain deploy seed`), voir les dépôts du coffre en pause, +700 000 USDC et +250 WETH revenus dans le coffre, l'empreinte ancrée, puis approuver `UNPAUSE_DEPOSITS` via l'API pour lever la pause.

**Specs clés.**

| Gravité max | Actions, dans l'ordre |
|---|---|
| critical | NOTIFY, PAUSE_DEPOSITS, EMERGENCY_WITHDRAW par position (auto), OPEN_INCIDENT, UNPAUSE_DEPOSITS (humain) |
| high | NOTIFY, PAUSE_DEPOSITS, EMERGENCY_WITHDRAW par position (humain), OPEN_INCIDENT |
| warning | NOTIFY seulement |
| info | rien, pas de décision |

- Exposition < 1 000 $ : seulement NOTIFY si la gravité est au moins high.
- Une seule décision par snapshot, id `DEC-<network>-<bloc>-<n>` ; une alerte déjà vue ne relance rien ; aucune exception ne remonte au moteur.
- Un échec (ex. revert `"MiniLend: paused"`) passe l'action en `failed` avec la raison, les suivantes continuent.
- Les `params` ne bougent jamais après planification (sinon `verify` échoue) ; `unpauseDeposits` se signe avec la clé owner.

**Livrables.** `backend/responder.py`, `executor.py`, `notify.py`, `evidence.py`, `cli.py`, `config/playbook.yaml`, `api/response.py`, tests `backend/tests/test_t4_*.py`, `mk/t4.mk` (cibles `verify`, `tamper`, `restore`, `test-t4`).

**Tests d'acceptation (ceux qui comptent).**
- T4-02 : R1 critique au bloc 45 201 812 → exactement 8 actions, 4 retraits dans l'ordre `lend-eth` USDC, WETH puis `lend-avax` USDC, WETH.
- T4-09 : R1 + R2 sur le même snapshot → exposition 1 325 000 $ (pas 1 700 000), pas de double comptage.
- T4-17 : rejouer les mêmes alertes → `[]` ; dépôts déjà en pause → PAUSE `skipped "already paused"`.
- T4-22 : `tamper` puis `verify` → `MISMATCH` avec `record_hash` et `action[2]` ; 2e falsification → `action count: stored 8 != replanned 7`.
- T4-24 : approbation via l'API → 200 puis 409 si rejouée, 400 index hors bornes, 404 id inconnu, 422 corps invalide.
- T4-25 (anvil) : retraits réels, ancrage on-chain et `make verify` → `MATCH`.

**En attendant les autres.** `DRY_RUN_ACTIONS=true`, snapshots lus dans `fixtures/snapshots_attack.jsonl`, alertes construites avec `make_alert`, `FakeStore` si `backend/store.py` manque, variables AWS vides. `make test-t4` doit être vert sans chaîne ni AWS (T4-25 en skip).

**Détails pour Claude Code.** Fiche détaillée T4, section 3 de ce document.

---

### T5 · Incident et DORA : suivre l'incident et préparer la déclaration réglementaire

**En une phrase.** Un module qui transforme les décisions de la réponse automatique (T4) en un incident suivi (statut, chronologie, montants sauvés et encore à risque), propose sa classification DORA (le règlement européen sur la résilience numérique des acteurs financiers) et produit le brouillon de déclaration qu'un humain valide puis soumet.

**Profil conseillé.** Python, goût pour les règles précises. Pas besoin de connaître la blockchain : tout se lit dans le store (la mémoire partagée du backend), et aucune transaction n'est jamais envoyée par T5.

**Concrètement, tu construis :**
- le **gestionnaire d'incident** `IncidentManager` : ouvre un incident quand une décision contient `OPEN_INCIDENT`, y rattache les décisions et alertes suivantes, recalcule montants, statut et chronologie ;
- la **classification DORA** `classify` : une fonction pure qui applique les seuils de l'Art. 9 et la règle « majeur » de l'Art. 8(1) du RTS (UE) 2024/1772, plus le calcul des **délais** de déclaration (règlement (UE) 2025/301) ;
- le **rapport** markdown en 8 sections, avec une description rédigée par Bedrock (l'IA d'AWS) si elle est disponible, sinon par un modèle de texte fixe ;
- le **registre des dépendances tierces** (RPC, AWS, oracle, protocoles, bridge) avec un statut ok / degraded / down / unknown ;
- les **routes** `/api/incidents`, `/api/incidents/{id}`, `/api/incidents/{id}/report.md`, `POST /api/incidents/{id}/submit`, `/api/dependencies`.

**À la fin, on doit pouvoir :**
1. lancer `make attack SEED=42` sur anvil avec `USE_FIXTURES=false` et obtenir **exactement un** incident `contained`, `saved_usd` ≈ 1 325 000, `at_risk_usd` 0, classé majeur avec les seuils 9(1) et 9(4) ;
2. télécharger le rapport via `GET /api/incidents/{id}/report.md`, ou l'écrire sur disque avec `make dora-report ID=INC-…` (→ `data/reports/INC-….md`) ;
3. lancer `make dora-demo` hors ligne et voir un rapport complet ;
4. soumettre via `POST /api/incidents/{id}/submit` : 200 la première fois, 409 `already submitted` la seconde ;
5. couper Bedrock : le moteur ne bloque jamais, le rapport sort avec le texte du modèle.

**Specs clés.**

| Point | Règle |
|---|---|
| Seuils Art. 9 (comparaisons strictes) | 9(1) clients > 10 % ou > 100 000 ; 9(3) durée > 24 h ou indisponibilité > 2 h ; 9(4) ≥ 2 États membres ; 9(6) impact > 100 000 EUR ; 9(2), 9(5)(a), 9(5)(b) lus dans le profil |
| Majeur (Art. 8(1)) | services critiques touchés **et** (accès malveillant 9(5)(b) **ou** ≥ 2 critères distincts) ; un critère compte une seule fois |
| Délais | initial = min(classification + 4 h, détection + 24 h) ; intermédiaire = +72 h ; final = +30 jours |
| Montants | `saved_usd` = retraits d'urgence exécutés ; `at_risk_usd` = part non retirable des positions concernées ; calcul en entiers, jamais `float(amount)` |
| Statut | `contained` après 10 snapshots sans nouvelle alerte pertinente et sans position bloquée ; une alerte high/critical ≥ 1 000 USD rouvre |

- La classification n'est qu'une **proposition** : seul un humain soumet. On ne modifie jamais une `Decision`.
- Bedrock : appel en thread séparé, au plus 1 appel par seconde, cache sur les mêmes faits, repli sur le modèle de texte en cas d'erreur.

**Livrables.** `backend/incidents.py`, `backend/dora.py`, `backend/llm.py`, `backend/config/dora_profile.yaml`, `backend/config/dependencies.yaml`, `backend/api/incidents.py`, `mk/t5.mk` (`test-t5`, `dora-report`, `dora-demo`), tests `backend/tests/test_t5_*.py`.

**Tests d'acceptation (ceux qui comptent).**
- `make test-t5` vert (T5-01 à T5-27), sans réseau ni AWS ; chaque seuil de l'Art. 9 a un test de borne (10 non atteint, 10.01 atteint).
- Série avec réaction : 1 incident `INC-20261011-001`, `contained` au bloc 45 201 832, `saved_usd` 1 325 000.0, `exposure_usd` 1 325 000.0, `at_risk_usd` 0.0, majeur `[9(1), 9(4)]`.
- Série brute sans réaction : `open`, `saved_usd` 0.0, `at_risk_usd` 375 000.0, seuils `[9(1), 9(4), 9(6)]` (345 000 EUR).
- Rapport : les 8 titres dans l'ordre, `1,325,000 USD` présent, aucun `None`, `nan` ou `TODO`.
- Dépendances sur la série brute : `rseth down`, `lend-eth degraded`, `lend-avax ok`.

**En attendant les autres.** Tout se fait sans T3 ni T4 : `FakeStore` en mémoire, décisions et alertes construites à la main (`make_decision_r1()`, `make_alert_r1()`), séries `fixtures/snapshots_attack.jsonl` et `make_reacted_series()`, `BEDROCK_MODEL_ID` vide (modèle de texte).

**Détails pour Claude Code.** Fiche détaillée T5, section 3 de ce document.

---

### T6 · Dashboard : montrer au jury ce que fait la plateforme

**En une phrase.** Un site web (dossier `frontend/`) qui interroge le backend toutes les 2 s et affiche, en anglais simple et en gros chiffres, l'état du coffre et des marchés, les alertes et décisions, l'incident et la déclaration DORA, la preuve de chaque décision, les métriques et un panneau de démo ; il ne calcule **aucune** règle, il affiche ce que l'API renvoie.

**Profil conseillé.** React + TypeScript. Pas besoin de connaître la blockchain : les montants arrivent en « unités de base » (entiers géants, ex. 18 décimales pour le WETH) qu'il suffit de convertir avec `BigInt`.

**Concrètement, tu construis :**
- le **client API** `src/api.ts` et sa **maquette** `src/fixtureDb.ts`, qui sert les fichiers `fixtures/*.json` sans aucun backend (`VITE_USE_FIXTURES=true`) ;
- le **hook de polling** `usePolling` : un appel immédiat, puis un appel 2 s après la fin du précédent, jamais deux requêtes en même temps ;
- les **fonctions de formatage** `lib/format.ts` (dollars, unités, %, couleurs, comptes à rebours, UTC) et les libellés `lib/labels.ts` ;
- la **mise en page** : barre latérale, en-tête (réseau, bloc, santé), bandeaux FIXTURE MODE / Waiting for first block / Backend unreachable / Data is stale ;
- les **8 pages** : `/` Overview, `/charts`, `/alerts`, `/incident`, `/evidence`, `/dependencies`, `/metrics`, `/demo`.

**À la fin, on doit pouvoir :**
1. lancer `make frontend` sans backend (mode fixtures) et voir sur `http://localhost:5173` la carte « Total treasury value » à `$1,325,000`, le badge `CRITICAL`, « Deposits PAUSED » et la couverture rsETH à `19.4%` ;
2. lancer `make backend` puis `VITE_USE_FIXTURES=false make frontend` : les 8 pages s'affichent, `/api/state`, `/api/alerts`, `/api/decisions`, `/api/health` sont appelées toutes les 2 s, sans erreur console ni CORS ;
3. cliquer **Approve** / **Reject** sur une action en attente, **Verify** sur une décision (`MATCH` vert ou `MISMATCH` rouge), **Submit to regulator** sur l'incident ;
4. lancer l'attaque depuis `/demo` (variant `default`, `slow` ou `usdc`, seed) et suivre le journal du run ;
5. au démarrage de `make demo`, voir « Waiting for first block » tant que l'API répond 503, puis les données sans recharger la page.

**Specs clés.**
- Erreurs : **503** `no snapshot yet` → encadré gris d'attente (pas une panne) ; **409** → message tel quel puis `refresh()` ; 400/404/422 → message rouge avec `detail`.
- Couleurs = seuils des règles : retirable ≥ 80 % ok, 50 à 79,99 % warn, < 50 % bad ; utilisation < 90 % ok, ≥ 98 % bad ; couverture ≥ 99 % ok. La couleur n'est jamais la seule information (mot en majuscules).
- Montants : jamais `Number` sur des unités de base, sauf `unitsToNumber` pour les graphiques ; pas de « bps » à l'écran, tout en %.
- Métriques : `*_rate` de 0 à 1 (× 100), `*_pct_*` déjà de 0 à 100, `ttd = -1` → `not detected`.
- Demo : seed vide → entier aléatoire dans [1, 999999] ; `0` = paramètres par défaut ; on envoie toujours un entier.
- Production : `VITE_API_URL` vide → appels relatifs `/api/...` ; seul `EXPLORER_URL` est injecté depuis le `.env` racine (qui contient des clés privées).
- `frontend/src/types.ts` appartient à T0 : on l'importe, on ne le modifie jamais.

**Livrables.** `frontend/` (sauf `src/types.ts`), `frontend/.env.example`, `mk/t6.mk` avec `make frontend`, `make frontend-build` (→ `frontend/dist/`), `make test-t6`.

**Tests d'acceptation (ceux qui comptent).**
- `make test-t6` vert : typecheck, build (aucun `_PK` ni `PRIVATE` dans `frontend/dist`), vitest T6-03 à T6-15.
- Overview en mode fixtures : `$1,325,000`, `CRITICAL`, `PAUSED`, `19.4%`, 6 lignes de réserves ; avec `positions: []` → « No open positions: all funds are back in the vault. ».
- Polling : 1 appel au montage, 3 après 4 s ; fetcher bloqué → 1 seul appel après 10 s ; 0 appel après démontage.
- Approve : POST exact `{"action_index":2,"approver":"jury-demo","approve":true}` ; Demo : `Seed 4242` affiché et corps `{"seed":4242,"variant":"default"}`.
- Mode fixtures sans backend : bandeau `FIXTURE MODE`, `fetch` appelé 0 fois, les 8 routes sans exception.

**En attendant les autres.** Tout se fait d'abord en `VITE_USE_FIXTURES=true` (fixtures de T0, approbation et soumission simulées en mémoire), puis contre le squelette `make backend` de T0 ; attention, plusieurs fixtures sont périmées et seront régénérées : ne rien coder en dur sur leur contenu.

**Détails pour Claude Code.** Fiche détaillée T6, section 3 de ce document.

---

### T7 · Évaluation : prouver en chiffres que la plateforme marche

**En une phrase.** Un banc d'essai qui lance plusieurs attaques et plusieurs journées normales sur la chaîne locale, lit l'API comme une boîte noire et produit 8 chiffres honnêtes : détection, délai, part de la trésorerie mise à l'abri, fausses alertes.

**Profil conseillé.** Python, à l'aise avec les statistiques simples et les tests. Pas besoin de connaître la blockchain : tu ne lis que l'API HTTP et des fichiers JSON (un « bloc » est juste un numéro qui avance sur la chaîne).

**Concrètement, tu construis :**
- les **métriques** (`evaluation/metrics.py`) : des fonctions pures qui, à partir de la vérité terrain d'un run (`RunRecord`), des alertes et des décisions, disent si l'attaque est détectée, en combien de blocs (TTD, *time to detect*) et combien de dollars sont sauvés ;
- le **client d'API** (`evaluation/api_client.py`) : une interface `EvalApi`, sa vraie version HTTP et une `FakeApi` en mémoire pour les tests ;
- le **banc** (`evaluation/run_synthetic.py`) : gèle les seuils (empreinte sha256 de `rules.yaml`), puis boucle reset → attaque → lecture → calcul, puis les journées normales ;
- le **rapport** (`evaluation/report.py`) : écrit `data/eval/report.md` avec tableaux, ratés et méthode ;
- la **route** `GET /api/metrics` : sert `data/eval/metrics.json`, ou la fixture si le fichier est absent ou cassé.

**À la fin, on doit pouvoir :**
1. lancer `make eval RUNS=10` (backend lancé avec `NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false`) et obtenir `metrics.json`, `report.md`, `runs.jsonl` et `rules_frozen.json` dans `data/eval/`, avec les variantes `default x4, slow x3, usdc x3` ;
2. lire dans le rapport une détection de 100 %, un TTD de 0 à 2 blocs, 100 % sauvé contre ~70 % pour une trésorerie passive qui ne bouge pas (71,7 en `default`, 69,8 en `usdc`) ;
3. appeler `GET /api/metrics` et retrouver ces chiffres (jamais de 500, même sur un fichier cassé) ;
4. voir dans les notes chaque raté, faux positif ou run en erreur, sans relance silencieuse.

**Specs clés.**

| Métrique (`synthetic`) | Définition | Format |
|---|---|---|
| `runs_attack`, `runs_normal` | runs valides (les runs en erreur sont exclus) | int |
| `detection_rate` | part des attaques avec une alerte `critical` dans la fenêtre | 0..1, 3 déc. |
| `false_positive_rate` | part des journées normales avec une alerte ≥ `high` | 0..1, 3 déc. |
| `ttd_blocks_p50`, `ttd_blocks_p90` | 1re alerte critique − `attack_start_block`, rang le plus proche | int, -1 si aucune détection |
| `saved_pct_mean` | retraits `EMERGENCY_WITHDRAW` `executed` / valeur au départ | 0..100, 1 déc. |
| `baseline_saved_pct_mean` | réserve vidée = 0 %, les autres = 100 % | 0..100, 1 déc. |

- Fenêtre d'un run : `[start_block, end_block + 10]` ; tout ce qui est hors fenêtre est ignoré.
- Dénominateur : 4 positions = **1 325 000 $** (150 WETH + 400 000 USDC sur `lend-eth`, 100 WETH + 300 000 USDC sur `lend-avax`).
- Ne comptent pas : statuts autres que `executed`, `amount = "0"`, `tx_hash` en `0xdry…` (dry-run, aucun fonds déplacé) ; plafond par position.
- Non-circularité : seuils gelés avant le premier run ; alerte avec un autre `rules_version` → arrêt, sortie 3 ; plus de 20 % de runs en erreur → sortie 2.

**Livrables.** `evaluation/metrics.py`, `api_client.py`, `run_synthetic.py`, `report.py`, `backend/api/metrics.py`, `mk/t7.mk` (`make eval`, `eval-report`, `test-t7`, `test-t7-e2e`), tests `backend/tests/test_t7_*.py` ; `data/eval/metrics.json` et `report.md` commités.

**Tests d'acceptation (ceux qui comptent).**
- T7-04 : 4 retraits complets → `saved_usd == 1325000.0`, `saved_pct == 100.0` ; T7-05 : seul `lend-eth:WETH` exécuté → 28,3.
- T7-07 : réserve vidée `lend-eth:WETH` → 71,7 ; `lend-eth:USDC` → 69,8 ; aucune → 100,0.
- T7-10 : agrégat → `detection_rate == 0.667`, `false_positive_rate == 0.5`, p50 = 0, p90 = 2, `saved_pct_mean == 66.7`, `baseline_saved_pct_mean == 71.1`.
- T7-17 : banc avec `FakeApi`, 3 attaques + 1 normal → détection 1,0, p50 = 1, sauvé 100,0, baseline 71,1, `runs.jsonl` de 4 lignes.
- T7-18 : alerte d'un autre `rules_version` → `SystemExit` code 3.
- T7-20 (`make test-t7-e2e`) : `detection_rate == 1.0`, `false_positive_rate == 0.0`, `ttd_blocks_p90 <= 2`, `saved_pct_mean >= 99.0`.

**En attendant les autres.** Tout se développe sans chaîne ni backend : `RunRecord`, `Alert` et `Decision` faits à la main, `FakeApi` pour le banc, `fixtures/snapshots_attack.jsonl` et `snapshots_normal.jsonl` pour les séries, `--no-anchor` pour l'ancrage. T7-16 et T7-20 restent en skip tant que T2, T3 et T4 ne sont pas livrés.

**Détails pour Claude Code.** Fiche détaillée T7, section 3 de ce document.

---

### T8 · Mise en ligne : la démo sur AWS, les services AWS et la CI

**En une phrase.** Mettre la plateforme en ligne sur AWS (us-east-1) derrière une URL publique stable branchée sur Fuji (le réseau de test d'Avalanche), fournir à T4 et T5 les services AWS dont ils ont besoin, et garder `main` vert avec une CI (tests lancés automatiquement à chaque PR), sans jamais laisser fuiter une clé.

**Profil conseillé.** Docker, shell et AWS CLI. Pas besoin de connaître la blockchain : on emballe et on déploie le code des autres.

**Concrètement, tu construis :**
- les **deux images Docker** : `sh-backend` (API FastAPI, un seul process, avec `make` et Foundry pour que le reset de démo puisse redéployer les contrats) et `sh-frontend` (le dashboard servi par nginx, qui renvoie `/api/*` vers le backend) ;
- le **compose** qui lance les deux, backend lié à `127.0.0.1:8000` uniquement, public sur le port 80 ;
- les **ressources AWS** décrites pas à pas dans un runbook : topic SNS (e-mails d'alerte), bucket S3 de preuves, modèle Bedrock (Claude), rôle IAM minimal, instance EC2 avec Elastic IP, secrets dans SSM (coffre de paramètres chiffrés) ;
- le **script de déploiement** `infra/deploy.sh` (envoie le code commité, assemble le `.env` sur l'instance, relance, vérifie la santé, rollback) ;
- `infra/check_aws.py`, qui vérifie que STS, SNS, S3, Bedrock et l'URL publique répondent ;
- la **CI** GitHub (5 jobs `python`, `contracts`, `frontend`, `gitleaks`, `docker`) et le scan anti-secrets des images.

**À la fin, on doit pouvoir :**
1. ouvrir `http://<elastic-ip>/` depuis un téléphone en 4G et voir le dashboard ;
2. lancer `make aws-smoke HOST=<ip>` et obtenir `OK http network=fuji chain_id=43113 rpc_ok=true engine_running=true` avec un numéro de bloc qui augmente entre deux appels espacés de 6 s ;
3. lancer `make aws-check HOST=<ip>` et obtenir `SUMMARY 4 OK, 0 FAIL, 0 SKIP` (chaque membre reçoit l'e-mail « secure-horizons check_aws ») ;
4. redémarrer l'instance (`sudo reboot`) et voir `make aws-smoke` repasser `OK` au plus 3 min plus tard sans intervention ;
5. ouvrir une PR et voir les 5 jobs CI au vert.

**Specs clés.**
- uvicorn **sans** `--workers` ni `--reload` : le moteur et le store sont en mémoire, deux process = deux retraits pour une même alerte.
- nginx : `proxy_pass http://backend:8000;` **sans** `/` final ; `/api/demo/` limité à 6 requêtes/min par IP, délai 300 s (le reset sur Fuji peut dépasser une minute).
- `infra/fuji.env` (commité, sans secret) force `NETWORK=fuji`, `CHAIN_ID=43113`, `ENGINE_ENABLED=true`, `USE_FIXTURES=false`, `DRY_RUN_ACTIONS=false`.
- IAM : exactement 7 actions (`sns:Publish`, `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` sur `/healthcheck/*` seulement, `bedrock:InvokeModel`, `ssm:GetParametersByPath`, `ssm:GetParameter`), aucune action `*`.
- EC2 `t3.medium`, disque 30 Go, `HttpPutResponseHopLimit=2` (sinon boto3 dans le conteneur ne trouve aucun identifiant) ; port 22 réservé aux IP `/32` de l'équipe, port 8000 jamais ouvert.
- Sorties pour les autres : `SNS_TOPIC_ARN` (topic `secure-horizons-alerts`), `EVIDENCE_BUCKET` (`secure-horizons-evidence-<account_id>`), `BEDROCK_MODEL_ID` copié depuis `aws bedrock list-inference-profiles`, jamais écrit à la main.
- Jamais de secret dans le repo, une image, `user-data` ou une variable `VITE_*` (elles finissent en clair dans le JS public).

**Livrables.** `infra/` (Dockerfiles et `.dockerignore`, `docker-compose.yml`, `nginx.conf`, `deploy.sh`, `render_env.sh`, `user-data.sh`, `scan_images.sh`, `check_aws.py`, `fuji.env`, `iam-policy.json`, `gitleaks.toml`, `setup-aws.md`, `testdata/frontend-stub/`), `.github/workflows/ci.yml`, `mk/t8.mk` (`deploy-aws`, `aws-check`, `aws-smoke`, `docker-smoke`, `scan-images`, `gitleaks`, `test-t8`…), tests `backend/tests/test_t8_*.py`.

**Tests d'acceptation (ceux qui comptent).**
- `make test-t8` vert (T8-01 à T8-06, sans AWS ni réseau ; `check_aws` testé avec des réponses AWS simulées).
- `make docker-smoke` : `localhost/api/health` renvoie le même JSON que `localhost:8000/api/health`, `localhost/` contient `<div id="root">`, `/api/does-not-exist` → `404` venu de FastAPI.
- `make scan-images` puis `--canary` : le faux secret `sh-canary-7f3a9c41` n'apparaît dans aucune image.
- `make gitleaks` → `no leaks found` sur tout l'historique.
- `make aws-check` → `SUMMARY 4 OK` ; `make aws-smoke` → `OK` avec bloc qui avance ; reboot et `make aws-rollback` restent `OK`.

**En attendant les autres.** Déploiement « squelette » avec `USE_FIXTURES=true` et `ENGINE_ENABLED=false` (l'API sert les fixtures, aucun contrat requis), faux front `infra/testdata/frontend-stub/` via `FRONTEND_DIR`. Attention : la fixture de santé dit déjà `network: fuji`, seuls `engine_running=true` et un bloc qui avance prouvent qu'on lit vraiment Fuji.

**Détails pour Claude Code.** Fiche détaillée T8, section 3 de ce document.

---

### T9 · Livrables jury : README, playbook, conformité, deck, vidéo, pitch, sans chiffre inventé

**En une phrase.** Tout ce que le jury lit, voit et entend (README, playbook de réponse, note de conformité, defense sheet, plan du deck, script vidéo, pitch), avec les parties liées au code générées automatiquement et un vérificateur qui refuse tout chiffre sans source.

**Profil conseillé.** Rédaction en anglais, rigueur sur les textes réglementaires (DORA, NIST), un peu de Python pour le générateur et le vérificateur. Pas besoin de connaître la blockchain : il suffit de lire les fichiers produits par les autres.

**Concrètement, tu construis :**
- le **générateur** `docs/tools/gen_docs.py` (+ `docs_lib.py`) : remplit les blocs entre marqueurs `<!-- gen:NAME:start -->` / `<!-- gen:NAME:end -->` (adresses Fuji, métriques, matrice de réponse, versions) à partir des fichiers des autres tâches ;
- le **vérificateur** `docs/tools/check_docs.py` : chaque nombre doit venir de `data/eval/metrics.json`, `deployments/fuji.json` ou `docs/numbers_allowlist.yaml` (avec sa source) ; il détecte aussi les secrets et les identifiants de référence ;
- les **7 documents jury** en anglais : `README.md`, `docs/playbook.md`, `docs/compliance.md`, `docs/defense-sheet.md`, `docs/deck-outline.md`, `docs/video-script.md`, `docs/pitch.md` ;
- la **table des sources** `docs/sources.md` : chaque article de loi (liens EUR-Lex) et chaque id NIST/OWASP/MITRE cité, avec une colonne `Vérifié` ;
- le **smoke test** `docs/tools/fresh_clone_check.sh` : clone neuf, démo, attaque, puis `make verify` (rejoue une décision et vérifie son empreinte ancrée, c'est-à-dire inscrite sur la blockchain).

**À la fin, on doit pouvoir :**
1. lancer `make docs` sur les maquettes et voir les blocs générés marqués PLACEHOLDER (ex. `[[PLACEHOLDER detection_rate]]`, jamais « 0 % ») ;
2. lancer `make docs-final` une fois T1, T4 et T7 livrés : code de sortie 0, plus aucun PLACEHOLDER ni TODO, vraies métriques, 9 adresses Fuji avec lien snowtrace (l'explorateur de blocs), playbook généré depuis le vrai `backend/config/playbook.yaml` ;
3. lancer `make docs-smoke` sur un clone neuf et lire `SMOKE OK` en dernière ligne ;
4. suivre le Quickstart du README en exactement 5 commandes (`git clone`, `cp .env.example .env`, `make setup`, `make demo`, `make attack SEED=42`) ;
5. lire dans `docs/compliance.md` une vraie sortie de `make verify ID=DEC-fuji-…` sur Fuji (première ligne `MATCH`, `anchored: yes`).

**Specs clés.**

| Livrable | Contrainte |
|---|---|
| Defense sheet | une page A4, ≤ 600 mots ; Detect / Respond / Recover, menaces, résultats, limites |
| Deck | 7 à 8 slides (dont Live demo, Results, Compliance, Business model), ≤ 3 puces, note orateur ≤ 40 mots |
| Vidéo | 8 à 12 plans, total 120 à 180 s |
| Pitch | Round 1 ≤ 700 mots + 10 questions (réponse ≤ 50 mots) ; finale ≤ 420 mots |
| Compliance | slide ≤ 80 mots + annexe : DORA Art. 17, 18, 19, 28 ; délais 4 h / 72 h / 1 mois attribués au Règlement délégué 2025/301, pas à DORA |

- Unités des métriques : `*_rate` en 0..1 (× 100 à l'affichage), `*_pct_*` déjà en %, `ttd_blocks_*` = -1 s'affiche « not detected ».
- Aucun article ni id NIST/OWASP/MITRE cité sans l'avoir lu sur la source officielle ; tout prix du business model est étiqueté « hypothèse ».
- Aucun secret, aucun nom d'employeur (liste dans `T9_FORBIDDEN_TERMS`, jamais commitée), aucun nom de personne.

**Livrables.** Les 7 documents ci-dessus, `docs/sources.md`, `docs/numbers_allowlist.yaml`, `docs/assets/`, `docs/tools/*`, `mk/t9.mk` (`make docs`, `docs-check`, `docs-final`, `docs-smoke`, `test-t9`), tests `backend/tests/test_t9_docs.py`.

**Tests d'acceptation (ceux qui comptent).**
- Playbook rendu depuis la maquette : ligne critical exactement `NOTIFY (auto) → PAUSE_DEPOSITS (auto) → EMERGENCY_WITHDRAW (auto) per concerned position → OPEN_INCIDENT (auto) → UNPAUSE_DEPOSITS (human)` ; YAML sans `matrix` → `ValueError`.
- Métriques de fixture : mode placeholder, ni `0 %` ni `0.0` ; métriques d'exemple réelles → `100 %`, `1 block`, `2 blocks`, `Mainnet replay: phase 2`.
- `We save 87 % of funds.` sans allowlist → problème signalé ; `Art. 19`, `2022/2554`, `R1`, `0:42` ne sont pas comptés comme chiffres.
- `GUARDIAN_PK=0x` + 64 `a` détecté comme secret ; un lien snowtrace `…/tx/0x…` ne l'est pas.
- `make test-t9` vert avec les tests stricts T9-03, T9-04, T9-06 skippés ; ces trois tests verts sous `make docs-final`.

**En attendant les autres.** `fixtures/metrics.json` (rendu PLACEHOLDER), `fixtures/deployments.example.json` (adresses d'exemple), `docs/tools/playbook.mock.yaml` et `rules.mock.yaml`, `fixtures/verify.json`, `fixtures/dependencies.json`, le dashboard sur fixtures (`USE_FIXTURES=true`) pour les captures, et `TODO(T8): URL` pour l'URL AWS.

**Détails pour Claude Code.** Fiche détaillée T9, section 3 de ce document.

---

## 0. Comment utiliser ce document

### 0.1 Démarrer une tâche avec Claude Code

1. Choisis ta tâche dans « Les tâches en clair » (en tête de ce document), clone le repo, crée ta branche : `git checkout -b tN-nom-court` (ex. `t3-monitor`).
2. Copie `.env.example` en `.env` et remplis ce dont ta tâche a besoin (section 2.1).
3. Ouvre Claude Code à la racine du repo et colle le **prompt de démarrage** de ta tâche (en fin de chaque section T).
4. Ta tâche est finie quand **tous ses tests passent** (rubrique « Tests qui doivent passer ») et que la checklist « Definition of done » est cochée.

### 0.2 Prompt générique (si ta tâche n'a pas le sien)

```
Tu travailles sur la tâche TN du fichier TASKS.md (racine du repo).
1. Lis les sections 1 et 2 de TASKS.md, puis la section TN en entier.
2. Ne modifie QUE les fichiers listés dans « Fichiers possédés » de TN.
   Si tu as besoin d'un changement ailleurs ou dans le contrat (section 2),
   n'édite pas : écris la demande dans docs/contract-requests.md et préviens-moi.
3. Travaille contre les maquettes indiquées (fixtures, dry-run, chaîne locale) tant que
   les autres tâches ne sont pas livrées.
4. Commence par écrire les tests de la rubrique « Tests qui doivent passer », puis le code.
5. Avant chaque commit : make test-tN (ou la commande indiquée) doit être vert.
   Pousse souvent (après chaque test vert) : le compte AWS est effacé à la fin de l'événement.
```

---

## 1. Contexte commun (à lire par tout le monde)

### 1.1 Ce qu'on construit

Une plateforme de **surveillance de trésorerie DeFi**. Notre client est un gestionnaire financier qui place les fonds de son coffre (un Safe) dans des protocoles de prêt. La plateforme :

1. lit, à chaque bloc, l'état des marchés où le coffre a de l'argent et l'état de ses positions ;
2. calcule **quelques indicateurs simples** (part retirable, utilisation, liquidité, couverture du collatéral) ;
3. lève des **alertes explicables** (une phrase chiffrée par alerte) ;
4. **réagit** automatiquement en resserrant : pause des nouveaux dépôts, retrait d'urgence vers le coffre de ce qui est encore retirable ;
5. **prouve** : chaque décision est enregistrée, hachée et son empreinte ancrée sur Avalanche Fuji ; une commande `verify` permet à un auditeur de la rejouer ;
6. ouvre un **incident** et prépare la **déclaration DORA** pré-remplie, qu'un humain valide et envoie ;
7. affiche tout dans un **dashboard**.

**Hors MVP (phase 2, ne pas coder maintenant)** : l'agent IA qui propose des allocations, le choix des instructions et de l'allowlist, les mandats signés, la sécurité entre agents, les règles de détection avancées (voir section 5).

### 1.2 Le scénario unique (fil rouge de la démo et des tests)

Rejeu synthétique de l'incident Kelp/Aave du 18 avril 2026, **sur nos propres contrats déployés sur Fuji** (et sur une chaîne locale anvil pour les tests).

| Phase | Ce qui se passe on-chain | Ce que la plateforme doit faire |
|---|---|---|
| 0. Normal | Des bots déposent et empruntent. Le coffre a 150 WETH + 400 000 USDC sur `lend-eth`, 100 WETH + 300 000 USDC sur `lend-avax`. | Rien (aucune alerte ≥ high). |
| 1. Émission forgée | Le bridge émet 5 000 rsETH **sans contrepartie** : la couverture du rsETH chute de 100 % à ~19 %. | **R1 critique** dans le bloc suivant → pause des dépôts + retrait d'urgence de toutes nos positions dans les déploiements qui acceptent le rsETH en garantie + incident ouvert. |
| 2. Fausse garantie | L'attaquant dépose les rsETH en garantie sur `lend-eth`. | (déjà en sécurité) |
| 3. Vidage | L'attaquant emprunte le WETH par tranches jusqu'à ce qu'il n'en reste plus. | R2 / R3 si on est encore exposé. |
| 4. Ruée | Les bots essaient de retirer leur WETH ; les derniers restent bloqués. | R4 si une de nos positions est bloquée. |
| 5. Gel tardif | Le guardian du protocole gèle la réserve rsETH. | R5 (information de contexte). |

**Le chiffre qu'on veut montrer** : notre retrait se fait au moment où 100 % de la position est encore retirable, alors qu'un déposant passif reste bloqué.

### 1.3 Architecture

```
            ┌───────────────────────── Avalanche Fuji (ou anvil en local) ─────────────────────────┐
            │  MockERC20 (USDC, WETH)   RsETH + MockBridge   MockOracle                             │
            │  MiniLend "lend-eth"      MiniLend "lend-avax"                                        │
            │  TreasuryVault (le coffre)                     EvidenceRegistry (empreintes)          │
            └───────▲───────────────────────────────▲───────────────────────────────▲──────────────┘
                    │ scripts (T2)                   │ lecture à chaque bloc          │ tx guardian / ancrage
        ┌───────────┴─────────┐          ┌──────────┴──────────────────────────────┴────────────┐
        │ scenario/ (T2)      │          │ backend/ (FastAPI, un seul process)                    │
        │ seed, attack,       │          │  collector → Snapshot → engine (règles R1..R5) → Alert │
        │ normal, reset       │          │  → responder (matrice) → Decision → executor (tx)      │
        └─────────────────────┘          │  → evidence (hash, ancrage, verify)                    │
                                         │  → incidents + DORA (rapport, Bedrock optionnel)       │
                                         │  API /api/* (T3, T4, T5, T2, T7)                       │
                                         └──────────────▲──────────────────────────▲─────────────┘
                                                        │ HTTP (polling 2 s)       │ SNS, S3, Bedrock
                                         ┌──────────────┴──────────┐      ┌────────┴─────────┐
                                         │ frontend/ (T6) Vite     │      │ AWS (T8)         │
                                         └─────────────────────────┘      └──────────────────┘
            evaluation/ (T7) : lance des scénarios, lit l'API, calcule les métriques → data/eval/
```

### 1.4 Stack

| Brique | Choix |
|---|---|
| Contrats | Solidity 0.8.24, Foundry (`forge`, `anvil`), OpenZeppelin |
| Backend, scénario, évaluation | Python 3.11, FastAPI, Pydantic v2, web3.py ≥ 6.20, PyYAML, boto3, pytest |
| Frontend | Node 20, Vite, React 18, TypeScript, Tailwind, Recharts, Vitest |
| Chaîne | `local` = anvil (chainId 31337, blocs instantanés) ; `fuji` = Avalanche Fuji C-Chain (chainId 43113, ~2 s par bloc, explorer `https://testnet.snowtrace.io`) |
| Cloud | AWS us-east-1 uniquement : EC2, SNS, S3, Bedrock (modèles Claude), SSM Parameter Store |

### 1.5 Arborescence du repo et propriétaire de chaque dossier

Chaque fichier a **une seule tâche propriétaire**. Tu ne modifies que les fichiers de ta tâche.

```
.
├── TASKS.md                     T0 (ce document)
├── CLAUDE.md                    T0 (règles pour tous les Claude Code)
├── README.md                    T9 (version finale ; chaque tâche fournit son paragraphe dans sa PR)
├── Makefile                     T0 (inclut mk/*.mk ; chaque tâche a son mk/tN.mk)
├── mk/tN.mk                     TN (cibles make de la tâche N)
├── .env.example .gitignore .pre-commit-config.yaml requirements.txt   T0
├── contracts/                   T1 (projet Foundry : src/, script/, test/)
├── deployments/<network>.json   T1 (écrit par le script de déploiement, commité pour fuji)
├── abi/<Contrat>.json           T1 (exportés par make abi)
├── scenario/                    T2 (sauf scenario/__init__.py, créé par T0)
├── backend/
│   ├── __init__.py main.py models.py settings.py chain.py store.py fixtures.py   T0 (figés)
│   ├── collector.py engine.py rules.py config/rules.yaml api/state.py            T3
│   ├── responder.py executor.py notify.py evidence.py cli.py
│   │   config/playbook.yaml api/response.py                                      T4
│   ├── incidents.py dora.py llm.py config/dora_profile.yaml
│   │   config/dependencies.yaml api/incidents.py                                 T5
│   ├── api/demo.py                                                               T2
│   ├── api/metrics.py                                                            T7
│   └── tests/test_tN_*.py                                                        TN (un préfixe par tâche)
├── evaluation/                  T7 (sauf evaluation/__init__.py, créé par T0)
├── frontend/                    T6 (sauf frontend/src/types.ts, possédé par T0 : miroir de models.py)
├── fixtures/                    T0 (les autres tâches peuvent AJOUTER des fichiers, jamais modifier ceux qui existent)
├── infra/ .github/workflows/    T8
├── docs/                        T9 (README final, playbook, conformité, defense sheet, deck, vidéo)
│   └── contract-requests.md     tout le monde (demandes de changement du contrat)
└── data/                        généré à l'exécution, ignoré par git sauf data/eval/metrics.json
```

### 1.6 Règles de collaboration (anti-friction)

1. **Le contrat d'abord.** La section 2 de ce document, `backend/models.py` et `fixtures/` sont figés. Toute demande de changement passe par `docs/contract-requests.md` (voir 2.12).
2. **Chacun ses fichiers.** On ne touche jamais un fichier possédé par une autre tâche. Les fichiers T0 ne bougent que via le processus de 2.12.
3. **On avance seul sur des maquettes.** Front sur fixtures, détecteurs sur séries enregistrées, réponse en dry-run, scripts sur anvil. Personne n'attend personne.
4. **Mêmes commandes pour tous.** `make <cible>` (section 2.10). Chaque tâche ajoute ses cibles dans son `mk/tN.mk`, jamais dans le `Makefile` racine.
5. **Branches et commits.** Une branche par tâche, petites PR vers `main`, `make test` vert avant merge, push fréquent après chaque test vert (règle AWS : le compte est effacé à la fin de l'événement).
6. **Secrets.** Aucune clé dans le repo (le jury vérifie). Clés dans `.env` (ignoré). `gitleaks` en pre-commit. Une clé par rôle (2.1), pour éviter les conflits de nonce.
7. **Langue.** Code, noms, API, UI, README : anglais. Docs internes : français.
8. **Règles d'usage AWS et Fuji.** On ne teste et n'attaque que ce qu'on a déployé nous-mêmes. Données synthétiques uniquement. Pas de jailbreak des modèles Bedrock. Moins d'une requête Bedrock par seconde et par personne.

---

## 2. Contrat d'interface (figé)

### 2.1 Réseaux, rôles et variables d'environnement

`NETWORK=local` (anvil) ou `NETWORK=fuji`. Tout le code lit l'environnement via `backend/settings.py`.

| Variable | Usage | Requis par |
|---|---|---|
| `NETWORK` | `local` ou `fuji` | tous |
| `RPC_URL` | RPC du réseau (défaut local `http://127.0.0.1:8545` ; pour fuji, une URL de fournisseur, le RPC public limite le débit) | tous |
| `RPC_FALLBACK_URL` | RPC de secours (`https://api.avax-test.network/ext/bc/C/rpc`) | T3, T4 |
| `CHAIN_ID` | 31337 ou 43113 (déduit de `NETWORK` si absent) | tous |
| `EXPLORER_URL` | `https://testnet.snowtrace.io` | T4, T6 |
| `DEPLOYER_PK` | déploie, mint les jetons de test, fixe les prix | T1, T2 |
| `OWNER_PK` | propriétaire du coffre (représente les signataires du Safe) | T1, T2, T4 |
| `GUARDIAN_PK` | clé de **notre plateforme** : pause des dépôts et retrait d'urgence, rien d'autre | T4 |
| `PROTOCOL_GUARDIAN_PK` | guardian du protocole de prêt (gel en fin de scénario) | T2 |
| `ATTACKER_PK` | attaquant | T2 |
| `EVIDENCE_PK` | ancre les empreintes dans `EvidenceRegistry` | T4 |
| `BOT_PKS` | 3 clés séparées par des virgules (utilisateurs normaux) | T2 |
| `USE_FIXTURES` | `true` : l'API sert les fixtures ; `false` : données réelles | T3, T4, T5 |
| `ENGINE_ENABLED` | `true` : la boucle de surveillance tourne au démarrage du backend | T3 |
| `POLL_INTERVAL_S` | intervalle de lecture (défaut 2) | T3 |
| `DRY_RUN_ACTIONS` | `true` : la réponse n'envoie aucune transaction | T4 |
| `AWS_REGION` | `us-east-1` | T4, T5, T8 |
| `SNS_TOPIC_ARN` | topic des alertes (vide = désactivé) | T4, T8 |
| `ALERT_WEBHOOK_URL` | webhook Slack/Discord (vide = désactivé) | T4 |
| `EVIDENCE_BUCKET` | bucket S3 des preuves (vide = local seulement) | T4, T8 |
| `BEDROCK_MODEL_ID` | modèle Claude sur Bedrock (vide = rapport sans IA) | T5, T8 |
| `ETH_ARCHIVE_RPC_URL` | RPC archive Ethereum (phase 2, rejeu du vrai incident) | T7 |
| `VITE_API_URL` | base de l'API pour le front ; vide en production (même origine, nginx sert `/api`), `http://localhost:8000` en développement | T6, T8 (dans `frontend/.env.example`) |
| `VITE_USE_FIXTURES` | `true` : le front lit `fixtures/` sans backend | T6 |

**Sur `local`, aucune clé à écrire** : `settings.private_key(role)` retombe sur les comptes publics d'anvil (mnémonique `test test … junk`) : deployer = index 0, owner = 1, guardian = 2, protocol_guardian = 3, attacker = 4, evidence = 5, bots = 6, 7, 8.

### 2.2 Contrats Solidity (interfaces exactes)

Tous en Solidity 0.8.24, OpenZeppelin pour ERC20 et Ownable. Montants en unités de base. Les erreurs sont des `revert` avec les messages indiqués (les tests les vérifient).

```solidity
// ---------- Jetons ----------
contract MockERC20 is ERC20, Ownable {          // USDC (decimals 6), WETH (decimals 18)
    constructor(string memory name, string memory symbol, uint8 decimals_) ;
    function mint(address to, uint256 amount) external onlyOwner;
}

contract RsETH is ERC20 {                       // symbol "rsETH", decimals 18
    address public bridge;                      // seul minteur
    function mint(address to, uint256 amount) external;   // revert "RsETH: only bridge"
    function burn(address from, uint256 amount) external; // revert "RsETH: only bridge"
}

contract MockBridge {                           // simule la route LayerZero/OFT du rsETH
    IERC20 public weth; RsETH public rseth;
    uint256 public sourceLocked;                 // montant canonique verrouillé/brûlé sur la chaîne source simulée
    uint256 public destinationReleased;          // montant libéré sur la chaîne destination
    uint64 public sourceNonce; uint64 public destinationNonce;
    bool public paused;
    function deposit(uint256 wethAmount) external; // flux sain : verrouille, avance les deux nonces, libère autant de rsETH
    function forgedRelease(address to, uint256 amount) external; // LA FAILLE : avance destinationNonce et libère sans source lock/nonce
    function pause() external;
    function conservationGap() external view returns (uint256);
    function backingRatioBps() external view returns (uint256);  // affichage de compatibilité, jamais déclencheur R1
    event Deposited(address indexed user, uint256 amount, uint64 sourceNonce);
    event Released(address indexed to, uint256 amount, uint64 destinationNonce, bool sourceVerified);
}

contract MockOracle is Ownable {                // prix en USD avec 8 décimales (style Chainlink)
    function setPriceE8(address asset, uint256 priceE8) external onlyOwner;
    function getPriceE8(address asset) external view returns (uint256);   // revert "Oracle: no price"
    event PriceUpdated(address indexed asset, uint256 priceE8);
}

// ---------- Protocole de prêt simplifié (déployé deux fois : lend-eth, lend-avax) ----------
contract MiniLend {
    struct ReserveData {
        address asset;
        uint256 totalSupplied;       // somme déposée côté prêt (actifs empruntables)
        uint256 totalBorrowed;
        uint256 availableLiquidity;  // totalSupplied - totalBorrowed
        uint256 utilizationBps;      // totalBorrowed * 10000 / totalSupplied (0 si rien)
        uint256 supplyRateBps;       // annualisé, indicatif (pas d'accumulation d'intérêts dans le MVP)
        uint256 borrowRateBps;
        uint256 totalCollateral;     // somme déposée en garantie (actifs collatéral)
        uint16  ltvBps;              // 0 si l'actif n'est pas un collatéral
        bool    borrowable;
        bool    frozen;              // gel : plus de nouveaux dépôts ni emprunts ; retraits et remboursements OK
        bool    paused;              // pause : tout est bloqué
    }
    address public protocolGuardian;
    IMockOracle public oracle;

    // Côté prêt (USDC, WETH)
    function supply(address asset, uint256 amount, address onBehalfOf) external;   // revert "MiniLend: frozen" / "paused" / "not borrowable"
    function withdraw(address asset, uint256 amount, address to) external returns (uint256 withdrawn);
        // amount = type(uint256).max : retire min(position, liquidité disponible), renvoie 0 sans revert s'il n'y a rien à retirer
        // sinon : revert "MiniLend: insufficient balance" si amount > position, "MiniLend: insufficient liquidity" si amount > liquidité
    // Côté garantie (rsETH)
    function depositCollateral(address asset, uint256 amount) external;            // revert "MiniLend: not collateral" / "frozen"
    function borrow(address asset, uint256 amount) external;
        // contrôle : valeur empruntée totale (oracle) <= valeur des garanties * ltv ; revert "MiniLend: insufficient collateral" / "insufficient liquidity"
    function repay(address asset, uint256 amount) external;                         // plafonné à la dette
    // Administration (protocolGuardian uniquement, revert "MiniLend: only guardian")
    function listReserve(address asset, bool borrowable, uint16 ltvBps) external;
    function setReserveFrozen(address asset, bool frozen) external;
    function setReservePaused(address asset, bool paused) external;
    function setLtv(address asset, uint16 ltvBps) external;
    // Lecture
    function getAssets() external view returns (address[] memory);
    function getReservesData() external view returns (ReserveData[] memory);         // une entrée par actif listé, dans l'ordre de getAssets()
    function getUserSupplied(address user, address asset) external view returns (uint256);
    function getUserCollateral(address user, address asset) external view returns (uint256);
    function getUserBorrowed(address user, address asset) external view returns (uint256);

    event Supplied(address indexed asset, address indexed from, address indexed onBehalfOf, uint256 amount);
    event Withdrawn(address indexed asset, address indexed user, address to, uint256 amount);
    event CollateralDeposited(address indexed asset, address indexed user, uint256 amount);
    event Borrowed(address indexed asset, address indexed user, uint256 amount);
    event Repaid(address indexed asset, address indexed user, uint256 amount);
    event ReserveListed(address indexed asset, bool borrowable, uint16 ltvBps);
    event ReserveFrozen(address indexed asset, bool frozen);
    event ReservePaused(address indexed asset, bool paused);
    event LtvUpdated(address indexed asset, uint16 ltvBps);
}
// Modèle de taux (identique partout, y compris dans les fixtures) :
//   U = utilisation (0..1). Si U <= 0.8 : borrow = 100 + 300 * U / 0.8 (bps) ; sinon borrow = 400 + 7500 * (U - 0.8) / 0.2.
//   supply = borrow * U * 0.85. À U = 100 % : borrow = 7900 bps, supply = 6715 bps (le rendement-appât).

// ---------- Le coffre (Safe simplifié du MVP) ----------
contract TreasuryVault {
    address public owner;            // représente les signataires du Safe
    address public guardian;         // clé de notre plateforme : ne peut que resserrer
    bool public depositsPaused;
    function supply(address market, address asset, uint256 amount) external;     // owner ; utilise le SOLDE DU COFFRE (envoyer les jetons au coffre d'abord) ; revert "Vault: deposits paused" / "Vault: only owner"
    function withdraw(address market, address asset, uint256 amount) external;    // owner
    function emergencyWithdraw(address market, address asset) external returns (uint256 withdrawn);
        // owner ou guardian ; retire min(position, liquidité) VERS LE COFFRE LUI-MÊME ; renvoie 0 (et émet l'event) s'il n'y a rien à retirer ;
        // revert "Vault: only guardian or owner" ; revert "MiniLend: paused" si la réserve est en pause (l'action passe alors en failed)
    function pauseDeposits() external;      // owner ou guardian ; idempotent (pas de revert si déjà en pause)
    function unpauseDeposits() external;    // owner uniquement (décision humaine)
    function setGuardian(address g) external; // owner
    event DepositsPaused(address indexed by);
    event DepositsUnpaused(address indexed by);
    event EmergencyWithdrawal(address indexed market, address indexed asset, uint256 amount, address indexed by);
    event Supplied(address indexed market, address indexed asset, uint256 amount);
    event Withdrawn(address indexed market, address indexed asset, uint256 amount);
}

// ---------- Registre des preuves ----------
contract EvidenceRegistry {
    mapping(bytes32 => uint256) public anchoredAt;   // empreinte -> numéro de bloc (0 si jamais ancrée)
    function anchor(bytes32 recordHash, string calldata kind, string calldata uri) external;
        // revert "Evidence: already anchored" ; kind ∈ {"decision", "rules", "incident"} ; pas de contrôle d'accès dans le MVP (clé evidence par convention)
    event Anchored(bytes32 indexed recordHash, string kind, string uri, address indexed by);
}
```

**Paramètres du déploiement initial** (fixés pour que fixtures, tests et démo concordent) :

| Élément | Valeur |
|---|---|
| Prix oracle | USDC = 1,00 $ ; WETH = 2 500 $ ; rsETH = 2 500 $ |
| Réserves de `lend-eth` et `lend-avax` | USDC (empruntable et collatéral, LTV 8 000 bps), WETH (empruntable et collatéral, LTV 8 000 bps), rsETH (collatéral seul, LTV 7 500 bps). Côté prêt et côté garantie sont deux soldes séparés : la garantie ne s'ajoute pas à la liquidité empruntable. |
| Liquidité initiale `lend-eth` | WETH : 2 000 déposés dont 150 par le coffre, 1 200 empruntés (utilisation 60 %) ; USDC : 3 000 000 déposés dont 400 000 par le coffre, 1 800 000 empruntés |
| Liquidité initiale `lend-avax` | WETH : 1 000 déposés dont 100 par le coffre, 550 empruntés ; USDC : 2 000 000 déposés dont 300 000 par le coffre, 1 100 000 empruntés |
| Garanties des emprunteurs normaux (bots) | `lend-eth` : 900 rsETH + 4 500 000 USDC (capacité 5 287 500 $ pour 4 800 000 $ empruntés) ; `lend-avax` : 300 rsETH + 3 000 000 USDC (capacité 2 962 500 $ pour 2 475 000 $ empruntés) |
| rsETH avant attaque | 1 200 en circulation, 1 200 WETH de couverture (100 %) ; 900 en garantie sur `lend-eth`, 300 sur `lend-avax` |
| Attaque par défaut | `forgedRelease` de 5 000 rsETH, dépôt en garantie sur `lend-eth`, emprunts de 100 WETH par tranche toutes les 8 s jusqu'à épuisement, 2 retraits de 100 WETH par des bots pendant le vidage, gel du rsETH par le guardian du protocole en fin de scénario |

### 2.3 Fichier `deployments/<network>.json` (écrit par T1, lu par tout le monde)

```json
{
  "network": "fuji",
  "chain_id": 43113,
  "deployed_at_block": 45201700,
  "explorer": "https://testnet.snowtrace.io",
  "assets": { "USDC": "0x…", "WETH": "0x…", "rsETH": "0x…" },
  "contracts": { "MockBridge": "0x…", "MockOracle": "0x…", "TreasuryVault": "0x…", "EvidenceRegistry": "0x…" },
  "lending": [
    { "id": "lend-eth",  "label": "Lending protocol, Ethereum deployment (simulated)",  "address": "0x…" },
    { "id": "lend-avax", "label": "Lending protocol, Avalanche deployment (simulated)", "address": "0x…" }
  ],
  "roles": { "deployer": "0x…", "owner": "0x…", "guardian": "0x…", "protocol_guardian": "0x…",
             "attacker": "0x…", "evidence": "0x…", "bots": ["0x…", "0x…", "0x…"] }
}
```

ABIs : `abi/MockERC20.json`, `abi/RsETH.json`, `abi/MockBridge.json`, `abi/MockOracle.json`, `abi/MiniLend.json`, `abi/TreasuryVault.json`, `abi/EvidenceRegistry.json` (format : la liste ABI JSON brute).

### 2.4 Helpers Python partagés (`backend/chain.py`, T0)

Tout le code Python passe par ces fonctions (personne ne réécrit son propre chargement d'ABI ou sa gestion de nonce).

```python
def w3() -> Web3                                   # client du réseau courant (RPC_URL)
def load_deployment() -> dict                      # relit deployments/<network>.json à chaque appel (un redéploiement est pris en compte)
def load_abi(name: str) -> list                    # abi/<name>.json
def token(symbol: str) -> Contract                 # "USDC" | "WETH" | "rsETH" (ABI MockERC20, RsETH pour rsETH)
def lending(deployment_id: str) -> Contract        # "lend-eth" | "lend-avax" (ABI MiniLend)
def vault() -> Contract                            # TreasuryVault
def bridge() -> Contract                           # MockBridge
def oracle() -> Contract                           # MockOracle
def registry() -> Contract                         # EvidenceRegistry
def account(role: str) -> LocalAccount             # "deployer" | "owner" | "guardian" | "protocol_guardian" | "attacker" | "evidence"
def bot_accounts() -> list[LocalAccount]
def send(fn, sender: LocalAccount, value: int = 0) -> dict
    # construit, signe, envoie, attend le reçu ; un verrou par expéditeur évite les conflits de nonce
    # retourne {"tx_hash": "0x…", "status": 1|0, "block_number": int, "gas_used": int}
def explorer_tx(tx_hash: str) -> str               # lien snowtrace
```

### 2.5 Conventions de données

- **Montants de jetons** : chaînes en unités de base (`"150000000000000000000"` = 150 WETH). Jamais de float pour un montant on-chain.
- **Valeurs en dollars** : float, pour l'affichage et l'exposition.
- **Taux et ratios** : entiers en points de base (1 % = 100 bps).
- **Temps** : datetime UTC avec fuseau, sérialisé ISO 8601 (`2026-10-11T08:00:26Z`). On garde toujours aussi le numéro de bloc.
- **Actifs** : par symbole (`USDC`, `WETH`, `rsETH`). **Déploiements** : par id (`lend-eth`, `lend-avax`).
- **Clés JSON** : snake_case. Toutes les clés du modèle sont toujours présentes, `null` quand vide (jamais d'`exclude_none`).
- **Identifiants** :
  - alerte : `ALT-<network>-<block>-<rule_id>-<deployment_id ou global>-<asset ou all>`
  - décision : `DEC-<network>-<block>-<n>` (n = 1, 2… dans le même bloc)
  - incident : `INC-<yyyymmdd>-<nnn>`
  - run de scénario : `RUN-<yyyymmddHHMMSS>-<kind>-<seed>`

### 2.6 Modèles de données (`backend/models.py`, T0, source de vérité)

Résumé des objets échangés entre les tâches. Le fichier Python fait foi ; les types TypeScript du front (`frontend/src/types.ts`) en sont le miroir exact.

| Objet | Produit par | Lu par | Champs principaux |
|---|---|---|---|
| `Snapshot` | T3 (collector) ; T7 (rejeu, phase 2) | T3, T4, T5, T7 | `network, chain_id, block_number, block_time, source, reserves[], tokens[], positions[], vault` |
| `ReserveSnapshot` | T3 | T3, T4, T6 | `deployment_id, asset, asset_address, decimals, total_supplied, total_borrowed, available_liquidity, total_collateral, utilization_bps, supply_apy_bps, borrow_apy_bps, ltv_bps, borrowable, frozen, paused, price_usd` |
| `TokenSnapshot` | T3 | T3, T6 | `symbol, address, decimals, total_supply, backing, backing_ratio_bps, price_usd, bridge_source_locked, bridge_destination_released, bridge_source_nonce, bridge_destination_nonce, bridge_paused` (champs bridge seulement pour rsETH) |
| `PositionSnapshot` | T3 | T3, T4, T5, T6 | `wallet, deployment_id, asset, supplied, withdrawable_now, withdrawable_ratio_bps, value_usd, withdrawable_usd` |
| `VaultStatus` | T3 | T4, T6 | `address, deposits_paused, idle_balances{symbol: base units}` |
| `Alert` | T3 | T4, T5, T6, T7 | `id, rule_id, severity, network, deployment_id, asset, block_number, block_time, detected_at, title, explanation, metrics{}, exposure_usd, rules_version` |
| `Action` | T4 | T4, T5, T6 | `type, mode, status, params{}, tx_hash, amount, executed_at, note` |
| `Decision` | T4 | T5, T6, T7 | `id, created_at, network, block_number, alert_ids[], severity, exposure_usd, withdrawable_usd, exit_cost_bps, matrix_cell, rationale, actions[], inputs_hash, rules_version, playbook_version, record_hash, anchor_tx, anchor_block` |
| `VerifyResult` | T4 | T6 | `decision_id, match, stored_hash, recomputed_hash, anchored, anchor_tx, anchor_block, diffs[]` |
| `Incident` | T5 | T6, T9 | `id, title, status, severity, opened_at, detected_at, contained_at, alert_ids[], decision_ids[], exposure_usd, saved_usd, at_risk_usd, dora, timeline[]` |
| `DoraAssessment` | T5 | T6 | `criteria, thresholds_met[], is_major, legal_basis, aware_at, classified_at, deadlines, report_markdown, ai_drafted_sections[], submitted, submitted_by, submitted_at` |
| `Dependency` | T5 | T6 | `id, name, kind, provider, criticality, supports[], fallback, status` |
| `StateResponse`, `SeriesPoint`, `Health` | T3 | T6 | voir 2.9 |
| `DemoRun`, `RunRecord` | T2 | T6, T7 | voir T2 |
| `EvalMetrics` | T7 | T6, T9 | voir T7 |

Définitions à respecter :

- `StateResponse.totals` : `idle_usd` = Σ soldes du coffre × prix ; `withdrawable_usd` = Σ `withdrawable_usd` des positions ; `value_usd` = Σ `value_usd` des positions + `idle_usd` ; `at_risk_usd` = Σ (`value_usd` − `withdrawable_usd`) des positions.
- `StateResponse.risk_level` : gravité maximale des conditions **encore vraies** au dernier snapshot (une alerte dont la condition a disparu ne compte plus) ; `info` sinon.
- `EvalMetrics.synthetic` : les `*_rate` sont des fractions de 0 à 1 ; les `*_pct_*` sont en pourcentage de 0 à 100 ; `ttd_blocks_p50` et `ttd_blocks_p90` valent `-1` si aucune attaque n'est détectée.
- `DoraCriteria` contient aussi trois champs optionnels de l'art. 9(1) : `counterparts_affected_pct` (défaut 0), `transactions_affected_count_pct` (défaut 0), `relevant_clients_affected` (défaut false).

Valeurs autorisées : `severity ∈ {info, warning, high, critical}` ; `Action.type ∈ {NOTIFY, PAUSE_DEPOSITS, EMERGENCY_WITHDRAW, FULL_EXIT, UNPAUSE_DEPOSITS, OPEN_INCIDENT}` ; `Action.mode ∈ {auto, human}` ; `Action.status ∈ {planned, executed, failed, skipped, pending_approval, approved, rejected}`.

### 2.7 Règles de détection KelpDAO du MVP

Cinq règles déterministes suivent la chaîne causale de l'incident : faux message bridge → afflux de rsETH en garantie → extraction des actifs liquides → perte de retrait de notre coffre → confinement officiel. Aucun LLM ou modèle ML ne décide d'une alerte. Les seuils sont figés dans `backend/config/rules.yaml` avant les runs d'évaluation.

| Id | Indicateur | Portée | Condition | Gravité |
|---|---|---|---|---|
| `R1_BRIDGE_INVARIANT` | écart de conservation du bridge : `destination_released - source_locked` et cohérence des nonces | global, par jeton ponté (rsETH) | écart > 0 ou `destination_nonce > source_nonce` | critical |
| `R2_COLLATERAL_SURGE` | hausse du rsETH déposé en garantie par rapport au maximum des snapshots précédents de la fenêtre | chaque déploiement qui accepte rsETH en garantie | hausse ≥ 50 % → high ; ≥ 200 % → critical | high / critical |
| `R3_LIQUIDITY_DRAIN` | baisse de la liquidité disponible par rapport à son maximum sur les snapshots précédents de la fenêtre | chaque réserve empruntable où le coffre a une position | baisse ≥ 30 % → high ; ≥ 60 % → critical | high / critical |
| `R4_EXITABILITY_DROP` | part réellement retirable de notre position : `withdrawable_ratio_bps` | chaque position du coffre | < 80 % → high ; < 50 % → critical | high / critical |
| `R5_CONTAINMENT` | bridge/token pausé ou réserve gelée/pause, transition false → true | bridge global et réserves des déploiements exposés | changement d'état on-chain | high ; critical si `withdrawable_ratio_bps < 5000` |

Précisions communes :

- **R1 détecte la cause réelle.** L'incident KelpDAO était une libération de rsETH par un faux message cross-chain sans verrouillage/burn canonique correspondant, pas un simple piratage d'Aave. Le mock peut matérialiser cela par `forgedRelease`, mais doit conserver séparément la comptabilité source et destination.
- **R2 détecte la propagation.** On surveille l'augmentation de `total_collateral` de la réserve rsETH ; le snapshot courant n'entre pas dans la baseline. Si moins de deux snapshots précédents existent ou si la baseline vaut 0, aucune alerte de ratio n'est calculée.
- **R3 détecte l'extraction.** Elle remplace le doublon « utilisation élevée » : la liquidité disponible est le signal directement lié à la capacité de sortie.
- **R4 mesure notre risque réel.** Une valeur comptable ou un prix stable ne signifie pas que la position peut être retirée.
- **R5 est une confirmation tardive**, jamais le seul mécanisme de détection. Une annonce ou un texte externe ne suffit pas : l'état doit être relu on-chain.
- **Exposition** (`exposure_usd`) : R1 = toutes les positions dans les déploiements acceptant rsETH ; R2 et R5 = toutes les positions du déploiement ; R3 et R4 = position de la réserve concernée.
- **Pas de doublon** : une alerte `(rule_id, deployment_id, asset)` n'est émise qu'une fois par gravité. Elle est ré-émise seulement si la gravité monte, ou si la condition disparaît puis revient.
- **Explication** : une phrase en anglais avec cause et chiffres observés.
- `rules_version` = `"sha256:" + sha256(contenu exact de rules.yaml)`.
- `window_snapshots` par défaut : 20. Il s'agit de snapshots, pas de blocs.

`backend/config/rules.yaml` initial :

```yaml
version: 2
window_snapshots: 20
R1_BRIDGE_INVARIANT:  { enabled: true }
R2_COLLATERAL_SURGE:  { enabled: true, asset: rsETH, high_increase_pct: 50, critical_increase_pct: 200 }
R3_LIQUIDITY_DRAIN:   { enabled: true, high_drop_pct: 30, critical_drop_pct: 60 }
R4_EXITABILITY_DROP:  { enabled: true, high_below_bps: 8000, critical_below_bps: 5000 }
R5_CONTAINMENT:       { enabled: true, critical_withdrawable_below_bps: 5000 }
```

### 2.8 Matrice de réponse du MVP (`backend/config/playbook.yaml`, T4)

| Gravité de l'alerte | Exposition | Actions (dans cet ordre) |
|---|---|---|
| critical | ≥ 1 000 $ | `NOTIFY` (auto) → `PAUSE_DEPOSITS` (auto, si pas déjà en pause) → `EMERGENCY_WITHDRAW` (auto) pour **chaque position concernée** dont `withdrawable_now > 0` → `OPEN_INCIDENT` (auto) → `UNPAUSE_DEPOSITS` (human, `pending_approval`) |
| high | ≥ 1 000 $ | `NOTIFY` (auto) → `PAUSE_DEPOSITS` (auto) → `EMERGENCY_WITHDRAW` (human, `pending_approval`) pour chaque position concernée → `OPEN_INCIDENT` (auto) |
| warning | toute | `NOTIFY` (auto) |
| info, ou exposition < 1 000 $ | — | `NOTIFY` (auto) si gravité ≥ high, sinon rien |

« Positions concernées » : pour R1, toutes les positions du coffre dans les déploiements qui acceptent le jeton en garantie ; pour R2 à R4, la position de la réserve ; pour R5, toutes les positions du déploiement.
Une décision regroupe toutes les alertes nouvelles d'un même snapshot. `exit_cost_bps` = 0 dans le MVP (un retrait sur un protocole de prêt ne coûte que le gas). `matrix_cell` = `"<severity>|exposure>=1k|exit_possible"` ou `"…|no_liquidity"`.

### 2.9 API HTTP (préfixe `/api`, port 8000)

Tant que `USE_FIXTURES=true`, chaque route renvoie la fixture indiquée (le squelette T0 le fait déjà). Chaque tâche propriétaire branche ensuite les vraies données.

| Méthode et route | Paramètres | Réponse | Propriétaire | Fixture |
|---|---|---|---|---|
| `GET /api/health` | — | `Health` | T3 | `health.json` |
| `GET /api/state` | — | `StateResponse` | T3 | `state.json` |
| `GET /api/series` | `deployment_id`, `asset`, `limit` (≤ 2000, défaut 300) | `SeriesPoint[]` (ordre chronologique) | T3 | `series.json` |
| `GET /api/alerts` | `since_block` (défaut 0) | `Alert[]` (plus récentes d'abord) | T3 | `alerts.json` |
| `GET /api/decisions` | — | `Decision[]` (plus récentes d'abord) | T4 | `decisions.json` |
| `POST /api/decisions/{id}/approve` | `{"action_index": int, "approver": str, "approve": bool}` | `Decision` (l'action passe `approved` puis `executed`, ou `rejected`) | T4 | — |
| `POST /api/verify/{decision_id}` | — | `VerifyResult` | T4 | `verify.json` |
| `GET /api/incidents` | — | `Incident[]` | T5 | `incident.json` (liste d'un élément) |
| `GET /api/incidents/{id}` | — | `Incident` | T5 | `incident.json` |
| `GET /api/incidents/{id}/report.md` | — | texte markdown | T5 | champ `dora.report_markdown` |
| `POST /api/incidents/{id}/submit` | `{"submitted_by": str}` | `Incident` (`dora.submitted = true`) | T5 | — |
| `GET /api/dependencies` | — | `Dependency[]` | T5 | `dependencies.json` |
| `POST /api/demo/attack` | `{"seed": int \| null, "variant": "default" \| "slow" \| "usdc"}` ; `seed = null` : le backend tire une graine au hasard et la renvoie ; `seed = 0` : paramètres par défaut, sans hasard | `DemoRun` (lancé en arrière-plan) | T2 | `demo_run.json` |
| `POST /api/demo/reset` | — | `DemoRun` (redéploie, re-seed, vide le store) | T2 | `demo_run.json` |
| `GET /api/demo/runs/{run_id}` | — | `DemoRun` | T2 | `demo_run.json` |
| `GET /api/metrics` | — | `EvalMetrics` (lit `data/eval/metrics.json`, sinon la fixture) | T7 | `metrics.json` |

Erreurs, toujours avec `{"detail": "..."}` :

| Code | Quand |
|---|---|
| 404 | id inconnu |
| 400 | `action_index` hors bornes |
| 409 | action qui n'est pas en `pending_approval` ; run de démo déjà en cours ; incident déjà soumis |
| 422 | corps invalide (validation FastAPI, ex. `submitted_by` vide) |
| 503 | `no snapshot yet` : le moteur n'a encore lu aucun bloc (le front affiche « Waiting for first block ») |

CORS ouvert (`*`).

### 2.10 Store et branchements internes (T0 fournit les signatures et des stubs)

```python
# backend/store.py (T0 ; en mémoire + écriture JSONL dans data/runtime/<network>/)
class Store:
    def add_snapshot(self, s: Snapshot) -> None
    def latest_snapshot(self) -> Snapshot | None
    def snapshots(self, limit: int = 500) -> list[Snapshot]
    def add_alerts(self, alerts: list[Alert]) -> None
    def alerts(self, since_block: int = 0) -> list[Alert]
    def add_decision(self, d: Decision) -> None
    def update_decision(self, d: Decision) -> None
    def decisions(self) -> list[Decision]
    def get_decision(self, decision_id: str) -> Decision | None
    def upsert_incident(self, i: Incident) -> None
    def incidents(self) -> list[Incident]
    def get_incident(self, incident_id: str) -> Incident | None
    def reset(self) -> None              # vide tout et incrémente generation
    generation: int                      # compteur de resets : le moteur vide sa fenêtre quand il change
store = Store()   # instance unique importée par tout le monde

# backend/engine.py (T3)
class Engine:
    def __init__(self, store: Store): ...
    def on_alerts(self, handler: Callable[[list[Alert], Snapshot], None]) -> None   # enregistre un abonné
    def process(self, snapshot: Snapshot) -> list[Alert]   # pur : règles sur la fenêtre, stocke, notifie les abonnés
    async def run_forever(self) -> None                     # boucle : nouveau bloc → collector → process

# backend/responder.py (T4)
class Responder:
    def __init__(self, store: Store, executor: "Executor"): ...
    def handle(self, alerts: list[Alert], snapshot: Snapshot) -> list[Decision]
    def on_decisions(self, handler: Callable[[list[Decision], list[Alert], Snapshot], None]) -> None

def plan_actions(alerts: list[Alert], snapshot: Snapshot, playbook: dict) -> list[Action]   # PUR, réutilisé par verify

# backend/incidents.py (T5)
class IncidentManager:
    def __init__(self, store: Store): ...
    def handle(self, decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot) -> Incident | None

# backend/executor.py (T4)
def get_executor() -> Executor   # singleton : DryRunExecutor si DRY_RUN_ACTIONS=true, sinon Web3Executor
```

Câblage (dans `backend/main.py`, T0) : `responder = Responder(store, get_executor())`, `engine.on_alerts(responder.handle)` puis `responder.on_decisions(incidents.handle)`. Chaque classe existe dès le départ sous forme de stub qui ne fait rien : chaque tâche remplace son stub par la vraie implémentation sans toucher au câblage.

Règles de fonctionnement partagées :

- **Abonnés hors de la boucle** : le moteur appelle les abonnés avec `await asyncio.to_thread(handler, alerts, snapshot)`, un appel à la fois, dans l'ordre des snapshots. Une réponse lente (transactions Fuji) ne bloque donc ni l'API ni le dashboard.
- **Mode maintenance** : tant que le fichier `data/runtime/<network>/maintenance.flag` existe, le moteur continue de lire et stocker les snapshots mais **n'évalue aucune règle**. Quand le fichier disparaît, ou quand `store.generation` change, il vide sa fenêtre. T2 crée ce fichier au début de `seed` et de `reset` et le supprime à la fin (dans un `finally`). Sans ça, l'installation de la liquidité ressemblerait à une attaque.

### 2.11 Commandes `make` (identiques pour tous)

Le `Makefile` racine (T0) contient `-include .env`, `export` des variables de 2.1, `include mk/*.mk` et les cibles transverses. Chaque tâche définit ses cibles dans `mk/tN.mk` et ne redéfinit jamais `NETWORK` (il vient de `.env` ou de la ligne de commande).

| Commande | Fait quoi | Défini par |
|---|---|---|
| `make setup` | installe les dépendances Python, npm, Foundry libs | T0 |
| `make chain` | lance anvil (`--block-time 1`) | T1 |
| `make deploy` | déploie sur `$NETWORK`, écrit `deployments/$NETWORK.json` et `abi/` ; sur fuji, exige `FORCE=1` si un déploiement existe déjà (les adresses changent : prévenir l'équipe) | T1 |
| `make abi` | exporte les ABIs | T1 |
| `make seed` / `make attack SEED=42` / `make normal MINUTES=5` / `make reset` | scénario | T2 |
| `make backend` | `uvicorn backend.main:app --reload --port 8000` | T0 |
| `make frontend` | `npm run dev` dans `frontend/` | T6 |
| `make demo` | chaîne locale + déploiement + seed + backend avec `ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false` + frontend | T0 |
| `make verify ID=DEC-…` / `make tamper ID=… FIELD=… VALUE=…` / `make restore ID=…` | vérifier, falsifier pour la démo, restaurer une preuve | T4 |
| `make eval RUNS=10` | évaluation synthétique sur chaîne locale | T7 |
| `make test` | toutes les suites (appelle `test-t0` … `test-t9`) | T0 |
| `make test-tN` | tests de la tâche N | TN |
| `make deploy-aws` | déploiement sur EC2 | T8 |

### 2.12 Changer le contrat

1. Écris la demande dans `docs/contract-requests.md` : quoi, pourquoi, qui est impacté.
2. La personne qui tient T0 valide, met à jour `models.py`, les fixtures (`python -m fixtures._generate`), `types.ts` et ce document, en **un seul commit** préfixé `contract:`.
3. Tout le monde rebase. Ajouter un champ optionnel ne casse personne ; renommer ou supprimer un champ est interdit sans accord de toutes les tâches concernées.

### 2.13 Fixtures disponibles (`fixtures/`, T0)

| Fichier | Contenu | Utilisé par |
|---|---|---|
| `snapshots_attack.jsonl` | 41 `Snapshot` (un tous les 2 blocs) du scénario **sans** notre réaction | T3 (tests des règles), T4 (tests de la matrice) |
| `snapshots_normal.jsonl` | 41 `Snapshot` d'une journée normale (gros dépôt légitime, gros emprunt légitime, rsETH adossé) | T3 (zéro alerte ≥ high), T7 |
| `health.json` `state.json` `series.json` `alerts.json` `decisions.json` `verify.json` `incident.json` `dependencies.json` `metrics.json` `demo_run.json` | réponses d'API valides, cohérentes avec le scénario **avec** notre réaction : alerte R1 et décision `DEC-fuji-45201812-1` au bloc 45 201 812, tout rapatrié (1 325 000 $), incident contenu. `series.json` est un objet indexé par `"<deployment_id>:<asset>"` (la route, elle, renvoie un tableau) | T6 (front), squelette d'API |
| `deployments.example.json` `run_record.example.json` | formats de référence | T1, T2, T7 |
| `_generate.py` | régénère tout depuis `models.py` | T0 |

---

## 3. Fiches détaillées des tâches (pour Claude Code)

Chaque tâche suit le même plan :
- **Objectif**, puis ce dont elle dépend et ce qu'elle débloque ;
- **Fichiers possédés** ;
- **Entrées et sorties**, avec les maquettes à utiliser en attendant ;
- **Spécification détaillée** ;
- **Tests qui doivent passer** et **definition of done** ;
- **Pièges connus** et **phase 2** ;
- **Prompt de démarrage** à coller dans Claude Code.

### 3.0 Vue d'ensemble

| Tâche | Ce qu'elle livre | A besoin de (maquette en attendant) | Débloque |
|---|---|---|---|
| **T0** Fondations | squelette du repo, modèles, helpers, store, stubs, API sur fixtures, fixtures, Makefile, garde-fous | rien | tout le monde |
| **T1** Contrats on-chain | jetons, bridge rsETH avec sa faille, oracle, 2 protocoles de prêt, coffre avec guardian, registre de preuves ; déploiement local et Fuji ; ABIs ; financement des rôles en AVAX de test | T0 | T2, T3, T4, T7, T8, T9 |
| **T2** Scénario | seed, attaque (3 variantes, graine aléatoire), trafic normal, reset, vérité terrain des runs, routes de démo | T1 (chaîne locale dès que `make deploy` marche) | T3, T4, T5, T6, T7 |
| **T3** Surveillance | collecteur, règles R1 à R5, moteur, routes d'état | T1/T2 (séries `fixtures/snapshots_*.jsonl`) | T4, T5, T6, T7 |
| **T4** Réponse et preuves | matrice, exécution on-chain, notifications, preuves ancrées, `verify`, approbations | T3 (alertes construites à la main), T1 (dry-run) | T5, T6, T7, T9 |
| **T5** Incident et DORA | incidents, chronologie, classification DORA, rapport, registre des dépendances | T4 (décisions construites à la main) | T6, T9 |
| **T6** Dashboard | toutes les vues, démo pilotable | T3, T4, T5, T2, T7 (fixtures, puis squelette T0) | T9 (captures, vidéo) |
| **T7** Évaluation | métriques simples sur runs synthétiques, rapport | T2, T3, T4 (chaîne locale) | T6, T9 |
| **T8** AWS et CI | images, compose, EC2, SNS, S3, Bedrock, CI, plan de repli | T0 (puis tout le reste pour la mise en ligne) | E2E-3, T9 |
| **T9** Livrables | README, playbook, conformité, defense sheet, deck, vidéo, pitch | tout (chiffres provisoires marqués en attendant) | la soumission |


### T0 · Fondations du repo et contrat partagé

**Objectif.** Poser le squelette commun pour que chaque tâche démarre seule dès la première minute : arborescence, contrat de données en code, helpers blockchain, store, stubs des classes branchées entre elles, API qui sert les fixtures sur toutes les routes, fixtures cohérentes, Makefile, garde-fous de sécurité. C'est **le premier commit mergé sur `main`** ; toutes les branches partent de lui. La personne qui tient T0 valide ensuite les demandes de changement du contrat (2.12) et coordonne l'intégration (section 4).

**Dépend de.** Rien.

**Débloque.** Toutes les tâches.

**Fichiers possédés.**
- Définitivement T0 : `TASKS.md`, `CLAUDE.md`, `Makefile`, `mk/t0.mk`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `requirements.txt`, `backend/__init__.py`, `backend/api/__init__.py`, `backend/tests/__init__.py`, `scenario/__init__.py`, `evaluation/__init__.py`, `backend/main.py`, `backend/models.py`, `backend/settings.py`, `backend/chain.py`, `backend/store.py`, `backend/fixtures.py`, `fixtures/*`, `frontend/src/types.ts`, `docs/contract-requests.md`, `backend/tests/test_t0_*.py`.
- Créés par T0 sous forme de **stub**, puis la propriété passe à la tâche indiquée : `backend/engine.py`, `backend/collector.py`, `backend/rules.py`, `backend/api/state.py` (→ T3) ; `backend/responder.py`, `backend/executor.py`, `backend/api/response.py` (→ T4) ; `backend/incidents.py`, `backend/api/incidents.py` (→ T5) ; `backend/api/demo.py` (→ T2) ; `backend/api/metrics.py` (→ T7) ; `backend/config/rules.yaml` (→ T3) ; `backend/config/playbook.yaml` (→ T4).

**À lire avant de commencer.** Sections 1 et 2 en entier.

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| Contrat d'interface | section 2 de ce document | — | — |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| `backend/models.py` | modèles Pydantic v2 de 2.6 | toutes les tâches Python |
| `frontend/src/types.ts` | miroir TypeScript exact des modèles (mêmes noms, mêmes champs, `string` pour les montants, `string` ISO pour les dates, unions littérales pour les enums) | T6 |
| `backend/settings.py` | variables de 2.1, repli sur les comptes anvil en local | toutes les tâches Python |
| `backend/chain.py` | fonctions de 2.4 | T2, T3, T4, T7 |
| `backend/store.py` | classe `Store` de 2.10 + instance `store` | T2, T3, T4, T5, T7 |
| Stubs `Engine`, `Responder`, `plan_actions`, `IncidentManager`, `Executor` | signatures de 2.10, comportement « ne fait rien » | T3, T4, T5 les remplacent |
| `backend/main.py` | app FastAPI, CORS, 5 routeurs, câblage de 2.10, démarrage du moteur si `ENGINE_ENABLED=true` | tout le monde |
| Routeurs stubs | toutes les routes de 2.9, réponses = fixtures | T6 dès la première minute |
| `fixtures/` | fichiers de 2.13, régénérables par `python -m fixtures._generate` | T3, T4, T5, T6, T7 |
| `Makefile` + `mk/t0.mk` | `include mk/*.mk`, cibles `setup`, `backend`, `demo`, `test`, `help`, `test-t0` | tout le monde |
| `.env.example` | toutes les variables de 2.1, valeurs vides, une ligne de commentaire chacune | tout le monde |
| `CLAUDE.md` | règles pour tous les Claude Code (voir étape 12) | tout le monde |

#### Spécification détaillée

1. **Arborescence.** Créer exactement les dossiers de 1.5, avec un `__init__.py` dans `backend/`, `backend/api/`, `backend/tests/`, `scenario/`, `evaluation/`, `fixtures/`.

2. **`requirements.txt`** (un seul environnement Python pour backend, scénario, évaluation) :
   ```
   fastapi>=0.111
   uvicorn[standard]>=0.30
   pydantic>=2.7
   web3>=6.20,<8
   eth-account>=0.11
   eth-utils>=4
   python-dotenv>=1.0
   pyyaml>=6
   boto3>=1.34
   httpx>=0.27
   pytest>=8
   pytest-asyncio>=0.23
   ```

3. **`backend/models.py`** : les modèles de 2.6, avec la docstring des conventions de 2.5. Aucune logique.

4. **`backend/settings.py`** : lit `.env` à la racine (python-dotenv), expose les variables de 2.1, `DEPLOYMENTS_FILE`, `ABI_DIR`, `FIXTURES_DIR`, `DATA_DIR`, `CONFIG_DIR`, `private_key(role)` et `bot_pks()`. En `local`, sans variable, les clés sont dérivées de la mnémonique publique d'anvil (`test test test test test test test test test test test junk`, chemin `m/44'/60'/0'/0/<index>`, index de 2.1). Rien n'est jamais écrit sur disque.

5. **`backend/chain.py`** : les fonctions de 2.4. `token("rsETH")` utilise l'ABI `RsETH`, les autres jetons `MockERC20`. `send()` prend un verrou par adresse d'expéditeur, lit le nonce `pending`, estime le gas (× 1,3), signe, envoie, attend le reçu (timeout 120 s) et renvoie `{"tx_hash", "status", "block_number", "gas_used"}` ; compatible web3.py 6 et 7 (`raw_transaction` ou `rawTransaction`).

6. **`backend/store.py`** : la classe de 2.10, thread-safe (un `threading.RLock`). Données en mémoire ; chaque ajout est aussi écrit en JSONL dans `data/runtime/<network>/` (`snapshots.jsonl`, `alerts.jsonl`, `decisions.jsonl`, `incidents.jsonl`). `snapshots(limit)` garde au plus 2 000 snapshots en mémoire. `reset()` vide la mémoire et renomme les fichiers JSONL avec un suffixe horodaté. `update_decision` remplace par id ; `upsert_incident` insère ou remplace par id.

7. **Stubs** (même signature que 2.10, docstring « STUB T0, à remplacer par TN ») :
   - `backend/engine.py` : `Engine.on_alerts` mémorise les abonnés ; `process` stocke le snapshot et renvoie `[]` ; `run_forever` boucle sur `asyncio.sleep(POLL_INTERVAL_S)` sans rien lire.
   - `backend/collector.py` : `build_snapshot(block_number: int | None = None) -> Snapshot` qui lève `NotImplementedError`.
   - `backend/rules.py` : `rules_version() -> str` (sha256 de `backend/config/rules.yaml`) et `evaluate(window, cfg) -> list[Alert]` qui renvoie `[]`.
   - `backend/responder.py` : `plan_actions(...)` renvoie `[]` ; `Responder.handle` renvoie `[]` ; `on_decisions` mémorise les abonnés.
   - `backend/executor.py` : protocole `Executor`, classe `DryRunExecutor` (hash factice `"0xdry" + sha256(params).hex()[:59]`), fonction `get_executor()` qui renvoie **toujours la même instance** (singleton), en dry-run si `DRY_RUN_ACTIONS=true`.
   - `backend/store.py` expose `generation` (entier incrémenté par `reset()`).
   - `backend/incidents.py` : `IncidentManager.handle` renvoie `None`.
   - `backend/config/rules.yaml` : le contenu exact de 2.7 ; `backend/config/playbook.yaml` : la matrice de 2.8 en YAML (structure libre, T4 la reprend).

8. **`backend/main.py`** : crée `app`, ajoute CORS `*`, inclut les routeurs `state`, `response`, `incidents`, `demo`, `metrics` avec le préfixe `/api`, instancie `engine = Engine(store)`, `responder = Responder(store, get_executor())`, `incidents = IncidentManager(store)`, branche `engine.on_alerts(responder.handle)` puis `responder.on_decisions(incidents.handle)`, et au démarrage lance `asyncio.create_task(engine.run_forever())` si `ENGINE_ENABLED=true`. Un seul worker uvicorn (le store est en mémoire).

9. **Routeurs stubs** : chaque route de 2.9 existe **une seule fois**, dans le fichier de sa tâche propriétaire : `api/state.py` (health, state, series, alerts), `api/response.py` (decisions, approve, verify), `api/incidents.py` (incidents, report.md, submit, dependencies), `api/demo.py`, `api/metrics.py`. Chaque route renvoie sa fixture validée par le modèle Pydantic ; `GET /api/series` extrait le tableau `"<deployment_id>:<asset>"` de `series.json` ; `GET /api/incidents` enveloppe `incident.json` dans une liste. `approve` et `submit` modifient la copie en mémoire et la renvoient. `metrics` lit `data/eval/metrics.json` s'il existe, sinon la fixture. Supprimer le dossier obsolète `backend/detectors/` s'il existe.

10. **Fixtures** : `fixtures/_generate.py` régénère tout à partir de `models.py`, avec les règles R1 à R5 de 2.7 et la matrice de 2.8. Histoire racontée par les fixtures « avec réaction » :
    - bloc 45 201 812 : faux message cross-chain, libération de 5 000 rsETH sans verrouillage source ; nonce destination 308, nonce source 307 ;
    - même bloc 45 201 812 (snapshot du bloc) : alerte `R1_BRIDGE_INVARIANT` critique, exposition 1 325 000 $, et décision `DEC-fuji-45201812-1` avec `NOTIFY`, `PAUSE_DEPOSITS`, 4 × `EMERGENCY_WITHDRAW` (lend-eth USDC, lend-eth WETH, lend-avax USDC, lend-avax WETH), `OPEN_INCIDENT`, `UNPAUSE_DEPOSITS` en attente d'approbation ; les transactions sont minées aux blocs suivants ;
    - état final : coffre en pause, 250 WETH + 700 000 USDC rapatriés, plus aucune position, `at_risk_usd = 0` ;
    - incident `INC-20261011-001` contenu, DORA majeur via 9(1) et 9(4) ;
    - `verify.json` = MATCH, avec le vrai `record_hash` de la décision.
    Les séries `snapshots_attack.jsonl` (sans réaction) et `snapshots_normal.jsonl` gardent les mêmes chiffres de marché ; seules les réserves USDC et WETH reçoivent `ltv_bps = 8000` et les garanties des bots de 2.2 (`total_collateral` USDC = 4 500 000 sur `lend-eth`, 3 000 000 sur `lend-avax`). `deployments.example.json` suit exactement 2.3 (`assets`, `contracts.MockBridge`, `contracts.MockOracle`…), `run_record.example.json` contient les 4 positions du coffre, `demo_run.json` utilise les paramètres `forged_amount`, `chunk_weth`, `interval_s`, `bot_withdrawals`.

11. **`Makefile`** : `-include .env` puis `export` des variables de 2.1, `include mk/*.mk`, `.PHONY`, cible `help` (liste les cibles et leur description avec `##`), `setup` (`pip install -r requirements.txt`, `npm --prefix frontend install` si `frontend/package.json` existe, `forge install` dans `contracts/` si `contracts/foundry.toml` existe), `backend` (un seul worker), `demo` (dans l'ordre : `chain` en arrière-plan, `deploy`, `seed`, backend avec `ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false`, `frontend`), `test` (exécute `test-t0` à `test-t9` quand elles existent). `mk/t0.mk` définit `test-t0` = `pytest backend/tests/test_t0_*.py`. Aucune cible ne fixe `NETWORK` : il vient de `.env` ou de la ligne de commande.

12. **`CLAUDE.md`** (court, pour tous les Claude Code) :
    - lire `TASKS.md` sections 1, 2 et sa tâche avant toute action ;
    - ne modifier que les fichiers possédés par sa tâche (1.5) ;
    - le contrat (section 2, `models.py`, `fixtures/`, `types.ts`) ne se change que via `docs/contract-requests.md` ;
    - écrire les tests avant le code, `make test-tN` vert avant chaque commit ;
    - aucune clé, aucun secret dans le code, les logs ou les commits ;
    - montants en chaînes d'unités de base, taux en bps, dates UTC ISO ;
    - code et UI en anglais.

13. **Sécurité** : `.gitignore` contient `.env`, `.env.*` sauf `!.env.example`, `data/runtime/`, `data/evidence/`, `data/runs/`, `data/reports/`, `data/eval/*` sauf `!data/eval/metrics.json` et `!data/eval/report.md`, `deployments/local.json`, `deployments/*.pending.json`, `node_modules/`, `frontend/dist/`, `frontend/.env*` sauf `!frontend/.env.example`, `contracts/out/`, `contracts/cache/`, `contracts/broadcast/*/31337/`, `__pycache__/`, `.venv/`. `.pre-commit-config.yaml` lance gitleaks. `.env.example` ne contient aucune valeur réelle.

14. **`docs/contract-requests.md`** : un modèle de demande (tâche, changement demandé, raison, tâches impactées, statut).

#### Tests qui doivent passer

| Id | Type | Commande | Résultat attendu |
|---|---|---|---|
| T0-01 | unitaire | `pytest backend/tests/test_t0_contract.py::test_fixtures_validate` | chaque fixture JSON se valide avec son modèle (`health`→`Health`, `state`→`StateResponse`, chaque point de `series`→`SeriesPoint`, `alerts`→`Alert[]`, `decisions`→`Decision[]`, `verify`→`VerifyResult`, `incident`→`Incident`, `dependencies`→`Dependency[]`, `metrics`→`EvalMetrics`, `demo_run`→`DemoRun`, `run_record.example`→`RunRecord`) et chaque ligne des deux `.jsonl` se valide en `Snapshot` (41 lignes chacune) |
| T0-02 | unitaire | `pytest backend/tests/test_t0_contract.py::test_fixture_story` | les alertes n'utilisent que `R1_BRIDGE_INVARIANT`…`R5_CONTAINMENT` ; la décision `DEC-fuji-45201812-1` contient exactement les 8 actions listées à l'étape 10, dans cet ordre ; `incident.saved_usd == 1325000.0` ; `state.totals` vaut `value_usd = 1325000`, `idle_usd = 1325000`, `withdrawable_usd = 0`, `at_risk_usd = 0` ; `state.positions == []` ; `verify.stored_hash == decisions[R1].record_hash` ; `deployments.example.json` a les clés `assets`, `contracts.MockBridge`, `contracts.MockOracle`, `contracts.TreasuryVault`, `contracts.EvidenceRegistry`, `lending`, `roles` |
| T0-03 | unitaire | `pytest backend/tests/test_t0_contract.py::test_record_hash_recomputes` | recalculer keccak256 du JSON canonique de la décision R1 (sans `record_hash`, `anchor_tx`, `anchor_block`) redonne `record_hash` |
| T0-04 | unitaire | `pytest backend/tests/test_t0_api.py::test_all_routes` | avec `USE_FIXTURES=true`, `TestClient` : toutes les routes de 2.9 répondent 200 et le corps se valide avec le modèle annoncé ; `GET /api/incidents/UNKNOWN` → 404 ; `POST /api/decisions/{id}/approve` avec `action_index` de l'action humaine renvoie le statut `approved` |
| T0-05 | unitaire | `pytest backend/tests/test_t0_settings.py::test_local_keys` | avec `NETWORK=local` et aucune clé : l'adresse de `account("deployer")` est `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266`, celle de `guardian` `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC`, `bot_accounts()` renvoie 3 comptes ; avec `NETWORK=fuji` et aucune clé, `private_key("guardian")` lève `RuntimeError` |
| T0-06 | unitaire | `pytest backend/tests/test_t0_store.py` | ajout, lecture, `since_block`, `update_decision`, `upsert_incident`, `reset()` vide tout ; écriture JSONL dans un dossier temporaire (variable `DATA_DIR` surchargée) |
| T0-07 | unitaire | `pytest backend/tests/test_t0_wiring.py` | `main.py` importe sans erreur ; `engine` a `responder.handle` parmi ses abonnés et `responder` a `incidents.handle` |
| T0-08 | manuel | `make backend` puis `curl -s localhost:8000/api/state` | renvoie la fixture `state.json` ; `localhost:8000/docs` liste toutes les routes de 2.9 |
| T0-09 | manuel | `make help` | liste au moins `setup backend demo test test-t0` |
| T0-10 | sécurité | `pre-commit run gitleaks --all-files` | aucun secret trouvé |
| T0-11 | typage | `npx -y -p typescript tsc --noEmit --strict frontend/src/types.ts` | compile sans erreur |

#### Definition of done

- [ ] Tous les tests T0 passent (`make test-t0`).
- [ ] `main` contient le squelette ; chaque tâche peut lancer `make backend` et obtenir les fixtures sur toutes les routes.
- [ ] `.env.example`, `CLAUDE.md`, `docs/contract-requests.md` présents.
- [ ] Les fixtures racontent l'histoire de l'étape 10 et se régénèrent sans erreur.
- [ ] Aucun fichier d'une autre tâche n'a été rempli au-delà du stub.

#### Pièges connus

- Ne pas mettre de logique métier dans les stubs : sinon la tâche propriétaire devra la défaire.
- Les clés anvil sont publiques : ne jamais les écrire dans un fichier versionné (gitleaks les détecte comme des clés privées).
- `types.ts` doit suivre `models.py` champ par champ ; une divergence casse le front en silence. Tout changement de modèle = régénérer fixtures + types dans le même commit.
- Pydantic sérialise les datetimes avec `Z` seulement si elles ont un fuseau : toujours créer les dates avec `timezone.utc`.

#### Plus tard (phase 2)

- Générer `types.ts` automatiquement depuis l'OpenAPI de FastAPI (`openapi-typescript`).
- Store persistant (SQLite) si le volume de snapshots le demande.

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T0 de TASKS.md (racine du repo) : les fondations communes.
1. Lis les sections 1 et 2 de TASKS.md, puis la section T0 en entier.
2. Crée exactement les fichiers listés dans « Fichiers possédés » de T0, et rien d'autre.
   Les stubs ne contiennent aucune logique métier.
3. Commence par les tests T0-01 à T0-07 (backend/tests/test_t0_*.py), puis le code.
4. make test-t0 doit être vert ; vérifie aussi T0-08 à T0-11.
5. Fais un seul commit "T0: repo foundations" et pousse sur main : toutes les autres tâches partent de ce commit.
```


---


### T1 · Contrats on-chain

**Objectif.** Écrire, tester et déployer (anvil puis Fuji) les 7 contrats de la section 2.2, **exactement** avec les signatures, événements et messages de revert donnés ; produire `deployments/<network>.json` (format 2.3) et les ABIs `abi/<Contrat>.json`. T1 **déploie et configure** (prix oracle, réserves listées, rôles du coffre) et, sur Fuji, **finance les rôles en AVAX de test** (`make fund-roles`) ; T1 ne mint aucun jeton et ne crée aucune position : c'est T2 (`make seed`).

**Dépend de.**
- T0 → squelette du repo, `Makefile` racine qui fait `include mk/*.mk`, `.env.example`, `.gitignore` (`contracts/out/`, `contracts/cache/`, `contracts/broadcast/*/31337/`), `backend/settings.py` → en attendant : lancer ses cibles avec `NETWORK=local make -f mk/t1.mk <cible>` (`mk/t1.mk` ne définit jamais `NETWORK`).
- Équipe / organisateurs → clé `DEPLOYER_PK` Fuji financée en AVAX (faucet) ; T1 finance ensuite tous les autres rôles depuis le deployer (`make fund-roles`) → en attendant : **anvil local** uniquement (aucune clé à écrire, comptes publics d'anvil).
- Rien d'autre : T1 est la racine du graphe, personne ne doit l'attendre longtemps (voir « livraison en deux temps » en 9).

**Débloque.** T2 (seed, attaque, reset appellent `make deploy`), T3 (collecteur : `getReservesData`, `sourceLocked`, `destinationReleased`, nonces bridge, `getUserSupplied`, `depositsPaused`), T4 (`pauseDeposits`, `emergencyWithdraw`, `unpauseDeposits`, `anchor`, `anchoredAt`), T7 (évaluation sur anvil), T8 (déploiement EC2 : adresses Fuji), T9 (adresses et liens Snowtrace dans le README).

**Fichiers possédés.** `contracts/**` (`foundry.toml`, `src/`, `script/`, `test/`, `lib/` via `forge install`), `deployments/**` (`local.json`, `fuji.json`, `fuji.md`, `history/`), `abi/**`, `mk/t1.mk`, `backend/tests/test_t1_deployment.py`.

**À lire avant de commencer.** TASKS.md sections 1.2, 1.5, 2.1, **2.2**, **2.3**, 2.4, 2.11 ; `backend/settings.py` (`ROLE_ENV`, `ANVIL_INDEX`, `private_key`) ; `backend/chain.py` (`load_abi` accepte une liste brute, `contract(name)` lit `contracts[name]`) ; `fixtures/deployments.example.json` (seules les **adresses** comptent, ses clés `Bridge`/`Oracle` sont périmées : la section 2.3 fait foi) ; dernière ligne de `fixtures/snapshots_attack.jsonl` (état final attendu de `lend-eth`).

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| Interfaces, events, reverts | section 2.2 (figée) | T0 | — |
| Paramètres de déploiement (prix, réserves, LTV) | tableau sous 2.2 | T0 | — |
| Format du fichier de déploiement | section 2.3 | T0 | — |
| Rôles et clés | `.env` : `DEPLOYER_PK`, `OWNER_PK`, `GUARDIAN_PK`, `PROTOCOL_GUARDIAN_PK`, `ATTACKER_PK`, `EVIDENCE_PK`, `BOT_PKS` (hex, avec ou sans `0x`) | chacun / organisateurs (Fuji) | local : mnémonique anvil `test test … junk`, index 0..8 (2.1) |
| Chaîne | anvil `127.0.0.1:8545` (31337) ou Fuji (43113) via `RPC_URL` | T1 (`make chain`) / fournisseur RPC | anvil |
| Adresses attendues sur anvil neuf | nonces 0 à 8 du deployer = adresses de `fixtures/*.json` | T0 | — |
| Foundry, OpenZeppelin v5.0.2, forge-std | `foundryup` ; `forge install` | T1 | — |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| `contracts/src/*.sol` | Solidity 0.8.24, un contrat par fichier du même nom | T2 (lecture), tous |
| `abi/MockERC20.json`, `RsETH.json`, `MockBridge.json`, `MockOracle.json`, `MiniLend.json`, `TreasuryVault.json`, `EvidenceRegistry.json` | **liste ABI JSON brute** (`[{"type":"function",…}]`), indentée 2, **commitée** | T2, T3, T4, T7 via `chain.load_abi` |
| `deployments/local.json` | format 2.3, `network="local"`, `chain_id=31337`, `explorer=""` (non commité) | T2, T3, T4, T7 |
| `deployments/fuji.json` | format 2.3, `chain_id=43113`, `explorer="https://testnet.snowtrace.io"`, **commité** | tous, organisateurs, jury |
| `deployments/fuji.md` | tableau markdown `Contrat | Adresse | Lien Snowtrace` | T9 (README), organisateurs |
| `deployments/history/fuji-<deployed_at_block>.json` | copie de chaque déploiement Fuji (l'ancien `fuji.json` y est archivé avant tout redéploiement) | traçabilité |
| AVAX de test sur chaque rôle Fuji | `make fund-roles AMOUNT=0.5` (deployer → owner, guardian, protocol_guardian, attacker, evidence, 3 bots) | T2, T4 (leurs transactions Fuji) |
| Cibles `make chain`, `make deploy`, `make abi`, `make fund-roles`, `make test-t1` (+ `t1-*`) | `mk/t1.mk` | tous, `make demo` (T0), `make reset` (T2) |

#### Spécification détaillée

**1. Projet Foundry.** `cd contracts && forge init --no-git --force .` puis `forge install foundry-rs/forge-std OpenZeppelin/openzeppelin-contracts@v5.0.2` (ajouter `--no-commit` si ta version de forge le demande). `foundry.toml` :

```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
solc_version = "0.8.24"
evm_version = "shanghai"        # sûr sur Fuji et anvil (pas d'opcode Cancun)
optimizer = true
optimizer_runs = 200
remappings = ["@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/", "forge-std/=lib/forge-std/src/"]
fs_permissions = [{ access = "read-write", path = "../deployments" }, { access = "read", path = "../fixtures" }]
```

Fichiers : `src/MockERC20.sol`, `src/RsETH.sol`, `src/MockBridge.sol`, `src/MockOracle.sol`, `src/MiniLend.sol`, `src/TreasuryVault.sol`, `src/EvidenceRegistry.sol`, `src/interfaces/IMockOracle.sol`, `src/interfaces/IMiniLend.sol` ; `script/Deploy.s.sol`, `script/deploy.sh`, `script/export_abi.py`, `script/check_deployment.py`, `script/fund_roles.py` ; `test/*.t.sol`, `test/utils/BaseTest.sol`, `test/harness/MiniLendHarness.sol`. Transferts via `SafeERC20`. Messages de revert : chaînes exactes, avec `require(cond, "MiniLend: frozen")`.

**2. Jetons.**
- `MockERC20(name, symbol, decimals_)` : `ERC20(name, symbol)`, `Ownable(msg.sender)`, `decimals()` surchargé. `mint` `onlyOwner` (OZ v5 : revert custom error `OwnableUnauthorizedAccount(address)`, pas de chaîne). Déployés : `("USD Coin (mock)", "USDC", 6)`, `("Wrapped Ether (mock)", "WETH", 18)`.
- `RsETH(address bridge_)` : `ERC20("Restaked ETH (mock)", "rsETH")`, 18 décimales, `bridge` immuable. `mint`/`burn` : `require(msg.sender == bridge, "RsETH: only bridge")`.
- `MockBridge(IERC20 weth_, RsETH rseth_)` : `deposit(a)` transfère le WETH, augmente `sourceLocked`, avance `sourceNonce`, libère/mint le même montant, augmente `destinationReleased`, aligne `destinationNonce=sourceNonce`, puis émet `Deposited` et `Released(..., true)`. `forgedRelease(to,a)` avance seulement `destinationNonce`, augmente `destinationReleased` et libère/mint le rsETH sans `sourceLocked/sourceNonce`, émet `Released(..., false)`, sans contrôle d'accès. `conservationGap()` = `max(destinationReleased-sourceLocked,0)`. `pause()` met `paused=true`. `backingRatioBps()` reste un affichage `destinationReleased==0 ? 10000 : sourceLocked*10000/destinationReleased`; R1 ne l'utilise pas.
- Œuf et poule RsETH/Bridge : le script **prédit** l'adresse du bridge (`vm.computeCreateAddress(deployer, vm.getNonce(deployer) + 1)`), déploie `RsETH(predicted)`, puis `MockBridge(weth, rseth)` et `require(address(bridge) == predicted, "Deploy: bridge address mismatch")`.

**3. `MockOracle`** (`Ownable(msg.sender)`) : `mapping(address => uint256) priceE8`. `setPriceE8` émet `PriceUpdated`. `getPriceE8` : `require(p > 0, "Oracle: no price")` (prix 0 = pas de prix).

**4. `MiniLend(address oracle_, address protocolGuardian_)`.** État : `address[] assets` ; `mapping(address => Reserve)` (`listed`, `decimals` lu via `IERC20Metadata` au listage, `totalSupplied`, `totalBorrowed`, `totalCollateral`, `ltvBps`, `borrowable`, `frozen`, `paused`) ; `supplied[user][asset]`, `collateral[user][asset]`, `borrowed[user][asset]`. Pas d'intérêts accumulés, pas de liquidation, pas de retrait de garantie (non présents en 2.2).
- `onlyGuardian` : `require(msg.sender == protocolGuardian, "MiniLend: only guardian")`.
- `listReserve(asset, borrowable, ltv)` : 1er appel → push dans `assets` ; appel suivant sur le même actif → met à jour `borrowable`/`ltvBps` **sans doublon**. Émet `ReserveListed`. `setReserveFrozen`/`setReservePaused`/`setLtv` émettent leurs events.
- Ordre des contrôles (le premier qui échoue gagne, les tests le vérifient) :

| Fonction | Contrôles, dans l'ordre | Effet |
|---|---|---|
| `supply(asset, amount, onBehalfOf)` | `paused` → `frozen` → `!listed \|\| !borrowable` = `"MiniLend: not borrowable"` | `transferFrom(msg.sender)`, `supplied[onBehalfOf] += amount`, `totalSupplied += amount`, `Supplied(asset, msg.sender, onBehalfOf, amount)` |
| `withdraw(asset, amount, to)` | `paused` ; si `amount == type(uint256).max` : `w = min(supplied[msg.sender], liquidity)` ; sinon `amount > supplied[msg.sender]` → `"MiniLend: insufficient balance"` (2.2), puis `amount > liquidity` → `"MiniLend: insufficient liquidity"` | **autorisé si frozen** ; `w == 0` → retourne 0 sans transfert ni event ; sinon décrémente, `transfer(to, w)`, `Withdrawn(asset, msg.sender, to, w)`, retourne `w` |
| `depositCollateral(asset, amount)` | `paused` → `frozen` → `!listed \|\| ltvBps == 0` = `"MiniLend: not collateral"` | `transferFrom(msg.sender)`, `collateral[msg.sender] += amount`, `totalCollateral += amount`, event. **Solde séparé** : ne touche ni `totalSupplied` ni la liquidité (une garantie USDC ne devient jamais empruntable) |
| `borrow(asset, amount)` | `paused` → `frozen` → `"not borrowable"` → `amount > liquidity` = `"MiniLend: insufficient liquidity"` → santé = `"MiniLend: insufficient collateral"` | `borrowed += amount`, `totalBorrowed += amount`, transfert, `Borrowed` |
| `repay(asset, amount)` | `paused` | `r = min(amount, borrowed[msg.sender])`, `transferFrom` de `r` seulement, décrémente, `Repaid(asset, msg.sender, r)` ; **autorisé si frozen** |

  `liquidity = totalSupplied - totalBorrowed` (comptable, jamais `balanceOf` : un don de jetons ou une garantie USDC/WETH déposée ne change rien). Le contrôle de liquidité passe **avant** celui de santé : l'attaquant de T2 sait qu'il a tout vidé quand il reçoit `"insufficient liquidity"`.
- Santé (`borrow`) : `valE8(a, x) = x * oracle.getPriceE8(a) / 10**decimals(a)`. Condition : `(Σ_a valE8(a, borrowed[user][a]) + valE8(asset, amount)) * 10000 <= Σ_a valE8(a, collateral[user][a]) * ltvBps(a)`. Égalité acceptée. La somme porte sur **tous** les actifs listés avec `ltvBps > 0` (rsETH 7 500, USDC et WETH 8 000) : c'est ce qui rend le seed de 2.2 faisable sans toucher aux prix. Une garantie gelée compte toujours. Un actif sans prix fait revert `"Oracle: no price"`.
- Modèle de taux (entiers, identique à 2.2) dans `function _rates(uint256 u) internal pure returns (uint256 supplyBps, uint256 borrowBps)` :
  `b = u <= 8000 ? 100 + 300 * u / 8000 : 400 + 7500 * (u - 8000) / 2000` ; `s = b * u * 85 / 1_000_000`. `u = totalSupplied == 0 ? 0 : totalBorrowed * 10000 / totalSupplied`. Réserve **non empruntable** → `(0, 0)`.
  Valeurs de référence : u=0 → (0, 100) ; 5500 → (143, 306) ; 6000 → (165, 325) ; 8000 → (272, 400) ; 9000 → (3174, 4150) ; 9800 → (5955, 7150) ; 10000 → (6715, 7900).
- `getReservesData()` : un `ReserveData` par actif dans l'ordre de `getAssets()`, champs **dans l'ordre exact de 2.2** (T3 décode par nom via l'ABI) ; `availableLiquidity`, `utilizationBps`, `supplyRateBps`, `borrowRateBps` calculés à la volée.

**5. `TreasuryVault(address owner_, address guardian_)`.**
- `supply(market, asset, amount)` : `"Vault: only owner"` puis `"Vault: deposits paused"` ; fonds pris sur le **solde du coffre** (jamais `transferFrom(owner)` : T2 mint ou envoie d'abord les jetons au coffre ; solde insuffisant → revert ERC20 `ERC20InsufficientBalance` d'OZ v5) ; `forceApprove(market, amount)` ; `IMiniLend(market).supply(asset, amount, address(this))` ; `Supplied(market, asset, amount)`.
- `withdraw(market, asset, amount)` : owner ; `IMiniLend(market).withdraw(asset, amount, address(this))` ; `Withdrawn(market, asset, w)`. Fonctionne même si `depositsPaused`.
- `emergencyWithdraw(market, asset)` : owner ou guardian, sinon `"Vault: only guardian or owner"` ; `w = withdraw(asset, type(uint256).max, address(this))` ; **destination toujours le coffre** (aucun paramètre `to`) ; émet `EmergencyWithdrawal(market, asset, w, msg.sender)` même si `w == 0` (position nulle ou liquidité nulle : **pas de revert**) ; retourne `w`. Une réserve `paused` fait remonter `"MiniLend: paused"` (T4 marque l'action `failed`).
- `pauseDeposits()` : owner ou guardian, **idempotent** (2e appel ne revert pas, ré-émet `DepositsPaused`). `unpauseDeposits()` : owner seul (`"Vault: only owner"`). `setGuardian(g)` : owner seul.
- Le coffre n'a aucune fonction pour sortir des jetons vers une adresse tierce (MVP).

**6. `EvidenceRegistry`.** `anchor(h, kind, uri)` : `require(anchoredAt[h] == 0, "Evidence: already anchored")`, `anchoredAt[h] = block.number`, `Anchored(h, kind, uri, msg.sender)`. Pas de contrôle d'accès ni de validation de `kind` on-chain (convention `decision|rules|incident` tenue par T4).

**7. `script/Deploy.s.sol`** (`contract Deploy is Script`).
- `function run() external` = `Roles memory r = loadRoles(); Deployed memory d = deployAll(r); _write(d, r);` ; `deployAll` est `public` pour être appelé depuis `Deploy.t.sol` sans écrire de fichier.
- `loadRoles()` reproduit **exactement** `settings.private_key` : pour chaque rôle, `vm.envOr(ROLE_ENV, string(""))` ; non vide → `vm.parseUint` (préfixer `0x` s'il manque) ; vide et `block.chainid == 31337` → `vm.deriveKey("test test test test test test test test test test test junk", ANVIL_INDEX)` ; vide sur Fuji → `revert("Deploy: missing <VAR>")`. Bots : `BOT_PKS` vide en local → index 6, 7, 8. Seules les clés `deployer` et `protocol_guardian` signent ; les autres ne servent qu'à calculer `vm.addr(pk)`. Aucune clé n'est jamais loguée (`console.log` d'adresses seulement).
- Garde-fou : `NETWORK=fuji` et `block.chainid != 43113` (ou `local` et `!= 31337`) → `revert("Deploy: chain id mismatch")`.
- Ordre **imposé** (adresses déterministes sur anvil neuf = adresses des fixtures) : `vm.startBroadcast(deployerPk)` → nonce 0 USDC `0x5FbDB2315678afecb367f032d93F642f64180aa3`, 1 WETH `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`, 2 RsETH `0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0`, 3 MockBridge `0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9`, 4 MockOracle `0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9`, 5 MiniLend lend-eth `0x5FC8d32690cc91D4c39d9d3abcBD16989F875707`, 6 MiniLend lend-avax `0x0165878A594ca255338adfa4d48449f69242Eb8F`, 7 TreasuryVault `0xa513E6E4b8f2a923D98304ec87F64353C4D5C853`, 8 EvidenceRegistry `0x2279B7A0a67DB372996a5FaB50D91eAA73d2eBe6` ; **ensuite seulement** `setPriceE8` USDC `1e8`, WETH `2500e8`, rsETH `2500e8` ; `stopBroadcast`. Puis `vm.startBroadcast(protocolGuardianPk)` : sur chaque MiniLend, `listReserve(USDC, true, 8000)`, `listReserve(WETH, true, 8000)`, `listReserve(rsETH, false, 7500)` (cet ordre = ordre de `getAssets()`). MiniLend : `protocolGuardian = roles.protocol_guardian`, `oracle = MockOracle`. Vault : `owner = roles.owner`, `guardian = roles.guardian`.
- `deployed_at_block` = `block.number` lu au début de `run()` (≤ bloc réel du 1er déploiement : T3 peut scanner les events à partir de là).
- Écriture : objets imbriqués via `vm.serializeAddress`/`vm.serializeString` (une chaîne JSON valide passée à `serializeString` est insérée comme objet) ; `lending` construit par `string.concat("[", l1, ",", l2, "]")` ; `roles.bots` via `vm.serializeAddress(key, "bots", address[])`. Fichier écrit : `deployments/<network>.pending.json` (**jamais directement** `<network>.json`, voir piège n°1). Clés : `network`, `chain_id`, `deployed_at_block`, `explorer`, `assets{USDC,WETH,rsETH}`, `contracts{MockBridge,MockOracle,TreasuryVault,EvidenceRegistry}`, `lending[{id,label,address}]` (labels exacts de 2.3), `roles{deployer,owner,guardian,protocol_guardian,attacker,evidence,bots[3]}`.

**8. Scripts annexes.**
- `script/check_deployment.py --network N --rpc-url URL --promote` (stdlib + `urllib`, pas d'import `backend`) : valide le schéma (clés exactes, adresses `0x` + 40 hex checksummées, 2 lending dans l'ordre `lend-eth`, `lend-avax`, 3 bots), vérifie `eth_getCode != "0x"` pour les 9 adresses de contrats, réécrit le JSON indenté 2 dans l'ordre de 2.3, renomme `.pending.json` → `<network>.json` ; sur Fuji copie aussi dans `deployments/history/fuji-<deployed_at_block>.json` et régénère `deployments/fuji.md`. Exit 1 avec message clair sinon (le `.json` précédent reste intact).
- `script/export_abi.py` : pour les 7 noms, lit `contracts/out/<Name>.sol/<Name>.json`, écrit `abi/<Name>.json` = `data["abi"]` (`json.dump(indent=2)`). Pas de `forge inspect` (son format de sortie change selon la version).
- `script/deploy.sh` (appelé par `make deploy`) : mémorise `NETWORK` reçu (le `Makefile` racine l'exporte depuis `.env` ou la ligne de commande ; vide → exit 1 « NETWORK non défini : mets-le dans .env ou lance NETWORK=local make deploy »), charge `../.env` s'il existe (`set -a; . .env; set +a`, **jamais** `set -x`) pour les lancements directs du script, ré-impose le `NETWORK` reçu ; local → RPC `http://127.0.0.1:8545`, vérifie `cast chain-id` (sinon « anvil ne répond pas : lance `make chain` ») ; fuji → **en premier** (avant tout appel réseau) : si `deployments/fuji.json` existe et `FORCE != 1` → exit 1 « un déploiement Fuji existe déjà : les adresses vont changer, préviens l'équipe puis relance avec FORCE=1 » ; avec `FORCE=1`, archive l'ancien fichier dans `deployments/history/fuji-<deployed_at_block>.json` (sans écraser une archive existante) avant de déployer ; puis `RPC_URL` obligatoire, ajoute `--slow` ; puis `forge script script/Deploy.s.sol:Deploy --rpc-url "$RPC" --broadcast`, `check_deployment.py --promote`, `export_abi.py`, affiche les adresses (et liens Snowtrace sur Fuji). `RESUME=1` → ajoute `--resume` (même commande forge). 1er argument `verify-src` → lance `forge verify-contract` (voir 10) pour les 9 contrats à partir de `deployments/fuji.json`. Aucune clé en argument de ligne de commande (`forge` lit les clés via `vm.envOr` dans le script).
- `script/fund_roles.py --amount 0.5` (appelé par `make fund-roles AMOUNT=0.5`) : **Fuji uniquement** (`NETWORK != fuji` → exit 1 « inutile en local : les comptes anvil ont déjà 10 000 ETH ») ; lit les adresses de rôles dans `deployments/fuji.json` (`owner`, `guardian`, `protocol_guardian`, `attacker`, `evidence`, `bots[3]`, jamais `deployer`) ; si le fichier n'existe pas encore (premier déploiement : le `protocol_guardian` doit avoir des AVAX **avant** `make deploy` pour signer les `listReserve`), les déduit des clés de `.env` via `backend.settings.private_key(role)` (mêmes adresses). Envoie depuis `DEPLOYER_PK` (web3 + `eth_account`, clé lue dans l'environnement, jamais en argument ni dans les logs) un virement de `AMOUNT` AVAX à chaque rôle dont le solde est inférieur à `AMOUNT` (un rôle déjà servi est sauté : on n'épuise pas le faucet en relançant) ; une transaction à la fois, attend le reçu ; vérifie d'abord que le deployer a `8 × AMOUNT` + 0,2 AVAX de marge, sinon exit 1 avec le montant manquant ; affiche un tableau `rôle | adresse | solde avant | envoyé | solde après`.

**9. `mk/t1.mk`** (cibles uniques, préfixe `t1-` pour les annexes ; **ne définit jamais `NETWORK`** : il vient de `.env` ou de la ligne de commande via le `Makefile` racine, qui fait `-include .env` et `export`) :

```make
.PHONY: chain deploy abi fund-roles test-t1 t1-build t1-resume t1-links t1-verify-src
chain:            ## anvil local, 1 bloc/s, chainId 31337
	anvil --block-time 1 --chain-id 31337
t1-build:
	cd contracts && forge build
deploy: t1-build  ## déploie sur $(NETWORK), écrit deployments/$(NETWORK).json et abi/
	@NETWORK=$(NETWORK) FORCE=$(FORCE) bash contracts/script/deploy.sh
abi: t1-build     ## exporte abi/<Contrat>.json
	@python3 contracts/script/export_abi.py
fund-roles:       ## Fuji : envoie AMOUNT AVAX du deployer à chaque rôle (défaut 0.5)
	@NETWORK=$(NETWORK) python3 contracts/script/fund_roles.py --amount $(or $(AMOUNT),0.5)
test-t1: t1-build ## tests Solidity + smoke test Python
	cd contracts && forge test -vv
	python -m pytest backend/tests/test_t1_deployment.py -q
t1-resume:        ## reprend un déploiement Fuji interrompu (forge script --resume)
	@NETWORK=fuji RESUME=1 bash contracts/script/deploy.sh
t1-links:         ## affiche deployments/fuji.md
	@cat deployments/fuji.md
t1-verify-src:    ## vérifie le source sur Snowtrace (routescan), optionnel
	@NETWORK=fuji bash contracts/script/deploy.sh verify-src
```

**Livraison en deux temps.** (a) Dès que les interfaces compilent : push des 7 `abi/*.json` et d'un `make deploy` local fonctionnel (même avec peu de tests), pour débloquer T2, T3 et T4. (b) Ensuite : tous les tests, puis Fuji.

**10. Fuji.** Coût : ~9 déploiements + 3 prix (deployer) + 6 listages (protocol_guardian), ordre de grandeur 10 M de gas ; prévoir ~0,5 AVAX de déploiement sur le deployer et ~0,1 sur le protocol_guardian (marge large). **Seul le deployer est financé de l'extérieur** : faucet `https://core.app/tools/testnet-faucet/` (limité par jour, parfois conditionné ; demander aux organisateurs s'ils distribuent des AVAX de test), viser ~5 AVAX. **C'est T1 qui finance tous les autres rôles** (owner, guardian, protocol_guardian, attacker, evidence, bots) : `make fund-roles AMOUNT=0.5` (8 × 0,5 = 4 AVAX), relançable à tout moment pour recharger un rôle à sec (T2 et T4 le demandent à T1). Ordre sur Fuji : faucet → deployer, `make fund-roles AMOUNT=0.5`, `make deploy` (puis `FORCE=1 make deploy` pour un redéploiement, l'ancien fichier part dans `history/`). RPC : le public `https://api.avax-test.network/ext/bc/C/rpc` limite le débit → `RPC_URL` d'un fournisseur ; `--slow` (une tx à la fois, attend le reçu) ; en cas de coupure, `make t1-resume` (`forge script … --resume`) puis `check_deployment.py --promote`. Vérification du source (optionnel, apprécié du jury) : `forge verify-contract <addr> src/MiniLend.sol:MiniLend --chain-id 43113 --verifier-url 'https://api.routescan.io/v2/network/testnet/evm/43113/etherscan' --etherscan-api-key verifyContract --constructor-args $(cast abi-encode "constructor(address,address)" <oracle> <pg>)`. Enregistrer `deployments/fuji.json` et `fuji.md` dans le repo (demande des organisateurs) et prévenir l'équipe à chaque redéploiement.

#### Tests qui doivent passer

Commande globale : `make test-t1` (= `cd contracts && forge test -vv` puis `pytest backend/tests/test_t1_deployment.py -q`). Une seule fonction : `cd contracts && forge test --mt <nom> -vvv`. `test/utils/BaseTest.sol` fournit : tokens, oracle aux prix 2.2, un MiniLend listé comme en 2.2 (USDC et WETH empruntables, LTV 8000 ; rsETH collatéral seul, LTV 7500), acteurs `pg`, `owner`, `guardian`, `alice`, `bob`, `carol`, `attacker`, helpers `_mint(sym, to, amt)`, `_supply(user, asset, amt)`, `_collat(user, amt)` (rsETH via `bridge.deposit`, donc adossé), `_collatAsset(user, asset, amt)` (garantie USDC ou WETH), `_seed(market, wethSup, usdcSup, rsethCol, usdcCol, wethBor, usdcBor)` (état initial 2.2 d'un déploiement).

| Id | Fichier :: test | Setup | Résultat attendu |
|---|---|---|---|
| T1-01 | `Tokens.t.sol::test_MockERC20_metadata` | déploiement BaseTest | USDC `decimals()==6`, symbol `"USDC"` ; WETH `18`, `"WETH"` |
| T1-02 | `Tokens.t.sol::test_MockERC20_mint_onlyOwner` | `alice` appelle `mint` | revert `OwnableUnauthorizedAccount(alice)` ; owner mint 5e6 → `balanceOf==5e6` |
| T1-03 | `Tokens.t.sol::test_RsETH_onlyBridge` | `alice` appelle `mint` puis `burn` | les deux revert `"RsETH: only bridge"` ; prank bridge → mint/burn OK ; `symbol()=="rsETH"`, `decimals()==18` |
| T1-04 | `MockBridge.t.sol::test_backingRatio_emptySupply` | aucun dépôt | `backingRatioBps()==10000` |
| T1-05 | `MockBridge.t.sol::test_deposit_backed` | `alice` dépose 1200e18 WETH | `sourceLocked==destinationReleased==1200e18`, `sourceNonce==destinationNonce==1`, `conservationGap()==0`, `rseth.totalSupply()==1200e18`, ratio `10000`, événements avec nonce 1 et `sourceVerified=true` |
| T1-06 | `MockBridge.t.sol::test_forgedRelease_unbacked` | T1-05 puis `attacker` `forgedRelease(attacker, 5000e18)` | supply et `destinationReleased` `6200e18`, `sourceLocked` `1200e18`, `conservationGap()==5000e18`, `sourceNonce==1`, `destinationNonce==2`, ratio d'affichage `1935`, event `Released(attacker,5000e18,2,false)` ; appelable par n'importe qui |
| T1-07 | `MockBridge.t.sol::test_backingRatio_half` | dépôt 1000e18 + forged 1000e18 | ratio `5000` |
| T1-08 | `MockOracle.t.sol::test_price_roundtrip_and_errors` | | `setPriceE8(WETH,2500e8)` → `getPriceE8==2500e8` + `PriceUpdated` ; actif inconnu → `"Oracle: no price"` ; `alice` set → `OwnableUnauthorizedAccount` |
| T1-09 | `MiniLend.t.sol::test_admin_onlyGuardian` | `alice` | `listReserve`, `setReserveFrozen`, `setReservePaused`, `setLtv` → `"MiniLend: only guardian"` ; par `pg` → events `ReserveListed`, `ReserveFrozen`, `ReservePaused`, `LtvUpdated` |
| T1-10 | `MiniLend.t.sol::test_listReserve_orderNoDuplicate` | relister WETH `(false, 100)` | `getAssets()==[USDC,WETH,rsETH]` (longueur 3), WETH `borrowable==false`, `ltvBps==100` |
| T1-11 | `MiniLend.t.sol::test_supply_and_onBehalfOf` | `alice` supply 2000e18 WETH pour `bob` | `getUserSupplied(bob,WETH)==2000e18`, alice 0, `totalSupplied==2000e18`, event `Supplied(WETH,alice,bob,2000e18)` |
| T1-12 | `MiniLend.t.sol::test_supply_reverts` | | rsETH → `"MiniLend: not borrowable"` ; jeton non listé → idem ; WETH frozen → `"MiniLend: frozen"` ; WETH paused → `"MiniLend: paused"` |
| T1-13 | `MiniLend.t.sol::test_rates_60pct` | supply 2000e18 WETH ; borrower `_collat` 2000e18 rsETH, borrow 1200e18 | `totalBorrowed==1200e18`, `availableLiquidity==800e18`, `utilizationBps==6000`, `supplyRateBps==165`, `borrowRateBps==325` |
| T1-14 | `MiniLend.t.sol::test_rates_55pct` | supply 1000e18, borrow 550e18 | `5500`, `143`, `306` |
| T1-15 | `MiniLend.t.sol::test_rates_100pct` | supply 1000e18, borrow 1000e18 | `availableLiquidity==0`, `10000`, **`6715`**, **`7900`** |
| T1-16 | `MiniLend.t.sol::test_rateModel_table` | `MiniLendHarness.exposedRates(u)` | u=0 → (0,100) ; 8000 → (272,400) ; 9000 → (3174,4150) ; 9800 → (5955,7150) ; 10000 → (6715,7900) ; rsETH (non empruntable) → `(0,0)` dans `getReservesData` |
| T1-17 | `MiniLend.t.sol::test_borrow_collateralLimit` | `_collat` 100e18 rsETH (250 000 $, capacité 187 500 $), liquidité large | borrow 75e18 WETH OK (égalité) ; puis borrow 1e6 USDC → `"MiniLend: insufficient collateral"` |
| T1-18 | `MiniLend.t.sol::test_borrow_multiAssetDecimals` | même garantie | borrow 50e18 WETH + 62_500e6 USDC OK ; +1e6 USDC → `"MiniLend: insufficient collateral"` |
| T1-19 | `MiniLend.t.sol::test_borrow_liquidityBeforeCollateral` | supply 100e18 WETH, borrower **sans** garantie | borrow 101e18 → `"MiniLend: insufficient liquidity"` ; borrow rsETH → `"MiniLend: not borrowable"` |
| T1-20 | `MiniLend.t.sol::test_depositCollateral_reverts` | | jeton non listé → `"MiniLend: not collateral"` ; WETH après `setLtv(WETH,0)` → `"MiniLend: not collateral"` ; rsETH frozen → `"MiniLend: frozen"` ; paused → `"MiniLend: paused"` ; OK → `totalCollateral` +x, `getUserCollateral` +x, event ; garantie USDC 1_000_000e6 → `totalSupplied` et `availableLiquidity` USDC **inchangés** |
| T1-21 | `MiniLend.t.sol::test_withdraw_exact_and_errors` | alice position 150e18, liquidité de la réserve 100e18 | `withdraw(50e18)` retourne `50e18` + `Withdrawn(WETH,alice,alice,50e18)` (position 100e18, liquidité 50e18) ; `withdraw(101e18)` → `"MiniLend: insufficient balance"` (contrôlé **avant** la liquidité) ; `withdraw(100e18)` → `"MiniLend: insufficient liquidity"` ; `carol` sans position `withdraw(1)` → `"MiniLend: insufficient balance"` |
| T1-22 | `MiniLend.t.sol::test_withdrawMax_minPositionLiquidity` | 3 cas | liquidité 800 / position 150 → retourne `150e18` ; liquidité 100 / position 150 → `100e18`, position restante `50e18` ; liquidité 0 → retourne `0`, pas de revert, solde inchangé ; utilisateur **sans position** (liquidité 800) → retourne `0`, pas de revert, aucun event `Withdrawn` (`vm.recordLogs`) |
| T1-23 | `MiniLend.t.sol::test_frozen_allowsWithdrawRepay_blocksSupplyBorrow` | position + dette, puis `setReserveFrozen(WETH,true)` | `withdraw` OK, `repay` OK ; `supply` et `borrow` → `"MiniLend: frozen"` |
| T1-24 | `MiniLend.t.sol::test_paused_blocksAll` | `setReservePaused(WETH,true)` | supply, withdraw (dont max), borrow, repay → `"MiniLend: paused"` |
| T1-25 | `MiniLend.t.sol::test_repay_clamps` | dette 100e18, emprunteur approuvé pour 1000e18 | `repay(40e18)` → dette 60e18, liquidité +40e18 ; `repay(1000e18)` → ne prélève que 60e18 (solde emprunteur −60e18 exactement), dette 0, event `Repaid(WETH,b,60e18)` ; `repay` sans dette → pas de revert, `Repaid(WETH,b,0)`, rien prélevé |
| T1-26 | `Scenario.t.sol::test_seedFeasible_noPriceTrick` | prix 2.2 **inchangés** (USDC 1e8, WETH/rsETH 2500e8). lend-eth : supply 2000e18 WETH + 3_000_000e6 USDC ; bot garantie 900e18 rsETH + 4_500_000e6 USDC. lend-avax : supply 1000e18 WETH + 2_000_000e6 USDC ; bot garantie 300e18 rsETH + 3_000_000e6 USDC | lend-eth : borrow 1200e18 WETH + 1_800_000e6 USDC **OK** ; WETH `6000`, `165`/`325` ; USDC `6000`, `availableLiquidity` 1_200_000e6 (la garantie USDC n'y est pas) ; `totalCollateral` rsETH `900e18`, USDC `4_500_000e6`. lend-avax : borrow 550e18 WETH + 1_100_000e6 USDC **OK** ; WETH `5500`, `143`/`306`. Sur chaque déploiement, marge restante 487 500 $ = 195 WETH : borrow 196e18 WETH → `"MiniLend: insufficient collateral"`, puis 195e18 → OK (égalité) ; ensuite 1e18 → `"MiniLend: insufficient collateral"` (valide l'état initial de 2.2 pour T2) |
| T1-27 | `Scenario.t.sol::test_drainWithoutReaction_matchesFixture` | seed lend-eth de T1-26 (sans les emprunts de marge) + coffre 150e18 dans les 2000 ; `forgedRelease` 5000 ; collat ; attaquant borrow 100e18 par tranche, 2 retraits de 100e18 par des bots intercalés | final : `totalSupplied 1800e18`, `totalBorrowed 1800e18`, liquidité 0, `10000`, `6715`/`7900`, `totalCollateral` rsETH `5900e18`, `backingRatioBps 1935` ; tranche suivante → `"MiniLend: insufficient liquidity"` ; `vault.emergencyWithdraw` retourne `0` ; `setReserveFrozen(rsETH,true)` → `frozen` |
| T1-28 | `Scenario.t.sol::test_guardianExitsBeforeDrain` | seed lend-eth de T1-26 (sans les emprunts de marge) + positions coffre 150e18 WETH et 400_000e6 USDC ; `forgedRelease` ; guardian `emergencyWithdraw` ×2 ; puis vidage | retours `150e18` et `400_000e6` (100 % retirable) ; `weth.balanceOf(vault)==150e18` ; un bot passif `withdraw(max)` après vidage → `0` |
| T1-29 | `TreasuryVault.t.sol::test_roles_and_supply` | | `owner()`, `guardian()`, `depositsPaused()==false` ; guardian/alice `supply` → `"Vault: only owner"` ; **solde du coffre** : owner détient 150e18 WETH, coffre 0 → owner `supply(150e18)` revert `ERC20InsufficientBalance` ; mint 150e18 **vers le coffre** → owner supply 150e18 → position coffre `150e18`, `weth.balanceOf(vault)==0`, solde de l'owner **inchangé** (150e18), `Supplied(market,WETH,150e18)` |
| T1-30 | `TreasuryVault.t.sol::test_pause_unpause` | | guardian `pauseDeposits` → `true` + `DepositsPaused(guardian)` ; 2e appel (guardian puis owner) ne revert pas, état reste `true`, ré-émet `DepositsPaused` ; owner `supply` → `"Vault: deposits paused"` ; guardian `unpauseDeposits` → `"Vault: only owner"` ; alice `pauseDeposits` → `"Vault: only guardian or owner"` ; owner unpause → `false` + `DepositsUnpaused(owner)` |
| T1-31 | `TreasuryVault.t.sol::test_emergencyWithdraw_toVaultOnly` | position 150e18, liquidité 800e18 | guardian → retourne `150e18`, `weth.balanceOf(vault)==150e18`, guardian et owner `0`, event `EmergencyWithdrawal(market,WETH,150e18,guardian)` ; liquidité 100e18 → `100e18` ; liquidité 0 → retourne `0` **sans revert** + `EmergencyWithdrawal(market,WETH,0,guardian)` ; actif sans position du coffre (USDC jamais déposé) → `0` sans revert + event avec montant 0 ; alice → `"Vault: only guardian or owner"` ; guardian `withdraw` → `"Vault: only owner"` |
| T1-32 | `TreasuryVault.t.sol::test_emergencyWithdraw_states` | | marche si `depositsPaused` ; marche si réserve frozen ; réserve paused → revert `"MiniLend: paused"` (remonté tel quel, aucun event `EmergencyWithdrawal`, position intacte : T4 marque l'action `failed`) |
| T1-33 | `TreasuryVault.t.sol::test_setGuardian` | | alice → `"Vault: only owner"` ; owner `setGuardian(bob)` → ancien guardian refusé, bob accepté |
| T1-34 | `TreasuryVault.t.sol::testFuzz_guardianNeverLosesFunds(uint8[] ops)` | séquence aléatoire d'appels guardian (pause, emergencyWithdraw USDC/WETH) | `balanceOf(vault) + position` constant pour chaque actif ; aucun jeton chez le guardian |
| T1-35 | `EvidenceRegistry.t.sol::test_anchor` | `vm.roll(123)` | `anchoredAt(h)==0` avant ; `anchor(h,"decision","s3://b/DEC-1.json")` → `anchoredAt(h)==123`, event `Anchored(h,"decision",uri,sender)` ; 2e ancrage → `"Evidence: already anchored"` |
| T1-36 | `Deploy.t.sol::test_deployAll_configuration` | `new Deploy().deployAll(roles anvil)` | prix 1e8/2500e8/2500e8 ; pour chaque MiniLend : `protocolGuardian==pg`, `getAssets()==[USDC,WETH,rsETH]`, LTV 8000/8000/7500, borrowable true/true/false, rien de gelé ; vault owner/guardian = index 1/2 ; `rseth.bridge()==bridge`, `bridge.weth()==WETH` ; `totalSupply()==0` pour les 3 jetons (T1 ne mint rien) |
| T1-37 | `Deploy.t.sol::test_deployAll_addressesMatchFixtures` | idem | les 9 adresses = celles listées en 7 |
| T1-38 | `test_t1_deployment.py::test_t1_local_json_format` | skip si `deployments/local.json` absent | clés exactes de 2.3, `network=="local"`, `chain_id==31337`, ids `["lend-eth","lend-avax"]`, labels exacts, 3 bots, adresses checksummées |
| T1-39 | `test_t1_deployment.py::test_t1_addresses_have_code` | skip si RPC `127.0.0.1:8545` injoignable | `eth.get_code` non vide pour assets, contracts, lending ; sinon échec « anvil redémarré : relance make deploy » |
| T1-40 | `test_t1_deployment.py::test_t1_abi_files` | | 7 fichiers, chacun une `list` ; `MiniLend` contient `getReservesData`, `withdraw`, `getUserSupplied` ; `TreasuryVault` contient `emergencyWithdraw`, `pauseDeposits` ; `EvidenceRegistry` contient `anchoredAt` |
| T1-41 | `test_t1_deployment.py::test_t1_onchain_config_and_roles` | idem T1-39 | via `chain.load_abi` + Web3 local : prix oracle, `getAssets` ordre, LTV USDC/WETH 8000 et rsETH 7500, `vault.owner()==roles.owner`, `roles[r] == Account.from_key(settings.private_key(r)).address` pour les 6 rôles |
| T1-42 | `test_t1_deployment.py::test_t1_fuji_json_format` | skip si `deployments/fuji.json` absent ; sans réseau | `chain_id==43113`, `explorer=="https://testnet.snowtrace.io"`, aucune valeur `"0x…"`, `deployments/fuji.md` existe |
| T1-43 | `test_t1_deployment.py::test_t1_fund_roles_refuses_local` | sans réseau | `subprocess.run(["python3","contracts/script/fund_roles.py","--amount","0.5"], env={…, "NETWORK":"local"})` → code ≠ 0, message contient `local` ; aucune transaction envoyée |
| T1-44 | `test_t1_deployment.py::test_t1_deploy_fuji_requires_force` | skip si `deployments/fuji.json` absent ; sans réseau (`RPC_URL` vide) | `bash contracts/script/deploy.sh` avec `NETWORK=fuji`, `FORCE` absent → code ≠ 0, message contient `FORCE=1` ; `deployments/fuji.json` inchangé (même sha256) et aucun nouveau fichier dans `deployments/history/` |

#### Definition of done

- [ ] `forge build` sans warning bloquant ; `forge test` : T1-01 à T1-37 verts ; `forge coverage` > 90 % des lignes de `src/` (indicatif).
- [ ] Les 7 `abi/*.json` commités (listes brutes) et à jour (`make abi` ne produit aucun diff).
- [ ] `make chain` puis `make deploy` sur anvil neuf → `deployments/local.json` valide, adresses = fixtures ; `pytest backend/tests/test_t1_deployment.py` vert (T1-38 à T1-41, T1-43).
- [ ] `make deploy` relancé sur la même anvil fonctionne (nouvelles adresses, `local.json` réécrit).
- [ ] `make fund-roles AMOUNT=0.5` exécuté sur Fuji : les 8 rôles (hors deployer) ont ≥ 0,5 AVAX.
- [ ] Déploiement Fuji fait, `deployments/fuji.json` + `fuji.md` + `history/` commités, T1-42 et T1-44 verts, `make deploy` sur Fuji refusé sans `FORCE=1`, liens Snowtrace ouverts et vérifiés à la main.
- [ ] Aucune clé dans le repo ni dans les logs (`git grep -i "PK="` vide hors `.env.example`, sortie de `make deploy` relue).
- [ ] L'équipe est prévenue (adresses Fuji, ABIs, `make fund-roles` disponible ; T2 sait que l'état initial de 2.2 est faisable tel quel, validé par T1-26).

#### Pièges connus

1. **`vm.writeJson` s'exécute pendant la simulation**, avant l'envoi des transactions : si le broadcast échoue, le fichier contient des adresses vides de code. D'où `.pending.json` + promotion après vérification `eth_getCode`.
2. **Garantie ≠ liquidité** : les bots empruntent contre 900 rsETH + 4,5 M USDC (`lend-eth`, capacité 5 287 500 $ pour 4,8 M $) et 300 rsETH + 3 M USDC (`lend-avax`, 2 962 500 $ pour 2,475 M $). Si `depositCollateral` ajoutait la garantie USDC à `totalSupplied`, les taux et la liquidité de 2.2 seraient faux (et l'attaquant pourrait emprunter la garantie des bots). Deux soldes séparés, liquidité comptable, et **aucun changement de prix oracle** au seed (validé par T1-26). Si l'on oublie la LTV 8000 sur USDC/WETH au listage, le seed revert `"insufficient collateral"`.
3. **Nonces et adresses** : tout appel du deployer (ex. `setPriceE8`) avant la fin des 9 déploiements décale toutes les adresses ; et un `make deploy` sur une anvil déjà utilisée donne d'autres adresses (normal ; `chain.load_deployment()` relit le fichier).
4. **Fixtures arrondies en float** : la dernière ligne de `snapshots_attack.jsonl` affiche `6714`/`7899` à U = 100 % ; le contrat renvoie `6715`/`7900` (entiers, valeur de 2.2). Prévenir T3 : ne pas comparer les taux on-chain aux fixtures à l'unité près.
5. **Clés vides dans `.env`** (`DEPLOYER_PK=` copié de `.env.example`) : `vm.envOr` renvoie `""`, à traiter comme absent ; `vm.envUint` sur `""` plante. Clé sans `0x` : préfixer avant `vm.parseUint`.
6. **Local avec des clés Fuji dans `.env`** : `settings.private_key` les utilise aussi en local ; ces comptes n'ont pas d'ETH anvil → « insufficient funds ». Commenter les `*_PK` pour travailler en local.
7. OZ v5 : `Ownable` exige `Ownable(initialOwner)` et les erreurs sont des custom errors (`expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, alice))`).
8. `fs_permissions` manquant → « path not allowed » ; `--slow` oublié sur Fuji → nonces en vol et timeouts RPC ; RPC public → HTTP 429.
9. `anvil` perd son état à l'arrêt : après chaque `make chain`, refaire `make deploy` puis `make seed`.
10. `forge inspect … abi` affiche un tableau dans les versions récentes : exporter depuis `out/` (script fourni).

#### Plus tard (phase 2)

- Intérêts accumulés (index), liquidations, retrait de garantie, facteur de santé exposé : permettraient des scénarios de liquidation en cascade.
- Allowlist des marchés dans `TreasuryVault` (le guardian ne peut appeler `emergencyWithdraw` que sur des marchés approuvés) ; module Safe réel au lieu du coffre simplifié.
- Oracle avec `updatedAt` et contrôle de fraîcheur ; plafonds d'émission sur le bridge.
- `EvidenceRegistry` avec liste d'émetteurs autorisés et validation de `kind`.
- `anvil --dump-state/--load-state` pour un état seedé réutilisable ; vérification du source automatisée dans le déploiement Fuji.

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T1 (contrats on-chain) du fichier TASKS.md à la racine du repo.
1. Lis les sections 1 et 2 de TASKS.md (2.2 et 2.3 sont le contrat exact), puis la section T1 en entier.
   Lis aussi backend/settings.py, backend/chain.py et fixtures/deployments.example.json (adresses seulement).
2. Ne modifie QUE : contracts/**, deployments/**, abi/**, mk/t1.mk, backend/tests/test_t1_deployment.py.
   Tout besoin de changement ailleurs ou dans la section 2 : n'édite pas, écris la demande dans
   docs/contract-requests.md (quoi, pourquoi, qui est impacté) et préviens-moi.
3. Pas de clé dans le repo ni dans les logs ; en local, utilise les comptes anvil (mnémonique public).
4. Ordre de travail : (a) projet Foundry + interfaces exactes de 2.2 qui compilent, export des ABIs,
   Deploy.s.sol + make deploy local, pour débloquer l'équipe ; (b) écris les tests T1-01 à T1-44
   AVANT l'implémentation complète, puis implémente jusqu'à ce que make test-t1 soit vert ;
   (c) déploiement Fuji (seulement quand je te le demande, avec mes clés dans .env) :
   make fund-roles AMOUNT=0.5 puis make deploy (FORCE=1 seulement si je le confirme).
5. Messages de revert, noms d'events, ordre des champs de ReserveData, ordre de déploiement
   (adresses = fixtures sur anvil neuf) : à respecter à la lettre.
6. Avant chaque commit : make test-t1 vert ; push fréquent après chaque test vert.
```


---


### T2 · Scénario : seed, attaque, trafic normal, reset

**Objectif.** Fournir les scripts qui mettent la chaîne (anvil ou Fuji) dans l'état de départ de 2.2 (`seed`), jouent l'attaque de 1.2 de façon reproductible (`attack`), produisent du trafic bénin (`normal`) et remettent tout à zéro (`reset`). Chaque run écrit sa **vérité terrain** (`RunRecord`) pour l'évaluation (T7), et l'API `/api/demo/*` permet de lancer attaque et reset depuis le dashboard (T6).

**Dépend de.**
- T1 → contrats + `make deploy` + `deployments/<network>.json` + `abi/*.json` → en attendant : tests purs uniquement (paramètres, planificateur, RunRecord, API avec faux runner) ; les tests chaîne se mettent en `skip` tout seuls.
- T0 → helpers de 2.4 dans `backend/chain.py` → si `token()`, `vault()`, `bridge()`, `oracle()`, `bot_accounts()` n'y sont pas encore (aujourd'hui seuls `w3`, `load_deployment`, `load_abi`, `contract`, `lending`, `account`, `send`, `explorer_tx` existent), utiliser le shim temporaire `scenario/_compat.py` (étape 1), à supprimer quand T0 livre.
- T0 → `backend/store.py` (`store.reset()`, qui incrémente `store.generation`) → appel isolé dans `_reset_store()` de `backend/api/demo.py`, remplacé par un compteur dans les tests.
- T1 → `make fund-roles` (envoie de l'AVAX de test aux rôles sur Fuji) → sur `local`, rien à faire (comptes anvil déjà crédités).
- T3 → respect du mode maintenance de 2.10 (le moteur n'évalue aucune règle tant que `data/runtime/<network>/maintenance.flag` existe) → T2 crée et supprime le fichier quoi qu'il arrive ; les scripts tournent moteur éteint (`ENGINE_ENABLED=false`) ou allumé. T4 : aucune dépendance.

**Débloque.** T7 (lance `python -m scenario.attack/normal --json`, lit `data/runs/*.json`), T6 (boutons « Run attack » / « Reset » via `/api/demo/*`), T3/T4/T5 (état de chaîne réel conforme à 2.2 pour l'intégration), T0 (`make demo` appelle `make seed`), T9 (script de démo).

**Fichiers possédés.**
- `scenario/common.py`, `scenario/params.py`, `scenario/seed.py`, `scenario/attack.py`, `scenario/normal.py`, `scenario/reset.py`, `scenario/testing.py`, `scenario/_compat.py` (temporaire)
- `backend/api/demo.py`
- `mk/t2.mk`
- `backend/tests/test_t2_params.py`, `test_t2_common.py`, `test_t2_normal_plan.py`, `test_t2_demo_api.py`, `test_t2_seed_chain.py`, `test_t2_attack_chain.py`, `test_t2_normal_chain.py`
- Généré (non commité) : `data/runs/<run_id>.json`, `data/runtime/<network>/maintenance.flag` (temporaire, pendant seed et reset)
- Pas à T2 : `scenario/__init__.py` (T0, déjà créé), `README.md` (T9 : fournir son paragraphe dans la PR)

**À lire avant de commencer.** TASKS.md 1.2 (phases), 1.5, 2.1 (rôles, clés anvil), 2.2 (interfaces + table des paramètres), 2.3, 2.4, 2.5 (identifiants), 2.9 (routes demo, codes d'erreur, sémantique de `seed`), 2.10 (mode maintenance), 2.11. Fichiers : `backend/models.py` (`DemoRun`, `RunRecord`), `backend/settings.py`, `backend/chain.py`, `fixtures/run_record.example.json`, `fixtures/demo_run.json`. **Ne pas lire** `backend/config/rules.yaml` ni 2.7 pour régler l'attaque (non-circularité, voir Pièges).

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| Adresses déployées | `deployments/<network>.json` (2.3) | T1 (`make deploy`) | aucune : tests chaîne en skip ; pour le code de chargement, `fixtures/deployments.example.json` |
| ABIs | `abi/<Contrat>.json` (liste ABI brute) | T1 (`make abi`) | idem |
| Clés des rôles | `settings.private_key(role)`, `settings.bot_pks()` | T0 | sur `local` : comptes anvil (deployer 0, owner 1, guardian 2, protocol_guardian 3, attacker 4, bots 6/7/8) |
| Helpers web3 | `backend.chain` (2.4) | T0 | `scenario/_compat.py` |
| Modèles | `RunRecord`, `DemoRun` (`backend/models.py`) | T0 | déjà livrés |
| `store.reset()` | `backend.store.store` | T0 | fonction patchée dans les tests |
| `make deploy FORCE=1` | commande shell, code retour 0 | T1 | `deploy_cmd=["true"]` injecté dans les tests de `reset` |
| AVAX de test des rôles (fuji) | `make fund-roles` | T1 | inutile sur `local` |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| État de chaîne après seed | exactement la table 2.2 (détail en 3.2) | T3, T4, T5, T7, démo |
| `data/runs/<run_id>.json` | `RunRecord` sérialisé (`model_dump_json(indent=2)`), un fichier par run attack (label `attack`) et normal (label `normal`) | T7 |
| `data/runtime/<network>/maintenance.flag` | fichier présent pendant tout `seed` et tout `reset`, supprimé dans un `finally` (2.10) | T3 (moteur) |
| Lignes `--json` sur stdout | une ligne JSON par étape : `{"run_id","step","status","block","tx_hash","msg","at"}` | `backend/api/demo.py`, T7 |
| `POST /api/demo/attack`, `POST /api/demo/reset`, `GET /api/demo/runs/{run_id}` | `DemoRun` (2.9) | T6 |
| Fonctions Python | `run_seed()`, `run_attack()`, `run_normal()`, `run_reset()`, `attack_params()`, `normal_params()` | T7 (import direct possible) |
| Cibles make | `seed`, `attack SEED= VARIANT=`, `normal MINUTES= SEED=`, `reset`, `test-t2` | tous |

#### Spécification détaillée

**1. Socle (`scenario/common.py`, `scenario/_compat.py`, `scenario/testing.py`)**

```python
# _compat.py (temporaire) : uniquement via chain.contract() et chain.load_deployment()
def token(symbol: str) -> Contract      # ABI "RsETH" si symbol == "rsETH", sinon "MockERC20"; adresse = dep["assets"][symbol]
def vault() / bridge() / oracle()       # contract("TreasuryVault") / contract("MockBridge") / contract("MockOracle")
def bot_accounts() -> list[LocalAccount] # [Account.from_key(k) for k in settings.bot_pks()]
# common.py
class ScenarioError(Exception): ...   # exit 1
class PreflightError(Exception): ...  # exit 2
def units(amount: int | str | Decimal, symbol: str) -> int     # USDC 6 décimales, WETH/rsETH 18 ; units(150,"WETH") == 150 * 10**18
def new_run_id(kind: str, seed: int, now: datetime | None = None) -> str   # "RUN-20261011080000-attack-42" (UTC)
def reserve(deployment_id: str, symbol: str, block: int | str = "latest") -> dict
    # getReservesData() indexé par getAssets() ; clés snake_case : total_supplied, total_borrowed, available_liquidity,
    # utilization_bps, total_collateral, ltv_bps, frozen, paused (ints / bools)
def tx(fn, sender, step: str, emit: "Emitter", expect_revert: bool = False) -> dict | None
    # appelle chain.send ; status 0 -> ScenarioError ; ContractLogicError (levée par estimate_gas) -> ScenarioError,
    # sauf expect_revert=True : émet status "blocked" et renvoie None
def ensure_allowance(acct, symbol: str, spender: str) -> None   # approve(2**256-1) seulement si allowance < 2**255
def write_run_record(rec: RunRecord) -> Path   # settings.DATA_DIR/"runs"/f"{rec.run_id}.json", écriture .tmp puis os.replace
def maintenance_flag_path() -> Path            # settings.DATA_DIR/"runtime"/settings.NETWORK/"maintenance.flag"
@contextmanager
def maintenance(emit: "Emitter") -> Iterator[None]
    # crée le dossier et le fichier (contenu : run_id + date ISO) à l'entrée, émet "maintenance_on" (info) ;
    # supprime le fichier dans un finally (missing_ok=True), émet "maintenance_off" (info), même si une exception remonte
class Emitter:
    def __init__(self, run_id: str, json_mode: bool, stream=sys.stdout)
    def __call__(self, step: str, msg: str, status: str = "ok", block: int | None = None, tx_hash: str | None = None) -> None
    # json_mode : print(json.dumps({...}), flush=True) ; sinon "[step] msg (block=…, tx=…)"
```
`status ∈ {"ok", "info", "blocked", "failed"}`. Toujours `flush=True` (sinon l'API ne voit rien avant la fin).
`testing.py` : `local_chain_ready() -> bool` (vrai si `settings.NETWORK == "local"`, `w3().is_connected()`, `chain_id == 31337` et `deployments/local.json` existe), `evm_snapshot() -> str`, `evm_revert(snap_id: str) -> None` via `w3().provider.make_request("evm_snapshot", [])`.

**2. Paramètres (`scenario/params.py`, pur, aucun accès chaîne)**

```python
@dataclass(frozen=True)
class AttackParams:
    variant: str; seed: int; market: str          # "lend-eth"
    forged_amount: int                            # rsETH, unités humaines
    drain_asset: str                              # "WETH" | "USDC"
    chunk: int                                    # unités humaines de drain_asset
    interval_s: float; warmup_s: float; gap_s: float; freeze_delay_s: float; cooldown_s: float
    withdraw_after: tuple[int, ...]               # index (1-based) des emprunts après lesquels un bot retire
    bot_withdraw_amount: int; max_chunks: int = 200
    def as_params(self) -> dict[str, str | int | float | bool]
    # clés obligatoires (noms du contrat) : forged_amount, chunk_weth (= chunk si WETH, sinon 0), interval_s,
    # bot_withdrawals (= len(withdraw_after)) ; clés en plus : drain_asset, chunk_usdc (= chunk si USDC, sinon 0),
    # withdraw_after -> "4,5" (pas de liste dans RunRecord.params), bot_withdraw_amount
def attack_params(variant: str = "default", seed: int = 0, network: str = settings.NETWORK) -> AttackParams
def normal_params(minutes: float, seed: int = 0, network: str = settings.NETWORK, ticks: int | None = None) -> NormalParams
```

| Paramètre | `default` | `slow` | `usdc` | Tirage si `seed ≥ 1` (`random.Random(seed)` uniquement) |
|---|---|---|---|---|
| `forged_amount` | 5 000 | 5 000 | 5 000 | multiple de 500 dans [3 000 ; 8 000] |
| `drain_asset`, `chunk` | WETH, 100 | WETH, 25 | USDC, 250 000 | WETH : {50, 100, 150, 200} ; USDC : {100 000, 250 000, 400 000} ; `slow` : {10, 25, 40} |
| `interval_s` | 8 (fuji) / 1 (local) | ×3 | idem default | × uniforme [0,75 ; 1,25], arrondi 0,1 |
| `warmup_s` / `gap_s` | 3 × interval / 1 × interval | idem | idem | idem (dérivés) |
| `withdraw_after`, `bot_withdraw_amount` | (4, 5), 100 WETH | (12, 20), 100 WETH | (2, 3), 250 000 USDC | 1 à 3 index distincts dans [2 ; 7] ; montant = 1 × chunk WETH arrondi à 100 ou 250 000 USDC |
| `freeze_delay_s` / `cooldown_s` | 10 × interval / 1 × interval | idem | idem | idem |

`seed = 0` (ou `--seed` absent) = paramètres par défaut exacts, aucun tirage. `seed ≥ 1` = tirage déterministe. Le tirage d'une graine au hasard (cas `seed = null` de l'API, 2.9) est fait par `backend/api/demo.py`, jamais ici. Variantes autorisées : `default`, `slow`, `usdc` ; variante inconnue → `ValueError`. Avec les paramètres par défaut : 6 tranches de 100 WETH et 2 retraits de bots de 100 WETH (identique à `fixtures/snapshots_attack.jsonl`). CLI : `--interval-s`, `--warmup-s`, `--freeze-delay-s` surchargent après tirage (utilisés par les tests).

**3. Seed (`scenario/seed.py`)**

3.1 Cibles (constante `SEED_TARGET`, unités humaines) : rôles des bots fixes : `bots[0]` = prêteur, `bots[1]` = emprunteur historique, `bots[2]` = emprunteur actif du trafic normal.

| Qui | Action | lend-eth | lend-avax |
|---|---|---|---|
| deployer | `mint` | bots[0] : 3 250 WETH + 5 300 000 USDC ; bots[1] : 1 200 WETH + 7 500 000 USDC ; bots[2] : 500 WETH ; coffre (adresse du coffre) : 250 WETH + 700 000 USDC | |
| bots[0] | `supply` | 1 850 WETH, 2 600 000 USDC | 900 WETH, 1 700 000 USDC |
| bots[1] | `bridge.deposit(1200)` puis `depositCollateral(rsETH)` | 900 rsETH | 300 rsETH |
| bots[1] | `depositCollateral(USDC)` | 4 500 000 USDC | 3 000 000 USDC |
| bots[1] | `borrow` | 1 200 WETH, 1 800 000 USDC | 550 WETH, 1 100 000 USDC |
| owner | `vault.supply(market, asset, amount)` | 150 WETH, 400 000 USDC | 100 WETH, 300 000 USDC |

Résultat attendu (= 2.2) : lend-eth WETH 2 000 / 1 200 (6 000 bps), USDC 3 000 000 / 1 800 000 ; lend-avax WETH 1 000 / 550 (5 500 bps), USDC 2 000 000 / 1 100 000 ; rsETH `totalSupply` 1 200, `sourceLocked == destinationReleased == 1 200`, nonces égaux, `conservationGap == 0`, `backingRatioBps` 10 000 ; collatéral rsETH 900 / 300 et collatéral USDC 4 500 000 / 3 000 000 (`total_collateral` de la réserve USDC, **séparé** de `total_supplied` : il n'augmente pas la liquidité empruntable) ; coffre `idle_balances` à 0, `depositsPaused == false`. Les mints du coffre vont **à l'adresse du coffre** : `TreasuryVault.supply` utilise le solde du coffre lui-même (2.2), pas de `transferFrom` ni d'`approve` côté owner.

3.2 **Couverture des emprunts sans toucher aux prix.** Avec les prix de 2.2 (USDC 1 $, WETH 2 500 $, rsETH 2 500 $), la capacité de bots[1] vient du rsETH (LTV 7 500) **et** du USDC en garantie (LTV 8 000) : lend-eth 900 × 2 500 × 0,75 + 4 500 000 × 0,8 = 5 287 500 $ pour 4 800 000 $ empruntés ; lend-avax 300 × 2 500 × 0,75 + 3 000 000 × 0,8 = 2 962 500 $ pour 2 475 000 $. Le collatéral USDC doit donc être déposé **avant** les `borrow`. Les prix ne changent jamais : aucune étape du seed (ni de l'attaque, ni du trafic normal) n'appelle `setPriceE8`.

3.3 **Mode maintenance pendant le seed (2.10).** Les emprunts du seed font chuter la liquidité et monter l'utilisation : moteur allumé, cela ressemblerait à une attaque. Donc tout `run_seed()` s'exécute dans `with maintenance(emit):` (fichier `data/runtime/<network>/maintenance.flag` créé au début, supprimé dans un `finally`, même en cas d'échec). Le moteur (T3) continue de stocker les snapshots mais n'évalue aucune règle et vide sa fenêtre quand le fichier disparaît. On ne touche jamais au guardian du coffre (`setGuardian` n'est pas appelé).

3.4 Ordre : préflight → `maintenance` ouvert → mints → `ensure_allowance` pour toutes les paires (bot, jeton, spender) utilisées par seed **et** normal (bots[0] USDC/WETH → 2 marchés ; bots[1] USDC → 2 marchés pour le collatéral ; bots[1] et bots[2] WETH → bridge, rsETH → 2 marchés, WETH/USDC → 2 marchés pour `repay`) → supplies bots[0] → bridge + collatéral rsETH → collatéral USDC → emprunts → supplies du coffre → vérification `detect_seed_state() == "seeded"` → `maintenance` fermé (finally).

3.5 Idempotence : `detect_seed_state() -> Literal["empty", "seeded", "partial"]`. `empty` : rsETH supply 0 et tous `total_supplied`/`total_collateral` à 0. `seeded` : toutes les valeurs de 3.1 exactes (y compris les collatéraux USDC) + guardian = `roles.guardian` + prix USDC/WETH/rsETH = 1 $ / 2 500 $ / 2 500 $. Sinon `partial`. `run_seed()` : `seeded` → émet `already_seeded`, n'envoie **aucune** transaction, renvoie `{"status": "already_seeded"}` ; `partial` → `PreflightError("partial seed state, run make reset")`, exit 2 ; `empty` → seed complet, renvoie `{"status": "seeded", "txs": n, "end_block": b}`.

3.6 Préflight (exit 2) : fichier de déploiement absent, `chain_id` ≠ `settings.CHAIN_ID`, moins de 3 bots, sur fuji solde natif < 0,05 AVAX pour un rôle utilisé (message listant les adresses concernées et invitant à lancer `make fund-roles` de T1). `run_seed(manage_maintenance: bool = True)` : `reset` l'appelle avec `False` car il a déjà ouvert le mode maintenance (sinon le `finally` du seed supprimerait le fichier avant la fin du reset).

**4. Attaque (`scenario/attack.py`)**

```python
def run_attack(p: AttackParams, run_id: str, emit: Emitter) -> RunRecord
def main(argv: list[str] | None = None) -> int
# CLI : python -m scenario.attack [--seed N] [--variant default|slow|usdc] [--json] [--run-id RUN-…]
#       [--interval-s X] [--warmup-s X] [--freeze-delay-s X]
```
Algorithme (M = `p.market`, A = `p.drain_asset`, X = attaquant, B0 = `bots[0]`) :
1. Préflight : `detect_seed_state()` doit être `seeded` (sinon exit 2, sauf `--skip-seed-check`). `start_block = w3().eth.block_number`. `treasury_supplied_at_start` = `getUserSupplied(vault, asset)` pour chaque déploiement × {USDC, WETH}, clé `"<deployment>:<asset>"`, en chaîne d'unités de base : **toujours les 4 clés** `lend-eth:WETH`, `lend-eth:USDC`, `lend-avax:WETH`, `lend-avax:USDC` (valeur `"0"` si la position est vide).
2. `sleep(warmup_s)` (baseline du moniteur), émet `start`.
3. `forgedRelease(X, units(forged_amount, "rsETH"))` envoyé par X → `phase_blocks["forged_release"]` = `attack_start_block`. Émet `forged_release` avec `conservationGap`, `sourceNonce`, `destinationNonce` et le ratio d'affichage lus juste après (1 935 par défaut).
4. `sleep(gap_s)` ; `ensure_allowance(X, "rsETH", M)` ; `depositCollateral(rsETH, montant)` → `collateral_deposit` (bloc du dépôt, pas de l'approve).
5. `sleep(gap_s / 2)` puis boucle, `i = 1..max_chunks` : lire `available_liquidity` de A sur M **à chaque tour** (le coffre peut avoir retiré entre-temps) ; si 0 → sortir ; `amount = min(units(chunk), avail)` ; `borrow(A, amount)` par X ; le premier fixe `first_borrow` ; si la liquidité lue après vaut 0 → `liquidity_zero` = bloc de ce borrow, sortir. Si `i ∈ withdraw_after` : B0 `withdraw(A, bot_withdraw_amount, B0)` avec `expect_revert=True` (si la liquidité ne suffit pas : étape `bot_withdraw` status `blocked`, c'est le déposant coincé). `sleep(interval_s)` entre deux tours. Revert « insufficient collateral » → étape `failed`, sortie de boucle, `liquidity_zero` absent, exit 1 après écriture du record.
6. Ruée finale : une tentative B0 `withdraw(A, bot_withdraw_amount)` → attendue `blocked`.
7. `sleep(freeze_delay_s)` ; protocol_guardian `setReserveFrozen(rsETH, true)` sur M → `protocol_freeze`.
8. `sleep(cooldown_s)` ; `end_block` ; `RunRecord(label="attack", network=settings.NETWORK, variant, seed, params=p.as_params(), …)` → `write_run_record` ; émet `done` avec `msg` = chemin du fichier.

Valeurs attendues, défaut, sans réaction du coffre (identiques à `fixtures/snapshots_attack.jsonl`) : 6 emprunts réussis (600 WETH), 2 retraits de bots réussis (après les emprunts 4 et 5), liquidité 800 → 0 ; lend-eth WETH `total_supplied` 1 800, `total_borrowed` 1 800, 10 000 bps ; collatéral rsETH lend-eth 5 900 ; rsETH supply 6 200, couverture 1 935 bps ; rsETH gelé sur lend-eth seulement ; lend-avax intact. Ne jamais supposer « 8 tranches » : si une fixture affiche encore `chunks: 8`, elle est périmée (la signaler à T0) ; les paramètres écrits sont ceux de `as_params()` (`forged_amount`, `chunk_weth`, `interval_s`, `bot_withdrawals`…).

**5. Trafic normal (`scenario/normal.py`)**

```python
@dataclass
class MarketView:    # par (deployment, asset) : supplied, borrowed, available (int base units)
class NormalAction:  kind: Literal["supply","withdraw","borrow","repay","large_deposit","bridge_deposit"]; actor: int; deployment_id: str; asset: str; amount: int
def plan_next_action(view: dict, rng: random.Random, p: NormalParams, tick: int) -> NormalAction | None   # PUR
def run_normal(p: NormalParams, run_id: str, emit: Emitter) -> RunRecord
# CLI : python -m scenario.normal --minutes M [--seed N] [--json] [--run-id …] [--tick-s X] [--ticks N]
```
- `tick_s` = 6 (fuji) / 1 (local) ; nombre de ticks = `ticks` ou `int(minutes*60/tick_s)`.
- Tick 0 : `bridge_deposit` bots[2] `bridge.deposit(200 WETH)` puis collatéral 150 rsETH sur lend-eth, 50 sur lend-avax (la couverture reste 10 000). Tick `int(0,4 × N)` : `large_deposit` bots[0] `supply` 300 WETH sur lend-eth.
- Autres ticks, tirage pondéré : supply 30 (bots[0], WETH [5 ; 40] ou USDC [10 000 ; 100 000]), withdraw 25 (bots[0]), borrow 25 (bots[2]), repay 20 (bots[2]) ; marché tiré parmi les 2 déploiements, actif parmi USDC/WETH.
- Garde-fous (action ignorée avec étape `skip` si impossible) : montant ≤ 10 % de `available` ; après un borrow `(borrowed+amt)*10000/supplied ≤ 8500` ; après un withdraw `borrowed*10000/(supplied-amt) ≤ 8500` et `amt ≤` position du bot ; borrow ≤ 80 % de la capacité restante de bots[2] (collatéral × prix oracle × LTV − dettes) ; repay ≤ min(dette, solde).
- Interdit : `forgedRelease`, `setReserveFrozen/Paused`, `setPriceE8`, toute opération sur le coffre, tout emprunt de bots[1] (sa capacité restante est réservée à l'état de 2.2).
- `run_normal` est **bloquant** (rend la main à la fin des ticks ; `make normal` aussi) et écrit toujours un `RunRecord(label="normal", variant="default", attack_start_block=None, phase_blocks={}, treasury_supplied_at_start=<les 4 clés>)` via `write_run_record`, même interrompu par Ctrl-C (dans un `finally`, `end_block` = dernier bloc lu).

**6. Reset (`scenario/reset.py`)** : `run_reset(emit, deploy_cmd=("make", "deploy", "FORCE=1")) -> None`. Tout le reset s'exécute dans `with maintenance(emit):` (fichier créé au début, supprimé dans un `finally`). Lance `deploy_cmd` (cwd = `settings.ROOT`, env courant, qui contient déjà `NETWORK` ; ne jamais le redéfinir), relaie chaque ligne en étape `deploy` (status `info`), exit ≠ 0 → `ScenarioError` (exit 1). `FORCE=1` est obligatoire sur fuji (T1 refuse d'écraser `deployments/fuji.json` sans lui) et sans effet sur local. Vérifie que `deployments/<network>.json` a changé (mtime ou `deployed_at_block`). Puis `run_seed(manage_maintenance=False)` (exit 2 si échec). Sur fuji, avertissement : redéploiement payant, ~2 min, les adresses changent. Pas de RunRecord pour reset/seed.

**7. API (`backend/api/demo.py`)**

```python
class AttackBody(BaseModel): seed: Optional[int] = None; variant: Literal["default", "slow", "usdc"] = "default"
class Runner(Protocol):
    def start(self, argv: list[str], on_line: Callable[[str], None], on_exit: Callable[[int], None]) -> None
class SubprocessRunner:   # Popen(argv, cwd=ROOT, stdout=PIPE, stderr=STDOUT, text=True, env={**os.environ, "PYTHONUNBUFFERED": "1"}) + thread lecteur
def get_runner() -> Runner          # dépendance FastAPI, surchargée dans les tests
def _reset_store() -> None          # from backend.store import store; store.reset()
_RUNS: dict[str, DemoRun]; _LOCK = threading.Lock()
```
- `USE_FIXTURES=true` → comportement fixture actuel (2.9). Sinon :
- `POST /api/demo/attack` : sémantique de 2.9 : `seed = null` (ou absent) → le backend tire `seed = random.SystemRandom().randint(1, 999999)` et le renvoie ; `seed = 0` → paramètres par défaut, sans hasard ; `seed ≥ 1` → tel quel ; `seed < 0` → 422. `run_id = new_run_id("attack", seed)` ; argv `[sys.executable, "-m", "scenario.attack", "--json", "--run-id", run_id, "--variant", v, "--seed", str(seed)]` ; `DemoRun(kind="attack", variant=v, seed=seed, status="running", params=attack_params(v, seed).as_params())` stocké puis renvoyé immédiatement (le front affiche la graine pour pouvoir rejouer le run).
- `POST /api/demo/reset` : argv `python -m scenario.reset --json --run-id …` ; à la sortie 0 : `_reset_store()` **puis** `status="done"` ; sortie ≠ 0 : pas de reset du store, `status="failed"`.
- `on_line` : ligne JSON → `f"[{block}] {step}: {msg}"` (sans `[block]` si nul) ; ligne non JSON → telle quelle ; 500 lignes max (on garde les dernières).
- `on_exit(code)` : `finished_at = now(UTC)`, `done` si 0, sinon `failed` + ligne `"exit code {code}"`.
- Un seul run `attack`/`reset` à la fois : sinon `409 {"detail": "demo run already running: RUN-…"}` (code prévu par 2.9). `variant` hors `default|slow|usdc` ou corps invalide → 422 (validation FastAPI).
- `GET /api/demo/runs/{run_id}` : `DemoRun` ou `404 {"detail": "run not found"}`.

**8. `mk/t2.mk`**
```make
# NETWORK n'est JAMAIS défini ici : il vient de .env (inclus et exporté par le Makefile racine) ou de la ligne de commande.
PYTHON ?= python3
SEED ?= 0
VARIANT ?= default
MINUTES ?= 5
.PHONY: seed attack normal reset test-t2
seed:    ; $(PYTHON) -m scenario.seed
attack:  ; $(PYTHON) -m scenario.attack --seed $(SEED) --variant $(VARIANT)
normal:  ; $(PYTHON) -m scenario.normal --minutes $(MINUTES) --seed $(SEED)   # bloquant, écrit un RunRecord label "normal"
reset:   ; $(PYTHON) -m scenario.reset                                         # make deploy FORCE=1 puis seed, sous maintenance.flag
test-t2: ; $(PYTHON) -m pytest backend/tests/test_t2_*.py -q
```
`make test` (T0) appelle `test-t2` ; ne jamais filtrer avec `-k`.

#### Tests qui doivent passer

Commande unique : `make test-t2`. Les fichiers `*_chain.py` commencent par `pytestmark = pytest.mark.skipif(not local_chain_ready(), reason="anvil + make deploy required")`. Setup chaîne : terminal 1 `anvil` (automine, plus rapide) ou `make chain` ; terminal 2 `NETWORK=local make deploy`. Fixture de session : `run_seed()` une fois puis `evm_snapshot()` ; chaque test commence par `evm_revert` + nouveau `evm_snapshot`. Les attaques de test passent `interval_s=0, warmup_s=0, freeze_delay_s=0`.

| Id | Type | Fichier :: test | Setup | Résultat attendu |
|---|---|---|---|---|
| T2-01 | unit | `test_t2_params.py::test_default_attack_params` | `attack_params("default", 0, "fuji")` | forged 5000, WETH, chunk 100, interval 8.0, warmup 24.0, freeze_delay 80.0, withdraw_after (4,5), bot 100 ; `network="local"` → interval 1.0 |
| T2-02 | unit | `::test_seeded_params_deterministic_and_in_range` | seeds 1..200, chaque variante | même seed → mêmes params ; forged ∈ [3000 ; 8000] multiple de 500 ; chunk dans l'ensemble ; 1–3 index distincts dans [2 ; 7] |
| T2-03 | unit | `::test_variants` | `slow`, `usdc`, `"foo"` | slow chunk 25 interval 24.0 ; usdc USDC 250000 ; `"foo"` → `ValueError` |
| T2-04 | unit | `::test_as_params_types` | défaut, réseau fuji | toutes valeurs str/int/float/bool ; clés `forged_amount`, `chunk_weth`, `interval_s`, `bot_withdrawals` présentes ; `forged_amount == 5000`, `chunk_weth == 100`, `interval_s == 8.0`, `bot_withdrawals == 2`, `withdraw_after == "4,5"` ; variante `usdc` → `chunk_weth == 0`, `chunk_usdc == 250000` |
| T2-05 | unit | `::test_no_rules_coupling` | lire `scenario/*.py` | aucun ne contient `rules.yaml`, `backend.rules`, `backend.engine`, `backend.config` |
| T2-06 | unit | `test_t2_common.py::test_run_id_format` | `new_run_id("attack", 42, datetime(2026,10,11,8,0,0,tzinfo=UTC))` | `"RUN-20261011080000-attack-42"` |
| T2-07 | unit | `::test_write_run_record_roundtrip` | `monkeypatch` `settings.DATA_DIR` → `tmp_path` ; record = `fixtures/run_record.example.json` | fichier `tmp_path/runs/RUN-20261011080000-attack-42.json` ; relu via `RunRecord.model_validate_json` == original |
| T2-08 | unit | `::test_emitter_json_line` | `Emitter(json_mode=True, stream=io.StringIO())` | une ligne, JSON valide, 7 clés exactes de la rubrique Sorties |
| T2-09 | unit | `::test_units` | — | `units(150,"WETH") == 150*10**18` ; `units(400000,"USDC") == 400000*10**6` |
| T2-12 | unit | `::test_maintenance_flag_lifecycle` | `monkeypatch` `settings.DATA_DIR` → `tmp_path` ; `with maintenance(emit): raise RuntimeError` | dans le bloc, `tmp_path/runtime/<network>/maintenance.flag` existe ; après l'exception, il n'existe plus |
| T2-13 | unit | `::test_reset_runs_under_maintenance` | `run_reset(emit, deploy_cmd=["true"])` avec `run_seed` patché (enregistre l'existence du flag et `manage_maintenance`) et le fichier de déploiement touché | flag présent pendant `run_seed`, `manage_maintenance is False`, flag absent à la fin ; `deploy_cmd` qui échoue → `ScenarioError` et flag absent |
| T2-10 | unit | `test_t2_normal_plan.py::test_guards_hold_over_2000_steps` | vue initiale 2.2, `rng=Random(7)`, applique chaque action à la vue | utilisation ≤ 8500 partout ; montant ≤ 10 % du disponible ; aucun `kind` hors liste |
| T2-11 | unit | `::test_scheduled_actions` | N = 50 ticks | tick 0 → `bridge_deposit` ; tick 20 → `large_deposit` 300 WETH lend-eth |
| T2-20 | chaîne | `test_t2_seed_chain.py::test_seed_matches_contract_table` | seed de session | les 4 réserves de prêt exactes de 3.1 ; collatéraux rsETH 900e18 / 300e18 et USDC 4500000e6 / 3000000e6 (`total_collateral`), `total_supplied` USDC inchangé par le collatéral ; rsETH supply 1200e18, backing 10000 ; positions coffre 150e18 / 400000e6 / 100e18 / 300000e6 ; idle 0 |
| T2-21 | chaîne | `::test_seed_leaves_prices_guardian_and_flag` | idem | `getPriceE8` = 1e8 (USDC), 2500e8 (WETH), 2500e8 (rsETH) ; aucun évènement `PriceUpdated` après `deployed_at_block` ; `vault.guardian() == roles.guardian` ; `depositsPaused() is False` ; `maintenance.flag` absent |
| T2-22 | chaîne | `::test_seed_idempotent` | relancer `run_seed()` | `{"status": "already_seeded"}` ; nonces de tous les rôles inchangés |
| T2-23 | chaîne | `::test_partial_state_rejected` | bots[0] `supply` 1 WETH en plus | `detect_seed_state() == "partial"` ; `run_seed()` lève `PreflightError` |
| T2-24 | chaîne | `::test_bot_balances` | idem T2-20 | bots[0] 500 WETH + 1 000 000 USDC ; bots[1] 1 750 WETH + 2 900 000 USDC, 0 rsETH ; bots[2] 500 WETH |
| T2-30 | chaîne | `test_t2_attack_chain.py::test_default_attack_end_state` | `run_attack(défaut)` | `conservationGap() == 5000e18`, `destinationNonce() == sourceNonce()+1`, ratio d'affichage `backingRatioBps() == 1935` ; lend-eth WETH available 0, supplied 1800e18, borrowed 1800e18, util 10000 ; attaquant 600e18 WETH empruntés et en solde ; collatéral rsETH 5900e18 ; rsETH gelé lend-eth, pas lend-avax ; lend-avax WETH available 450e18 |
| T2-31 | chaîne | `::test_attack_run_record` | idem | `data/runs/<run_id>.json` existe ; label attack, variant default, seed 0 ; 5 clés de phase ; `forged_release < collateral_deposit < first_borrow < liquidity_zero < protocol_freeze` ; `attack_start_block == forged_release` ; `start_block < forged_release` ; `end_block ≥ protocol_freeze` ; `treasury_supplied_at_start` = exactement les 4 clés `lend-eth:WETH` `"150000000000000000000"`, `lend-eth:USDC` `"400000000000"`, `lend-avax:WETH` `"100000000000000000000"`, `lend-avax:USDC` `"300000000000"` ; `params` contient `forged_amount`, `chunk_weth`, `interval_s`, `bot_withdrawals` |
| T2-32 | chaîne | `::test_attack_json_cli` | `subprocess.run([sys.executable,"-m","scenario.attack","--json","--interval-s","0","--warmup-s","0","--freeze-delay-s","0"])` | exit 0 ; chaque ligne est du JSON ; comptes : `borrow` 6, `bot_withdraw` 2 `ok`, 1 `blocked`, puis `liquidity_zero`, `protocol_freeze`, `done` |
| T2-33 | chaîne | `::test_attack_after_treasury_exit` | owner `vault.emergencyWithdraw(lend-eth, WETH)` avant l'attaque | attaquant emprunte 450e18 ; 2e retrait de bot `blocked` ; coffre idle WETH 150e18 ; available 0 |
| T2-34 | chaîne | `::test_usdc_variant` | variante `usdc` | lend-eth USDC available 0 ; lend-eth WETH available 800e18 inchangé |
| T2-40 | chaîne | `test_t2_normal_chain.py::test_normal_safe` | `run_normal(ticks=60, seed=7, tick_s=0)` | pour chaque bloc de `[start_block ; end_block]`, `getReservesData(block_identifier=b)` : util ≤ 8500 sur USDC/WETH ; 0 évènement `Released` avec `backed == false` ; `backingRatioBps() == 10000` ; rsETH supply 1400e18 |
| T2-41 | chaîne | `::test_normal_run_record` | idem | `data/runs/<run_id>.json` écrit à la fin de l'appel (bloquant) ; label normal, `attack_start_block is None`, `phase_blocks == {}`, 4 clés dans `treasury_supplied_at_start` ; étapes émises contiennent `bridge_deposit` et `large_deposit` (status ok) |
| T2-50 | API | `test_t2_demo_api.py::test_attack_starts_run` | `TestClient(app)`, `USE_FIXTURES=False`, `FakeRunner` qui enregistre argv | corps `{}` : 200, `kind=="attack"`, `status=="running"`, `1 ≤ seed ≤ 999999`, argv contient `-m scenario.attack --json --run-id <run_id> --variant default --seed <seed>`, `run_id` finit par `-attack-<seed>` ; corps `{"seed": 0}` : `seed == 0`, `params["chunk_weth"] == 100` ; corps `{"seed": 42}` : `seed == 42` |
| T2-51 | API | `::test_log_and_exit_done` | Fake émet `{"step":"forged_release","block":12,"msg":"x",…}` puis exit 0 | GET → `log == ["[12] forged_release: x"]`, `status=="done"`, `finished_at` non nul |
| T2-52 | API | `::test_exit_nonzero_failed` | exit 3 | `status=="failed"`, dernière ligne `"exit code 3"` |
| T2-53 | API | `::test_reset_calls_store_reset_only_on_success` | `_reset_store` patché (compteur) | exit 0 → 1 appel ; exit 1 → 0 appel |
| T2-54 | API | `::test_404_and_409_and_422` | — | run inconnu 404 `{"detail": "run not found"}` ; 2e attaque (ou reset) pendant `running` 409 ; `variant="foo"` 422 ; `seed=-1` 422 |
| T2-55 | API | `::test_fixture_mode` | `USE_FIXTURES=True` | réponse == `fixtures/demo_run.json` ; runner jamais appelé |

#### Definition of done

- [ ] `make test-t2` vert avec anvil + `make deploy` (0 skip) et sans chaîne (tests chaîne en skip, le reste vert).
- [ ] `make reset && make attack` sur local reproduit les chiffres de T2-30.
- [ ] `make seed` deux fois de suite : la 2e n'envoie aucune transaction.
- [ ] `make attack SEED=42` et `SEED=43` donnent des params différents et deux `data/runs/*.json` valides.
- [ ] `make normal MINUTES=2` sur local tourne sans exception, rend la main à la fin et écrit un `data/runs/*.json` label `normal`.
- [ ] Moteur allumé (`make demo`), `make reset` puis `make seed` : aucune alerte ni décision créée pendant le seed ; `data/runtime/local/maintenance.flag` absent à la fin, y compris après un seed interrompu (Ctrl-C).
- [ ] Rôles financés sur Fuji via `make fund-roles` (T1) ; un seed + une attaque par défaut joués une fois sur Fuji ; liens snowtrace des tx `forgedRelease` et `setReserveFrozen` notés pour T9.
- [ ] Bouton du front (ou `curl -X POST :8000/api/demo/attack -H 'content-type: application/json' -d '{"seed": null}'`) → `DemoRun` avec une graine tirée dans [1 ; 999999], qui passe `done`, logs visibles ; un 2e appel pendant le run → 409.
- [ ] `POST /api/demo/reset` sur fuji redéploie (`make deploy FORCE=1`) puis re-seed sans intervention.
- [ ] `scenario/_compat.py` supprimé si T0 a livré les helpers 2.4.

#### Pièges connus

- **Ordre du seed** (3.2) : le collatéral USDC de bots[1] (4 500 000 / 3 000 000) doit être déposé **avant** les emprunts, sinon `borrow` revert « insufficient collateral ». Ne jamais « réparer » en touchant à l'oracle : les prix de 2.2 ne bougent pas.
- Le collatéral et la liquidité sont deux soldes séparés : `depositCollateral(USDC)` augmente `total_collateral`, pas `total_supplied` ni `available_liquidity`. Ne pas utiliser `supply` pour le collatéral.
- **bots[1] n'emprunte plus après le seed** : seul bots[2] emprunte dans le trafic normal (la marge de bots[1] fait partie de l'état de référence).
- **Mode maintenance** : toujours dans un `finally` ; un fichier `maintenance.flag` oublié éteint toute la détection (le moteur n'évalue plus aucune règle). En cas de doute : `rm data/runtime/<network>/maintenance.flag`. Ne pas imbriquer deux `maintenance()` (d'où `run_seed(manage_maintenance=False)` dans le reset).
- `TreasuryVault.supply` utilise le solde du coffre : minter (ou transférer) les jetons **au coffre** avant `vault.supply`, sinon revert.
- `MiniLend.withdraw` d'un montant précis revert « insufficient balance » si le montant dépasse la position du bot, « insufficient liquidity » s'il dépasse la liquidité : seul le second est attendu (`blocked`) pendant la ruée ; le premier est un bug du scénario (`failed`).
- `chain.send` appelle `estimate_gas` : un revert lève `ContractLogicError` **avant** l'envoi (pas de reçu status 0). Les retraits de bots bloqués doivent être attrapés (`expect_revert=True`).
- `approve` avant `supply`, `bridge.deposit`, `depositCollateral`, `repay`. USDC a 6 décimales.
- Nonces : un process par rôle. Ne jamais lancer `normal` et `attack` en même temps (bots[0] commun) ; l'API refuse les runs concurrents.
- Sur fuji, `make deploy` sans `FORCE=1` refuse d'écraser le déploiement existant : `reset` passe toujours `FORCE=1`. Prévenir l'équipe, les adresses changent.
- Après `make reset`, les adresses changent : toujours rappeler `chain.lending()`, `token()`… à chaque run, ne pas garder d'objet `Contract` en variable globale.
- Sous-processus : `PYTHONUNBUFFERED=1` et `flush=True`, sinon les logs arrivent à la fin.
- `RunRecord.params` n'accepte pas les listes : `"4,5"`.
- `fixtures/deployments.example.json` utilise `Bridge`/`Oracle` ; 2.3 fait foi (`MockBridge`/`MockOracle`).
- Fuji : attaque par défaut ≈ 3 min (warmup 24 s + 6 emprunts × 8 s + gel à 80 s) ; RPC public limité, utiliser un RPC fournisseur.
- **Non-circularité** : aucun paramètre d'attaque ne doit être choisi en regardant les seuils de 2.7/rules.yaml (T2-05 le vérifie). Les plages de tirage ci-dessus sont la seule référence.
- Si la réaction de T4 est active, la liquidité baisse plus vite (le coffre retire 150 WETH) : la boucle relit la liquidité à chaque tour (T2-33).

#### Plus tard (phase 2)

- Variantes : vidage sur lend-avax, attaque en un seul bloc (flash), saignée lente, plusieurs attaquants, manipulation d'oracle.
- Liquidations dans le trafic normal, profils de trafic plus réalistes (périodes creuses, rafales).
- Rejeu de l'incident mainnet (avec T7).

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T2 (scénario : seed, attaque, trafic normal, reset) de TASKS.md.
1. Lis TASKS.md sections 1 et 2, puis la section T2 en entier. Lis backend/models.py,
   backend/settings.py, backend/chain.py, fixtures/run_record.example.json, fixtures/demo_run.json.
   Ne lis PAS backend/config/rules.yaml pour régler l'attaque (non-circularité).
2. Ne modifie QUE : scenario/* (sauf scenario/__init__.py, à T0), backend/api/demo.py, mk/t2.mk, backend/tests/test_t2_*.py.
   Pour tout changement ailleurs ou du contrat (section 2), n'édite pas : écris la demande
   dans docs/contract-requests.md et préviens-moi.
3. Commence par les tests purs (T2-01 à T2-11, T2-50 à T2-55), puis le code qui les fait passer.
   Si backend/chain.py n'a pas encore token()/vault()/bridge()/oracle()/bot_accounts(),
   crée scenario/_compat.py basé sur chain.contract() et chain.load_deployment().
4. Ensuite les tests chaîne (T2-20 à T2-41) : ils doivent se mettre en skip sans anvil.
   Quand T1 a livré, lance `anvil` puis `NETWORK=local make deploy` et fais-les passer.
5. Respecte exactement les chiffres de la section T2 (3.1, 3.2, valeurs attendues de l'attaque).
   Aucun appel à setPriceE8 ni à setGuardian : le seed dépose le collatéral USDC avant les emprunts
   et tourne sous data/runtime/<network>/maintenance.flag (créé au début, supprimé dans un finally).
6. Avant chaque commit : make test-t2 vert (pytest backend/tests/test_t2_*.py, jamais -k).
   Push fréquent après chaque test vert.
```


---


### T3 · Moteur de surveillance : collecteur, règles R1 à R5, API d'état

**T3 branch hardening — version 3:** the rule formulas, evidence qualifications and replay expectations in the legacy version-2 sheet below are superseded for T3 by `docs/product/THRESHOLDS.md`, `backend/config/rules.yaml` and the `test_t3_*` regression tests. CR-004 in `docs/contract-requests.md` records the integration delta; other tasks and shared fixtures are not rewritten. R1 cannot establish real-chain forgery from the current Snapshot contract. Eight alerts (including global bridge pause), not seven, are expected when the unchanged synthetic attack snapshots are processed by version 3. Collector and live state API remain incomplete; mocked tests do not validate live detection.

**Objectif.** Lire l'état de la chaîne à chaque nouveau bloc (un `Snapshot`), appliquer les cinq règles simples R1 à R5 de la section 2.7 sur une fenêtre glissante, émettre des `Alert` sans doublon, les passer aux abonnés (T4) et servir `GET /api/health`, `/api/state`, `/api/series`, `/api/alerts` à partir du store quand `USE_FIXTURES=false`. Un indicateur par règle, rien de plus dans le MVP.

**Dépend de.**
- T0 → `backend/models.py`, `settings.py`, `chain.py`, `store.py` (dont `Store.generation`, incrémenté par `reset()`), `main.py`, fixtures → en attendant `backend/store.py` : la classe `MemStore` écrite dans tes tests (voir T3-12, avec son propre `generation`) ; en attendant le câblage de `main.py` : `make monitor` lance la boucle seule.
- T1 → contrats, compteurs bridge `sourceLocked/destinationReleased`, nonces source/destination, `deployments/<network>.json`, `abi/*.json` → en attendant : `fixtures/snapshots_attack.jsonl` et `snapshots_normal.jsonl` (les règles, le moteur et l'API se testent entièrement sans chaîne) ; le test collecteur sur anvil est `skip` tant que `deployments/local.json` n'existe pas ou que le coffre n'a rien déposé (`getUserSupplied(vault, WETH) == 0` sur `lend-eth`).
- T2 → `make seed` (positions du coffre sur anvil) et le fichier `data/runtime/<network>/maintenance.flag` créé au début de `seed`/`reset` et supprimé dans un `finally` (2.10) → en attendant : mêmes fixtures ; les tests créent et suppriment le fichier eux-mêmes.

**Débloque.** T4 (reçoit `(alerts, snapshot)` via `Engine.on_alerts`, appelé par `await asyncio.to_thread(handler, alerts, snapshot)` un appel à la fois, utilise `rules_version`), T2 (le mode maintenance évite que `seed`/`reset` ressemblent à une attaque), T5 (lit `store.alerts()`, `store.latest_snapshot()`), T6 (les quatre routes de T3 en mode réel), T7 (lit `/api/alerts` pour la détection et le délai de détection), T9 (chiffres de la démo).

**Fichiers possédés.** `backend/collector.py`, `backend/rules.py`, `backend/engine.py`, `backend/config/rules.yaml`, `backend/api/state.py`, `backend/tests/test_t3_*.py`, `mk/t3.mk`.

**À lire avant de commencer.** TASKS.md sections 1.2, 1.5, 2.2 (MiniLend, MockBridge, MockOracle, TreasuryVault), 2.3, 2.4, 2.5, 2.6, 2.7, 2.9, 2.10 ; `backend/models.py` (Snapshot, Alert, StateResponse, SeriesPoint, Health) ; `backend/chain.py` ; les deux fichiers `fixtures/snapshots_*.jsonl` (une ligne = un `Snapshot` JSON, un snapshot tous les 2 blocs, blocs 45201800 à 45201880).

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| Adresses des contrats | `deployments/<network>.json` (2.3), relu à chaque boucle via `chain.load_deployment()` | T1 | aucune nécessaire pour règles/moteur/API ; collecteur : `skip` |
| ABIs | `abi/MiniLend.json`, `MockERC20.json`, `RsETH.json`, `MockBridge.json`, `MockOracle.json`, `TreasuryVault.json` | T1 | idem |
| Chaîne locale peuplée | anvil + `make deploy` + `make seed` (positions 150 WETH + 400 000 USDC sur `lend-eth`, 100 WETH + 300 000 USDC sur `lend-avax`) | T1, T2 | fixtures jsonl |
| Séries de snapshots | `fixtures/snapshots_attack.jsonl` (sans notre réaction), `snapshots_normal.jsonl` | T0 (finales) | — |
| Store | `backend.store.store` (2.10), dont `generation` | T0 | `MemStore` locale aux tests |
| Mode maintenance | présence du fichier `settings.DATA_DIR / "runtime" / settings.NETWORK / "maintenance.flag"` (2.10) | T2 | créé et supprimé par les tests |
| Variables | `NETWORK`, `RPC_URL`, `RPC_FALLBACK_URL`, `CHAIN_ID`, `USE_FIXTURES`, `ENGINE_ENABLED`, `POLL_INTERVAL_S` | `.env` | valeurs par défaut de `settings.py` |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| `Snapshot` (source `"live"`) | `models.Snapshot`, stocké par `store.add_snapshot` | T3 (règles), T4, T5, T6 via `/api/state` |
| `Alert` | `models.Alert`, id `ALT-<network>-<block>-<rule_id>-<deployment_id ou global>-<asset ou all>`, stockée par `store.add_alerts` | T4 (`on_alerts`), T5, T6, T7 |
| Appel des abonnés | `handler(new_alerts: list[Alert], snapshot: Snapshot)`, seulement si `new_alerts` non vide ; dans `run_forever` : `await asyncio.to_thread(handler, new_alerts, snapshot)`, un appel à la fois, dans l'ordre des snapshots | T4 (`responder.handle`) |
| `rules_version` | `"sha256:" + sha256(octets exacts de backend/config/rules.yaml)` (71 caractères) | T4 (décision), T7, T9 |
| `GET /api/health`, `/api/state`, `/api/series`, `/api/alerts` | `Health`, `StateResponse`, `SeriesPoint[]`, `Alert[]` (2.9) | T6, T7 |
| `make test-t3`, `make monitor-once`, `make monitor`, `make replay-t3` | cibles dans `mk/t3.mk` | tout le monde (debug) |

#### Spécification détaillée

**1. `backend/config/rules.yaml`.** Copie octet pour octet du bloc YAML de 2.7 (avec le saut de ligne final). Toute modification change `rules_version` : c'est voulu (la preuve T4 référence la version).

**2. `backend/rules.py` (fonctions pures, aucun appel réseau, aucune horloge).**

```python
SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
RULES_PATH = settings.CONFIG_DIR / "rules.yaml"

def rules_version(path: Path = RULES_PATH) -> str          # "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
def load_rules(path: Path = RULES_PATH) -> dict             # yaml.safe_load + cfg["_version"] = rules_version(path)
def treasury_positions(s: Snapshot) -> dict[tuple[str, str], PositionSnapshot]   # (deployment_id, asset) -> position, supplied > 0 seulement
def position_value(s: Snapshot, deployment_id: str, asset: str) -> float          # 0.0 si pas de position
def deployment_exposure(s: Snapshot, deployment_id: str) -> float                 # somme value_usd des positions du déploiement
def collateral_exposure(s: Snapshot, token: str) -> tuple[float, list[str]]      # déploiements où reserve(token).ltv_bps > 0 ; somme de leurs positions
def evaluate_r1(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_r2(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_r3(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_r4(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_r5(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_all(window: list[Snapshot], cfg: dict) -> list[Alert]   # concatène R1..R5 (règles enabled), trié (rule_id, deployment_id or "", asset or "")
```

Conventions communes : `s = window[-1]` ; une règle `enabled: false` renvoie `[]` ; `window` vide renvoie `[]`. Chaque alerte : `network=s.network`, `block_number=s.block_number`, `block_time=s.block_time`, `detected_at=s.block_time` (le moteur le remplace), `rules_version=cfg["_version"]`, `id` construit avec `make_alert_id(s, rule_id, deployment_id, asset)`. Les montants affichés sont convertis en unités humaines (`int(x) / 10**decimals`), formatés `f"{v:,.0f}"` si entier sinon `f"{v:,.2f}"` ; les pourcentages à une décimale (`19.4 %`, espace avant `%`). Les `metrics` ne contiennent que des `int`, `float` ou `str` (pas de `bool`).

| Règle | Algorithme | `metrics` | `title` / `explanation` (anglais) |
|---|---|---|---|
| R1 | pour chaque token ponté : `gap = destination_released - source_locked`; critical si `gap > 0` ou `destination_nonce > source_nonce`; `deployment_id=None`, `asset=symbol`; exposition = `collateral_exposure` | `source_locked`, `destination_released`, `conservation_gap`, `source_nonce`, `destination_nonce`, `exposed_deployments` | `"rsETH bridge invariant broken"` / `"The rsETH bridge released 5,000 tokens without canonical source backing; destination nonce 308 is ahead of source nonce 307."` |
| R2 | pour la réserve rsETH de chaque déploiement qui l'accepte en garantie : `baseline=max(total_collateral)` sur `window[:-1]`; si au moins 2 valeurs et baseline > 0, `increase_bps=(current-baseline)*10000//baseline`; ≥ 20000 → critical, sinon ≥ 5000 → high | `total_collateral`, `baseline_collateral`, `increase_pct`, `window_snapshots` | `"rsETH collateral surge on lend-eth"` / `"rsETH collateral on lend-eth rose 555.6 % within the last 20 snapshots (from 900 to 5,900 rsETH)."` |
| R3 | pour chaque réserve `borrowable` avec position du coffre : baseline = max de `available_liquidity` sur `window[:-1]`; baisse ≥ 60 % → critical, ≥ 30 % → high | `available_liquidity`, `max_available_liquidity`, `drop_pct`, `window_snapshots` | `"WETH liquidity draining on lend-eth"` / `"Available WETH liquidity on lend-eth fell 37.5 % within the last 20 snapshots (from 800 to 500 WETH)."` |
| R4 | chaque position (`supplied > 0`) : `withdrawable_ratio_bps < 5000` → critical, sinon `< 8000` → high | `withdrawable_ratio_bps`, `withdrawable_now`, `supplied`, `threshold_bps` | `"Our WETH exitability dropped on lend-eth"` / `"Only 66.7 % of our 150 WETH position on lend-eth can be withdrawn now (100 WETH)."` |
| R5 | compare `window[-2]` et `s` : bridge `bridge_paused`, ou réserve `frozen/paused`, passe de false à true; high, ou critical si une position concernée a `withdrawable_ratio_bps < critical_withdrawable_below_bps` | `state`, `scope`, `withdrawable_ratio_bps` | `"rsETH containment activated on lend-eth"` / `"The rsETH reserve on lend-eth was frozen; only 0.0 % of our WETH position is withdrawable."` |

Exposition R1 = `collateral_exposure`; R2 et R5 = `deployment_exposure`; R3 et R4 = `position_value`.

```python
class AlertLatch:
    """Dédoublonnage de 2.7 : une émission par (rule_id, deployment_id, asset) et par gravité."""
    def __init__(self) -> None: self._active: dict[tuple[str, str | None, str | None], str] = {}
    def filter(self, candidates: list[Alert]) -> list[Alert]
    def active(self) -> dict[tuple[str, str | None, str | None], str]
    def reset(self) -> None
```

`filter` reçoit **tous** les candidats du snapshot (toutes règles confondues) : une clé absente → retirée de `_active` (la condition a disparu) ; une clé nouvelle → émise ; une clé présente avec gravité strictement plus haute → émise et mise à jour ; même gravité ou plus basse → rien (on ne rétrograde pas la gravité mémorisée). Ordre de sortie = ordre des candidats.

**3. `backend/collector.py`.**

```python
def build_snapshot(block_number: int, client: Web3 | None = None) -> Snapshot   # client par défaut chain.w3()
def ratio_bps(part: int, whole: int) -> int     # arrondi au plus proche, entier : (part*10000 + whole//2) // whole ; 0 si whole == 0
def struct_to_dict(abi: list, fn_name: str, value: tuple) -> dict   # nomme les champs du tuple ReserveData d'après les composants de l'ABI
```

Algorithme (tous les `.call(block_identifier=block_number)` pour un état cohérent ; contrats construits avec `client.eth.contract(address, abi=chain.load_abi(name))` afin de pouvoir passer le client de secours) :
1. `dep = chain.load_deployment()` ; `addr_to_symbol` = inverse de `dep["assets"]` (adresses en minuscules) ; `vault_addr = dep["contracts"]["TreasuryVault"]`.
2. Par actif : `decimals` (cache module, clé adresse), `price_usd = oracle.getPriceE8(asset) / 1e8` (une fois par snapshot ; revert `"Oracle: no price"` → `0.0` + log WARNING).
3. Par déploiement de `dep["lending"]` : **un** appel `getReservesData()` ; pour chaque entrée → `ReserveSnapshot(deployment_id, asset=symbol, asset_address, decimals, total_supplied=str(totalSupplied), total_borrowed, available_liquidity, total_collateral, utilization_bps=utilizationBps, supply_apy_bps=supplyRateBps, borrow_apy_bps=borrowRateBps, ltv_bps=ltvBps, borrowable, frozen, paused, price_usd)`. Adresse inconnue → ignorée, log WARNING.
4. Pour chaque réserve `borrowable` : `supplied = getUserSupplied(vault_addr, asset)` ; si `supplied > 0` → `withdrawable = min(supplied, available_liquidity)`, `PositionSnapshot(wallet=vault_addr, …, withdrawable_ratio_bps=ratio_bps(withdrawable, supplied), value_usd=round(supplied/10**dec*price, 2), withdrawable_usd=round(withdrawable/10**dec*price, 2))`.
5. Jetons : `totalSupply()` de chaque symbole. Pour `rsETH`, lire séparément `bridge.sourceLocked()`, `bridge.destinationReleased()`, `bridge.sourceNonce()`, `bridge.destinationNonce()` et `bridge.paused()` ; renseigner les cinq champs `bridge_*`. Garder `backing=sourceLocked`, et `backing_ratio_bps=ratio_bps(sourceLocked, destinationReleased)` uniquement comme affichage de compatibilité, jamais comme déclencheur R1. Pour les autres jetons, tous les champs bridge et backing valent `None`.
6. Coffre : `VaultStatus(address=vault_addr, deposits_paused=vault.depositsPaused(), idle_balances={symbol: str(token.balanceOf(vault_addr))} pour chaque symbole de dep["assets"])`.
7. `block_time = datetime.fromtimestamp(client.eth.get_block(block_number)["timestamp"], tz=timezone.utc)` ; `network=settings.NETWORK`, `chain_id=settings.CHAIN_ID`, `source="live"`.
8. Toute exception RPC remonte telle quelle (pas de snapshot partiel). Environ 20 appels RPC par snapshot.
9. `python -m backend.collector --once [--block N]` imprime le snapshot en JSON (`model_dump_json(indent=2)`) ; sans `--block`, prend `client.eth.block_number`.

**4. `backend/engine.py`.**

```python
@dataclass
class EngineStatus:
    running: bool = False; rpc_ok: bool = False; rpc_url: str = ""; last_block: int = 0
    last_update: datetime | None = None; last_error: str | None = None; consecutive_errors: int = 0
    maintenance: bool = False; pending_handlers: int = 0
STATUS = EngineStatus()          # lu par backend/api/state.py (interne à T3)

class Engine:
    def __init__(self, store, cfg: dict | None = None, clock: Callable[[], datetime] | None = None): ...
    def on_alerts(self, handler: Callable[[list[Alert], Snapshot], None]) -> None
    def process(self, snapshot: Snapshot) -> list[Alert]   # ingest + appel SYNCHRONE des abonnés (tests, --replay)
    def ingest(self, snapshot: Snapshot) -> list[Alert]    # règles + store, sans appeler les abonnés (utilisé par run_forever)
    def reset(self) -> None                   # vide fenêtre et latch
    def in_maintenance(self) -> bool          # maintenance_flag_path().exists()
    def stop(self) -> None
    async def run_forever(self) -> None
    def _make_client(self, url: str) -> Web3  # remplaçable dans les tests

def maintenance_flag_path() -> Path           # settings.DATA_DIR / "runtime" / settings.NETWORK / "maintenance.flag" (relu à chaque appel)
```

`cfg` par défaut `rules.load_rules()` ; `clock` par défaut `lambda: datetime.now(timezone.utc)` ; la fenêtre contient les `cfg["window_snapshots"]` (= 20) **derniers snapshots** (pas des blocs : sur anvil `--block-time 1` avec `POLL_INTERVAL_S=2`, cela fait un snapshot tous les ~2 blocs, comme les fixtures).

`ingest(snapshot)` (dans cet ordre) :
1. **Génération.** `g = getattr(store, "generation", 0)` ; si `g != self._generation` → `reset()`, `self._generation = g`, log INFO `"store generation changed, window reset"` (un `store.reset()` de T2 a tout vidé). `self._generation` est initialisé dans `__init__` avec la génération courante du store.
2. **Doublon / retour en arrière.** Si `snapshot.block_number == self._last_block` → `return []` (déjà traité). Si `<` → la chaîne a été réinitialisée : `reset()` puis log WARNING `"chain went backwards, window reset"`. `self._last_block = snapshot.block_number` (suivi aussi pendant la maintenance).
3. **Mode maintenance.** Si `in_maintenance()` : `store.add_snapshot(snapshot)`, `self._maintenance = True`, `STATUS.maintenance = True`, log INFO `block=… maintenance=on`, `return []` : **aucune règle évaluée**, le snapshot n'entre pas dans la fenêtre. Sinon, si `self._maintenance` était vrai (le fichier vient de disparaître) → `reset()`, `self._maintenance = False`, `STATUS.maintenance = False`, log INFO `"maintenance ended, window reset"`, puis on continue normalement avec ce snapshot.
4. Ajoute à la fenêtre, tronque à `window_snapshots`.
5. `new = latch.filter(rules.evaluate_all(window, cfg))`, puis `detected_at = clock()` sur chaque alerte (`model_copy(update=…)`).
6. `store.add_snapshot(snapshot)` ; si `new` : `store.add_alerts(new)`.
7. Log INFO `block=45201812 positions=4 new_alerts=1` et un WARNING par alerte : `ALERT critical R1_BRIDGE_INVARIANT global/rsETH exposure=1325000 | bridge released without canonical source backing…`. Retourne `new`.

`process(snapshot)` = `new = ingest(snapshot)` puis, si `new`, chaque handler appelé directement dans un `try/except` (`logger.exception`, on continue). Réservé aux tests et à `--replay` (pas d'event loop) ; la boucle de production passe par `ingest` + le répartiteur ci-dessous.

`run_forever()` :
1. `STATUS.running = True` ; client primaire `RPC_URL` ; crée `self._queue: asyncio.Queue[tuple[list[Alert], Snapshot]]` et lance la tâche **répartiteur** `self._dispatcher()`.
2. Boucle tant que non stoppé : relit `chain.load_deployment()` (fichier absent → WARNING, on attend) ; si `(deployed_at_block, contracts.TreasuryVault)` a changé depuis le tour précédent → `reset()` (un `make reset` a redéployé). `head = await asyncio.to_thread(lambda: client.eth.block_number)` ; si `head > last_block` → `snap = await asyncio.to_thread(collector.build_snapshot, head, client)` puis `new = await asyncio.to_thread(self.ingest, snap)` ; si `new` → `self._queue.put_nowait((new, snap))`, `STATUS.pending_handlers = self._queue.qsize()`. Succès → `rpc_ok=True`, `consecutive_errors=0`, `last_block`, `last_update`.
3. Exception → `rpc_ok=False`, `last_error=str(e)[:200]`, `consecutive_errors += 1`, WARNING. À 3 erreurs consécutives et si `RPC_FALLBACK_URL` non vide → bascule sur le secours (`STATUS.rpc_url` mis à jour, WARNING `"switching to fallback RPC"`). Tous les 30 tours sur le secours, on retente le primaire.
4. `await asyncio.sleep(settings.POLL_INTERVAL_S)`. On ne traite que le bloc de tête (pas de rattrapage bloc par bloc).
5. `_dispatcher()` : boucle `alerts, snap = await self._queue.get()` puis, pour chaque handler dans l'ordre d'enregistrement, `await asyncio.to_thread(handler, alerts, snap)` dans un `try/except` (`logger.exception`, on continue). Une seule tâche répartiteur → **un appel à la fois, dans l'ordre des snapshots** (2.10) ; la collecte et l'API continuent pendant qu'une réponse lente (transactions Fuji de T4) s'exécute. `stop()` arrête la boucle ; le répartiteur termine l'élément en cours puis est annulé.
6. `python -m backend.engine --loop` (boucle seule, store T0) ; `python -m backend.engine --replay <file.jsonl>` (rejoue un jsonl dans un `Engine` neuf via `process` et imprime une ligne par alerte : `block rule_id severity deployment/asset exposure explanation`).

Démarrage dans l'API : `backend/main.py` (T0) crée `engine = Engine(store)`, câble `engine.on_alerts(responder.handle)` et, si `settings.ENGINE_ENABLED`, lance `asyncio.create_task(engine.run_forever())` au startup. T3 ne modifie pas `main.py`.

**5. `backend/api/state.py`.** Lire `settings.USE_FIXTURES` **à chaque requête** (pas à l'import, sinon les tests ne peuvent pas basculer). `true` → comportement actuel (fixtures). `false` :
- `/health` : `Health(status="ok" si STATUS.running and STATUS.rpc_ok sinon "degraded", network=settings.NETWORK, chain_id=settings.CHAIN_ID, block_number=dernier snapshot ou 0, rpc_ok=STATUS.rpc_ok, engine_running=STATUS.running, version="0.1.0")`.
- `/state` : pas de snapshot → `503 {"detail": "no snapshot yet"}` (code et message exacts du tableau d'erreurs de 2.9 ; le front affiche « Waiting for first block »). Sinon `StateResponse` avec `updated_at = STATUS.last_update or latest.block_time`, `open_incident_id` = id du premier incident de `store.incidents()` dont `status != "resolved"` (sinon `None`), `vault/positions/reserves/tokens` copiés, `totals = compute_totals(latest)` et `risk_level = compute_risk_level(store)`. Toutes les clés du modèle sont présentes (`null` si vide, jamais d'`exclude_none`, 2.5).
- `compute_totals(s: Snapshot) -> dict[str, float]` (pure, testée seule), définitions exactes de 2.6, chaque valeur arrondie à 2 décimales :
  - `idle_usd` = Σ sur `s.vault.idle_balances` de `int(balance) / 10**decimals * price_usd` (decimals et prix du `TokenSnapshot` du même symbole ; symbole inconnu → ignoré, log WARNING) ;
  - `withdrawable_usd` = Σ `withdrawable_usd` des positions ;
  - `value_usd` = Σ `value_usd` des positions **+ `idle_usd`** ;
  - `at_risk_usd` = Σ (`value_usd` − `withdrawable_usd`) **des positions** (l'argent rapatrié dans le coffre n'est jamais à risque).
- `compute_risk_level(store) -> str` : gravité maximale des conditions **encore vraies** au dernier snapshot (2.6) = `max(SEVERITY_RANK)` sur `rules.evaluate_all(fenêtre, cfg)` recalculé sans latch sur les `window_snapshots` derniers snapshots du store (triés par `block_number`) ; `"info"` si aucune. Une alerte dont la condition a disparu ne compte plus. Si le dernier snapshot a été stocké en mode maintenance (`STATUS.maintenance`), `"info"`.
- `/series` : snapshots du store (≤ `limit`, ordre chronologique) contenant la réserve `(deployment_id, asset)` → `SeriesPoint(block_number, block_time, utilization_bps, available_liquidity, supply_apy_bps, withdrawable_ratio_bps` de la position si elle existe sinon `None`, `backing_ratio_bps` du `TokenSnapshot` rsETH). Réserve inconnue → `[]`. `limit: int = Query(300, ge=1, le=2000)`.
- `/alerts` : `store.alerts(since_block)` trié par `(block_number, rule_id)` décroissant (plus récentes d'abord).

**6. `mk/t3.mk`.** Ne redéfinit jamais `NETWORK` (il vient de `.env`, exporté par le `Makefile` racine, ou de la ligne de commande).

```make
test-t3:      ; python -m pytest -q backend/tests/test_t3_*.py
monitor-once: ; python -m backend.collector --once
monitor:      ; python -m backend.engine --loop
replay-t3:    ; python -m backend.engine --replay $(or $(FILE),fixtures/snapshots_attack.jsonl)
```

#### Tests qui doivent passer

Commande : `make test-t3` (= `python -m pytest -q backend/tests/test_t3_*.py`, jamais de `-k`). Chargement commun : `snaps = [Snapshot.model_validate_json(l) for l in open("fixtures/snapshots_attack.jsonl")]` ; `win(b)` = les 20 snapshots se terminant au bloc `b`. Horloge fixe `clock = lambda: datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)`. Les tests qui touchent le vrai store font `store.reset()` et `monkeypatch.setattr(settings, "DATA_DIR", tmp_path)` ; le `DATA_DIR` temporaire garantit aussi qu'aucun `maintenance.flag` résiduel ne fausse les tests.

| Id | Fichier :: fonction | Setup | Résultat attendu |
|---|---|---|---|
| T3-01 | `test_t3_rules.py::test_rules_yaml_matches_contract` | — | `yaml.safe_load` == dict de 2.7 ; `rules_version()` commence par `sha256:`, longueur 71, égal au sha256 des octets du fichier |
| T3-02 | `test_t3_rules.py::test_exposure_helpers` | `s = snaps[0]` | `collateral_exposure(s, "rsETH") == (1325000.0, ["lend-eth", "lend-avax"])` ; `deployment_exposure(s, "lend-eth") == 775000.0` ; `"lend-avax"` → `550000.0` ; `len(treasury_positions(s)) == 4` |
| T3-03 | `test_t3_rules.py::test_r1_bridge_invariant` | `win(45201810)`, `win(45201812)` | 810 → `[]` ; 812 → 1 critical, id `ALT-fuji-45201812-R1_BRIDGE_INVARIANT-global-rsETH`, `metrics["conservation_gap"] == 5000.0`, `source_nonce == 307`, `destination_nonce == 308`, exposition 1325000.0, explication contenant `without canonical source backing` |
| T3-04 | `test_t3_rules.py::test_r2_collateral_surge` | `win(45201810)`, `win(45201814)` | 810 → `[]` ; 814 → 1 critical sur `lend-eth/rsETH`, baseline 900.0, total 5900.0, `increase_pct == 555.55`, exposition 775000.0 ; aucune R2 sur `lend-avax` |
| T3-05 | `test_t3_rules.py::test_r3_liquidity_drain` | `win(45201824)`, `win(45201826)`, `win(45201832)` | 824 (-25 %) → `[]` ; 826 → high, `drop_pct == 37.5`, max 800.0, courant 500.0 ; 832 → critical, `drop_pct == 62.5` ; exposition 375000.0 ; aucune R3 sur `lend-avax` ou USDC |
| T3-06 | `test_t3_rules.py::test_r4_exitability_drop` | `win(45201834/836/838)` | 834 → `[]` ; 836 → high, ratio 6667, retirable 100.0 ; 838 → critical, ratio 0 ; exposition 375000.0 |
| T3-07 | `test_t3_rules.py::test_r5_containment` | `win(45201876/878/880)` | 876 → `[]` ; 878 → 1 critical `lend-eth/rsETH`, exposition 775000.0, state `frozen`, ratio retirable minimum 0 ; 880 → `[]` |
| T3-08 | `test_t3_rules.py::test_disabled_rule_and_empty_window` | `cfg["R1_BRIDGE_INVARIANT"]["enabled"] = False` | `evaluate_r1(win(45201812), cfg) == []` ; `evaluate_all([], cfg) == []` |
| T3-09 | `test_t3_rules.py::test_alert_latch` | alertes synthétiques même clé | high → émise ; high → rien ; critical → émise ; high → rien ; absente → clé retirée ; high → ré-émise |
| T3-10 | `test_t3_engine.py::test_attack_replay_expected_alerts` | `Engine(MemStore(), clock=clock)`, `process` sur les 41 snapshots | exactement 7 alertes, dans cet ordre : `(45201812, R1_BRIDGE_INVARIANT, global, rsETH, critical, 1325000)`, `(45201814, R2_COLLATERAL_SURGE, lend-eth, rsETH, critical, 775000)`, `(45201826, R3_LIQUIDITY_DRAIN, lend-eth, WETH, high, 375000)`, `(45201832, R3…, critical)`, `(45201836, R4_EXITABILITY_DROP, lend-eth, WETH, high)`, `(45201838, R4…, critical)`, `(45201878, R5_CONTAINMENT, lend-eth, rsETH, critical, 775000)` ; aucun doublon ; aucune R2/R3/R4 sur `lend-avax` ; toutes ont `detected_at == clock()` |
| T3-11 | `test_t3_engine.py::test_normal_replay_no_alert` | idem avec `snapshots_normal.jsonl` | `0` alerte : gap bridge 0, nonces égaux, hausse collatérale sous 50 %, baisse de liquidité max 13,6 %, positions 100 % retirables, aucun gel |
| T3-12 | `test_t3_engine.py::test_handlers_and_store` | `MemStore` (listes en mémoire, mêmes méthodes que 2.10, `generation = 0` incrémenté par `reset()`) ; un handler qui enregistre, un qui lève | handler appelé 7 fois (blocs 812, 814, 826, 832, 836, 838, 878) ; l'exception du second n'interrompt rien ; store : 41 snapshots, 7 alertes |
| T3-13 | `test_t3_engine.py::test_duplicate_and_backwards_blocks` | rejouer `snaps[5]` deux fois ; puis `snaps[0]` après `snaps[40]` | doublon → `[]` ; retour en arrière → fenêtre de taille 1, latch vide |
| T3-14 | `test_t3_engine.py::test_rpc_fallback` | `POLL_INTERVAL_S=0`, `RPC_FALLBACK_URL="http://fallback"`, `_make_client` renvoie un faux client qui lève `ConnectionError` pour le primaire, renvoie `block_number=45201812` pour le secours ; `collector.build_snapshot` monkeypatché → `snaps[6]` ; `stop()` après le premier `process` | `STATUS.rpc_url == "http://fallback"`, `STATUS.rpc_ok`, 1 alerte R1 produite, `asyncio.wait_for(…, 2)` ne lève pas |
| T3-15 | `test_t3_collector.py::test_ratio_bps` | — | `ratio_bps(100*10**18, 150*10**18) == 6667` ; `ratio_bps(0, 5) == 0` ; `ratio_bps(5, 0) == 0` ; `ratio_bps(150, 150) == 10000` |
| T3-16 | `test_t3_collector.py::test_snapshot_on_anvil` | `skipif` si `deployments/local.json` absent, anvil injoignable, ou `getUserSupplied(vault, WETH)` == 0 sur `lend-eth` (pas encore seedé) ; après `make chain deploy seed` | 6 réserves ; 4 positions (lend-eth WETH 150, USDC 400 000 ; lend-avax WETH 100, USDC 300 000), toutes `withdrawable_ratio_bps == 10000` ; rsETH `backing_ratio_bps == 10000` ; lend-eth WETH `utilization_bps == 6000` ; `source == "live"`, `network == "local"`, `chain_id == 31337` ; somme `value_usd == 1325000.0` |
| T3-17 | `test_t3_api.py::test_fixture_mode` | `USE_FIXTURES=True`, `TestClient(app)` | 200 sur les 4 routes, réponses validées par les modèles (pas de chiffres : fixtures régénérées) |
| T3-18 | `test_t3_api.py::test_live_mode_attack` | `USE_FIXTURES=False`, store T0 réinitialisé, `Engine(store, clock=clock)` sur les 41 snapshots d'attaque | `/api/state` : `block_number == 45201880`, `totals == {"value_usd": 1325000.0, "withdrawable_usd": 950000.0, "idle_usd": 0.0, "at_risk_usd": 375000.0}`, `risk_level == "critical"` ; `/api/alerts` : 7 éléments, le premier au bloc 45201878 (R5), le dernier au bloc 45201812 ; `?since_block=45201836` → 3 ; `/api/series?deployment_id=lend-eth&asset=WETH` : 41 points, premier `available_liquidity == "800000000000000000000"`, dernier `"0"`, dernier `withdrawable_ratio_bps == 0`, `backing_ratio_bps == 1935` ; `limit=5` → 5 points, le dernier au bloc 45201880 ; `asset=DAI` → `[]` ; `/api/health` : `engine_running is False`, `status == "degraded"`, `block_number == 45201880` |
| T3-19 | `test_t3_api.py::test_live_mode_normal_and_empty` | idem avec le jsonl normal ; puis store vide | normal : `risk_level == "info"`, `at_risk_usd == 0.0`, `withdrawable_usd == 1325000.0`, `idle_usd == 0.0` ; store vide : `/api/state` → 503 avec `{"detail": "no snapshot yet"}`, `/api/alerts` → `[]` |
| T3-20 | `test_t3_api.py::test_totals_and_risk_definitions` | `s = snaps[40]` ; `s2 = s` avec `vault.idle_balances["WETH"] = str(10 * 10**18)` (`model_copy`) | `compute_totals(s) == {"value_usd": 1325000.0, "withdrawable_usd": 950000.0, "idle_usd": 0.0, "at_risk_usd": 375000.0}` ; `compute_totals(s2)` : `idle_usd == 25000.0`, `value_usd == 1350000.0`, `at_risk_usd == 375000.0` (inchangé) ; store avec les 41 snapshots d'attaque puis 20 copies de `snaps[0]` aux blocs 45201882… (conditions disparues) → `compute_risk_level(store) == "info"` |
| T3-21 | `test_t3_engine.py::test_maintenance_mode` | `DATA_DIR=tmp_path` ; crée `tmp_path/runtime/fuji/maintenance.flag` ; `Engine(MemStore(), clock=clock)` ; `process(snaps[0..10])` ; supprime le fichier ; `process(snaps[11])` | pendant le fichier : 0 alerte (pourtant R1 est vraie dès 45201812), handler jamais appelé, store : 11 snapshots, `STATUS.maintenance is True`, fenêtre vide ; après suppression : fenêtre de taille 1, 1 alerte R1 critical au bloc 45201822, `STATUS.maintenance is False` |
| T3-22 | `test_t3_engine.py::test_generation_change_resets_window` | `MemStore()` ; `process(snaps[0..6])` (R1 émise à 812) ; `store.reset()` (`generation` 0 → 1) ; `process(snaps[7])` | après le reset : fenêtre de taille 1, latch vidé, R1 ré-émise au bloc 45201814 ; sans `store.reset()`, `snaps[7]` ne produit rien (contrôle) |
| T3-23 | `test_t3_engine.py::test_handlers_off_loop_one_at_a_time` | `POLL_INTERVAL_S=0` ; faux client qui renvoie successivement les blocs de `snaps[6]`, `snaps[16]`, `snaps[19]` (812, 832, 838) ; `build_snapshot` monkeypatché ; handler lent (`time.sleep(1.0)`) qui note son thread, l'ordre des blocs et le nombre d'appels simultanés ; pendant ce temps, `httpx.AsyncClient(transport=ASGITransport(app))` appelle `/api/health` ; `asyncio.run` avec `wait_for(…, 6)` | `/api/health` répond 200 en moins de 0,5 s pendant que le handler dort ; handler appelé 3 fois, blocs dans l'ordre 812, 832, 838 ; jamais plus d'un appel simultané ; thread du handler ≠ thread de l'event loop |

Si `backend/store.py` n'est pas encore livré, T3-18, T3-19 et T3-20 (partie store) font `pytest.importorskip("backend.store")`.

#### Definition of done

- [ ] Avec `make seed` lancé pendant que le moteur tourne : aucune alerte pendant l'installation (fichier `maintenance.flag` présent), fenêtre vidée à sa disparition.
- [ ] `make test-t3` vert (T3-16 en `skip` accepté tant que T1/T2 ne sont pas livrés, puis vert sur anvil).
- [ ] `make replay-t3` imprime les 7 alertes de T3-10 ; `make replay-t3 FILE=fixtures/snapshots_normal.jsonl` n'imprime rien.
- [ ] `make monitor-once` sur anvil seedé imprime un `Snapshot` JSON valide.
- [ ] Avec `ENGINE_ENABLED=true USE_FIXTURES=false make backend` puis `make attack` (T2) : R1 apparaît dans `/api/alerts` au plus 2 polls après l'émission forgée.
- [ ] Couper `RPC_URL` (mauvaise URL) : `/api/health` passe `degraded`, le moteur continue sur `RPC_FALLBACK_URL`.
- [ ] Aucun fichier hors « Fichiers possédés » modifié ; demandes éventuelles dans `docs/contract-requests.md`.

#### Pièges connus

- Mode maintenance : sans lui, l'installation de la liquidité par `make seed` / `make reset` (gros dépôts puis emprunts des bots) déclenche R2/R3 comme une attaque. Le fichier est relu **à chaque snapshot** (pas de cache) ; son chemin dépend de `settings.DATA_DIR` et `settings.NETWORK` lus à l'appel, sinon les tests ne peuvent pas le rediriger.
- `store.generation` : comparer à chaque `ingest`, pas seulement au démarrage ; T2 appelle `store.reset()` pendant `POST /api/demo/reset` alors que la boucle tourne.
- Abonnés : jamais `handler(...)` directement dans `run_forever` (l'API se figerait pendant les transactions Fuji de T4) et jamais un `create_task` par alerte (les appels se chevaucheraient et l'ordre des snapshots serait perdu) : une seule file, un seul répartiteur, `await asyncio.to_thread`.
- `totals.value_usd` inclut `idle_usd` : après le rapatriement, la valeur totale reste 1 325 000 $ (elle passe des positions au coffre) et `at_risk_usd` tombe à 0. Ne pas soustraire l'idle de `at_risk_usd`.
- `window_snapshots` compte explicitement des snapshots, pas des blocs. Ne pas « corriger » en divisant par l'intervalle de bloc : les attendus de T3-10 en dépendent.
- Arrondis : `backing_ratio_bps` vient tel quel du bridge (division entière, 1935) ; `withdrawable_ratio_bps` est arrondi au plus proche (6667). Ne jamais passer par un float pour un montant : `int(str)` puis division seulement pour l'affichage.
- R2 : après le vidage, la fenêtre ne contient plus que des zéros (à partir du bloc 45201876 dans les fixtures) → `max == 0` → pas d'alerte, la clé sort du latch. C'est normal ; il n'y a pas de ré-émission ensuite.
- R5 ne voit qu'une **transition** : une réserve déjà gelée au démarrage du moteur ne lève rien (accepté dans le MVP). Le latch en mémoire repart vide au redémarrage du backend : des alertes déjà émises peuvent être ré-émises une fois (accepté, voir phase 2).
- `latch.filter` doit recevoir tous les candidats du snapshot d'un coup : l'appeler règle par règle effacerait les clés des autres règles.
- web3 est synchrone : toujours `asyncio.to_thread` dans `run_forever` (lecture du bloc, collecte, `ingest`, abonnés), sinon l'API se fige pendant l'attente d'un reçu par T4.
- `getReservesData()` renvoie des tuples : nommer les champs via l'ABI (`struct_to_dict`), pas par position codée en dur.
- `chain.py` ne contient pas encore `token()`, `vault()`, `bridge()`, `oracle()` de 2.4 et `chain.contract()` utilise toujours le client primaire : le collecteur construit ses contrats sur le `client` reçu.
- `fixtures/deployments.example.json` utilise encore les clés `Bridge`/`Oracle` : le collecteur suit 2.3 (`MockBridge`, `MockOracle`).
- Fuji : environ 20 appels RPC par snapshot toutes les 2 s ; le RPC public limite le débit, utiliser un `RPC_URL` de fournisseur.
- `settings.USE_FIXTURES` lu à l'import = tests impossibles à basculer : le lire dans chaque route.

#### Plus tard (phase 2)

- Règles avancées : rendement-appât (`supply_apy_bps` anormal), corrélation multi-chaînes réelle, écart oracle vs prix de marché, preuve cryptographique de non-existence du message source, traçage des événements `Released(sourceVerified=false)`/`Borrowed` et des fonds de l'attaquant.
- Multicall3 pour lire un snapshot en un seul appel RPC ; rattrapage bloc par bloc au lieu du seul bloc de tête.
- Latch persistant (rechargé depuis `store.alerts()`), rechargement à chaud de `rules.yaml`, fenêtre en blocs ou en secondes, seuils par actif.
- Métriques internes du moteur (latence de collecte, erreurs RPC) exposées dans `/api/health`.

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T3 (moteur de surveillance) du fichier TASKS.md à la racine du repo.
1. Lis TASKS.md sections 1 et 2 en entier, puis la section T3 en entier. Lis backend/models.py,
   backend/settings.py, backend/chain.py, backend/api/state.py et quelques lignes de
   fixtures/snapshots_attack.jsonl.
2. Ne modifie QUE : backend/collector.py, backend/rules.py, backend/engine.py,
   backend/config/rules.yaml, backend/api/state.py, backend/tests/test_t3_*.py, mk/t3.mk.
   Pour tout autre changement (models.py, chain.py, store.py, main.py, fixtures, contrat de la
   section 2), n'édite pas : écris la demande dans docs/contract-requests.md et préviens-moi.
3. Commence par les tests de la rubrique « Tests qui doivent passer » (T3-01 à T3-23), dans
   l'ordre : rules.yaml, rules.py, engine.py (sur les fixtures jsonl, avec une MemStore locale
   avec generation si backend/store.py n'existe pas ; mode maintenance, generation, répartiteur
   des abonnés via asyncio.to_thread), api/state.py (totals et risk_level exactement selon 2.6,
   503 "no snapshot yet"), puis collector.py (test anvil en skip tant que deployments/local.json
   n'existe pas ou que le coffre n'a pas de position).
4. Les chiffres attendus (blocs 45201812, 826, 832, 836, 838, 878 ; expositions 1 325 000 et
   775 000 USD) sont mesurés sur les fixtures : si un test ne les retrouve pas, c'est le code
   qu'il faut corriger, pas l'attendu. Signale-moi tout écart réel.
5. Garde les règles simples : un indicateur par règle, rien d'autre que R1..R5.
6. Avant chaque commit : make test-t3 vert (pytest backend/tests/test_t3_*.py, jamais -k).
   Push fréquent après chaque test vert.
```


---


### T4 · Réponse et preuves : matrice, actions on-chain, notifications, ancrage, verify

**Objectif.** Transformer les alertes nouvelles d'un snapshot en **une** `Decision` déterministe (matrice 2.8), exécuter les actions automatiques (pause des dépôts, retraits d'urgence vers le coffre) avec la clé guardian, notifier, puis **prouver** : fichier de preuve, `inputs_hash`, `record_hash`, ancrage dans `EvidenceRegistry`, et une commande `verify` qu'un auditeur peut rejouer (`MATCH` / `MISMATCH` avec les différences).

**Dépend de.**
- T0 → `backend/models.py`, `backend/settings.py`, `backend/chain.py`, `backend/store.py`, câblage `main.py` → déjà là ; si `backend/store.py` n'existe pas encore, utiliser le `FakeStore` des tests (voir 3.9).
- T3 → objets `Alert` (R1..R5) et `Snapshot` live → en attendant : `Snapshot` lus dans `fixtures/snapshots_attack.jsonl` et `Alert` construites à la main (helper `make_alert`, voir 3.9).
- T1 → contrats déployés, `deployments/local.json`, `abi/*.json` → en attendant : `DRY_RUN_ACTIONS=true` (`DryRunExecutor`, aucune transaction) ; plus tard anvil local (`make chain && make deploy`).
- T2 → coffre seedé sur anvil (`make seed`) → en attendant : seuls les tests dry-run tournent, le test anvil est `skip`.
- T8 → `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET` → en attendant : vides (log + fichiers locaux seulement).

**Débloque.** T5 (reçoit `Decision` via `on_decisions`, lit `saved_usd` à partir des `EMERGENCY_WITHDRAW.amount`), T6 (`GET /api/decisions`, bouton d'approbation, bouton Verify), T7 (lit les décisions pour le délai de réaction et le % sauvé), T9 (démo `make verify`, démo `tamper` pour le jury).

**Fichiers possédés.** `backend/responder.py`, `backend/executor.py`, `backend/notify.py`, `backend/evidence.py`, `backend/cli.py`, `backend/config/playbook.yaml`, `backend/api/response.py`, `backend/tests/test_t4_*.py`, `mk/t4.mk`. Écrit à l'exécution (non commité) : `data/evidence/<decision_id>.json`, `data/evidence/anchors.json`.

**À lire avant de commencer.** TASKS.md sections 1.2, 1.5, 2.1, 2.2 (`TreasuryVault`, `EvidenceRegistry`, `MiniLend.getUserSupplied/getReservesData`), 2.4, 2.5, 2.6, 2.7, **2.8**, 2.9, **2.10** ; `backend/models.py` (`Action`, `Decision`, `VerifyResult`) ; `backend/chain.py` ; 3 lignes de `fixtures/snapshots_attack.jsonl` (blocs 45201812, 45201826, 45201838).

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| Alertes nouvelles d'un snapshot | `list[Alert]` (2.6, rule_id `R1_BRIDGE_INVARIANT`..`R5_CONTAINMENT`) passée à `Responder.handle` | T3 (`engine.on_alerts`) | `make_alert(...)` dans `backend/tests/test_t4_fixtures.py` ; `fixtures/alerts.json` (régénérée : alerte R1 au bloc 45201812) sert d'exemple de format, pas d'entrée de test |
| Snapshot courant | `Snapshot` (positions, reserves avec `ltv_bps`, `vault.deposits_paused`) | T3 (collector) | `load_attack(block)` qui lit `fixtures/snapshots_attack.jsonl` (network `fuji`, 41 snapshots) |
| Adresses et ABIs | `deployments/<network>.json`, `abi/TreasuryVault.json`, `abi/EvidenceRegistry.json`, `abi/MiniLend.json` | T1 | `DRY_RUN_ACTIONS=true` |
| Clés | `settings.private_key("guardian" / "owner" / "evidence")` via `chain.account(role)` | T0 / `.env` | comptes anvil (index 2, 1, 5) automatiques sur `local` |
| Store | `store` de `backend/store.py` (2.10) | T0 | `FakeStore` (listes en mémoire, mêmes méthodes) |
| Config AWS | `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `AWS_REGION`, `ALERT_WEBHOOK_URL` | T8 / `.env` | vides |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| `Decision` | modèle 2.6 ; id `DEC-<network>-<block>-<n>` où `<block>` = bloc du snapshot des alertes (alerte au bloc N → `DEC-<network>-N-1`) ; ajoutée par `store.add_decision`, mise à jour par `store.update_decision` | T5, T6, T7 |
| Appel des abonnés | `handler(decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot)` après stockage | T5 (`IncidentManager.handle`) |
| Fichier de preuve | `data/evidence/<decision_id>.json` = `{"decision": {...}, "inputs": {"alerts": [...], "snapshot": {...}}, "playbook_yaml": "<texte>", "approvals": []}` (UTF-8, indent 2) | `verify`, T9, auditeur |
| Ancrages dry-run | `data/evidence/anchors.json` = `{"0x<record_hash>": {"tx_hash": "0xdry…", "block_number": int, "kind": "decision", "uri": "…"}}` | `verify` en dry-run |
| Copie S3 | `s3://$EVIDENCE_BUCKET/evidence/<decision_id>.json` (même contenu) si la variable est définie | T8, auditeur |
| Ancre on-chain | `EvidenceRegistry.anchor(record_hash, "decision", uri)` signé par `evidence` | `verify`, T6 (lien explorer via `anchor_tx`) |
| Notification | log toujours ; POST JSON webhook ; publish SNS | humains, T8 |
| Routes | `GET /api/decisions`, `POST /api/decisions/{id}/approve`, `POST /api/verify/{decision_id}` (2.9) | T6 |
| CLI | `python -m backend.cli verify <id>` → stdout `MATCH`/`MISMATCH` + diffs, exit 0/1 (2 si id inconnu) ; `tamper`, `restore` | T9, jury |

#### Spécification détaillée

**3.1 `backend/config/playbook.yaml`** (encode 2.8, rien d'autre)

```yaml
version: 1
min_exposure_usd: 1000
matrix:                      # gravité max du groupe -> actions, dans cet ordre
  critical:
    - { type: NOTIFY,             mode: auto }
    - { type: PAUSE_DEPOSITS,     mode: auto }
    - { type: EMERGENCY_WITHDRAW, mode: auto,  per_position: true }
    - { type: OPEN_INCIDENT,      mode: auto }
    - { type: UNPAUSE_DEPOSITS,   mode: human }
  high:
    - { type: NOTIFY,             mode: auto }
    - { type: PAUSE_DEPOSITS,     mode: auto }
    - { type: EMERGENCY_WITHDRAW, mode: human, per_position: true }
    - { type: OPEN_INCIDENT,      mode: auto }
  warning:
    - { type: NOTIFY, mode: auto }
  info: []
below_min_exposure:          # exposition < min_exposure_usd
  notify_if_severity_at_least: high
```

`load_playbook() -> tuple[dict, str, str]` dans `responder.py` : lit `settings.CONFIG_DIR / "playbook.yaml"`, renvoie `(dict, version, texte)` avec `version = "sha256:" + hashlib.sha256(octets_du_fichier).hexdigest()` (71 caractères). Rechargé à chaque `handle` (une modif du fichier change `playbook_version`).

**3.2 Fonctions pures de `backend/responder.py`** (aucun accès réseau, disque, horloge ou env)

- `SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}`.
- `deployment_order(snapshot) -> list[str]` : ids de déploiement dans l'ordre de première apparition dans `snapshot.reserves` (fixtures : `["lend-eth", "lend-avax"]`).
- `concerned_positions(alert, snapshot) -> list[PositionSnapshot]` :
  - `R1_BRIDGE_INVARIANT` : déploiements où une réserve `asset == alert.asset` a `ltv_bps > 0` ; toutes les positions du coffre dans ces déploiements ;
  - `R3_LIQUIDITY_DRAIN`, `R2_COLLATERAL_SURGE`, `R4_EXITABILITY_DROP` : la position `(alert.deployment_id, alert.asset)` si elle existe ;
  - `R5_CONTAINMENT` : toutes les positions de `alert.deployment_id` ;
  - rule_id inconnu : `[]` + `logger.warning`.
  - Les positions dont `supplied == "0"` sont ignorées. Tri : `(index dans deployment_order, asset)` → `lend-eth USDC, lend-eth WETH, lend-avax USDC, lend-avax WETH`.
- `assess(alerts, snapshot, playbook) -> dict` : `severity` = gravité max ; `positions` = union (clé `(deployment_id, asset)`, **sans doublon**) des positions concernées de toutes les alertes de gravité ≥ high ; `exposure_usd` = somme des `value_usd` de l'union des positions concernées de **toutes** les alertes ; `withdrawable_usd` = somme des `withdrawable_usd` de cette même union ; `matrix_cell = f"{severity}|{'exposure>=1k' if exposure_usd >= min_exposure_usd else 'exposure<1k'}|{'exit_possible' if withdrawable_usd > 0 else 'no_liquidity'}"`. Arrondir les floats à 2 décimales.
- `plan_actions(alerts: list[Alert], snapshot: Snapshot, playbook: dict) -> list[Action]` (signature 2.10) :
  1. `alerts` vide → `[]`. Calculer `assess`.
  2. Si `exposure_usd < min_exposure_usd` : `[Action(NOTIFY, auto, planned)]` si `severity >= notify_if_severity_at_least`, sinon `[]`.
  3. Sinon, pour chaque entrée de `matrix[severity]` : `status = "planned"` si `mode == "auto"`, `"pending_approval"` si `mode == "human"` ; `params = {}`.
     - `PAUSE_DEPOSITS` : toujours présent dans la liste (verify reste stable) ; si `snapshot.vault.deposits_paused` est vrai → `status="skipped"`, `note="already paused"`.
     - `per_position: true` : une `EMERGENCY_WITHDRAW` par position de `assess.positions` avec `int(withdrawable_now) > 0`, `params` = **exactement** `{"deployment_id": ..., "asset": ...}` (rien d'autre, pas de montant : le montant va dans `Action.amount`, rempli seulement quand l'action passe `executed`). Zéro position retirable → aucune action de ce type.
     - `OPEN_INCIDENT` : `params = {}` (c'est T5 qui attribue l'id `INC-…` ; T4 ne l'écrit nulle part dans la décision). `NOTIFY`, `PAUSE_DEPOSITS`, `UNPAUSE_DEPOSITS` : `params = {}` aussi.
  4. `amount`, `tx_hash`, `executed_at` restent `None`. Ne jamais modifier les objets reçus (utiliser `model_copy`).
- `rationale(decision_fields) -> str`, gabarit fixe en anglais : `"{severity} alert(s) {rule_ids} with ${exposure_usd:,.0f} exposed: {n_auto} automatic action(s), {n_human} awaiting approval."` (`rule_ids` triés, séparés par `", "`).

**3.3 `backend/executor.py`**

```python
class ExecResult(TypedDict):
    status: Literal["executed", "failed", "skipped"]
    tx_hash: str | None; block_number: int | None; amount: str | None; note: str | None

class Executor(Protocol):
    def pause_deposits(self) -> ExecResult: ...
    def unpause_deposits(self) -> ExecResult: ...
    def emergency_withdraw(self, deployment_id: str, asset: str) -> ExecResult: ...
    def anchor(self, record_hash: str, kind: str, uri: str) -> ExecResult: ...

def make_executor() -> Executor      # DryRunExecutor si settings.DRY_RUN_ACTIONS, sinon Web3Executor
def get_executor() -> Executor       # singleton (2.10, functools.lru_cache) : DryRunExecutor si DRY_RUN_ACTIONS=true, sinon Web3Executor ;
                                     # partagé par Responder (main.py : Responder(store, get_executor())) et api/response.py ;
                                     # les tests appellent get_executor.cache_clear() après avoir monkeypatché DRY_RUN_ACTIONS
```

- **Aucune méthode ne lève** : toute exception → `{"status": "failed", "note": f"{type(e).__name__}: {e}"[:200]}` + `logger.exception`.
- `Web3Executor` (contrats via `chain.vault()`, `chain.lending(id)`, `chain.registry()` de 2.4 ; si ces helpers manquent encore dans `chain.py`, `chain.contract("TreasuryVault")` / `chain.contract("EvidenceRegistry")`) :
  - `pause_deposits` : si `vault.functions.depositsPaused().call()` → `skipped`, `"already paused"` ; sinon `chain.send(vault.functions.pauseDeposits(), chain.account("guardian"))` (`pauseDeposits` est idempotent côté contrat, le pré-contrôle sert seulement à ne pas dépenser de gas). `status` du reçu 0 → `failed`, `"reverted"`.
  - **Raison du revert** : avant chaque `chain.send`, simuler l'appel avec `fn.call({"from": sender.address})` ; un `ContractLogicError` → `failed`, `note` = message de revert (ex. `"MiniLend: paused"`, `"Vault: only guardian or owner"`), sans envoyer la transaction. Même traitement si `chain.send` lève un `ContractLogicError` (estimation du gas).
  - `unpause_deposits` : clé **owner** (`unpauseDeposits` est owner-only) ; non pausé → `skipped`, `"not paused"`.
  - `emergency_withdraw(dep, asset)` : `asset_addr = chain.load_deployment()["assets"][asset]` ; `supplied = lending(dep).functions.getUserSupplied(vault.address, asset_addr).call()` ; `0` → `skipped`, `"no position left"` ; liquidité = `availableLiquidity` de l'entrée de `getReservesData()` dont `asset == asset_addr` ; `0` → `skipped`, `"no liquidity"` (le contrat renverrait 0 sans revert, inutile de payer le gas) ; sinon `send(vault.functions.emergencyWithdraw(lending(dep).address, asset_addr), guardian)` ; `amount` = champ `amount` de l'event `EmergencyWithdrawal` du reçu (`vault.events.EmergencyWithdrawal().process_receipt(w3().eth.get_transaction_receipt(tx))`), à défaut `min(supplied, liquidité)`, en chaîne décimale. Réserve en pause (`setReservePaused`) : `emergencyWithdraw` revert `"MiniLend: paused"` → l'action passe `failed` avec `note="MiniLend: paused"` (la raison du revert, pas `"reverted"`) ; les actions suivantes continuent.
  - `anchor(record_hash, kind, uri)` : `h = bytes.fromhex(record_hash[2:])` ; si `registry.functions.anchoredAt(h).call() > 0` → `skipped`, `"already anchored"`, `block_number` = cette valeur ; sinon `send(registry.functions.anchor(h, kind, uri), chain.account("evidence"))`.
- `DryRunExecutor` : aucune transaction, mais un petit état pour l'idempotence : `paused: bool = False`, `withdrawn: set[tuple[str, str]]`, `seq: int = 0`. Hash factice : `"0xdry" + hashlib.sha256(f"{method}|{json.dumps(args)}|{seq}".encode()).hexdigest()` (69 caractères, déterministe pour une instance neuve). `block_number` = `seq`. `pause_deposits` deux fois → 2e `skipped "already paused"` ; `emergency_withdraw` deux fois sur la même paire → 2e `skipped "no position left"` ; `amount=None` (le Responder complète avec `withdrawable_now`). `anchor` écrit/complète `data/evidence/anchors.json` (`skipped "already anchored"` si la clé existe).

**3.4 `backend/notify.py`**

`notify(decision: Decision, alerts: list[Alert]) -> list[str]` : renvoie les canaux **configurés** (`["log"]`, + `"webhook"` si `ALERT_WEBHOOK_URL`, + `"sns"` si `SNS_TOPIC_ARN`). Toujours `logger.warning("NOTIFY %s %s exposure=$%.0f %s", decision.id, decision.severity, decision.exposure_usd, decision.rationale)`. Webhook et SNS partent dans un `threading.Thread(daemon=True)` pour ne pas retarder le retrait d'urgence. Corps JSON : `{"text": résumé, "content": résumé, "decision_id", "severity", "network", "block_number", "exposure_usd", "matrix_cell", "alerts": [{"id","rule_id","severity","explanation"}], "actions": [{"type","mode","status"}]}` (`text` pour Slack, `content` pour Discord). `httpx.post(url, json=..., timeout=3)`. SNS : `boto3.client("sns", region_name=settings.AWS_REGION).publish(TopicArn=..., Subject=f"[{severity.upper()}] {decision.id}"[:100], Message=json.dumps(corps))`. Toute exception est loggée et avalée. Fonction interne `build_payload(decision, alerts) -> dict` testable.

**3.5 `backend/evidence.py`**

```python
EVIDENCE_DIR: Path = settings.DATA_DIR / "evidence"          # les tests le monkeypatchent vers tmp_path
def canonical_json(obj) -> str            # BaseModel -> model_dump(mode="json") ; listes de BaseModel idem ; puis
                                          # json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def keccak_hex(text: str) -> str          # "0x" + eth_utils.keccak(text.encode("utf-8")).hex()  (66 caractères)
def inputs_hash(alerts, snapshot) -> str  # keccak_hex(canonical_json({"alerts": [a triées par id], "snapshot": snapshot}))
def record_hash(decision) -> str          # keccak_hex(canonical_json(decision.model_dump(mode="json",
                                          #   exclude={"record_hash", "anchor_tx", "anchor_block"})))
def evidence_uri(decision_id) -> str      # f"s3://{EVIDENCE_BUCKET}/evidence/{id}.json" si bucket, sinon f"file://data/evidence/{id}.json"
def write_evidence(decision, alerts, snapshot, playbook_yaml) -> Path   # écrit le fichier, puis upload S3 si bucket (échec loggé, jamais levé)
def anchor_decision(decision, executor) -> Decision                      # executor.anchor(record_hash, "decision", uri) -> anchor_tx, anchor_block
def load_evidence(decision_id) -> dict | None                            # local, sinon S3 si bucket, sinon None
def verify(decision_id) -> VerifyResult
```

`verify` (n'utilise **que** le fichier de preuve, jamais le store, car les approbations modifient la décision vivante) :
1. `ev = load_evidence(id)` ; absent → `LookupError` (API → 404, CLI → exit 2).
2. `d = Decision.model_validate(ev["decision"])`, `alerts`, `snapshot` depuis `ev["inputs"]`.
3. `inputs_hash` recalculé ≠ `d.inputs_hash` → diff `"inputs_hash: stored 0x… != recomputed 0x…"`.
4. Playbook : `ev["playbook_yaml"]` ; son sha256 ≠ `d.playbook_version` → diff `"playbook_version: …"`. Re-planifier `plan_actions(alerts, snapshot, yaml.safe_load(playbook_yaml))` et comparer `(type, mode, params)` index par index : `"action count: stored 8 != replanned 7"`, `"action[2]: stored EMERGENCY_WITHDRAW/auto {'asset': 'DAI', ...} != replanned EMERGENCY_WITHDRAW/auto {'asset': 'USDC', ...}"`.
5. `recomputed_hash = record_hash(d)` ; ≠ `d.record_hash` → diff `"record_hash: …"`.
6. Ancrage : si `d.anchor_tx` commence par `"0xdry"` → `anchors.json` contient `d.record_hash` ; sinon `registry.functions.anchoredAt(bytes.fromhex(d.record_hash[2:])).call() > 0` (erreur RPC → `anchored=False`, diff `"registry unreachable: …"`). Si `d.anchor_tx` est défini et non ancré → diff `"record_hash 0x… is not anchored on-chain"`.
7. `match = (diffs == [])`. `VerifyResult(decision_id, match, stored_hash=d.record_hash, recomputed_hash, anchored, anchor_tx, anchor_block, diffs)`.

**3.6 `Responder` (`backend/responder.py`)**

`__init__(self, store, executor)` : garde `self._handlers = []`, `self._seen_alert_ids: set[str]` (initialisé depuis `store.decisions()`) et `self._generation = store.generation` ; au début de `handle`, si `store.generation` a changé (reset de démo), vider `_seen_alert_ids` et mémoriser la nouvelle génération. `handle` est appelé par le moteur via `await asyncio.to_thread(handler, alerts, snapshot)`, un appel à la fois dans l'ordre des snapshots (2.10) : pas de verrou à ajouter, mais `handle` tourne hors de la boucle asyncio (pas d'`await` dedans). `on_decisions(handler)` ajoute un abonné. `handle(alerts, snapshot) -> list[Decision]`, **jamais d'exception** (try/except global → `logger.exception`, retourne `[]`) :
1. Filtrer les alertes déjà vues (`id in _seen_alert_ids`) ; rien de neuf → `[]`.
2. `playbook, version, text = load_playbook()` ; `actions = plan_actions(...)` ; `actions == []` → `[]` (aucune décision pour du `info`).
3. `n = 1 + nombre de décisions du store avec ce block_number` → `id = f"DEC-{snapshot.network}-{snapshot.block_number}-{n}"` : le bloc est celui du **snapshot des alertes** (= `alert.block_number`), jamais le bloc d'exécution des transactions ni celui de l'ancrage. Alerte R1 au bloc 45201812 → `DEC-fuji-45201812-1` (comme dans les fixtures régénérées). `created_at = datetime.now(timezone.utc).replace(microsecond=0)`. `rules_version` = celle de la 1re alerte. `exit_cost_bps = 0`.
4. Exécuter dans l'ordre, uniquement `mode == "auto"` et `status == "planned"` : `NOTIFY` → `notify(...)`, `status="executed"`, `note="channels: log,webhook"` (ne **jamais** toucher `params`) ; `PAUSE_DEPOSITS` → `executor.pause_deposits()` ; `EMERGENCY_WITHDRAW` → `executor.emergency_withdraw(dep, asset)`, `amount = result.amount or position.withdrawable_now` si `executed` ; `OPEN_INCIDENT` → `status="executed"`, `note="delegated to incident manager"`, `params` reste `{}`. Copier `status`, `tx_hash`, `amount`, `note`, `executed_at=now` depuis l'`ExecResult`. Un échec n'arrête pas les actions suivantes.
5. `inputs_hash`, `rationale`, puis `record_hash` ; `write_evidence` ; `anchor_decision` (échec → `anchor_tx=None`, log) ; réécrire le fichier avec les champs d'ancrage ; `store.add_decision(d)` ; marquer les alertes vues.
6. Logs : `DECISION DEC-fuji-45201812-1 critical exposure=$1,325,000 cell=critical|exposure>=1k|exit_possible actions=NOTIFY,PAUSE_DEPOSITS,EMERGENCY_WITHDRAWx4,OPEN_INCIDENT,UNPAUSE_DEPOSITS(pending)` puis une ligne `ACTION <type> <params> <status> tx=<hash> amount=<amount>` par action.
7. Appeler chaque handler `(decisions, alerts, snapshot)` dans un try/except séparé ; retourner `[d]`.

**3.7 `backend/api/response.py`** (routes T4 de 2.9 ; lire `settings.USE_FIXTURES` **à chaque requête**, pas à l'import)
- `GET /decisions` : fixtures → `decisions.json` ; sinon `store.decisions()` (plus récentes d'abord).
- `POST /decisions/{id}/approve` body `ApproveBody` ; codes d'erreur du contrat (2.9), toujours `{"detail": "..."}` : id inconnu → 404 ; `action_index` hors bornes → 400 ; action pas en `pending_approval` → 409 `{"detail": "action is not pending approval (status=executed)"}` ; corps invalide → 422 (FastAPI). `approve=false` → `rejected`, `note=f"rejected by {approver}; no transaction sent"`. `approve=true` → `approved` puis exécution via `get_executor()` (`EMERGENCY_WITHDRAW` → `emergency_withdraw`, `UNPAUSE_DEPOSITS` → `unpause_deposits`, `PAUSE_DEPOSITS` → `pause_deposits`) → `executed`/`failed`/`skipped`, `note=f"approved by {approver}; {result.note or ''}"`. **Format de `note` documenté pour T5** (qui le lit pour la timeline de l'incident) : toujours `"approved by <approver>; <détail>"` ou `"rejected by <approver>; <détail>"` ; T5 extrait l'approbateur avec `note.split(";")[0].split(" by ", 1)[1]`. Un `EMERGENCY_WITHDRAW` approuvé qui revert `"MiniLend: paused"` → `failed`, `note="approved by <approver>; MiniLend: paused"`. En dry-run `amount` vaut `None` : le compléter avec `withdrawable_now` de la position dans `ev["inputs"]["snapshot"]`. `store.update_decision(d)` et ajout dans `ev["approvals"]` de `{"action_index", "approver", "approve", "at", "result": action.model_dump(mode="json")}`. Le `record_hash` n'est **pas** recalculé (il fige l'état au moment de la décision).
- `POST /verify/{decision_id}` : fixtures → `verify.json` avec `decision_id` remplacé ; sinon `evidence.verify` (LookupError → 404).

**3.8 `backend/cli.py` et `mk/t4.mk`**

`main(argv: list[str] | None = None) -> int` (testable sans subprocess), `argparse` :
- `verify <id>` : 1re ligne `MATCH` ou `MISMATCH`, puis `decision: …`, `record_hash: …`, `anchored: yes (block 123, tx 0x…)` + lien `chain.explorer_tx` si fuji, puis une ligne `- <diff>` par diff. Exit 0 si match, 1 sinon, 2 si id inconnu.
- `tamper <id> --field <chemin> --value <v>` : chemin pointé sur le fichier de preuve (`decision.actions.2.params.asset`, `inputs.snapshot.positions.1.withdrawable_now`) ; entiers = index de liste ; `v` passé par `json.loads`, sinon chaîne. Sauvegarde `data/evidence/<id>.json.bak` avant modif (sans écraser une `.bak` existante). Affiche `TAMPERED <chemin>: <ancien> -> <nouveau>`.
- `restore <id>` : remet la `.bak`.

```make
verify:  ; python -m backend.cli verify $(ID)
tamper:  ; python -m backend.cli tamper $(ID) --field $(FIELD) --value '$(VALUE)'
restore: ; python -m backend.cli restore $(ID)
test-t4: ; DRY_RUN_ACTIONS=true USE_FIXTURES=false python -m pytest backend/tests/test_t4_*.py -q
```

**3.9 Maquettes de test (`backend/tests/test_t4_fixtures.py`, sans test, importé par les autres)** : `load_attack(block) -> Snapshot` ; `make_alert(rule_id, severity, snapshot, deployment_id=None, asset=None, exposure_usd=...) -> Alert` (id au format 2.5, `rules_version="sha256:test"`) ; `FakeStore` (méthodes 2.10 en mémoire) ; fixture pytest `evidence_tmp` qui monkeypatche `backend.evidence.EVIDENCE_DIR` vers `tmp_path`.

#### Tests qui doivent passer

Commande : `make test-t4` (= `python -m pytest backend/tests/test_t4_*.py -q`, jamais `-k`). Tous en dry-run sauf T4-25.

| Id | Fichier::test | Setup | Résultat attendu |
|---|---|---|---|
| T4-01 | `test_t4_plan.py::test_playbook_loads` | fichier réel | `min_exposure_usd == 1000` ; version commence par `sha256:`, longueur 71 |
| T4-02 | `test_t4_plan.py::test_plan_r1_critical_attack` | `load_attack(45201812)` + R1 critical `rsETH` (exposure 1325000) | 8 actions, exactement : `NOTIFY/auto/planned`, `PAUSE_DEPOSITS/auto/planned`, `EMERGENCY_WITHDRAW/auto/planned` ×4 avec params `{lend-eth,USDC}`, `{lend-eth,WETH}`, `{lend-avax,USDC}`, `{lend-avax,WETH}`, `OPEN_INCIDENT/auto/planned`, `UNPAUSE_DEPOSITS/human/pending_approval` ; `assess` : `exposure_usd == 1325000.0`, `withdrawable_usd == 1325000.0`, `matrix_cell == "critical|exposure>=1k|exit_possible"` |
| T4-03 | `test_t4_plan.py::test_plan_r3_high` | `load_attack(45201826)` + R3 liquidity high `lend-eth/WETH` | `NOTIFY`, `PAUSE_DEPOSITS(auto, planned)`, `EMERGENCY_WITHDRAW(human, pending_approval, {lend-eth, WETH})`, `OPEN_INCIDENT` ; exposure 375000.0 |
| T4-04 | `test_t4_plan.py::test_plan_warning_notify_only` | alerte synthétique `warning` (la matrice reste générique même si R1–R5 KelpDAO ne produisent pas warning) | `[NOTIFY/auto/planned]` |
| T4-05 | `test_t4_plan.py::test_plan_below_min_exposure` | snapshot 45201836 dont la position `lend-eth/WETH` a `value_usd=500` ; R4 high puis R4 critical | `[NOTIFY]` dans les deux cas ; cell `high|exposure<1k|exit_possible` |
| T4-06 | `test_t4_plan.py::test_plan_info_empty` | R5 forcée en `info` | `[]` |
| T4-07 | `test_t4_plan.py::test_plan_critical_no_liquidity` | `load_attack(45201838)` + R4 critical `lend-eth/WETH` (ratio 0) | `NOTIFY, PAUSE_DEPOSITS, OPEN_INCIDENT, UNPAUSE_DEPOSITS(human)` (aucun `EMERGENCY_WITHDRAW`) ; cell `critical|exposure>=1k|no_liquidity` |
| T4-08 | `test_t4_plan.py::test_plan_already_paused` | snapshot 45201812 avec `vault.deposits_paused=True` | `PAUSE_DEPOSITS` présent, `status=="skipped"`, `note=="already paused"` |
| T4-09 | `test_t4_plan.py::test_plan_group_no_double_count` | 45201812 : R1 critical + R2 collateral high `lend-eth/rsETH` | 1 groupe critical, exposure 1325000.0 (pas 1700000), 4 `EMERGENCY_WITHDRAW` |
| T4-10 | `test_t4_plan.py::test_plan_is_pure` | 2 appels identiques | sorties égales ; `snapshot.model_dump()` inchangé |
| T4-11 | `test_t4_evidence.py::test_canonical_json` | — | `canonical_json({"b":1,"a":2}) == '{"a":2,"b":1}'` ; `canonical_json({"x":"é"}) == '{"x":"é"}'` ; `keccak_hex("") == "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"` |
| T4-12 | `test_t4_evidence.py::test_hash_roundtrip` | décision de T4-16 | `record_hash(Decision.model_validate_json(d.model_dump_json())) == d.record_hash` ; `inputs_hash` identique sur 2 appels et pour alertes passées dans l'ordre inverse |
| T4-13 | `test_t4_evidence.py::test_record_hash_scope` | idem | changer `anchor_tx` → hash inchangé ; changer `actions[0].note` → hash différent |
| T4-14 | `test_t4_executor.py::test_dry_run_hash` | 2 `DryRunExecutor` neufs | `pause_deposits()["tx_hash"]` commence par `0xdry`, longueur 69, identique entre les 2 instances |
| T4-15 | `test_t4_executor.py::test_dry_run_idempotent` | 1 instance | 2e pause → `skipped "already paused"` ; 2e retrait `lend-eth/USDC` → `skipped "no position left"` |
| T4-16 | `test_t4_responder.py::test_handle_critical` | `FakeStore`, `DryRunExecutor`, `evidence_tmp`, R1 sur 45201812, handler espion | retourne 1 décision `DEC-fuji-45201812-1` ; statuts : NOTIFY `executed`, PAUSE `executed`, 4 EW `executed` avec `amount` `"400000000000"`, `"150000000000000000000"`, `"300000000000"`, `"100000000000000000000"`, OPEN_INCIDENT `executed`, UNPAUSE `pending_approval` ; `record_hash` 66 car. ; `anchor_tx` commence par `0xdry` ; `anchor_block > 0` ; `evidence_tmp/DEC-fuji-45201812-1.json` existe ; handler appelé 1 fois |
| T4-17 | `test_t4_responder.py::test_handle_idempotent` | rejouer T4-16 ; puis R4 critical sur 45201838 avec `deposits_paused=True` | 2e appel identique → `[]`, store = 1 décision ; décision suivante `DEC-fuji-45201838-1` avec PAUSE `skipped "already paused"` et 0 EW |
| T4-18 | `test_t4_responder.py::test_handle_survives_failures` | executor dont `emergency_withdraw` lève `RuntimeError("boom")` | aucune exception ; 4 EW `failed` avec `note` contenant `boom` ; OPEN_INCIDENT `executed` ; décision stockée |
| T4-19 | `test_t4_notify.py::test_notify_never_raises` | `ALERT_WEBHOOK_URL=http://127.0.0.1:9`, `SNS_TOPIC_ARN` bidon, `boto3.client` monkeypatché pour lever | pas d'exception ; retourne `["log", "webhook", "sns"]` |
| T4-20 | `test_t4_notify.py::test_payload` | décision T4-16 | `build_payload` a les clés `text`, `content`, `decision_id`, `severity=="critical"`, 1 alerte |
| T4-21 | `test_t4_verify.py::test_verify_match` | décision T4-16 | `match is True`, `diffs == []`, `anchored is True`, `stored_hash == recomputed_hash` |
| T4-22 | `test_t4_verify.py::test_verify_tamper` | `cli.main(["tamper", id, "--field", "decision.actions.2.params.asset", "--value", "DAI"])` puis `cli.main(["verify", id])` ; ensuite `restore`, puis tamper `inputs.snapshot.positions.1.withdrawable_now` = `"0"` | 1er : exit 1, stdout commence par `MISMATCH`, diffs contiennent `record_hash` et `action[2]` ; après `restore` : exit 0, `MATCH` ; 2e tamper : diffs contiennent `inputs_hash` et `action count: stored 8 != replanned 7` |
| T4-23 | `test_t4_verify.py::test_verify_not_anchored` | retirer l'entrée de `anchors.json` | `anchored False`, `match False`, diff contient `not anchored` ; `cli.main(["verify", "DEC-x"])` → 2 |
| T4-24 | `test_t4_api.py::test_routes` | `TestClient(app)`, `USE_FIXTURES` monkeypatché, `FakeStore` + `DryRunExecutor` injectés | fixtures : `GET /api/decisions` = longueur de `decisions.json` ; live : décision R3 high de T4-03 créée via `Responder.handle` (preuve écrite, id `DEC-fuji-45201826-1`), `POST /api/decisions/<id>/approve {"action_index":2,"approver":"risk-officer","approve":true}` → 200, `actions[2].status=="executed"`, `amount=="150000000000000000000"`, `note` commence par `approved by risk-officer` ; même POST → 409 ; index 0 → 409 ; index 9 → 400 ; id inconnu → 404 ; corps sans `approver` → 422 ; sur une 2e décision, `approve:false` → `rejected`, `note` commence par `rejected by risk-officer;` ; `POST /api/verify/<id>` → `match true` ; verify id inconnu → 404 |
| T4-25 | `test_t4_anvil.py::test_critical_on_anvil` (skip si RPC injoignable, `deployments/local.json` absent ou coffre vide) | `make chain && make deploy && make seed` ; `DRY_RUN_ACTIONS=false` ; snapshot construit depuis la chaîne par le test (positions via `getUserSupplied`, réserves via `getReservesData`) ; R1 critical à la main ; `Web3Executor` | `vault.depositsPaused() is True` ; `USDC.balanceOf(vault)` +700000000000 et `WETH.balanceOf(vault)` +250000000000000000000 ; 4 EW `executed` avec `tx_hash` 0x 66 car. ; `registry.anchoredAt(record_hash) > 0` ; `subprocess.run(["make","verify",f"ID={id}"])` → code 0, sortie contient `MATCH` ; approbation de `UNPAUSE_DEPOSITS` via l'API → `depositsPaused() is False` |

#### Definition of done

- [ ] `make test-t4` vert en dry-run sans chaîne ni AWS (T4-25 skip).
- [ ] T4-25 vert sur anvil après `make chain deploy seed`.
- [ ] `plan_actions` pur, réutilisé tel quel par `verify`.
- [ ] Une seule `Decision` par snapshot, idempotente, jamais d'exception remontée à l'engine.
- [ ] `data/evidence/<id>.json` écrit et ancré pour chaque décision ; `make verify ID=…` → `MATCH` ; `make tamper` → `MISMATCH` lisible.
- [ ] Routes 2.9 de T4 fonctionnelles en fixtures et en live ; front T6 peut approuver un `EMERGENCY_WITHDRAW` et un `UNPAUSE_DEPOSITS`.
- [ ] Aucune clé dans le code ; `GUARDIAN_PK` utilisé seulement pour pause et retrait d'urgence.
- [ ] Démo Fuji : une décision ancrée, lien snowtrace de `anchor_tx` ouvert à la main.

#### Pièges connus

- **Hash instable** : toujours `model_dump(mode="json")` avant `canonical_json` ; datetimes en UTC avec fuseau (sinon `+00:00` vs `Z`) ; ne jamais réécrire un float après coup ; trier les alertes par id.
- **`.hex()`** : selon la version de `hexbytes`, `HexBytes.hex()` inclut ou non `0x`. Utiliser `"0x" + bytes(x).hex()` ou `Web3.to_hex`.
- **`params` modifiés après planification** = `MISMATCH` systématique au verify. Les résultats vont dans `status/tx_hash/amount/note`, jamais dans `params`.
- **Ordre des déploiements** : `lend-eth` avant `lend-avax` (ordre du snapshot), pas l'ordre alphabétique.
- **`unpauseDeposits` est owner-only** : l'appeler avec la clé guardian revert.
- **`Evidence: already anchored`** : vérifier `anchoredAt` avant d'envoyer (re-run, redémarrage).
- **Latence Fuji** : ~2 s par transaction, 6 transactions en série ≈ 12 s ; `handle` tourne dans un thread (`asyncio.to_thread`, 2.10) donc l'API et le dashboard restent réactifs, mais le snapshot suivant n'est traité qu'après (acceptable en MVP, voir phase 2). Le webhook/SNS ne doit jamais retarder les retraits (thread).
- **Mode maintenance** (2.10) : pendant `seed`/`reset`, le moteur n'évalue aucune règle, donc `handle` n'est pas appelé ; après un reset, `store.generation` change et le Responder vide ses alertes vues (3.6).
- **Réserve en pause** : `emergencyWithdraw` revert `"MiniLend: paused"` ; l'action est `failed` avec cette raison dans `note`, jamais une exception remontée.
- **Nonces** : une clé par rôle et toujours `chain.send` (verrou par expéditeur) ; ne pas signer avec `evidence` et `guardian` depuis un autre process en parallèle.
- **`settings` lus à l'import** : en test, monkeypatcher `backend.settings.X` et lire `settings.X` au moment de l'appel.
- **Fixtures API** (`alerts.json`, `decisions.json`, `verify.json`) : régénérées (R1 et `DEC-fuji-45201812-1` au bloc 45201812) ; si ta copie locale montre encore des ids `D1..D7`, rebase. Pour les attentes numériques des tests, seules `snapshots_*.jsonl` font foi.
- **`tx_hash` `0xdry…`** : 69 caractères, pas un vrai hash ; le front ne doit pas en faire un lien explorer.

#### Plus tard (phase 2)

- Ancrer aussi chaque approbation humaine (nouveau `record_hash` chaîné au précédent) et l'état des règles (`kind="rules"`).
- Envoi des retraits en parallèle (threads) et priorisation par risque (actif drainé d'abord) au lieu de l'ordre fixe.
- `FULL_EXIT`, coût de sortie réel (`exit_cost_bps`), seuils d'exposition multiples dans la matrice.
- Bascule automatique sur `RPC_FALLBACK_URL` dans `Web3Executor`.
- Verify via S3 avec Object Lock, signature des fichiers de preuve.
- Rejouer `verify` côté front pour toutes les décisions et afficher l'historique d'approbations.

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T4 (réponse et preuves) du fichier TASKS.md à la racine du repo.
1. Lis TASKS.md sections 1 et 2 en entier, puis la section T4 en entier. Lis backend/models.py,
   backend/settings.py, backend/chain.py et 3 lignes de fixtures/snapshots_attack.jsonl
   (blocs 45201812, 45201826, 45201838). Les attentes chiffrées des tests viennent de
   snapshots_attack.jsonl, pas de fixtures/alerts.json ni decisions.json (exemples de format).
2. Ne modifie QUE : backend/responder.py, backend/executor.py, backend/notify.py,
   backend/evidence.py, backend/cli.py, backend/config/playbook.yaml, backend/api/response.py,
   backend/tests/test_t4_*.py, mk/t4.mk. Si tu as besoin d'un changement ailleurs (models.py,
   chain.py, store.py, main.py, fixtures) ou dans le contrat de la section 2, n'édite pas :
   écris la demande dans docs/contract-requests.md et préviens-moi.
3. Travaille avec DRY_RUN_ACTIONS=true, des Alert construites à la main (helper make_alert),
   les Snapshot de fixtures/snapshots_attack.jsonl et un FakeStore si backend/store.py manque.
   Le test anvil (T4-25) doit se mettre en skip proprement tant que la chaîne n'est pas là.
4. Commence par écrire backend/tests/test_t4_fixtures.py puis les tests T4-01 à T4-25
   (noms et valeurs exactes de la section T4), vérifie qu'ils échouent, puis implémente dans
   cet ordre : playbook.yaml, plan_actions/assess, evidence, executor, notify, Responder,
   cli, api/response.py, mk/t4.mk.
5. Avant chaque commit : make test-t4 (pytest backend/tests/test_t4_*.py) doit être vert.
   Petits commits, push fréquent après chaque test vert.
```


---


### T5 · Incident et DORA : ouverture, chronologie, classification, rapport, dépendances

**Objectif.** Transformer les décisions de T4 en **un incident suivi** (statut, chronologie, montants sauvés et encore à risque), proposer sa **classification DORA** exactement selon le RTS (UE) 2024/1772 (Art. 8 et 9), calculer les **délais** du règlement (UE) 2025/301, produire le **brouillon de notification initiale** (markdown, description éventuellement rédigée par Bedrock) et tenir le **registre des dépendances tierces**. La classification est une **proposition** : seul un humain la soumet (`POST /api/incidents/{id}/submit`).

**Dépend de.**
- T0 → `backend/store.py`, `backend/models.py`, stubs, `fixtures/` → si `store.py` n'est pas encore mergé : `FakeStore` dans `backend/tests/test_t5_factories.py` (mêmes méthodes que 2.10, en mémoire, y compris l'attribut `generation` incrémenté par `reset`).
- T3 → `Alert` et `Snapshot` stockés → `fixtures/snapshots_attack.jsonl` (sans réaction) + série « avec réaction » fabriquée par `make_reacted_series()` ; alertes construites à la main (`make_alert_r1()`).
- T4 → `Decision` (actions exécutées, `tx_hash`, `amount`), approbations humaines via `store.update_decision` → décisions construites à la main selon 2.8 (`make_decision_r1()`), mutation directe du `FakeStore` pour simuler une approbation. Aucune transaction : T5 n'en envoie jamais.
- T8 → accès Bedrock (`BEDROCK_MODEL_ID`, credentials AWS) → `BEDROCK_MODEL_ID` vide = modèle de repli déterministe ; client boto3 remplacé par un stub dans les tests.

**Débloque.** T6 (page incident, chronologie, badge DORA, délais, bouton Submit, tableau des dépendances), T7 (`saved_usd` / `at_risk_usd` par run), T9 (rapport DORA d'exemple, fiche conformité), T0 (régénération de `incident.json` et `dependencies.json` avec les vrais chiffres).

**Fichiers possédés.** `backend/incidents.py`, `backend/dora.py`, `backend/llm.py`, `backend/config/dora_profile.yaml`, `backend/config/dependencies.yaml`, `backend/api/incidents.py`, `mk/t5.mk`, `backend/tests/test_t5_*.py`.

**À lire avant de commencer.** `TASKS.md` sections 1.2, 1.5, 2.5, 2.6, 2.7 (exposition), 2.8 (positions concernées), 2.9 (routes T5), 2.10 (`IncidentManager`), 2.13 ; `backend/models.py` (`Incident`, `TimelineEvent`, `DoraCriteria`, `DoraDeadlines`, `DoraAssessment`, `Dependency`) ; `fixtures/incident.json` et `fixtures/dependencies.json` pour la **forme** (les attentes chiffrées des tests sont calculées par nos fabriques, pas lues dans les fixtures).

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| `decisions, alerts, snapshot` passés à `IncidentManager.handle` | `list[Decision]`, `list[Alert]`, `Snapshot` | T4 via `responder.on_decisions` (câblage T0) | appel direct dans les tests avec `make_decision_r1()`, `make_alert_r1()` |
| Historique des snapshots | `store.snapshots(limit=500)`, `store.latest_snapshot()` | T3 (engine) | `FakeStore` rempli avec `snapshots_attack.jsonl` ou `make_reacted_series()` |
| Statut à jour des actions (approbations, exécutions humaines) | `store.get_decision(id)` | T4 (`POST /api/decisions/{id}/approve` → `update_decision`) | modifier la décision dans le `FakeStore` puis `manager.refresh(incident_id)` |
| Profil DORA de l'entité | `backend/config/dora_profile.yaml` | T5 | — |
| Registre des tiers | `backend/config/dependencies.yaml` | T5 | — |
| Rédaction IA | Bedrock Converse (`BEDROCK_MODEL_ID`, `AWS_REGION`) | T8 (accès), T5 (code) | variable vide → template ; stub de client |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| Incident courant | `Incident` écrit par `store.upsert_incident` à chaque changement | T6, T7, T9 |
| `GET /api/incidents` | `Incident[]`, plus récent d'abord (`opened_at` décroissant) | T6 |
| `GET /api/incidents/{id}` | `Incident` ; 404 `{"detail": "incident not found"}` | T6 |
| `GET /api/incidents/{id}/report.md` | `text/markdown; charset=utf-8`, contenu de `dora.report_markdown` | T6 (lien), T9 |
| `POST /api/incidents/{id}/submit` | corps `{"submitted_by": str}` → `Incident` avec `dora.submitted = true` ; 409 si déjà soumis ou sans DORA | T6 |
| `GET /api/dependencies` | `Dependency[]` (ordre du YAML) | T6 |
| Rapport sur disque | `data/reports/<INC-id>.md` via `make dora-report ID=…` | T9 |
| Logs | logger `t5.incidents` / `t5.dora` / `t5.llm`, une ligne `key=value` par événement | tous (debug) |

#### Spécification détaillée

**1. Profil DORA (`backend/config/dora_profile.yaml`)** — données synthétiques, jamais de vraie entité :
```yaml
version: 1
entity_name: "Example Treasury SAS (synthetic)"
entity_type: "crypto-asset service provider"
clients_count: 1200
client_member_states: [FR, DE]
critical_services: ["on-chain treasury management"]
usd_to_eur: 0.92
reputational_impact: false
data_losses: false
malicious_unauthorised_access: false   # la faille est chez le bridge tiers, pas dans nos systèmes (Art. 9(5)(b) vise nos SI)
```
`load_profile(path: Path = settings.CONFIG_DIR / "dora_profile.yaml") -> dict` : `yaml.safe_load`, vérifie la présence de chaque clé, lève `ValueError("dora_profile: missing <key>")` sinon.

**2. `backend/dora.py` : classification pure (aucun I/O hors `load_profile`).**
```python
T_9_1  = "9(1) clients, financial counterparts and transactions"
T_9_2  = "9(2) reputational impact"
T_9_3  = "9(3) duration and service downtime"
T_9_4  = "9(4) geographical spread"
T_9_5A = "9(5)(a) data losses"
T_9_5B = "9(5)(b) malicious unauthorised access"
T_9_6  = "9(6) economic impact"
class Classification(NamedTuple): thresholds_met: list[str]; is_major: bool; legal_basis: str
def classify(c: DoraCriteria) -> Classification
```
Seuils (comparaisons **strictes** « > », sauf 9(4)) :
- 9(1) atteint si l'un : `clients_affected_pct > 10` ; `clients_affected_count > 100_000` ; `counterparts_affected_pct > 30` ; `transactions_affected_value_pct > 10` ; `transactions_affected_count_pct > 10` ; `relevant_clients_affected`. Les trois champs optionnels `counterparts_affected_pct`, `transactions_affected_count_pct` et `relevant_clients_affected` existent dans `models.py` (2.6, défauts `0` / `0` / `false`) : les lire directement (`c.counterparts_affected_pct`, etc.).
- 9(2) `reputational_impact` ; 9(3) `duration_hours > 24` ou `critical_service_downtime_hours > 2` ; 9(4) `member_states_affected >= 2` ; 9(5)(a) `data_losses` ; 9(5)(b) `malicious_unauthorised_access` ; 9(6) `economic_impact_eur > 100_000`.
- `thresholds_met` dans l'ordre des articles ci-dessus. Un critère compte **une fois** même si plusieurs sous-seuils sont atteints (9(5)(a) et 9(5)(b) comptent comme un seul critère « 9(5) » pour la règle des deux critères).

Art. 8(1) : `is_major = critical_services_affected and (T_9_5B in met or nb_criteres_distincts >= 2)`. `legal_basis` (une phrase, exactement ces gabarits) :
- `"RTS (EU) 2024/1772 Art. 8(1)(a): critical services affected and malicious unauthorised access (Art. 9(5)(b)) identified."`
- `"RTS (EU) 2024/1772 Art. 8(1)(b): critical services affected and 2 materiality thresholds of Art. 9 met (9(1), 9(4))."` (nombre et liste courte calculés)
- `"RTS (EU) 2024/1772 Art. 8(1): not major, no critical service affected."`
- `"RTS (EU) 2024/1772 Art. 8(1): not major, critical services affected but only 1 materiality threshold of Art. 9 met (9(1))."` (ou `0 ... met (none)`).

**3. Faits → critères.**
```python
@dataclass(frozen=True)
class IncidentFacts:
    exposure_usd: float; total_treasury_usd: float; at_risk_usd: float
    aware_at: datetime; end_at: datetime; deposits_paused_hours: float
def compute_criteria(f: IncidentFacts, profile: dict) -> DoraCriteria
```
- `critical_services_affected = bool(profile["critical_services"]) and f.exposure_usd > 0`.
- `clients_affected_pct = round(min(100.0, f.exposure_usd / f.total_treasury_usd * 100), 2)` (0 si total = 0) ; `clients_affected_count = round(clients_count * pct / 100)`.
- `transactions_affected_value_pct = 0.0`, `counterparts_affected_pct = 0.0`, `transactions_affected_count_pct = 0.0`, `relevant_clients_affected = False` (pas de flux clients ni de contreparties dans le MVP, documenté dans le rapport ; toujours écrits explicitement, aucune clé absente).
- `duration_hours = (end_at - aware_at) / 3600 s` ; `critical_service_downtime_hours = deposits_paused_hours` (le service « dépôt dans la trésorerie » est indisponible tant que le coffre est en pause).
- `member_states_affected = len(client_member_states) if pct > 0 else 0`.
- `reputational_impact`, `data_losses`, `malicious_unauthorised_access` : valeurs du profil.
- `economic_impact_eur = round(f.at_risk_usd * usd_to_eur, 2)`.

Scénario avec réaction : exposition 1 325 000, total 1 325 000, à risque 0 → pct 100.0, count 1200, États 2, économique 0.0 → `[T_9_1, T_9_4]`, majeur via 8(1)(b). Sans réaction (série brute) : à risque 375 000 → 345 000.0 EUR → `[T_9_1, T_9_4, T_9_6]`.

**4. Délais.** `def deadlines(aware_at, classified_at, initial_submitted_at=None) -> DoraDeadlines` :
- `initial_notification_due = min(classified_at + 4 h, aware_at + 24 h)` ;
- `intermediate_report_due = (initial_submitted_at or initial_notification_due) + 72 h` ;
- `final_report_due = intermediate_report_due + 30 jours` (approximation documentée d'« un mois » ; phase 2 : vrai mois calendaire et date du dernier rapport intermédiaire).

**5. Rapport.** `def render_report(incident: Incident, description: str | None = None, profile: dict | None = None) -> str`. `description=None` → `template_description(incident)`. Sortie (titres exacts, dans cet ordre) :
```
# DORA initial notification (draft, human review required)
## 1. General information      (entité, type, référence incident, détection = aware_at, classification = classified_at)
## 2. Classification proposal   (Major / Not major + legal_basis)
## 3. Description               (paragraphe ; suffixe "_(AI-drafted, review required)_" si IA)
## 4. Classification criteria (RTS 2024/1772 Art. 9)   (tableau | Criterion | Value | Threshold | Met |, une ligne par seuil)
## 5. Actions taken             (une puce par action exécutée : type, montant lisible, déploiement, tx hash)
## 6. Deadlines (Regulation (EU) 2025/301)            (tableau initial / intermediate / final)
## 7. Third parties involved    (ids des dépendances concernées : rseth, lend-eth, lend-avax, oracle)
## 8. Human review              ("This classification is a proposal. It must be reviewed and submitted by an authorised person." + statut submitted)
```
Formats : dates ISO `2026-10-11T08:00:26Z`, montants `1,325,000 USD`, jetons `150 WETH` (division entière par `10**decimals`, 2 décimales max sans zéros inutiles). Aucun `None`, `nan`, `{` ou `TODO` dans la sortie.
`template_description(incident)` : `"At <aware_at> the monitoring platform raised <rule_id> (<severity>): <explanation of first alert> Automated controls paused new deposits and withdrew <saved> USD to the treasury vault. Exposure at detection: <exposure> USD; value still at risk: <at_risk> USD. Current status: <status>."`

**6. `backend/llm.py` (optionnel, jamais bloquant).**
```python
def enabled() -> bool                                    # settings.BEDROCK_MODEL_ID != ""
def draft_description(facts: dict) -> tuple[str, bool]   # (texte, ai_used)
def last_status() -> Literal["ok", "degraded", "unknown"]
```
- Client : `boto3.client("bedrock-runtime", region_name=settings.AWS_REGION, config=Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 1}))`, créé paresseusement.
- Appel : `converse(modelId=BEDROCK_MODEL_ID, system=[{"text": SYSTEM}], messages=[{"role": "user", "content": [{"text": json.dumps(facts, sort_keys=True)}]}], inferenceConfig={"maxTokens": 400, "temperature": 0})` ; texte = `resp["output"]["message"]["content"][0]["text"].strip()`.
- `SYSTEM` : « Write the Description paragraph of a DORA initial incident notification, in English, max 120 words, factual, using only the facts provided. Do not speculate on attribution. Do not invent numbers. »
- `facts` : id, titre, rule ids, gravité, aware_at, montants USD, actions exécutées (type, actif, déploiement), statut. Rien d'autre (pas de clé, pas d'adresse privée).
- Débit : verrou + `time.monotonic()` ; si le dernier appel date de moins de 1,0 s, `time.sleep(reste)`. Cache module `{sha256(facts): texte}` : mêmes faits → pas de nouvel appel.
- Repli : variable vide, exception, texte vide ou > 1 500 caractères → `(template, False)` + log `WARNING t5.llm fallback reason=<type>`.
- L'appel Bedrock ne doit **jamais** retarder le moteur : `IncidentManager` l'exécute dans un `threading.Thread(daemon=True)` ; le rapport sort d'abord avec le template (`ai_drafted_sections = []`), puis le thread remplace la section Description, met `ai_drafted_sections = ["Description"]` et refait `upsert_incident`. Option constructeur `IncidentManager(store, llm_async=True)` ; les tests passent `llm_async=False`.

**7. `backend/incidents.py` : `IncidentManager`.** Tout l'état vit dans le store (le manager peut être instancié deux fois, par `main.py` et par l'API, sans divergence). Un `threading.RLock` protège `handle` et `refresh`.
```python
CONTAINMENT_SNAPSHOTS = 10
class IncidentManager:
    def __init__(self, store: Store, *, llm_async: bool = True, profile: dict | None = None): ...
    def handle(self, decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot) -> Incident | None
    def refresh(self, incident_id: str) -> Incident | None   # recalcule tout depuis le store, upsert si changé
    def submit(self, incident_id: str, submitted_by: str) -> Incident   # KeyError / ValueError("already submitted")
def concerned_positions(alert: Alert, snapshot: Snapshot) -> set[tuple[str, str]]   # (deployment_id, asset)
```
`handle` :
1. Si le store ne contient pas `snapshot.block_number`, l'utiliser comme snapshot de secours.
2. `current` = incident le plus récent dont `status != "resolved"`.
3. Si `current is None` : chercher la première décision contenant une action `OPEN_INCIDENT` (tout statut sauf `failed`). Aucune → `return None` (les alertes isolées n'ouvrent rien). Sinon créer : `id = f"INC-{created_at:%Y%m%d}-{n:03d}"` (n = 1 + nb d'incidents du store avec ce préfixe), `opened_at = decision.created_at`, `detected_at = min(alert.detected_at)`, `severity` = max des alertes, `title = f"{first_alert.title} ({', '.join(sorted(deployments concernés))})"`. Log `INFO t5.incidents opened id=… decision=… exposure_usd=…`.
4. Sinon : attacher **toutes** les décisions et alertes reçues (sans doublon, ordre d'arrivée).
5. `refresh(id)` puis retourner l'incident.

`concerned_positions` (règle de 2.8) : R1 (asset = jeton, `deployment_id=None`) → toutes les positions du coffre dans les déploiements où la réserve `asset == alert.asset` a `ltv_bps > 0` ; R2, R3, R4 → `(deployment_id, asset)` ; R5 → toutes les positions du déploiement. S'y ajoutent les `(params["deployment_id"], params["asset"])` de chaque `EMERGENCY_WITHDRAW` des décisions.

`refresh` recalcule, dans cet ordre :
- **saved_usd** = Σ des `EMERGENCY_WITHDRAW` au statut `executed` avec `amount` : `int(amount) / 10**decimals * price_usd`, `decimals` et `price_usd` lus dans la réserve `(deployment_id, asset)` du snapshot du bloc `decision.block_number` (sinon le plus proche en dessous, sinon le dernier). Scénario : 150×2 500 + 400 000 + 100×2 500 + 300 000 = **1 325 000.0**.
- **exposure_usd** = Σ `value_usd` des positions concernées, prise au snapshot où chaque position devient concernée → **1 325 000.0**.
- **at_risk_usd** = Σ `max(0, value_usd − withdrawable_usd)` des positions concernées dans `store.latest_snapshot()` (position absente = 0). Avec réaction 0.0 ; série brute au bloc 45 201 880 : **375 000.0**.
- **status** : « alerte pertinente » = gravité ∈ {high, critical} et `exposure_usd >= 1000`. `after` = snapshots de bloc > dernière alerte pertinente. `contained` si `len(after) >= 10` **et** pour le dernier snapshot aucune position concernée n'a `int(withdrawable_now) < int(supplied)` ; `contained_at` = `block_time` du premier snapshot de la série continue finale où la condition position tient, au plus tôt `after[9]`. Sinon `open`, `contained_at = None` (une nouvelle alerte pertinente rouvre). `resolved` n'est jamais posé par le code MVP. Série avec réaction et alerte au bloc 45 201 812 → `contained_at = 2026-10-11T08:01:04Z` (bloc 45 201 832).
- **DORA** (sauf si `dora.submitted`, rapport alors figé) : `aware_at = detected_at` ; `end_at = contained_at or latest.block_time` ; `deposits_paused_hours` = depuis le premier `PAUSE_DEPOSITS` exécuté jusqu'à un `UNPAUSE_DEPOSITS` exécuté ou `latest.block_time` ; `total_treasury_usd` = Σ `value_usd` de toutes les positions + soldes `idle_balances` valorisés (même définition que `StateResponse.totals.value_usd` en 2.6), au snapshot d'ouverture. `classified_at` = `opened_at` à la première évaluation ; si `is_major` passe de false à true plus tard, `classified_at = latest.block_time`.
- **timeline** reconstruite entièrement (stateless, triée par `(at, block_number or 0)`) :

| kind | source | text (exemple exact) | ref |
|---|---|---|---|
| alert | chaque alerte | `R1_BRIDGE_INVARIANT critical: rsETH bridge invariant broken` (`<rule_id> <severity>: <alert.title>`) | alert id |
| decision | chaque décision | `Decision DEC-fuji-45201812-1: critical\|exposure>=1k\|exit_possible` | decision id |
| action | action `executed` | `Deposits paused` / `Emergency withdrawal: 150 WETH from lend-eth to the vault (375,000 USD)` / `Notification sent (log, webhook, sns)` (canaux lus dans `Action.note` au format T4 `channels: log,webhook,sns` : regex `channels: ([^;]+)`, découpe sur `,`, `strip()`, rejoints par `", "` ; note absente ou sans `channels:` → `Notification sent`) ; suffixe ` (dry run)` si `tx_hash` commence par `0xdry` | tx hash sinon decision id |
| action | action `failed` | `EMERGENCY_WITHDRAW failed: <note>` | decision id |
| human | `pending_approval` | `Awaiting human approval: UNPAUSE_DEPOSITS` | decision id |
| human | action dont `note` contient une décision humaine (statut final `approved`, `rejected`, `executed`, `failed` ou `skipped` après approbation) | `UNPAUSE_DEPOSITS approved by treasury-signer-1` : `re.search(r"(approved\|rejected) by ([^;]+)", note)` → `f"{type} {m[1]} by {m[2].strip()}"` ; pas de correspondance → pas d'événement humain | decision id |
| chain | 1er snapshot où `available_liquidity == "0"` sur une réserve d'une position concernée | `WETH liquidity on lend-eth reaches zero` | None |
| dora | classification | `DORA classification proposed: major (9(1), 9(4))` | incident id |
| human | soumission | `DORA initial notification submitted by <submitted_by>` | incident id |
| decision | `contained_at` | `Incident contained: no exposed position left` | incident id |

Logs : `INFO t5.incidents status id=… from=open to=contained at=…`, `INFO t5.dora classified id=… major=true thresholds=9(1),9(4)`.

**8. Dépendances (`backend/config/dependencies.yaml` + `incidents.dependency_statuses(store, now=None) -> list[Dependency]`).** Chaque entrée = champs de `Dependency` + `check` (clé interne, retirée avant validation) :

| id | kind | criticality | fallback | check → statut |
|---|---|---|---|---|
| `rpc-fuji` | rpc | critical | `RPC_FALLBACK_URL` | `freshness` : âge du dernier snapshot (`now − block_time`) ≤ 30 s ok, ≤ 120 s degraded, sinon down ; pas de snapshot unknown |
| `aws-compute` | cloud | critical | `make demo` en local | `none` → unknown |
| `aws-sns` | alerting | important | webhook | `none` → unknown |
| `aws-s3` | cloud | important | `data/evidence` + hash on-chain | `none` → unknown |
| `bedrock` | ai_model | standard | template déterministe | `llm.last_status()` ; unknown si jamais appelé |
| `oracle` | oracle | critical | second oracle (prévu) | ok si tous les `price_usd > 0`, sinon degraded |
| `lend-eth`, `lend-avax` | protocol | critical | — | réserve `paused` → down ; réserve `frozen` ou position du coffre `withdrawable_ratio_bps < 10000` → degraded ; sinon ok |
| `rseth` | bridge | important | — | `backing_ratio_bps` ≥ 9900 ok, ≥ 5000 degraded, sinon down |

**9. API (`backend/api/incidents.py`, `router = APIRouter(tags=["incidents"])`).** Lire `settings.USE_FIXTURES` **à chaque requête**. Mode fixtures : comportement du squelette T0 (fixture validée, `submit` modifie une copie). Mode réel : `IncidentManager(store)` puis `refresh` avant chaque lecture. `SubmitBody(submitted_by: str = Field(min_length=1))` → 422 si vide. 404 `{"detail": "incident not found"}` ; 409 `{"detail": "incident has no DORA assessment"}` ou `{"detail": "already submitted"}` (cas « incident déjà soumis » de 2.9) ; 422 pour `submitted_by` vide (cas « corps invalide » de 2.9, géré par la validation FastAPI). Report : `PlainTextResponse(md, media_type="text/markdown; charset=utf-8")`.

**10. `mk/t5.mk`.**
```make
test-t5:      ## T5 tests
	python -m pytest backend/tests/test_t5_*.py -q
dora-report:  ## write data/reports/$(ID).md from the running backend
	python -m backend.dora report --id $(ID) --api http://127.0.0.1:8000
dora-demo:    ## print the report for the scenario facts (offline, no API)
	python -m backend.dora demo
```
`report` fait un GET `/api/incidents/<ID>/report.md` (urllib, timeout 5 s), écrit `data/reports/<ID>.md`, l'affiche ; code de sortie 1 avec message clair si l'API ne répond pas.

#### Tests qui doivent passer

Commande globale : `make test-t5` (= `python -m pytest backend/tests/test_t5_*.py -q`, jamais de `-k`). Fabriques communes dans `backend/tests/test_t5_factories.py` (aucune fonction `test_*`) : `load_attack()` (41 snapshots), `make_reacted_series()` (copie de la série ; à partir du bloc 45 201 814 : positions `supplied = withdrawable_now = "0"`, `withdrawable_ratio_bps = 10000`, `value_usd = withdrawable_usd = 0.0`, `deposits_paused = True`, `idle_balances = {"WETH": "250000000000000000000", "USDC": "700000000000"}`), `make_alert_r1()` (`ALT-fuji-45201812-R1_BRIDGE_INVARIANT-global-rsETH`, critical, `deployment_id=None`, asset rsETH, bloc 45 201 812, `block_time` 08:00:24Z, `detected_at` 08:00:26Z, exposition 1 325 000.0, title **exactement** celui de T3 `rsETH bridge invariant broken`, explanation au format T3 `The rsETH bridge released 5,000 tokens without canonical source backing; destination nonce 308 is ahead of source nonce 307.`, `metrics` au format T3 `{"source_locked": 1200.0, "destination_released": 6200.0, "conservation_gap": 5000.0, "source_nonce": 307, "destination_nonce": 308, "exposed_deployments": "lend-eth,lend-avax"}`), `make_decision_r1(no_reaction=False)` (`DEC-fuji-45201812-1`, `created_at` 08:00:26Z, 8 actions de 2.8 : NOTIFY, PAUSE_DEPOSITS, 4 × EMERGENCY_WITHDRAW lend-eth WETH `150e18`, lend-eth USDC `400000e6`, lend-avax WETH `100e18`, lend-avax USDC `300000e6` avec `tx_hash = "0x" + f"{i:02x}" * 32`, NOTIFY `note="channels: log,webhook,sns"`, OPEN_INCIDENT, UNPAUSE_DEPOSITS human `pending_approval` ; `no_reaction=True` → les 4 retraits `skipped`, `amount=None`, pour simuler une plateforme qui n'a pas pu réagir), `FakeStore`, `run_series(manager, snapshots, at={block: (decisions, alerts)})` (ajoute chaque snapshot puis appelle `handle`, avec `[]`, `[]` hors des blocs donnés).

| Id | Type | Fichier::test | Setup | Résultat attendu |
|---|---|---|---|---|
| T5-01 | unit | `test_t5_dora.py::test_no_critical_service_never_major` | tous les seuils atteints, `critical_services_affected=False` | `is_major is False`, 7 libellés dans `thresholds_met`, `legal_basis` contient `not major, no critical service` |
| T5-02 | unit | `::test_single_threshold_not_major` | critical, `clients_affected_pct=15`, reste à 0 | `thresholds_met == [T_9_1]`, `is_major is False` |
| T5-03 | unit | `::test_malicious_access_alone_major` | critical, `malicious_unauthorised_access=True` seul | `== [T_9_5B]`, majeur, `Art. 8(1)(a)` dans `legal_basis` |
| T5-04 | unit | `::test_two_thresholds_major` (paramétré sur 6 paires) | ex. 9(2)+9(4), 9(3)+9(6) | `is_major is True`, `Art. 8(1)(b)` |
| T5-05 | unit | `::test_boundaries` (paramétré) | pct 10 / 10.01 ; count 100000 / 100001 ; durée 24 / 24.01 ; downtime 2 / 2.01 ; États 1 / 2 ; 100000 / 100000.01 EUR ; et un cas par champ optionnel de 9(1) : `counterparts_affected_pct` 30 / 30.01, `transactions_affected_count_pct` 10 / 10.01, `relevant_clients_affected` False / True | premier non atteint, second atteint (pour les trois optionnels : `T_9_1` dans `thresholds_met` uniquement pour le second) |
| T5-06 | unit | `::test_criterion_counts_once` | critical, pct 50 et count 200 000 | `[T_9_1]`, non majeur ; `data_losses` + malicious → 9(5) compte 1 |
| T5-07 | unit | `::test_deadlines_nominal` | aware `2026-10-11T08:00:26Z`, classified `08:02:26Z` | `12:02:26Z`, `2026-10-14T12:02:26Z`, `2026-11-13T12:02:26Z` |
| T5-08 | unit | `::test_deadlines_24h_cap` | aware `2026-10-11T00:00:00Z`, classified `22:00:00Z` | initial `2026-10-12T00:00:00Z` |
| T5-09 | unit | `::test_deadlines_after_submission` | T5-07 + soumis `2026-10-11T10:00:00Z` | intermédiaire `2026-10-14T10:00:00Z`, final `2026-11-13T10:00:00Z` |
| T5-10 | unit | `::test_scenario_facts` | faits avec réaction + profil | pct 100.0, count 1200, États 2, économique 0.0, `[T_9_1, T_9_4]`, majeur |
| T5-11 | unit | `::test_counterfactual_facts` | `at_risk_usd=375000` | économique 345000.0, `[T_9_1, T_9_4, T_9_6]` |
| T5-12 | unit | `::test_report_markdown` | incident de T5-17 (`llm_async=False`, LLM désactivé) | 1re ligne = titre H1 exact, les 8 titres `##` présents dans l'ordre, contient `1,325,000 USD` et `INC-20261011-001`, aucune correspondance de la regex `\bNone\b\|\bnan\b\|TODO\|\{[a-z_]+\}` (attention : « financial » contient `nan`, d'où les `\b`) |
| T5-13 | unit | `test_t5_llm.py::test_disabled_uses_template` | `BEDROCK_MODEL_ID=""`, `boto3.client` patché pour lever | `(template, False)`, incident `ai_drafted_sections == []` |
| T5-14 | unit | `::test_bedrock_error_falls_back` | stub dont `converse` lève `ReadTimeoutError` | template, `last_status() == "degraded"` |
| T5-15 | unit | `::test_bedrock_success` | stub renvoyant un paragraphe ; `llm_async=False` | `converse` appelé avec `modelId`, `temperature=0`, `maxTokens=400` ; `ai_drafted_sections == ["Description"]` ; texte dans la section 3 |
| T5-16 | unit | `::test_rate_limit_and_cache` | horloge factice | 2 faits différents d'affilée → `sleep(≈1.0)` ; mêmes faits → 1 seul appel |
| T5-17 | intégration | `test_t5_incidents.py::test_opens_one_incident_reacted` | `make_reacted_series()`, décision R1 au bloc 45 201 812 | 1 incident `INC-20261011-001`, `contained`, `contained_at = 2026-10-11T08:01:04Z`, `saved_usd 1325000.0`, `at_risk_usd 0.0`, `exposure_usd 1325000.0`, `severity critical`, DORA majeur `[T_9_1, T_9_4]`, `initial_notification_due 2026-10-11T12:00:26Z` |
| T5-18 | intégration | `::test_no_open_incident_action` | décision warning (NOTIFY seul) | `handle` → `None`, `store.incidents() == []` |
| T5-19 | intégration | `::test_attaches_later_decisions_raw` | série brute, R1 `no_reaction=True` + décision R3 liquidity high au bloc 45 201 826 (avec OPEN_INCIDENT) | 1 seul incident, 2 décisions, 2 alertes, `open`, `saved_usd 0.0`, `at_risk_usd 375000.0`, seuils `[T_9_1, T_9_4, T_9_6]` |
| T5-20 | intégration | `::test_timeline` | T5-17 | kinds ⊇ {alert, decision, action, human, dora} ; triée par `at` ; 4 événements `Emergency withdrawal` avec `ref` = tx hash ; contient `Emergency withdrawal: 150 WETH from lend-eth to the vault (375,000 USD)`, `Notification sent (log, webhook, sns)` et `R1_BRIDGE_INVARIANT critical: rsETH bridge invariant broken` |
| T5-21 | intégration | `::test_human_approval_picked_up` | T5-17, action 7 → `executed`, `note="approved by treasury-signer-1; "` (format T4), `refresh` ; puis variante `rejected`, `note="rejected by risk-officer"` | événement `UNPAUSE_DEPOSITS approved by treasury-signer-1` (sans `;` ni espace final) ; variante : `UNPAUSE_DEPOSITS rejected by risk-officer` ; plus d'événement `Awaiting human approval` |
| T5-22 | intégration | `::test_reopen_on_new_relevant_alert` | T5-17 puis alerte critical exposition 5 000 | `open`, `contained_at is None` |
| T5-23 | intégration | `::test_idempotent_and_resolved` | `handle` 2× même décision ; puis incident forcé `resolved` + nouvelle décision OPEN_INCIDENT | pas de doublon ; nouvel id `INC-20261011-002` |
| T5-24 | API | `test_t5_api.py::test_fixture_mode` | `USE_FIXTURES=true`, `FastAPI()` + routeur T5 | liste de 1, détail 200, `UNKNOWN` → 404 |
| T5-25 | API | `::test_live_mode` | `USE_FIXTURES=false`, store de T5-17 (monkeypatch `backend.store.store`) | détail `saved_usd 1325000.0` ; `report.md` → `content-type` commence par `text/markdown`, corps commence par le titre H1 |
| T5-26 | API | `::test_submit` | idem | 1er POST 200 `submitted true` ; 2e → 409 `{"detail": "already submitted"}` (incident déjà soumis, 2.9) ; `submitted_by=""` → 422 (corps invalide, 2.9) ; id inconnu → 404 |
| T5-27 | unit | `test_t5_dependencies.py::test_statuses` | dernier snapshot = ligne 41 de la série brute, `now = block_time + 10 s` | 9 entrées validées `Dependency` ; `rseth down`, `lend-eth degraded`, `lend-avax ok`, `rpc-fuji ok`, `aws-sns unknown`, `bedrock unknown` ; `now + 200 s` → `rpc-fuji down` |

#### Definition of done

- [ ] `make test-t5` vert (T5-01 à T5-27), sans réseau ni AWS.
- [ ] `classify` ne dépend que de `DoraCriteria` ; chaque seuil de l'Art. 9 a un test de borne.
- [ ] Avec `USE_FIXTURES=false` et le moteur actif sur anvil, une attaque (`make attack SEED=42`) produit exactement un incident `contained`, `saved_usd ≈ 1 325 000`, rapport téléchargeable.
- [ ] `make dora-demo` affiche un rapport complet ; `make dora-report ID=INC-…` écrit `data/reports/INC-….md`.
- [ ] Bedrock coupé ou en erreur : aucun blocage du moteur, rapport issu du template.
- [ ] Aucune modification de fichier hors « Fichiers possédés » ; demandes écrites dans `docs/contract-requests.md`.

#### Pièges connus

- Ne **jamais** modifier une `Decision` (son `record_hash` est ancré par T4) : le lien décision → incident passe par `Incident.decision_ids`, pas par les `params` de `OPEN_INCIDENT`.
- `handle` est appelé par le moteur via `await asyncio.to_thread(...)`, un appel à la fois dans l'ordre des snapshots (2.10) : il ne bloque pas l'API, mais un `handle` lent retarde le traitement des snapshots suivants. Donc pas d'appel réseau synchrone (Bedrock en thread), pas d'exception qui remonte (try/except + log `ERROR`, retour `None`). L'API appelle `refresh` depuis un autre thread : d'où le `RLock`.
- `store.reset()` (via `make reset` / `POST /api/demo/reset`) vide les incidents et incrémente `store.generation` : le thread Bedrock mémorise `generation` au lancement et n'appelle pas `upsert_incident` si elle a changé (sinon un incident effacé réapparaît). Pendant le mode maintenance (2.10), le moteur n'évalue aucune règle : aucune décision n'arrive, rien à faire de spécial côté T5.
- Un `EMERGENCY_WITHDRAW` `executed` avec `amount="0"` (rien à retirer, 2.2) compte 0 dans `saved_usd` ; un retrait `failed` (`MiniLend: paused`) produit l'événement `EMERGENCY_WITHDRAW failed: <note>`.
- Les approbations humaines n'appellent pas `handle` : d'où `refresh` sur chaque lecture d'API.
- Montants en unités de base : `int(amount)`, jamais `float(amount)` avant la division finale.
- `store.snapshots()` peut avoir perdu le snapshot d'ouverture (fenêtre limitée) : retomber sur le plus proche puis le dernier.
- Le fixture `incident.json` sert de modèle de forme ; nos attentes chiffrées viennent des fabriques (T0 le régénère ensuite avec nos vrais chiffres).
- Fixtures « avec réaction » de T0 régénérées : alerte R1 et `DEC-fuji-45201812-1` au bloc 45 201 812, comme nos fabriques (l'id de décision reprend le bloc du snapshot des alertes). Ne pas coder de numéro de bloc en dur dans le code de production.
- `datetime` toujours avec fuseau UTC ; sérialiser avec `Z`.
- Le texte légal : faire relire par la personne de T9 les libellés Art. 8(1)(a)/(b) contre EUR-Lex avant la démo.

#### Plus tard (phase 2)

- Route `POST /api/incidents/{id}/resolve` (humaine) et statut `resolved` ; rapports intermédiaire et final (templates, délais en mois calendaire).
- Critères 9(1) contreparties et nombre de transactions alimentés par de vraies données ; détection des incidents récurrents (RTS Art. 16).
- Ancrage de l'empreinte de l'incident dans `EvidenceRegistry` (`kind = "incident"`), export S3 du rapport.
- Statuts réels SNS, S3, EC2 (sondes) ; historique des statuts des dépendances.
- `FULL_EXIT` compté dans `saved_usd` ; corrélation de plusieurs incidents simultanés.

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T5 (incident et DORA) du fichier TASKS.md à la racine du repo.
1. Lis les sections 1 et 2 de TASKS.md, puis la section T5 en entier, puis backend/models.py,
   backend/settings.py et fixtures/snapshots_attack.jsonl (quelques lignes).
2. Ne modifie QUE : backend/incidents.py, backend/dora.py, backend/llm.py,
   backend/config/dora_profile.yaml, backend/config/dependencies.yaml,
   backend/api/incidents.py, mk/t5.mk, backend/tests/test_t5_*.py.
   Tout autre changement (models.py, main.py, response.py, fixtures, contrat) : n'édite pas,
   écris la demande dans docs/contract-requests.md et préviens-moi.
3. Commence par backend/tests/test_t5_factories.py puis les tests T5-01 à T5-27 (ils doivent
   échouer), ensuite dora.py, llm.py, incidents.py, api/incidents.py, dans cet ordre.
4. Pas de dépendance aux autres tâches : décisions et alertes construites à la main selon 2.8,
   FakeStore si backend/store.py manque, BEDROCK_MODEL_ID vide, aucun appel réseau dans les tests.
5. Ne modifie jamais une Decision. Montants en unités de base (int), dates UTC ISO avec Z.
6. Avant chaque commit : make test-t5 vert. Commits petits, préfixe "t5:", push fréquent après chaque test vert.
```

**Contrat.** Les trois champs optionnels de l'Art. 9(1) (`counterparts_affected_pct`, `transactions_affected_count_pct`, `relevant_clients_affected`) sont désormais dans `DoraCriteria` (2.6) ; aucune demande de contrat en attente pour T5.


---


### T6 · Dashboard

**Objectif.** Construire le dashboard web (dossier `frontend/`) qui montre au jury, en un coup d'œil et en anglais simple : l'état de la trésorerie et des marchés, les alertes R1..R5 et les décisions prises (avec leurs transactions), l'incident et la déclaration DORA pré-remplie, la preuve vérifiable de chaque décision, le registre des tiers, les métriques d'évaluation et un panneau de démo (lancer l'attaque, réinitialiser). Le front ne calcule **aucune** règle de détection : il affiche ce que l'API renvoie (section 2.9), en interrogeant le backend toutes les 2 s.

**Dépend de.**
- T0 → `frontend/src/types.ts` (miroir de `models.py`, possédé par T0), `fixtures/*.json` (réponses d'API), squelette backend qui sert déjà toutes les routes avec `USE_FIXTURES=true`, `Makefile` racine qui inclut `mk/*.mk` → **maquette** : mode `VITE_USE_FIXTURES=true` (le front importe directement `fixtures/*.json`, aucun backend nécessaire), puis `make backend` (squelette T0).
- T3 → `GET /api/health`, `/api/state`, `/api/series`, `/api/alerts` → maquette : `health.json`, `state.json`, `series.json`, `alerts.json`.
- T4 → `GET /api/decisions`, `POST /api/decisions/{id}/approve`, `POST /api/verify/{decision_id}` → maquette : `decisions.json`, `verify.json`, et l'approbation simulée en mémoire (étape 3).
- T5 → `GET /api/incidents`, `/api/incidents/{id}`, `/api/incidents/{id}/report.md`, `POST /api/incidents/{id}/submit`, `GET /api/dependencies` → maquette : `incident.json`, `dependencies.json`, soumission simulée en mémoire.
- T2 → `POST /api/demo/attack`, `POST /api/demo/reset`, `GET /api/demo/runs/{run_id}` → maquette : `demo_run.json`.
- T7 → `GET /api/metrics` → maquette : `metrics.json`.

**Débloque.** T9 (captures d'écran, vidéo, script de démo), T8 (sert le build statique `frontend/dist/` sur EC2), le jury (c'est ce qu'il voit).

**Fichiers possédés.**
- `frontend/` en entier **sauf** `frontend/src/types.ts` : `package.json`, `package-lock.json`, `index.html`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.js`, `postcss.config.js`, `.env.example`, `src/main.tsx`, `src/App.tsx`, `src/index.css`, `src/api.ts`, `src/fixtureDb.ts`, `src/hooks/usePolling.ts`, `src/hooks/useNow.ts`, `src/lib/format.ts`, `src/lib/labels.ts`, `src/lib/chart.ts`, `src/components/*.tsx`, `src/pages/*.tsx`, `src/test/setup.ts`, `src/**/*.test.ts(x)`.
- `mk/t6.mk`.
- **Pas à T6** : `frontend/src/types.ts` appartient à **T0** (miroir de `models.py`, mis à jour par le processus 2.12). T6 l'importe et ne le modifie jamais. S'il manque ou s'il diverge de `models.py`, T6 écrit une demande dans `docs/contract-requests.md` et, en attendant, n'utilise une copie locale (`src/test/types.local.ts`) **que dans les tests** ; le code applicatif importe toujours `src/types.ts`.

**À lire avant de commencer.** TASKS.md sections 1 (surtout 1.2 scénario et 1.5 propriété), 2.5 (conventions), 2.6 (modèles et définitions de `totals`, `risk_level`, `EvalMetrics.synthetic`), 2.7 (règles R1..R5 et seuils), 2.8 (matrice, actions `pending_approval`), 2.9 (routes et codes d'erreur), 2.12 ; `backend/models.py` ; `frontend/src/types.ts` (T0) ; `fixtures/state.json`, `fixtures/series.json`, `fixtures/verify.json`, `fixtures/demo_run.json`.
Attention : `alerts.json`, `decisions.json`, `incident.json`, `state.json`, `series.json` sont **périmées** (anciens ids `D1..D7`, seul le WETH retiré) et seront régénérées pour suivre 2.7/2.8 (alerte R1 et décision `DEC-fuji-45201812-1` au bloc 45 201 812, tout rapatrié). Le code ne doit dépendre ni des anciens ids ni du nombre exact de positions : les tests utilisent soit des invariants du scénario, soit des valeurs lues dans la fixture, soit des objets écrits dans le test.

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| `GET /api/health` | `Health` | T3 | `fixtures/health.json` |
| `GET /api/state` | `StateResponse` (totals : `value_usd`, `withdrawable_usd`, `idle_usd`, `at_risk_usd`, définis en 2.6) ; **503** `{"detail":"no snapshot yet"}` tant que le moteur n'a lu aucun bloc | T3 | `fixtures/state.json` |
| `GET /api/series?deployment_id=&asset=&limit=300` | `SeriesPoint[]` chronologique | T3 | `fixtures/series.json` (objet indexé `"<deployment_id>:<asset>"` → `SeriesPoint[]` ; accepter aussi un tableau brut) |
| `GET /api/alerts?since_block=0` | `Alert[]` plus récentes d'abord | T3 | `fixtures/alerts.json` |
| `GET /api/decisions` | `Decision[]` plus récentes d'abord | T4 | `fixtures/decisions.json` |
| `POST /api/decisions/{id}/approve` | corps `{"action_index": int, "approver": str, "approve": bool}` → `Decision` | T4 | `fixtureDb.approve()` en mémoire |
| `POST /api/verify/{decision_id}` | `VerifyResult` | T4 | `fixtures/verify.json` |
| `GET /api/incidents`, `/api/incidents/{id}` | `Incident[]`, `Incident` | T5 | `fixtures/incident.json` (objet unique, à envelopper en liste) |
| `GET /api/incidents/{id}/report.md` | texte markdown | T5 | `incident.dora.report_markdown` |
| `POST /api/incidents/{id}/submit` | corps `{"submitted_by": str}` → `Incident` | T5 | `fixtureDb.submit()` en mémoire |
| `GET /api/dependencies` | `Dependency[]` | T5 | `fixtures/dependencies.json` |
| `POST /api/demo/attack` (corps `{"seed": int, "variant": "default" \| "slow" \| "usdc"}`), `POST /api/demo/reset`, `GET /api/demo/runs/{run_id}` | `DemoRun` ; 409 si un run est déjà en cours | T2 | `fixtures/demo_run.json` (seed et variant remplacés par ceux envoyés) |
| `GET /api/metrics` | `EvalMetrics` (`*_rate` de 0 à 1, `*_pct_*` de 0 à 100, `ttd_blocks_*` = -1 si rien détecté) | T7 | `fixtures/metrics.json` |
| `EXPLORER_URL` (`.env` racine) | URL, défaut `https://testnet.snowtrace.io` | T0 (2.1) | valeur par défaut |
| `VITE_API_URL`, `VITE_USE_FIXTURES` (`frontend/.env`) | URL ; absente → `http://localhost:8000` en dev, `''` en build de production (appels relatifs `/api/...` sur la même origine, nginx de T8 sert le front et l'API) ; `"true"`/`"false"` (défaut `false`) | T6 | `frontend/.env.example` livré avec `VITE_USE_FIXTURES=true` |
| `frontend/src/types.ts` | types TS miroir de `models.py` | T0 | copie locale dans les tests seulement (voir « Fichiers possédés ») |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| Application de dev | `make frontend` → `http://localhost:5173` | tous, T9 (démo) |
| Build statique | `make frontend-build` → `frontend/dist/` (HTML + JS + CSS, aucun secret) | T8 (sert `dist/` sur EC2 avec nginx, même origine que `/api` : `VITE_API_URL` laissée vide au build) |
| Routes du front | `/` Overview, `/charts`, `/alerts`, `/incident`, `/evidence`, `/dependencies`, `/metrics`, `/demo` | T9 (vidéo, captures, liens dans le README) |
| Appels HTTP | exactement ceux de 2.9 ; en écriture seulement : approve, verify, submit, demo attack/reset | T4, T5, T2 |
| `make test-t6` | code de sortie 0 si typecheck, build et vitest passent (dans cet ordre) | T0 (`make test`), T8 (CI) |

#### Spécification détaillée

**1. Squelette et outillage.**
- `npm create vite@latest frontend -- --template react-ts`, puis : `react-router-dom@6`, `recharts@2`, `react-markdown@9`, `remark-gfm@4`, `tailwindcss@3 postcss autoprefixer`, en dev `vitest@1 jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event`.
- Scripts `package.json` : `"dev": "vite --port 5173"`, `"build": "vite build"`, `"typecheck": "tsc --noEmit"`, `"test": "vitest run"`, `"preview": "vite preview --port 5173"`.
- `vite.config.ts` :
  - alias `@fixtures` → `path.resolve(__dirname, '../fixtures')` ; `server.fs.allow: ['..']` (sinon Vite refuse de servir les fichiers hors de `frontend/`) ;
  - `const rootEnv = loadEnv(mode, path.resolve(__dirname, '..'), '')` puis `define: { __EXPLORER_URL__: JSON.stringify(rootEnv.EXPLORER_URL || 'https://testnet.snowtrace.io') }`. On n'injecte **que** cette variable : le `.env` racine contient des clés privées ;
  - `test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', globals: true }` ;
  - option (dev seulement) : `server.proxy: { '/api': 'http://localhost:8000' }`, qui permet de lancer le front avec `VITE_API_URL=` (vide) et des appels relatifs, comme en production. Par défaut on n'en dépend pas : en dev, `API_URL` vaut `http://localhost:8000` (CORS `*`).
- `tsconfig.json` : `strict: true`, `resolveJsonModule: true`, `paths: { "@fixtures/*": ["../fixtures/*"] }`, `src/vite-env.d.ts` déclare `declare const __EXPLORER_URL__: string` et `ImportMetaEnv { VITE_API_URL?: string; VITE_USE_FIXTURES?: string }`.
- `src/test/setup.ts` : `import '@testing-library/jest-dom/vitest'`, polyfill `ResizeObserver` (classe vide), `afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); })`.
- `frontend/.env.example` : `VITE_API_URL=http://localhost:8000` (commentaire : « laisser vide en production : même origine, nginx sert `/api` ») et `VITE_USE_FIXTURES=true`.
- `mk/t6.mk` (syntaxe `cible: ; commande`, pas de tabulation à gérer ; ne redéfinit jamais `NETWORK`, qui vient du `Makefile` racine) :
  ```make
  .PHONY: frontend frontend-build test-t6
  frontend:        ; cd frontend && npm run dev
  frontend-build:  ; cd frontend && npm ci && npm run build
  test-t6:         ; cd frontend && npm run typecheck && npm run build && npm run test
  ```

**2. `src/types.ts` (fichier de T0, lu par T6).** T6 ne crée ni ne modifie ce fichier : il l'importe partout (`import type { StateResponse } from '../types'`). Ce qu'on peut en attendre, pour le lire et pour écrire la copie locale de test si T0 ne l'a pas encore livré. Règles de traduction utilisées par T0 : `str` → `string` ; `int`/`float` → `number` ; `datetime` → `string` (ISO 8601) ; `Optional[X] = None` → `x: X | null` (pydantic sérialise `None` en `null`, la clé est toujours présente, jamais d'`exclude_none`, 2.5) ; champ avec défaut → champ **obligatoire** côté TS (toujours présent dans le JSON) ; `Literal[...]` → union de chaînes ; `dict[str, X]` → `Record<string, X>`. Exemples :
```ts
export type Severity = 'info' | 'warning' | 'high' | 'critical';
export type Network = 'local' | 'fuji' | 'replay';
export type ActionType = 'NOTIFY' | 'PAUSE_DEPOSITS' | 'EMERGENCY_WITHDRAW' | 'FULL_EXIT' | 'UNPAUSE_DEPOSITS' | 'OPEN_INCIDENT';
export type ActionStatus = 'planned' | 'executed' | 'failed' | 'skipped' | 'pending_approval' | 'approved' | 'rejected';
export interface Action { type: ActionType; mode: 'auto' | 'human'; status: ActionStatus;
  params: Record<string, string | number | boolean | string[]>; tx_hash: string | null; amount: string | null;
  executed_at: string | null; note: string | null; }
export interface StateResponse { network: Network; chain_id: number; block_number: number; block_time: string;
  updated_at: string; risk_level: Severity; open_incident_id: string | null; vault: VaultStatus;
  positions: PositionSnapshot[]; reserves: ReserveSnapshot[]; tokens: TokenSnapshot[]; totals: Record<string, number>; }
```
Tous les modèles de 2.6 y figurent, plus `Health`, `SeriesPoint`, `DemoRun`, `EvalMetrics`, `Dependency`, `DoraAssessment`, `DoraCriteria` (avec les trois champs de l'art. 9(1) ajoutés en 2.6 : `counterparts_affected_pct`, `transactions_affected_count_pct`, `relevant_clients_affected`), `DoraDeadlines`, `TimelineEvent`, `VerifyResult`. `rule_id` reste `string` (le Python dit `str`) ; les libellés R1..R5 vivent dans `lib/labels.ts`. Si `src/types.ts` manque ou diverge des fixtures (T6-15 rouge) : demande dans `docs/contract-requests.md`, jamais d'édition directe.

**3. Client API `src/api.ts` et maquette `src/fixtureDb.ts`.**
```ts
export const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');
// production : '' → fetch('/api/...') relatif, même origine (nginx de T8 sert dist/ et /api)
export function isFixtureMode(): boolean { return import.meta.env.VITE_USE_FIXTURES === 'true'; } // lu à chaque appel (testable avec vi.stubEnv)
export class ApiError extends Error { constructor(public status: number, public detail: string) { super(`${status}: ${detail}`); } }
export const api = {
  health(): Promise<Health>; state(): Promise<StateResponse>;
  series(deploymentId: string, asset: string, limit = 300): Promise<SeriesPoint[]>;
  alerts(sinceBlock = 0): Promise<Alert[]>; decisions(): Promise<Decision[]>;
  approve(decisionId: string, body: { action_index: number; approver: string; approve: boolean }): Promise<Decision>;
  verify(decisionId: string): Promise<VerifyResult>;
  incidents(): Promise<Incident[]>; incident(id: string): Promise<Incident>; incidentReport(id: string): Promise<string>;
  submitIncident(id: string, submittedBy: string): Promise<Incident>;
  dependencies(): Promise<Dependency[]>; metrics(): Promise<EvalMetrics>;
  demoAttack(seed: number, variant: DemoVariant = 'default'): Promise<DemoRun>; demoReset(): Promise<DemoRun>; demoRun(runId: string): Promise<DemoRun>;
};
export type DemoVariant = 'default' | 'slow' | 'usdc';
export function isNoSnapshotYet(e: unknown): boolean { return e instanceof ApiError && e.status === 503; }
```
- Mode réel : `fetch(\`${API_URL}/api/...\`)`, paramètres via `URLSearchParams` (ordre : `deployment_id`, `asset`, `limit`), POST avec `headers: {'Content-Type': 'application/json'}` et `body: JSON.stringify(...)` (`verify` et `demoReset` : POST sans corps). Statut non 2xx → `throw new ApiError(status, json.detail ?? statusText)`. `incidentReport` lit `res.text()`.
- Codes d'erreur de 2.9 et affichage : **503** `no snapshot yet` → état « Waiting for first block » (voir 7 et 8, ce n'est pas une panne) ; **409** → message tel quel (« action is not pending approval », « a demo run is already running », « incident already submitted ») et `refresh()` ; **400** / **404** / **422** → message rouge avec `detail`. Les tests vitest tournent avec `import.meta.env.DEV === true`, donc `API_URL` y vaut `http://localhost:8000`.
- Mode fixtures : chaque fonction délègue à `fixtureDb` qui charge les JSON par `import('@fixtures/state.json')` (import dynamique : les fixtures ne sont pas embarquées dans le build réel), fait une copie profonde (`structuredClone`) au premier accès, et la garde en mémoire. Cast `as unknown as T` (les JSON importés ont des types `string` larges). Comportements simulés :
  - `series(dep, asset)` : `data[\`${dep}:${asset}\`] ?? []` si l'objet est indexé, le tableau tel quel sinon, puis `slice(-limit)` ;
  - `approve(id, body)` : action `body.action_index` → `status = body.approve ? 'executed' : 'rejected'`, `note = (body.approve ? 'approved by ' : 'rejected by ') + body.approver` ; renvoie la décision ; id inconnu → `ApiError(404, 'decision not found')` ;
  - `verify(id)` : `{...verify.json, decision_id: id}` ;
  - `incidents()` : `[incident.json]` ; `submitIncident` : `dora.submitted = true`, `submitted_by`, `submitted_at = new Date().toISOString()` ;
  - `demoAttack(seed, variant)` : `{...demo_run.json, seed, variant, run_id: \`RUN-<yyyymmddHHMMSS>-attack-${seed}\`, status: 'running'}` ; `demoReset` : même chose avec `kind: 'reset'`, `status: 'done'`.
  - Aucun `fetch` n'est appelé en mode fixtures (test T6-14).

**4. Hook de polling `src/hooks/usePolling.ts`.**
```ts
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs = 2000, deps: unknown[] = []):
  { data: T | undefined; error: Error | undefined; loading: boolean; lastUpdated: number | undefined; refresh: () => Promise<void> }
```
Algorithme : appel immédiat au montage, puis **chaîne de `setTimeout`** (le prochain appel est programmé quand le précédent est terminé, jamais deux requêtes en vol) ; en erreur, on garde le dernier `data` et on remplit `error` ; un succès vide `error` ; `refresh()` lance un appel tout de suite (utilisé après approve/submit/verify) ; au démontage et au changement de `deps` : `clearTimeout` + flag `cancelled` (le StrictMode de React 18 monte deux fois en dev). Intervalles : 2 000 ms pour health, state, alerts, decisions, series, incidents, demo run ; 30 000 ms pour dependencies et metrics.
`src/hooks/useNow.ts` : `useNow(tickMs = 1000): number` (Date.now() rafraîchi), pour les comptes à rebours.
Un `DashboardDataProvider` (contexte React dans `App.tsx`) poll une seule fois `health`, `state`, `alerts`, `decisions` et les partage (en-tête, Overview, Charts, Alerts, Evidence) ; les autres pages pollent leurs propres routes.

**5. Formatage `src/lib/format.ts` (fonctions pures, testées en T6-03).**
- `formatUsd(n: number): string` → `Intl.NumberFormat('en-US', {style:'currency', currency:'USD', maximumFractionDigits: 0})` : `1325000` → `"$1,325,000"`.
- `formatUnits(base: string, decimals: number, maxFrac = 2): string` avec **BigInt** (jamais `Number` sur un montant en unités de base) : `("1850000000000000000000", 18)` → `"1,850"` ; `("400000000000", 6)` → `"400,000"` ; `("1500000000000000000", 18)` → `"1.5"` ; `("0", 18)` → `"0"`.
- `unitsToNumber(base: string, decimals: number): number` pour les graphiques uniquement (précision 2 décimales).
- `formatBpsPct(bps: number): string` → `(Math.round(bps / 10) / 10).toFixed(1) + '%'` : `1935` → `"19.4%"`, `10000` → `"100.0%"`, `6714` → `"67.1%"`.
- `withdrawableTone(bps): 'ok' | 'warn' | 'bad'` : `≥ 8000` ok, `5000..7999` warn, `< 5000` bad (seuils de R4). `utilizationTone(bps)` : `< 9000` ok, `9000..9799` warn, `≥ 9800` bad (seuils de R3). `backingTone(bps)` : `≥ 9900` ok, sinon bad (R1).
- `shortHash(h)` → `"0x433c…74cc"` (6 premiers + `…` + 4 derniers caractères).
- `formatCountdown(dueIso: string, nowMs: number): string` : `"4 h 00 min left"`, `"2 d 3 h left"` au-delà de 48 h, `"overdue by 1 h 05 min"` si dépassé.
- `formatUtc(iso)` → `"2026-10-11 08:00:27 UTC"` (toujours afficher UTC, explicitement).
- `tones` → classes Tailwind : ok `bg-green-600`, warn `bg-amber-500`, bad `bg-red-600` ; gravités : info `bg-slate-500`, warning `bg-amber-500`, high `bg-orange-600`, critical `bg-red-600` (texte blanc, mot écrit en majuscules : la couleur n'est jamais la seule information).

**6. Libellés `src/lib/labels.ts`.** `RULE_LABELS` : `R1_BRIDGE_INVARIANT` "Bridge invariant broken", `R2_COLLATERAL_SURGE` "Suspicious collateral surge", `R3_LIQUIDITY_DRAIN` "Market liquidity drain", `R4_EXITABILITY_DROP` "Treasury exitability drop", `R5_CONTAINMENT` "Containment activated" ; repli sur l'id brut. `ACTION_LABELS` : NOTIFY "Notify the team", PAUSE_DEPOSITS "Pause new deposits", EMERGENCY_WITHDRAW "Emergency withdrawal to the vault", FULL_EXIT "Full exit", UNPAUSE_DEPOSITS "Resume deposits", OPEN_INCIDENT "Open incident". `DEPLOYMENT_LABELS` : `lend-eth` "Lending protocol (Ethereum deployment)", `lend-avax` "Lending protocol (Avalanche deployment)".

**7. Mise en page (`App.tsx`, `components/Layout.tsx`).** Barre latérale avec les 8 routes ; badge du nombre d'actions `pending_approval` sur "Alerts & decisions". En-tête : réseau (`FUJI`/`LOCAL`), bloc courant, point vert/rouge `rpc_ok`, `engine_running`, "Updated 2 s ago" (depuis `lastUpdated`), champ "Operator name" (stocké dans `localStorage['sh.operator']`, défaut `dashboard-operator`, lecture/écriture dans un `try/catch`), utilisé comme `approver` et `submitted_by`. Bandeau jaune `FIXTURE MODE: data from fixtures/, no backend` si `isFixtureMode()`. Bandeau gris `Waiting for first block: the monitoring engine has not read the chain yet` si le polling de `state` renvoie 503 (`isNoSnapshotYet`) : ce n'est pas une panne, le polling continue et le bandeau disparaît au premier snapshot. Bandeau rouge `Backend unreachable: showing last data from block N` si le polling de `state` est en erreur pour toute autre raison (réseau, 5xx autre que 503). Bandeau ambre `Data is stale` si `now - updated_at > 15 s` (désactivé en mode fixtures).
Lisibilité jury : chiffres clés en `text-4xl font-bold tabular-nums`, texte de base 16 px, contraste AA, barres avec `role="progressbar"` et `aria-valuenow`, focus clavier visible, pas d'abréviations (pas de "bps" à l'écran : tout en %).

**8. Page Overview (`/`, `pages/Overview.tsx`).**
- Tant que `state` n'a jamais été reçu et que l'erreur est un 503 : un seul encadré `data-testid="waiting-first-block"` avec « Waiting for first block » et un indicateur d'attente, à la place des cartes (pas de `$0` trompeur). Même règle pour Charts, Alerts et Evidence, qui dépendent de `state`.
- 4 cartes (data-testid `total-value`, `total-withdrawable`, `total-idle`, `total-at-risk`) : "Total treasury value", "Withdrawable now", "Back in the vault (idle)", "At risk" ← `state.totals.value_usd`, `withdrawable_usd`, `idle_usd`, `at_risk_usd`, avec `formatUsd`. "At risk" en rouge si > 0. Le front ne recalcule rien : les définitions sont celles de 2.6 (`value_usd` = positions + idle ; `at_risk_usd` = Σ (value − withdrawable) des positions) ; info-bulle courte sous chaque carte reprenant cette définition en anglais.
- Badge de risque (`data-testid="risk-badge"`) : `state.risk_level` en majuscules (`CRITICAL`) avec la couleur de gravité ; sous-titre « Highest severity of conditions still true at block N » (2.6 : une alerte dont la condition a disparu ne compte plus, donc `INFO` est normal après retour au calme) ; lien vers l'incident si `open_incident_id`.
- Statut du coffre (`data-testid="vault-status"`) : "Deposits PAUSED" (rouge) ou "Deposits open" (vert) selon `vault.deposits_paused` ; soldes `idle_balances` en unités lisibles (décimales prises dans `state.tokens` par symbole).
- Carte couverture rsETH (`data-testid="backing-card"`) : jeton avec `backing_ratio_bps !== null` ; grand chiffre `formatBpsPct` (`19.4%`), ton `backingTone`, sous-titre `"1,200 WETH backing for 6,200 rsETH supply"` (`formatUnits(backing)` et `formatUnits(total_supply)`).
- Tableau des positions (une ligne `data-testid="position-row"` par position avec `supplied !== "0"`) : déploiement, actif, "Supplied" (`formatUnits` avec les décimales de la réserve correspondante), "Value" (`value_usd`), "Withdrawable now" + barre de `withdrawable_ratio_bps` (`data-tone` = `withdrawableTone`). Liste vide → message `"No open positions: all funds are back in the vault."` (cas attendu après régénération des fixtures, où toutes les positions sont retirées).
- Tableau des réserves (une ligne `data-testid="reserve-row"` par entrée de `state.reserves`, groupées par déploiement) : actif, rôle (`borrowable` et `ltv_bps > 0` → "Lending + collateral, LTV 80.0%" pour USDC et WETH ; `ltv_bps > 0` seul → "Collateral only, LTV 75.0%" pour rsETH ; `borrowable` seul → "Lending"), "Collateral deposited" (`total_collateral`, solde séparé de la liquidité prêtable, 2.2), "Utilization" (barre, `utilizationTone`), "Available liquidity" (unités + valeur USD = `unitsToNumber × price_usd`), "Supply APY", "Borrow APY", badges `FROZEN` / `PAUSED`.

**9. Page Charts (`/charts`, `pages/Charts.tsx`, `lib/chart.ts`).**
- Sélecteur de réserve : réserves `borrowable` de `state.reserves`, valeur `"<deployment_id>:<asset>"`, défaut `lend-eth:WETH` ; mémorisé dans l'URL (`?reserve=lend-eth:WETH`).
- `toChartPoints(points: SeriesPoint[], decimals: number)` → `{block, utilization, liquidity, withdrawable, apy, backing}` en % ou en unités (`null` conservé, `connectNulls={false}` : la courbe "withdrawable" s'arrête quand la position est retirée, avec la mention "position closed").
- 5 graphiques (`data-testid="chart-utilization" | "chart-liquidity" | "chart-withdrawable" | "chart-apy" | "chart-backing"`), `XAxis type="number" dataKey="block" domain={['dataMin','dataMax']}`, lignes de seuil horizontales pointillées : utilization 90 % et 98 %, withdrawable 80 % et 50 %, backing 99 %.
- Marqueurs d'alertes : `alertsForReserve(alerts, dep, asset, minBlock, maxBlock): Alert[]` = alertes dont `deployment_id === null` (globales, ex. R1) **ou** `deployment_id === dep`, et dont `block_number` est dans `[minBlock, maxBlock]` de la série. Chaque alerte donne une `ReferenceLine x={block_number}` avec `className="alert-marker"`, couleur de gravité, étiquette `R1`..`R5` (préfixe de `rule_id`) ; trait plein si `asset === asset` sélectionné, pointillé sinon. Sous les graphiques, liste "Events on this chart" (un `li data-testid="alert-marker-item"` par alerte : bloc, gravité, titre).

**10. Page Alerts & decisions (`/alerts`, `pages/Alerts.tsx`).**
- Flux unique : alertes et décisions triées par `block_number` décroissant ; à bloc égal, la décision au-dessus de ses alertes.
- Carte alerte (`data-testid="alert-card"`) : badge de gravité, `RULE_LABELS[rule_id]`, `title`, `explanation` (en entier, police normale), déploiement/actif, bloc et `formatUtc(block_time)`, "Exposure" `formatUsd(exposure_usd)`.
- Carte décision (`data-testid="decision-card"`) : gravité, `rationale`, `matrix_cell` en petit, "Exposure" et "Withdrawable", tableau des actions : libellé, badge `AUTO` / `HUMAN`, statut, montant (`formatUnits(amount, décimales de params.asset)`), lien de transaction `TxLink`.
- `components/TxLink.tsx` : `href = \`${__EXPLORER_URL__}/tx/${hash}\``, `target="_blank" rel="noreferrer"`, texte `shortHash(hash)` ; si `state.network === 'local'`, hash court sans lien (title "local chain: no explorer").
- Pour chaque action `pending_approval` : boutons **Approve** et **Reject** (`data-testid="approve-<decisionId>-<index>"`, `reject-…`) → `api.approve(decision.id, {action_index: index, approver: operatorName, approve: true|false})` ; boutons désactivés pendant la requête ; succès → `refresh()` des décisions ; `ApiError` → message rouge avec `detail`.

**11. Page Incident & DORA (`/incident`, `pages/Incident.tsx`).**
- Incident affiché : `state.open_incident_id` sinon le plus récent de `api.incidents()` ; aucun → "No incident so far.".
- En-tête : `title`, badge statut (`open` rouge, `contained` ambre, `resolved` vert), gravité, "Saved" `formatUsd(saved_usd)` en grand vert, "Still at risk" `formatUsd(at_risk_usd)` en grand rouge si > 0, "Time to contain" = `contained_at - detected_at` en secondes.
- Chronologie : `timeline` triée par `at`, une ligne par événement (heure UTC, bloc, `kind` en badge, `text`, `ref` cliquable si c'est un hash).
- DORA (si `dora`) : badge `MAJOR INCIDENT` si `is_major`, `legal_basis`, puces `thresholds_met` (source officielle). Tableau des critères (données statiques `CRITERIA_ROWS` : champ, libellé, seuil affiché, ex. "Clients affected | 100.0% | > 10% (Art. 9(1)(a))" ; une ligne par champ de `DoraCriteria`, soit 14 avec les trois champs optionnels de 2.6 : `counterparts_affected_pct` "Financial counterparts affected", `transactions_affected_count_pct` "Transactions affected (count)", `relevant_clients_affected` "Relevant clients or counterparts affected"). Champ absent de la réponse (fixture ancienne) → cellule `—`, pas de crash.
- Échéances (`data-testid="deadline-initial" | "deadline-intermediate" | "deadline-final"`) : date UTC + `formatCountdown(due, useNow())`, rouge si dépassée.
- Rapport : `react-markdown` + `remark-gfm`, **sans** `rehype-raw` (le texte peut venir d'un LLM : pas de HTML brut). Encadré "AI-drafted sections, human review required: …" si `ai_drafted_sections` non vide.
- Bouton **Submit to regulator** (`data-testid="submit-incident"`) : `window.confirm`, puis `api.submitIncident(id, operatorName)` ; désactivé et remplacé par "Submitted by X at Y" si `dora.submitted`.

**12. Page Evidence (`/evidence`).** Tableau des décisions : id, bloc, gravité, `record_hash` (court), "Anchored on-chain" (`TxLink(anchor_tx)` + bloc, ou "not anchored yet"), bouton **Verify** (`data-testid="verify-<id>"`) → `api.verify(id)`. Résultat (`data-testid="verify-result"`, attribut `data-result="match" | "mismatch"`) : `MATCH` sur fond vert + "Record matches its stored fingerprint" + stored/recomputed hash ; `MISMATCH` sur fond rouge + liste `diffs`. Si `anchored` est false : mention ambre "not anchored". Ligne d'aide copiable : `make verify ID=<id>`.

**13. Page Third-party dependencies (`/dependencies`).** Titre "Third-party register (DORA Art. 28)". Tableau trié par criticité (critical, important, standard) : name, kind, provider, criticality (badge), supports (puces), fallback, status (point coloré + mot : ok, degraded, down, unknown).

**14. Page Metrics (`/metrics`).** Unités de 2.6, à ne pas confondre : les `*_rate` sont des fractions de 0 à 1 (affichées `× 100` en %), les `*_pct_*` sont **déjà** de 0 à 100 (affichés tels quels avec `%`), `ttd_blocks_p50` / `ttd_blocks_p90` valent `-1` quand rien n'est détecté. Helpers purs dans `lib/format.ts` : `formatRate(0.95) === '95.0%'`, `formatPct(87.5) === '87.5%'`, `formatTtd(-1) === 'not detected'`, `formatTtd(1) === '1 block'`, `formatTtd(3) === '3 blocks'`. Cartes : "Detection rate" (`formatRate(detection_rate)`), "False positive rate" (`formatRate`), "Time to detect" p50/p90 (`formatTtd`), "Saved with us" vs "Saved without us" (`formatPct(saved_pct_mean)` et `formatPct(baseline_saved_pct_mean)`, petit `BarChart` à 2 barres sur une échelle 0..100), "Runs" (`runs_attack` / `runs_normal`). `mainnet_replay === null` → carte "Mainnet replay: phase 2". `notes` en liste, `rules_version` court. `runs_attack === 0` → bandeau "No evaluation run yet (fixture values)". Les clés de `synthetic` sont lues avec repli (`?? '—'`) : pas de crash si T7 en ajoute ou en retire.

**15. Page Demo (`/demo`).**
- Sélecteur "Variant" (`data-testid="variant-select"`) : `default` "Default attack (fast drain)", `slow` "Slow drain", `usdc` "USDC market drained" ; défaut `default`.
- Champ "Seed" facultatif (entier de 0 à 999999 ; `0` = paramètres par défaut, sans hasard, utile pour une démo reproductible ; hors bornes → message de validation, pas d'envoi).
- Bouton **Launch attack** (`data-testid="launch-attack"`) : si le champ est vide, `seed = Math.floor(Math.random() * 999_999) + 1` (entier dans [1, 999999]) ; le front envoie **toujours** un entier, jamais `null` ; afficher `Seed <n>` **avant** l'envoi ; `api.demoAttack(seed, variant)` ; puis polling `api.demoRun(run_id)` toutes les 2 s tant que `status === 'running'`. Afficher le `seed` et le `variant` **renvoyés** par le backend (ils font foi). 409 « run already running » → message ambre et reprise du polling du run en cours si son id est connu.
- Bouton **Reset** (`data-testid="reset-demo"`) : `window.confirm('Redeploy contracts and clear all alerts?')` puis `api.demoReset()`.
- Panneau du run : `run_id`, `kind`, `status` (badge), `params`, `log` en monospace, défilement automatique vers la dernière ligne. En mode fixtures : mention "Fixture mode: nothing happens on chain".

#### Tests qui doivent passer

Commande globale : `make test-t6`. Les tests de composants rendent la page dans un `MemoryRouter` ; le réseau est simulé avec `vi.stubGlobal('fetch', vi.fn(...))` qui renvoie `new Response(JSON.stringify(x), {status: 200})` ; le mode est choisi avec `vi.stubEnv('VITE_USE_FIXTURES', 'true' | 'false')`. Recharts ne dessine rien sous jsdom sans taille : dans les tests de graphiques, `vi.mock('recharts', ...)` remplace `ResponsiveContainer` par un rendu à `width=800 height=240` (cloneElement de l'enfant).

- **T6-01 · typecheck.** `cd frontend && npm run typecheck` → code 0, aucune erreur.
- **T6-02 · build.** `cd frontend && npm run build` → code 0, `frontend/dist/index.html` existe ; `grep -rE "_PK|PRIVATE" frontend/dist` ne trouve rien.
- **T6-03 · formatage** (`src/lib/format.test.ts`) : `formatUsd(1325000) === '$1,325,000'`, `formatUsd(0) === '$0'` ; `formatUnits('1850000000000000000000', 18) === '1,850'`, `formatUnits('400000000000', 6) === '400,000'`, `formatUnits('1500000000000000000', 18) === '1.5'` ; `formatBpsPct(1935) === '19.4%'`, `formatBpsPct(10000) === '100.0%'` ; `withdrawableTone(8000) === 'ok'`, `(7999) === 'warn'`, `(5000) === 'warn'`, `(4999) === 'bad'` ; `utilizationTone(9800) === 'bad'` ; `shortHash('0x433c5ce05750d9c9189b632954beb23cccdbf172c5556778a026ccf10a6f74cc') === '0x433c…74cc'` ; `formatCountdown('2026-10-11T12:02:27Z', Date.parse('2026-10-11T08:02:27Z')) === '4 h 00 min left'` ; `formatCountdown('2026-10-11T07:00:00Z', Date.parse('2026-10-11T08:05:00Z')) === 'overdue by 1 h 05 min'` ; `formatRate(0.95) === '95.0%'`, `formatRate(0) === '0.0%'` ; `formatPct(87.5) === '87.5%'` ; `formatTtd(-1) === 'not detected'`, `formatTtd(3) === '3 blocks'`.
- **T6-04 · polling** (`src/hooks/usePolling.test.ts`, `vi.useFakeTimers()`, `renderHook`) : `test_calls_immediately_then_every_2s` → 1 appel au montage, 3 après `await vi.advanceTimersByTimeAsync(4000)` ; `test_no_overlap` → fetcher qui ne se résout jamais : 1 seul appel après 10 s ; `test_keeps_data_on_error` → succès `{a:1}` puis rejet : `data` reste `{a:1}`, `error` défini ; `test_stops_on_unmount` → 0 appel après démontage.
- **T6-05 · client API** (`src/api.test.ts`) : `test_fixture_mode_no_fetch` → `VITE_USE_FIXTURES=true`, `await api.state()` renvoie `block_number` égal à celui de `fixtures/state.json`, `fetch` jamais appelé ; `test_series_url` → mode réel, `api.series('lend-eth', 'WETH', 300)` appelle `http://localhost:8000/api/series?deployment_id=lend-eth&asset=WETH&limit=300` ; `test_404_raises` → réponse 404 `{"detail":"decision not found"}` : `api.verify('X')` rejette avec `ApiError` (`status 404`, `detail 'decision not found'`) ; `test_fixture_series_key` → mode fixtures, `api.series('lend-eth','WETH')` renvoie 41 points (série de `series.json`, `limit` 300) ; `test_503_no_snapshot` → réponse 503 `{"detail":"no snapshot yet"}` : `api.state()` rejette avec `ApiError` status 503 et `isNoSnapshotYet(err) === true` ; `test_demo_attack_body` → `api.demoAttack(7, 'slow')` poste exactement `{"seed":7,"variant":"slow"}`.
- **T6-06 · Overview depuis les fixtures** (`src/pages/Overview.test.tsx`, mode fixtures) : `total-value` contient `$1,325,000` (invariant 2.2 : 250 WETH × 2 500 $ + 700 000 USDC) ; `total-withdrawable`, `total-idle`, `total-at-risk` contiennent `formatUsd()` des valeurs lues dans `fixtures/state.json` ; `risk-badge` a le texte `CRITICAL` ; `vault-status` contient `PAUSED` ; `backing-card` contient `19.4%` (1 200 / 6 200) ; nombre de `reserve-row` = 6 ; nombre de `position-row` = nombre de positions de la fixture avec `supplied !== "0"`.
- **T6-07 · Overview sans position et en attente** : fetch simulé renvoyant `state.json` avec `positions: []` → texte `No open positions: all funds are back in the vault.` et 0 `position-row` ; `test_waiting_first_block` → fetch de `/api/state` renvoyant 503 `{"detail":"no snapshot yet"}` : `waiting-first-block` visible avec le texte `Waiting for first block`, aucune carte `total-value`, pas de bandeau `Backend unreachable`.
- **T6-08 · couleurs de la barre retirable** : état inline avec 3 positions à `withdrawable_ratio_bps` 10000, 7000, 4000 → barres avec `data-tone` `ok`, `warn`, `bad` et `aria-valuenow` 100, 70, 40.
- **T6-09 · marqueurs d'alertes** (`src/pages/Charts.test.tsx`) : série = `series.json["lend-eth:WETH"]` (blocs 45201800 à 45201880) ; alertes inline : globale R1 au bloc 45201812 (`deployment_id: null`), R2 `lend-eth`/`WETH` à 45201835, R3 `lend-avax`/`WETH` à 45201850, R4 `lend-eth`/`WETH` à 45209999 (hors fenêtre). Attendu : `alertsForReserve(...)` renvoie 2 alertes ; 2 `alert-marker-item` ; dans `chart-utilization`, `querySelectorAll('.alert-marker').length === 2`.
- **T6-10 · flux alertes et décisions** (`src/pages/Alerts.test.tsx`) : `test_newest_first` → alertes inline aux blocs 10, 30, 20 : ordre affiché 30, 20, 10 ; `test_approve_posts_body` → `localStorage['sh.operator'] = 'jury-demo'`, décision inline `DEC-fuji-45201812-1` avec actions `[NOTIFY executed, PAUSE_DEPOSITS executed, UNPAUSE_DEPOSITS human pending_approval]`, clic sur `approve-DEC-fuji-45201812-1-2` → `fetch` appelé avec `http://localhost:8000/api/decisions/DEC-fuji-45201812-1/approve`, `method: 'POST'`, corps JSON exactement `{"action_index":2,"approver":"jury-demo","approve":true}` ; `test_reject_posts_false` → même chose avec `approve: false` ; `test_tx_link` → action avec `tx_hash` `0x8a1f…e8d7` : lien `href === 'https://testnet.snowtrace.io/tx/0x8a1f0c3d9e7b6a5f4e3d2c1b0a9f8e7d6c5b4a39281706f5e4d3c2b1a0f9e8d7'`.
- **T6-11 · Verify** (`src/pages/Evidence.test.tsx`) : `test_verify_match_from_fixture` → mode fixtures, clic sur le bouton Verify de la première décision : `verify-result` a `data-result="match"` et le texte `MATCH` ; `test_verify_mismatch` → fetch renvoie `{...verify.json, match: false, recomputed_hash: '0xdead…', diffs: ['actions[2].status: stored executed, recomputed failed']}` : `data-result="mismatch"`, texte `MISMATCH`, la ligne de diff est visible.
- **T6-12 · Incident et DORA** (`src/pages/Incident.test.tsx`, mode fixtures, `vi.setSystemTime(dora.classified_at)` de la fixture) : `deadline-initial` contient `4 h 00 min left` ; le rapport est rendu en HTML (un `h1` contenant `DORA`) ; `test_submit_posts_body` → mode réel, clic sur `submit-incident` (confirm simulé à `true`) : `POST /api/incidents/INC-20261011-001/submit` avec corps `{"submitted_by":"jury-demo"}`.
- **T6-13 · Demo** (`src/pages/Demo.test.tsx`) : `vi.spyOn(Math, 'random').mockReturnValue(0.004242)` → texte `Seed 4242` affiché (`Math.floor(0.004242 × 999999) + 1`), `POST /api/demo/attack` avec corps `{"seed":4242,"variant":"default"}`, puis `GET /api/demo/runs/<run_id renvoyé>` appelé ; les lignes de `log` de la réponse sont affichées ; `test_variant_and_seed_zero` → sélection `usdc` dans `variant-select` et champ Seed à `0` : corps exactement `{"seed":0,"variant":"usdc"}` ; `test_seed_range` → `Math.random` simulé à `0` puis à `0.9999999` : seeds envoyés `1` et `999999` (jamais `0` ni `null` quand le champ est vide) ; `test_409_running` → réponse 409 `{"detail":"demo run already running"}` : message visible, aucune exception.
- **T6-14 · mode fixtures sans backend** (`src/App.test.tsx`) : `VITE_USE_FIXTURES=true`, `fetch = vi.fn(() => Promise.reject(new Error('no backend')))`, rendu de `<App/>` sur `/` → bandeau `FIXTURE MODE` présent, `total-value` contient `$1,325,000`, `fetch` appelé 0 fois ; navigation vers les 8 routes sans exception.
- **T6-15 · conformité types/fixtures** (`src/types.contract.test.ts`) : pour `StateResponse`, `Alert`, `Decision`, `Action`, `Incident`, `VerifyResult`, `DemoRun`, `EvalMetrics`, une constante `const STATE_KEYS: Record<keyof StateResponse, true> = {...}` (le compilateur refuse une clé en trop ou manquante) ; à l'exécution, `Object.keys(fixture).sort()` égale `Object.keys(STATE_KEYS).sort()` (toutes les clés sont toujours présentes, 2.5). Les types sont importés de `src/types.ts` (T0) ; tant que T0 ne l'a pas livré, depuis la copie locale `src/test/types.local.ts` (tests uniquement), à rebasculer dès la livraison. Détecte toute dérive entre `models.py` (via les fixtures régénérées) et `types.ts` ; en cas d'échec, demande à T0 via `docs/contract-requests.md`, ne pas corriger `types.ts` soi-même.
- **T6-16 · fumée manuelle contre le squelette T0.** `make backend` (`USE_FIXTURES=true`) puis `VITE_USE_FIXTURES=false make frontend` : les 8 pages s'affichent, l'onglet réseau montre `/api/state`, `/api/alerts`, `/api/decisions`, `/api/health` toutes les 2 s, aucune erreur console, aucune erreur CORS.

#### Definition of done

- [ ] `make test-t6` vert (T6-01 à T6-15) sur une machine propre après `make setup`.
- [ ] T6-16 fait contre le squelette T0, puis refait contre le vrai backend dès que T3/T4/T5 sont livrés.
- [ ] Le code applicatif importe uniquement `src/types.ts` (livré par T0, jamais modifié par T6) ; plus aucune copie locale de types hors de `src/test/` ; toute divergence remontée dans `docs/contract-requests.md`.
- [ ] Build de production testé avec `VITE_API_URL` vide : les appels partent en relatif vers `/api/...` (même origine, nginx de T8).
- [ ] « Waiting for first block » affiché au démarrage de `make demo` tant que l'API répond 503, puis remplacé par les données sans rechargement.
- [ ] Les 8 routes existent et sont lisibles sur un projecteur 1920×1080 sans zoom ; Overview tient sans défilement horizontal.
- [ ] Aucun montant en unités de base converti en `Number` hors de `unitsToNumber` (graphiques).
- [ ] Aucun id de règle `D1..D7` dans le code ; aucun texte français dans l'UI.
- [ ] Le build ne contient aucune variable du `.env` racine sauf `EXPLORER_URL`.
- [ ] `frontend/.env.example` et `mk/t6.mk` commités ; `make frontend` et `make frontend-build` fonctionnent depuis la racine.
- [ ] Captures d'écran des 8 pages (mode fixtures) déposées dans la PR pour T9.

#### Pièges connus

- **Recharts sous jsdom** : `ResponsiveContainer` mesure 0 px et ne dessine rien. Mocker `ResponsiveContainer` dans les tests (voir plus haut) et polyfiller `ResizeObserver`.
- **Axe X catégoriel** : une `ReferenceLine x=45201811` est ignorée si 45201811 n'est pas un point de la série (les séries ont un point tous les 2 blocs). Toujours `XAxis type="number"`.
- **BigInt** : `Number("1850000000000000000000")` perd de la précision ; `formatUnits` travaille en `BigInt`. Cible ES2020 minimum dans `tsconfig`.
- **Imports JSON** : TS infère `network: string`, pas `'fuji'` ; caster `as unknown as StateResponse`. Les fixtures sont hors de `frontend/` : alias + `server.fs.allow`.
- **Fuite de secrets** : ne jamais mettre `envPrefix: ''` ni `envDir: '..'` avec un préfixe large ; seul `EXPLORER_URL` est injecté via `define`.
- **Faux timers + promesses** : utiliser `await vi.advanceTimersByTimeAsync()` (pas la version synchrone), sinon les `fetch` simulés ne se résolvent pas.
- **StrictMode** : en dev les effets tournent deux fois ; sans nettoyage du `setTimeout` on poll en double.
- **Fixtures périmées puis régénérées** : après régénération, toutes les positions sont retirées (positions vides ou `supplied: "0"`), les actions `pending_approval` changent d'index. Ne rien coder en dur sur ces valeurs ; les tests utilisent des objets inline ou les invariants (1 325 000 $, 19.4 %, `CRITICAL`).
- **Lien explorer en local** : sur anvil, snowtrace ne connaît pas les transactions ; afficher le hash sans lien quand `network === 'local'`.
- **Fuseau horaire** : afficher l'UTC explicitement ; le jury est à Paris (UTC+2), une heure locale implicite crée des incohérences avec la chronologie de l'incident.
- **Markdown du rapport** : jamais de HTML brut (`rehype-raw` interdit), le texte peut venir de Bedrock.
- **Approve puis polling** : ne pas modifier l'état local de façon optimiste, re-lire `GET /api/decisions` (sinon le polling suivant écrase l'affichage et fait clignoter le statut).
- **CORS** : l'API est en `*` (2.9) ; si une erreur CORS apparaît, c'est presque toujours une mauvaise `VITE_API_URL` (port ou `http`/`https`).
- **`VITE_API_URL` en production** : la variable est figée au build. Ne pas builder avec `http://localhost:8000` pour EC2 (le navigateur du jury appellerait sa propre machine) : la laisser vide, `API_URL` vaut alors `''` et les appels sont relatifs. Attention à `??` : une variable définie mais vide donne bien `''` (voulu), pas le défaut de dev.
- **503 au démarrage** : juste après `make demo` ou un reset, `/api/state` répond 503 `no snapshot yet` pendant quelques blocs. Ne pas l'afficher comme une panne rouge, ne pas arrêter le polling.
- **Unités des métriques** : `detection_rate` 0.95 → `95.0%` mais `saved_pct_mean` 95 → `95.0%` (pas `9500%`) ; `ttd_blocks_p50 = -1` → `not detected` (pas `-1 blocks`).
- **`risk_level` qui redescend** : il ne reflète que les conditions encore vraies au dernier snapshot ; après retrait complet il peut repasser à `INFO` alors que l'incident reste ouvert. Ne pas déduire la gravité de l'incident de `risk_level`.

#### Plus tard (phase 2)

- Server-Sent Events ou WebSocket à la place du polling ; chargement incrémental des alertes avec `since_block`.
- Graphiques supplémentaires (indicateurs de phase 2 : APY-appât, concentration des garanties, contagion entre déploiements), comparaison multi-réserves sur un même graphique.
- Plusieurs incidents simultanés, filtres et recherche dans le flux d'alertes.
- Authentification et rôles pour Approve/Submit (signature par les signataires du Safe), journal des opérateurs.
- Export PDF du rapport DORA, export CSV du registre des tiers.
- Tests de bout en bout Playwright sur `make demo`, mode sombre, version mobile, internationalisation.

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T6 (Dashboard) du fichier TASKS.md à la racine du repo.
1. Lis TASKS.md sections 1 et 2 en entier, puis la section T6 en entier, puis backend/models.py,
   frontend/src/types.ts (T0) et les fichiers fixtures/state.json, fixtures/series.json, fixtures/verify.json, fixtures/demo_run.json.
   Attention : alerts.json, decisions.json, incident.json, state.json et series.json sont périmées
   (ids D1..D7) et seront régénérées : ne code rien en dur sur leur contenu.
2. Ne modifie QUE les fichiers listés dans « Fichiers possédés » de T6 (frontend/ sauf src/types.ts,
   et mk/t6.mk ; ne redéfinis jamais NETWORK dans mk/t6.mk).
   frontend/src/types.ts appartient à T0 : ne le crée pas et ne le modifie pas. S'il manque ou diverge,
   écris la demande dans docs/contract-requests.md, préviens-moi, et en attendant utilise une copie
   locale src/test/types.local.ts uniquement dans les tests.
   Toute autre demande de changement (contrat, routes, fixtures, .env.example racine) : n'édite pas,
   écris-la dans docs/contract-requests.md et préviens-moi.
3. Travaille d'abord en mode VITE_USE_FIXTURES=true (aucun backend), puis contre le squelette T0
   (make backend, USE_FIXTURES=true). N'attends aucune autre tâche.
4. Commence par écrire les tests T6-03 à T6-15 (vitest + Testing Library) aux noms et chemins indiqués,
   puis le code, page par page dans cet ordre : format/labels, api + fixtureDb, usePolling, Layout,
   Overview, Alerts, Evidence, Incident, Charts, Demo, Dependencies, Metrics.
5. Avant chaque commit : make test-t6 doit être vert (typecheck, build, vitest). Petits commits,
   push fréquent après chaque test vert.
   Points du contrat à ne pas rater : API_URL = VITE_API_URL ?? (DEV ? 'http://localhost:8000' : '') ;
   503 "no snapshot yet" → « Waiting for first block » ; *_rate en 0..1, *_pct_* en 0..100,
   ttd -1 → "not detected" ; variants default|slow|usdc ; seed aléatoire dans [1, 999999], 0 = défauts.
6. UI en anglais simple, gros chiffres, la couleur n'est jamais la seule information.
```


---


### T7 · Évaluation et métriques (version simple)

**Objectif.** Mesurer, de façon reproductible et honnête, ce que la plateforme fait sur le scénario : est-ce qu'elle détecte l'attaque, en combien de blocs, quelle part de la trésorerie elle met à l'abri (comparée à une trésorerie passive), et est-ce qu'elle crie au loup sur une journée normale. Le banc d'essai lance N attaques et M journées normales sur la chaîne locale, lit l'API comme une boîte noire, et écrit `data/eval/metrics.json` (servi par `GET /api/metrics`, affiché par T6, cité par T9) et `data/eval/report.md`. Les métriques restent **simples** dans le MVP : 8 chiffres, définis exactement ci-dessous.

**Dépend de.**
- T1 → chaîne locale + `make deploy` + `deployments/local.json` + ABIs → en attendant : aucun besoin pour les tests unitaires ; pour l'ancrage, `--no-anchor`.
- T2 → `POST /api/demo/reset`, `POST /api/demo/attack`, `GET /api/demo/runs/{run_id}`, `make normal`, et les `RunRecord` écrits dans `data/runs/<run_id>.json` → en attendant : `RunRecord` construits à la main dans les tests (avec les 4 positions de trésorerie, comme le `RunRecord` du contrat et `fixtures/run_record.example.json` régénéré) et un `FakeApi` (étape 6).
- T3 → `GET /api/health`, `GET /api/alerts`, `GET /api/series`, `GET /api/state`, `backend/config/rules.yaml` → en attendant : listes d'`Alert` faites à la main, contenu de `rules.yaml` recopié depuis 2.7 dans un fichier temporaire.
- T4 → `GET /api/decisions` avec des actions `EMERGENCY_WITHDRAW` `executed` et leur `amount` → en attendant : listes de `Decision` faites à la main.

**Débloque.** T6 (carte « Evaluation » du dashboard via `GET /api/metrics`), T9 (chiffres du README, du deck, de la defense sheet, tableau de `report.md`).

**Fichiers possédés.** `evaluation/metrics.py`, `evaluation/run_synthetic.py`, `evaluation/report.py`, `evaluation/api_client.py`, `backend/api/metrics.py`, `mk/t7.mk`, `backend/tests/test_t7_*.py` (`evaluation/__init__.py` appartient à T0). Fichiers générés (écrits à l'exécution) : `data/eval/metrics.json` et `data/eval/report.md` (**commités** : le `.gitignore` de T0 fait l'exception), `data/eval/runs.jsonl`, `data/eval/rules_frozen.json` (non commités).

**À lire avant de commencer.** TASKS.md sections 1.2 (scénario), 1.5 (propriété des fichiers), 2.2 (paramètres du déploiement initial, `EvidenceRegistry`), 2.4 (helpers), 2.5 (conventions), 2.6 (`RunRecord`, `EvalMetrics` et ses unités, totaux de `StateResponse`), 2.7 (règles), 2.8 (matrice), 2.9 (API, codes d'erreur), 2.10 (mode maintenance), 2.11 (`make`), 4.2 (E2E-1) ; `backend/models.py` (`Alert`, `Decision`, `Action`, `RunRecord`, `EvalMetrics`, `SeriesPoint`, `Health`, `DemoRun`) ; `backend/api/metrics.py` ; `fixtures/snapshots_attack.jsonl`, `fixtures/snapshots_normal.jsonl`.

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| Vérité terrain d'un run | `data/runs/<run_id>.json` → `RunRecord` (`label`, `variant`, `seed`, `start_block`, `end_block`, `attack_start_block`, `phase_blocks`, `treasury_supplied_at_start` avec les 4 positions de trésorerie) | T2 | `RunRecord` à la main dans les tests (4 positions, voir T7-04) |
| Lancement d'une attaque | `POST /api/demo/attack {"seed": int, "variant": "default"\|"slow"\|"usdc"}` → `DemoRun` ; suivi par `GET /api/demo/runs/{run_id}`. Le banc envoie toujours une graine entière ≥ 1 (jamais `null`, tirée au hasard par le backend, ni `0`, paramètres par défaut sans hasard). 409 si un run de démo est déjà en cours | T2 | `FakeApi` (étape 6) |
| Lancement d'une journée normale | `make normal MINUTES=<m> SEED=<s>` (bloquant, écrit un `RunRecord` `label="normal"`) | T2 | `FakeApi.run_normal()` |
| Remise à zéro | `POST /api/demo/reset` → `DemoRun` (`kind="reset"`) | T2 | `FakeApi.reset()` |
| Santé du backend | `GET /api/health` → `Health` (`network`, `block_number`, `engine_running`) | T3 | `FakeApi.health()` (bloc qui avance de 1 à chaque appel) |
| Alertes | `GET /api/alerts?since_block=<start_block>` → `Alert[]` | T3 | listes d'`Alert` à la main ; plus tard rejeu des `.jsonl` via `Engine.process` (T7-16) |
| Décisions | `GET /api/decisions` → `Decision[]` | T4 | listes de `Decision` à la main |
| Liquidité par réserve | `GET /api/series?deployment_id=…&asset=…&limit=2000` → `SeriesPoint[]` | T3 | les deux `.jsonl` convertis en séries (T7-08) |
| Prix et décimales | `GET /api/state` → `reserves[].price_usd`, `reserves[].decimals`, `vault.idle_balances`, `totals.idle_usd` (= Σ soldes du coffre × prix, 2.6) ; 503 `no snapshot yet` tant que le moteur n'a lu aucun bloc | T3 | constantes de 2.2 : USDC 1,00 $ / 6 déc., WETH 2 500 $ / 18 déc., rsETH 2 500 $ / 18 déc. |
| Seuils figés | octets exacts de `backend/config/rules.yaml` | T3 | fichier temporaire avec le YAML de 2.7 |
| Registre de preuves | `EvidenceRegistry.anchor(bytes32, "rules", uri)` via `backend.chain` | T1 (contrat), T0 (helpers) | `--no-anchor` |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| `data/eval/metrics.json` (commité) | `EvalMetrics` (unités de 2.6, toutes les clés présentes, `null` si vide) : `generated_at`, `rules_version` (`"sha256:<64 hex>"`), `synthetic` avec **exactement** les 8 clés `runs_attack` (int), `runs_normal` (int), `detection_rate` (float 0..1, 3 décimales), `false_positive_rate` (float 0..1, 3 décimales), `ttd_blocks_p50` (int, -1 si aucune détection), `ttd_blocks_p90` (int, -1 idem), `saved_pct_mean` (float 0..100, 1 décimale), `baseline_saved_pct_mean` (float 0..100, 1 décimale) ; `mainnet_replay: null` ; `notes: list[str]` | T6, T9, `GET /api/metrics` |
| `data/eval/report.md` (commité) | markdown, gabarit étape 5 | T9 |
| `data/eval/runs.jsonl` | une ligne JSON par run (`AttackRunResult` ou `NormalRunResult` sérialisé, avec `"kind"`) | `make eval-report`, T9 |
| `data/eval/rules_frozen.json` | `{"rules_version": "sha256:…", "frozen_at": "<ISO>", "anchor_tx": "0x…"\|null, "anchor_block": int\|null, "network": "local"}` | T9 (preuve du gel) |
| `GET /api/metrics` | `EvalMetrics` (fichier si présent et valide, sinon fixture) | T6 |
| `make eval`, `make eval-report`, `make test-t7`, `make test-t7-e2e` | cibles de `mk/t7.mk` | tous |

#### Spécification détaillée

**1. Définitions (à recopier telles quelles en tête de `evaluation/metrics.py`).**
- *Fenêtre d'un run* : blocs `[record.start_block, record.end_block + settle_blocks]` (`settle_blocks` = 10 par défaut). Toute alerte ou décision hors fenêtre est ignorée.
- *Détecté* (run d'attaque) : il existe au moins une alerte `severity == "critical"` avec `attack_start_block <= block_number <= end_block + settle_blocks`.
- *TTD* (`ttd_blocks`) : `block_number` de la première alerte de ce type − `attack_start_block` (entier ≥ 0). `None` si non détecté. Sur la fixture régénérée, l'émission forgée est visible dans le snapshot du bloc 45 201 812 et l'alerte R1 porte ce même bloc (comme la décision `DEC-fuji-45201812-1`) → TTD = 0 en rejeu. En live, le moteur peut lire le bloc suivant : TTD de 0 à 2.
- *Positions concernées* : toutes les clés de `record.treasury_supplied_at_start` (`"<deployment>:<asset>"`). Dans le MVP, les deux déploiements acceptent le rsETH en garantie, donc R1 concerne **les 4 positions** : `lend-eth:WETH` 150 (375 000 $), `lend-eth:USDC` 400 000 (400 000 $), `lend-avax:WETH` 100 (250 000 $), `lend-avax:USDC` 300 000 (300 000 $) ; total **1 325 000 $**.
- *Valeur au départ* : `Σ int(supplied) / 10**decimals[asset] * price[asset]` sur les positions concernées.
- *Valeur sauvée* : somme, sur les décisions de la fenêtre, des actions `type == "EMERGENCY_WITHDRAW"` **et** `status == "executed"` **et** `amount` non nul **et** `tx_hash` qui ne commence pas par `0xdry`, de `int(amount) / 10**decimals * price`, la clé de position étant `f'{params["deployment_id"]}:{params["asset"]}'`. Par position, le montant retenu est plafonné à `treasury_supplied_at_start[clé]` (pas de double comptage). Les statuts `planned`, `skipped`, `failed`, `pending_approval`, `approved`, `rejected` ne comptent pas. Une action `executed` dont le `tx_hash` commence par `0xdry` (exécutée en dry-run, aucun fonds déplacé) est exclue de la valeur sauvée, avec un avertissement et une note `"dry-run withdrawals excluded from saved: <run_id>"`. Un `EMERGENCY_WITHDRAW` qui renvoie 0 (rien à retirer) a `amount = "0"` : il ne compte pas. Un `EMERGENCY_WITHDRAW` qui revert (`"MiniLend: paused"`) est `failed` : il ne compte pas.
- *`saved_pct`* = `100 * valeur sauvée / valeur au départ` (0,0 si valeur au départ = 0, avec une note).
- *`baseline_saved_pct`* (trésorerie passive, qui ne bouge pas) : une position dont la réserve a atteint une liquidité disponible nulle pendant la fenêtre vaut 0 % ; les autres valent 100 %. Résultat = `100 * valeur des positions non vidées / valeur au départ`. Attaque `default` (réserve vidée `lend-eth:WETH`) → **71,7** ; variante `usdc` (réserve vidée `lend-eth:USDC`) → **69,8** ; aucune réserve vidée → 100,0.
- *Faux positif* (run normal) : au moins une alerte `severity ∈ {"high", "critical"}` dans la fenêtre.
- *Percentile* : rang le plus proche, `sorted(v)[ceil(p/100 * len(v)) - 1]`, calculé sur les TTD des runs détectés uniquement.
- *Moyennes* `saved_pct_mean` et `baseline_saved_pct_mean` : sur **tous** les runs d'attaque valides, ratés compris (un raté compte avec ce qu'il a réellement sauvé).

**2. `evaluation/metrics.py` (pur : aucun I/O, aucun réseau).**
```python
SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
DEFAULT_PRICES = {"USDC": 1.0, "WETH": 2500.0, "rsETH": 2500.0}
DEFAULT_DECIMALS = {"USDC": 6, "WETH": 18, "rsETH": 18}
SYNTHETIC_KEYS = ("runs_attack", "runs_normal", "detection_rate", "false_positive_rate",
                  "ttd_blocks_p50", "ttd_blocks_p90", "saved_pct_mean", "baseline_saved_pct_mean")

@dataclass
class AttackRunResult:
    run_id: str; variant: str; seed: int; attack_start_block: int
    detected: bool; first_critical_block: int | None; first_rule_id: str | None; ttd_blocks: int | None
    start_value_usd: float; saved_usd: float; saved_pct: float; baseline_saved_pct: float
    drained_keys: list[str]; pre_attack_alerts: int          # alertes >= high AVANT attack_start_block
    warnings: list[str] = field(default_factory=list)       # ex. "no executed EMERGENCY_WITHDRAW"

@dataclass
class NormalRunResult:
    run_id: str; seed: int; false_positive: bool; high_alert_ids: list[str]; max_severity: str

def in_window(block: int, record: RunRecord, settle_blocks: int = 10) -> bool
def first_critical_after(alerts: list[Alert], record: RunRecord, settle_blocks: int = 10) -> Alert | None
def ttd_blocks(alerts, record, settle_blocks=10) -> int | None
def start_values_usd(record, prices=DEFAULT_PRICES, decimals=DEFAULT_DECIMALS) -> dict[str, float]
def saved_usd(decisions: list[Decision], record, prices=..., decimals=..., settle_blocks=10) -> float
def baseline_saved_pct(record, drained_keys: set[str], prices=..., decimals=...) -> float
def drained_keys_from_series(series: dict[str, list[SeriesPoint]], record, settle_blocks=10) -> set[str]
def percentile(values: list[int], p: float) -> int           # ValueError si values est vide
def evaluate_attack(record, alerts, decisions, drained_keys, prices=..., decimals=..., settle_blocks=10) -> AttackRunResult
def evaluate_normal(record, alerts, settle_blocks=10) -> NormalRunResult
def rules_version_of(path: Path) -> str                      # "sha256:" + sha256(octets exacts du fichier)
def aggregate(attacks: list[AttackRunResult], normals: list[NormalRunResult], rules_version: str,
              notes: list[str], now: datetime | None = None) -> EvalMetrics
```
Détails :
- Une `Action` sans `params["deployment_id"]` ou `params["asset"]` → ignorée + avertissement `"EMERGENCY_WITHDRAW without deployment_id/asset in <decision_id>"`.
- Une clé d'action absente de `treasury_supplied_at_start` → ignorée + avertissement.
- Une action `executed` avec `tx_hash.startswith("0xdry")` → ignorée + avertissement `"dry-run EMERGENCY_WITHDRAW excluded in <decision_id>"` (le banc ajoute la note de run correspondante).
- `drained_keys_from_series` : clé vidée si un point avec `start_block <= block_number <= end_block + settle` a `int(available_liquidity) == 0`.
- `aggregate` : `detection_rate = détectés / runs_attack` (0,0 si aucun run) ; `false_positive_rate = fp / runs_normal` ; taux arrondis à 3 décimales dans 0..1, pourcentages arrondis à 1 décimale dans 0..100 (2.6) ; si aucun run détecté, `ttd_blocks_p50 = ttd_blocks_p90 = -1` et note `"no detected attack run: ttd undefined"`. Ajoute aux notes une ligne par raté (`"MISS <run_id> variant=<v> seed=<s>: no critical alert in window"`) et par faux positif (`"FALSE POSITIVE <run_id>: <alert ids>"`). Valide la sortie avec `EvalMetrics.model_validate` avant de la renvoyer.

**3. `evaluation/api_client.py`.** Une interface, deux implémentations (la vraie, et `FakeApi` dans les tests) :
```python
class EvalApi(Protocol):
    def health(self) -> Health
    def reset(self) -> DemoRun
    def attack(self, seed: int, variant: str) -> DemoRun
    def demo_run(self, run_id: str) -> DemoRun
    def run_normal(self, seed: int, minutes: int) -> str     # renvoie le run_id
    def alerts(self, since_block: int) -> list[Alert]
    def decisions(self) -> list[Decision]
    def series(self, deployment_id: str, asset: str) -> list[SeriesPoint]
    def state(self) -> StateResponse
    def run_record(self, run_id: str) -> RunRecord           # lit data/runs/<run_id>.json

class HttpEvalApi:   # httpx.Client(base_url=api, timeout=30)
```
`HttpEvalApi.run_normal` : liste `data/runs/*.json` avant, lance `subprocess.run(["make", "normal", f"MINUTES={m}", f"SEED={s}"], check=True)`, puis prend le **nouveau** fichier dont `label == "normal"` (erreur si zéro ou plusieurs). Chaque réponse est validée avec le modèle Pydantic (une réponse invalide = run en erreur, pas un plantage du banc).

**4. `evaluation/run_synthetic.py` (le banc).**
```
python -m evaluation.run_synthetic --runs 10 --normal 3 --minutes 2 --settle-blocks 10 \
    --base-seed 1 --api http://127.0.0.1:8000 --out data/eval [--no-anchor]
```
`def run_eval(api: EvalApi, runs: int, normal: int, minutes: int, settle_blocks: int, base_seed: int, out_dir: Path, anchor: bool) -> EvalMetrics`

1. **Pré-vol.** `settings.NETWORK == "local"` sinon sortie 1 (`"eval runs on local only in the MVP"`). `GET /api/health` : `status == "ok"`, `network == "local"`, `engine_running == true`, sinon sortie 1 avec le rappel : `NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false make backend`. `backend/config/rules.yaml` doit exister, sinon sortie 1.
2. **Gel des seuils (avant le premier run).** `frozen = rules_version_of(CONFIG_DIR / "rules.yaml")`. Écrit `rules_frozen.json`. Si `anchor` : après le premier `reset` (le reset redéploie, donc un ancrage antérieur serait perdu), appelle `chain.send(chain.registry().anchor(bytes.fromhex(hex), "rules", "repo://backend/config/rules.yaml"), chain.account("evidence"))` (si `registry()` n'existe pas encore dans `chain.py`, utiliser `chain.contract("EvidenceRegistry")`). Revert `"Evidence: already anchored"` → lire `anchoredAt(hash)` et continuer. Toute autre erreur → note `"rules hash not anchored: <raison>"`, on continue. Sur local, l'ancrage est éphémère : le noter. L'ancrage se fait quand aucun scénario ne tourne (pas de conflit de nonce avec T4 qui utilise la même clé).
3. **Boucle d'attaques** `i = 0..runs-1` : `seed = base_seed + i`, `variant = ("default", "slow", "usdc")[i % 3]`.
   a. `reset()`, puis attendre `demo_run(reset.run_id).status == "done"` (poll 2 s, timeout 180 s) puis `health()` ok avec `block_number` qui avance (timeout 120 s). Le reset pose `data/runtime/local/maintenance.flag` puis le supprime dans un `finally` et incrémente `store.generation` : le moteur n'évalue aucune règle pendant ce temps et repart d'une fenêtre vide. Si `reset()` ou `attack()` renvoie 409 (run de démo déjà en cours), attendre 2 s et réessayer (timeout 180 s, puis run en erreur). `state()` peut renvoyer 503 `no snapshot yet` juste après le reset : réessayer de la même façon.
   b. `prices, decimals, idle_before` ← `state()` (`idle_before` = `totals.idle_usd`, soit Σ soldes du coffre × prix ; repli sur les constantes si l'appel échoue, avec avertissement).
   c. `run = attack(seed, variant)` ; poll `demo_run(run.run_id)` toutes les 2 s jusqu'à `done` ou `failed` (timeout 600 s).
   d. `record = run_record(run.run_id)` ; attendre `health().block_number >= record.end_block + settle_blocks`.
   e. `alerts(since_block=record.start_block)`, `decisions()`, `series()` pour chaque clé concernée, `state()` (pour `idle_after` = `totals.idle_usd`).
   f. Contrôle anti-dérive : toute alerte dont `rules_version != frozen` → arrêt, sortie 3 (`"rules.yaml changed during evaluation"`).
   g. `drained = drained_keys_from_series(...)` ; si les séries sont vides, repli : si `"liquidity_zero" in record.phase_blocks`, `drained = {VARIANT_TARGET[variant]}` avec `VARIANT_TARGET = {"default": "lend-eth:WETH", "slow": "lend-eth:WETH", "usdc": "lend-eth:USDC"}` + avertissement.
   h. `evaluate_attack(...)`. Contrôle croisé : `idle_delta_usd` (idle après − avant, valorisé) vs `saved_usd` ; écart > 1 % de la valeur au départ → avertissement. Si détecté mais aucune `EMERGENCY_WITHDRAW` `executed` → avertissement `"no executed EMERGENCY_WITHDRAW"`. Si un `tx_hash` `0xdry…` apparaît → exclu de la valeur sauvée et note `"dry-run withdrawals excluded from saved: <run_id> (backend must run with DRY_RUN_ACTIONS=false)"`.
   i. Ajoute la ligne à `runs.jsonl` immédiatement (un crash ne perd pas les runs déjà faits). Log : `[eval] attack 3/10 seed=3 variant=usdc run=RUN-… detected=yes rule=R1_BRIDGE_INVARIANT ttd=1 saved=100.0% baseline=69.8%`.
4. **Boucle normale** `j = 0..normal-1` : `seed = 10_000 + base_seed + j` ; reset comme en 3a ; `run_id = run_normal(seed, minutes)` ; attendre `end_block + settle` ; `evaluate_normal`. Log : `[eval] normal 1/3 seed=10001 run=RUN-… false_positive=no max_severity=warning`.
5. **Runs en erreur.** `DemoRun.status == "failed"`, timeout, `RunRecord` absent ou invalide → run « errored » : exclu des taux, listé dans les notes (`"ERRORED <run_id or seed>: <raison>"`) et dans le rapport. Jamais relancé en silence. Si plus de 20 % des runs sont en erreur → métriques écrites quand même, sortie 2.
6. **Fin.** `aggregate(...)` → `metrics.json` (écriture atomique : fichier `.tmp` puis `os.replace`) ; `report.write_report(...)`. Notes systématiques : `"network=local"`, `"variants: default x4, slow x3, usdc x3"`, `"settle_blocks=10"`, `"rules anchored: tx 0x… block N (local, ephemeral)"` ou `"rules not anchored"`, `"thresholds frozen before first run; variants authored by T2 independently of rules.yaml"`.

**5. `evaluation/report.py`.** `def write_report(metrics: EvalMetrics, attacks: list[AttackRunResult], normals: list[NormalRunResult], errored: list[str], out: Path) -> None` et `python -m evaluation.report` (relit `runs.jsonl` + `metrics.json`, réécrit `report.md`). Gabarit :
```markdown
# Synthetic evaluation report
Generated <ISO 8601 UTC> · network local · rules sha256:09bf…2847 (anchored tx 0x… block 57)
## Summary
| Metric | Value |
|---|---|
| Attack runs | 10 |
| Detection rate | 100.0 % (10/10) |
| False positive rate | 0.0 % (0/3) |
| Time to detect, p50 / p90 (blocks) | 1 / 2 |
| Treasury value saved (mean) | 100.0 % |
| Passive treasury baseline (mean) | 71.1 % |
## Attack runs
| run_id | variant | seed | detected | first rule | ttd (blocks) | saved % | baseline % | warnings |
## Normal runs
| run_id | seed | false positive | alerts >= high |
## Misses, false positives, errors
- None.          (sinon une ligne par cas, avec la raison)
## Method
(les 3 règles de non-circularité ci-dessous, et les définitions de l'étape 1 en une ligne chacune)
```

**6. `FakeApi` (dans `backend/tests/test_t7_harness.py`).** Implémente `EvalApi` en mémoire : `health()` renvoie un bloc qui avance de 1 par appel ; `attack()` crée un `RunRecord` (`start_block = b`, `attack_start_block = b + 12`, `end_block = b + 80`, les 4 positions de 2.2) et l'écrit dans `tmp_path/runs/` ; `alerts()` renvoie une R1 critique à `attack_start_block + 1` ; `decisions()` renvoie une décision avec 4 `EMERGENCY_WITHDRAW` `executed` pour les montants complets ; `series()` met `available_liquidity = "0"` sur `lend-eth:WETH` (ou `lend-eth:USDC` en variante `usdc`) ; `run_normal()` crée un `RunRecord` normal sans alerte ≥ high. Les sleeps sont injectés (`sleep=lambda s: None`) pour que le test tourne en moins d'1 s.

**7. `backend/api/metrics.py`.** Garder la route existante. Ajouter : si `data/eval/metrics.json` existe mais ne se valide pas (JSON cassé, schéma faux), logger `WARNING data/eval/metrics.json invalid: <erreur>` et servir la fixture (jamais de 500). Lire `settings.DATA_DIR` à l'appel (pas à l'import) pour que les tests puissent le surcharger.

**8. `mk/t7.mk`.**
```make
RUNS ?= 10
EVAL_NORMAL ?= 3
EVAL_MINUTES ?= 2
eval: ## synthetic evaluation on local chain (backend must run with engine on)
	python -m evaluation.run_synthetic --runs $(RUNS) --normal $(EVAL_NORMAL) --minutes $(EVAL_MINUTES)
eval-report: ## rebuild data/eval/report.md from runs.jsonl
	python -m evaluation.report
test-t7:
	pytest -q backend/tests/test_t7_*.py
test-t7-e2e:
	T7_E2E=1 pytest -q backend/tests/test_t7_e2e.py
```
Préfixe `EVAL_` pour ne pas écraser `MINUTES` de T2 (tous les `mk/*.mk` sont inclus dans le même `Makefile`). Ne jamais redéfinir `NETWORK` dans `mk/t7.mk` (il vient de `.env`, exporté par le `Makefile` racine, ou de la ligne de commande). `make test-t7` inclut `test_t7_e2e.py`, qui se met en skip tant que `T7_E2E` n'est pas défini ; `make test` (qui appelle `test-t0` … `test-t9`) ne lance donc jamais de vraie évaluation.

**Règles de non-circularité (à recopier dans `report.md`).**
1. Les seuils sont gelés avant le premier run : leur sha256 est écrit dans `metrics.json` et `rules_frozen.json`, et ancré si possible ; toute alerte portant un autre `rules_version` arrête l'évaluation.
2. Les variantes d'attaque (`default`, `slow`, `usdc`) sont écrites par T2 sans regarder `rules.yaml` ; T7 ne modifie ni les règles ni les variantes, et ne choisit pas les graines après coup (`base_seed` fixé avant).
3. Chaque raté, faux positif et run en erreur est rapporté ; aucun run n'est relancé ou retiré pour améliorer un chiffre.

#### Tests qui doivent passer

Commande globale : `make test-t7` (= `pytest backend/tests/test_t7_*.py`, sans réseau, < 10 s ; T7-20 en skip sans `T7_E2E=1`). Données de base des tests : `REC` = `RunRecord(label="attack", variant="default", seed=1, start_block=100, end_block=180, attack_start_block=112, phase_blocks={"forged_release":112,"liquidity_zero":138}, treasury_supplied_at_start={"lend-eth:WETH": 150e18, "lend-eth:USDC": 400000e6, "lend-avax:WETH": 100e18, "lend-avax:USDC": 300000e6})` (montants en chaînes d'unités de base), `settle_blocks=10`.

| Id | Type | Commande | Mise en place | Résultat attendu |
|---|---|---|---|---|
| T7-01 | unitaire | `pytest backend/tests/test_t7_metrics.py::test_percentile_nearest_rank` | listes fixes | `[0,1,2,3,10]` → p50 = 2, p90 = 10 ; `[3]` → 3 et 3 ; `[2,0,1,1]` → p50 = 1, p90 = 2 ; `[]` → `ValueError` |
| T7-02 | unitaire | `…::test_detected_and_ttd` | `REC` ; alertes : R1 critical bloc 113, R3 high bloc 130, R2 critical bloc 105 (avant l'attaque) | `detected is True`, `first_critical_block == 113`, `first_rule_id == "R1_BRIDGE_INVARIANT"`, `ttd_blocks == 1`, `pre_attack_alerts == 1` |
| T7-03 | unitaire | `…::test_not_detected` | `REC` ; alertes : R4 high bloc 140, R1 critical bloc 195 (hors fenêtre : 195 > 190) | `detected is False`, `ttd_blocks is None` |
| T7-04 | unitaire | `…::test_saved_full` | `REC` ; 1 décision bloc 114 avec 4 `EMERGENCY_WITHDRAW` `executed`, montants complets | `start_value_usd == 1325000.0`, `saved_usd == 1325000.0`, `saved_pct == 100.0` |
| T7-05 | unitaire | `…::test_saved_ignores_non_executed` | `REC` ; `lend-eth:WETH` 150 `executed` ; `lend-eth:USDC` `failed` ; `lend-avax:WETH` `pending_approval` ; `lend-avax:USDC` `planned` avec `amount` rempli | `saved_usd == 375000.0`, `saved_pct == 28.3` |
| T7-06 | unitaire | `…::test_saved_capped_and_unknown_key` | `REC` ; `lend-eth:WETH` 200 WETH `executed` ; une action `lend-eth:rsETH` `executed` ; `lend-avax:WETH` 100 WETH `executed` avec `tx_hash = "0xdry…"` | `saved_usd == 375000.0` (plafonné, dry-run exclu), 1 avertissement pour la clé inconnue, 1 avertissement `"dry-run EMERGENCY_WITHDRAW excluded …"` |
| T7-07 | unitaire | `…::test_baseline` | `REC` | drained `{"lend-eth:WETH"}` → 71.7 ; `{"lend-eth:USDC"}` → 69.8 ; `set()` → 100.0 |
| T7-08 | unitaire | `…::test_drained_from_fixtures` | lit `fixtures/snapshots_attack.jsonl` et `snapshots_normal.jsonl`, convertit chaque réserve en `SeriesPoint` ; record `start_block=45201800`, `end_block=45201880` | attaque → `{"lend-eth:WETH"}` (liquidité nulle dès 45 201 838) ; normal → `set()` |
| T7-09 | unitaire | `…::test_false_positive` | record normal `start_block=100`, `end_block=180` | `[R3 warning 120]` → `False` (alerte synthétique générique) ; `[R2 high 150]` → `True` ; `[R2 high 195]` → `False` ; `max_severity` cohérent |
| T7-10 | unitaire | `…::test_aggregate` | 3 attaques (ttd 0, saved 100, baseline 71.7) / (ttd 2, saved 100, baseline 71.7) / (raté, saved 0, baseline 69.8) ; 2 normaux dont 1 FP | `runs_attack == 3`, `runs_normal == 2`, `detection_rate == 0.667`, `false_positive_rate == 0.5`, `ttd_blocks_p50 == 0`, `ttd_blocks_p90 == 2`, `saved_pct_mean == 66.7`, `baseline_saved_pct_mean == 71.1` ; notes contiennent `"MISS "` et `"FALSE POSITIVE "` ; `set(synthetic) == set(SYNTHETIC_KEYS)` |
| T7-11 | unitaire | `…::test_aggregate_no_detection` | 1 attaque ratée, 0 normal | `ttd_blocks_p50 == -1`, `ttd_blocks_p90 == -1`, `false_positive_rate == 0.0`, note `"no detected attack run: ttd undefined"` |
| T7-12 | unitaire | `…::test_rules_version` | fichier temporaire contenant `version: 1\n` | `"sha256:09bfcc6a14b83e2192b8673677725c84883ee9cd0c70e45c9ec09daa8f2b2847"` ; format `^sha256:[0-9a-f]{64}$` |
| T7-13 | unitaire | `pytest backend/tests/test_t7_report.py::test_outputs_schema` | résultats de T7-10, `write_report` + écriture de `metrics.json` dans `tmp_path` | `EvalMetrics.model_validate(json.load(...))` passe ; `report.md` contient `"| Detection rate | 66.7 % (2/3) |"`, 3 lignes dans « Attack runs », 2 dans « Normal runs », la ligne du raté |
| T7-14 | API | `pytest backend/tests/test_t7_api.py::test_metrics_file_then_fixture` | `monkeypatch.setattr(settings, "DATA_DIR", tmp_path)`, `TestClient(app)` | sans fichier : 200 et `synthetic.runs_attack == 0` (fixture) ; avec le `metrics.json` de T7-13 : 200 et `synthetic.detection_rate == 0.667` |
| T7-15 | API | `…::test_metrics_invalid_file` | `tmp_path/eval/metrics.json` = `"{oops"` | 200, corps = fixture, un log `WARNING` |
| T7-16 | intégration hors ligne | `pytest backend/tests/test_t7_replay.py` | rejoue les 41 snapshots de chaque `.jsonl` dans `backend.engine.Engine(Store()).process` ; **`pytest.skip` si `backend.store` ou `Engine` est encore un stub (aucune alerte sur la série d'attaque)** | attaque : première alerte critique `R1_BRIDGE_INVARIANT` au bloc 45 201 812 → `ttd_blocks == 0` avec `attack_start_block = 45201812` ; normal : `false_positive is False` |
| T7-17 | banc hors ligne | `pytest backend/tests/test_t7_harness.py::test_run_eval_with_fake_api` | `FakeApi` (étape 6), `runs=3`, `normal=1`, `anchor=False`, `out_dir=tmp_path` | `metrics.json` valide ; `runs_attack == 3`, `runs_normal == 1`, `detection_rate == 1.0`, `ttd_blocks_p50 == 1`, `saved_pct_mean == 100.0`, `baseline_saved_pct_mean == 71.1` ; `runs.jsonl` a 4 lignes ; variantes `default, slow, usdc` |
| T7-18 | banc hors ligne | `…::test_rules_drift_aborts` | `FakeApi` dont une alerte a `rules_version="sha256:" + "0"*64` | `SystemExit` code 3 |
| T7-19 | banc hors ligne | `…::test_failed_run_reported` | `FakeApi` où le run 2 renvoie `status="failed"` | `runs_attack == 2`, note commençant par `"ERRORED "`, ligne dans `report.md` |
| T7-20 | bout en bout | `make test-t7-e2e` (= `T7_E2E=1 pytest backend/tests/test_t7_e2e.py`) | skip si `T7_E2E` absent, si `127.0.0.1:8545` ne répond pas, ou si `GET /api/health` n'est pas `ok`/`local`/`engine_running` ; backend lancé avec `NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false` ; lance `python -m evaluation.run_synthetic --runs 2 --normal 1 --minutes 1` | code 0 ; `runs_attack == 2`, `runs_normal == 1`, `detection_rate == 1.0`, `false_positive_rate == 0.0`, `ttd_blocks_p90 <= 2` (aligné sur E2E-1), `saved_pct_mean >= 99.0`, `baseline_saved_pct_mean < saved_pct_mean`, `rules_version` = sha256 du `rules.yaml` courant |

#### Definition of done

- [ ] `make test-t7` vert sans chaîne ni backend (T7-01 à T7-19, T7-16 éventuellement en skip, T7-20 en skip sans `T7_E2E=1`).
- [ ] `make test-t7-e2e` vert sur la chaîne locale une fois T1 à T4 mergés.
- [ ] `make eval RUNS=10` produit `data/eval/metrics.json` valide, `report.md`, `runs.jsonl`, `rules_frozen.json`.
- [ ] `GET /api/metrics` sert le fichier mesuré ; jamais de 500 sur un fichier cassé.
- [ ] `metrics.json` contient exactement les 8 clés de `synthetic`, unités respectées (taux 0..1, pourcentages 0..100).
- [ ] Les notes listent réseau, variantes, ancrage, et chaque raté / faux positif / erreur.
- [ ] Section « Method » de `report.md` avec les 3 règles de non-circularité.
- [ ] `data/eval/metrics.json` et `data/eval/report.md` commités après la mesure finale (T9 les lit dans le repo).
- [ ] Aucun fichier hors « Fichiers possédés » modifié ; demandes éventuelles dans `docs/contract-requests.md`.

#### Pièges connus

- **Le reset redéploie** : un ancrage fait avant le premier `reset` pointe vers un ancien registre. Ancrer après le premier reset.
- **Dénominateur** : le `RunRecord` porte les 4 positions de trésorerie, soit 1 325 000 $. Vérifier `treasury_supplied_at_start` sur le premier vrai run (et que `fixtures/run_record.example.json` a bien été régénéré avec les 4 positions) : s'il en manque, `saved_pct` est faux.
- **Hash `0xdry`** : en dry-run, les retraits sont marqués `executed` avec un `tx_hash` `0xdry…` sans qu'aucun fonds ne bouge. Le banc tourne avec `DRY_RUN_ACTIONS=false` ; si un `0xdry` apparaît quand même, l'exclure de la valeur sauvée et l'écrire dans les notes (étape 4.3h), jamais le compter.
- **Unités** : `amount` en unités de base (chaîne). Ne jamais convertir en float avant la division par `10**decimals` sur un `int` Python.
- **Ancienne alerte qui traîne** : filtrer par fenêtre de blocs, même si le reset vide le store.
- **`GET /api/alerts` est trié du plus récent au plus ancien** : trier par `block_number` croissant avant de chercher la première alerte.
- **anvil `--block-time 1` et `POLL_INTERVAL_S=2`** : le moteur peut sauter un bloc, TTD de 0 à 2 est normal sur local.
- **Collision de variables make** : utiliser `EVAL_NORMAL` / `EVAL_MINUTES`, pas `MINUTES`.
- **`make normal` doit être bloquant** ; sinon le banc ne trouve pas de nouveau `RunRecord`. À vérifier avec T2 dès que possible.
- **`make test` ne doit jamais lancer de vraie évaluation** (elle ferait un reset de la chaîne d'un collègue) : l'E2E est derrière `T7_E2E=1`.
- **`data/` est ignoré par git sauf `data/eval/metrics.json` et `data/eval/report.md`** (exception faite par T0 dans `.gitignore`) : ne pas commiter `runs.jsonl` ni `rules_frozen.json` par erreur avec `git add -f`.

#### Plus tard (phase 2)

- **Rejeu mainnet du vrai incident Aave du 18 avril 2026** (bloc 24 908 285) via `ETH_ARCHIVE_RPC_URL` : un adaptateur `evaluation/replay_mainnet.py` lit Aave v3 Ethereum et le rsETH réels bloc par bloc et produit des `Snapshot(source="replay", network="replay")` donnés à `Engine.process` ; remplit `mainnet_replay` : `exploit_block`, `first_alert_block`, `ttd_minutes`, `protocol_freeze_minutes`, `withdrawable_pct_at_alert`, `withdrawable_pct_at_freeze`, `alerts_on_normal_days`.
- **Alertes sur jours normaux réels** : 30 jours d'historique mainnet, taux d'alertes ≥ high par jour.
- **Intervalles de confiance** : Wilson pour `detection_rate` et `false_positive_rate`, bootstrap pour les percentiles de TTD.
- Avance sur le gel du protocole (`phase_blocks.protocol_freeze − first_critical_block`), détail par règle, évaluation sur Fuji, coût en gas de la réponse, variantes adverses supplémentaires (émission forgée lente sous le seuil R1, drainage multi-réserves).

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T7 (Évaluation et métriques) du fichier TASKS.md à la racine du repo.
1. Lis TASKS.md sections 1 et 2 en entier, puis la section T7 en entier. Lis backend/models.py
   (Alert, Decision, Action, RunRecord, EvalMetrics, SeriesPoint, Health, DemoRun), backend/settings.py,
   backend/chain.py et backend/api/metrics.py.
2. Ne modifie QUE : evaluation/ (metrics.py, api_client.py, run_synthetic.py, report.py ; pas __init__.py, T0),
   backend/api/metrics.py, mk/t7.mk, backend/tests/test_t7_*.py. Rien d'autre : ni rules.yaml, ni les
   scénarios, ni models.py, ni fixtures/. Si tu as besoin d'un changement ailleurs ou dans le contrat
   (section 2), n'édite pas : écris la demande dans docs/contract-requests.md et préviens-moi.
3. Commence par les tests T7-01 à T7-15 (backend/tests/test_t7_metrics.py, test_t7_report.py,
   test_t7_api.py) avec les valeurs exactes de la section T7, puis écris evaluation/metrics.py et
   report.py jusqu'à ce qu'ils passent. Ensuite FakeApi + T7-17 à T7-19, puis run_synthetic.py.
   T7-16 et T7-20 se mettent en skip tant que T3/T2/T4 ne sont pas livrés.
4. Travaille sur maquettes : RunRecord, Alert et Decision construits à la main, FakeApi pour le banc,
   fixtures/snapshots_*.jsonl pour les séries. fixtures/alerts.json et decisions.json ne servent que
   d'exemples de format (R1 et DEC-fuji-45201812-1 au bloc 45201812). Le dénominateur de référence
   est 1 325 000 $ (4 positions). Un tx_hash 0xdry… n'est jamais compté comme sauvé.
5. Garde les métriques simples : exactement les 8 clés de EvalMetrics.synthetic. Tout le reste va
   dans notes ou dans « Plus tard ». Respecte les règles de non-circularité.
6. Avant chaque commit : make test-t7 vert (pytest backend/tests/test_t7_*.py), push fréquent après chaque
   test vert. Ne lance jamais make eval contre la chaîne d'un collègue.
```


---


### T8 · AWS, CI et mise en ligne de la démo

**Objectif.** Mettre la plateforme en ligne sur AWS (us-east-1) avec une URL publique stable qui sert le dashboard et l'API branchés sur Fuji, fournir à T4/T5 les ressources AWS (topic SNS, bucket de preuves, modèle Bedrock) avec un rôle IAM minimal, et garder `main` vert grâce à une CI (tests Python, tests Foundry, build du front, scan de secrets). Rien de ce que fait T8 ne doit pouvoir faire fuiter une clé : ni dans le repo, ni dans une image Docker, ni dans le bundle du front.

**Dépend de.**
- T0 → `requirements.txt`, `Makefile` (avec `-include .env`, `export` des variables et `include mk/*.mk`), `.env.example`, `.gitignore`, squelette `backend/` → disponibles dès le départ. Le `.gitignore` appartient à T0 : il ignore `.env` et `.env.*` sauf `.env.example` (donc `.env.fuji`, `.env.secrets`, `.env.canary`, `frontend/.env.local` sont ignorés) ; toute autre exception se demande dans `docs/contract-requests.md`.
- T1 → `deployments/fuji.json` et `abi/*.json` **commités** → en attendant : déploiement « squelette » avec `USE_FIXTURES=true`, `ENGINE_ENABLED=false` (l'API sert les fixtures, aucun contrat requis).
- T3 → vraie route `GET /api/health` (`rpc_ok`, `engine_running`, `block_number` réels) → en attendant : `fixtures/health.json` (attention, elle dit déjà `network: fuji`, `rpc_ok: true`, voir Pièges).
- T6 → `frontend/package.json` avec scripts `build` (et idéalement `typecheck`), appels API en chemin relatif `/api/...` → en attendant : un faux front minimal `infra/testdata/frontend-stub/` (possédé par T8) passé au build via `FRONTEND_DIR`.
- T2 → `POST /api/demo/reset` qui lance `make deploy` puis `make seed` **dans le conteneur backend** (sur fuji, `make deploy` exige `FORCE=1` quand un déploiement existe déjà : c'est T2 qui le passe) → l'image backend contient donc `make`, le `Makefile`, `mk/`, `contracts/` et Foundry (`WITH_FOUNDRY=true` par défaut) ; en attendant T2 : on vérifie seulement que `make -n deploy` et `make -n seed` se résolvent dans l'image.
- T4, T5 → lisent `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID` → rien à attendre, T8 les produit.

**Débloque.**
- T4 : `SNS_TOPIC_ARN` (notifications) et `EVIDENCE_BUCKET` (preuves) + droits IAM de l'instance.
- T5 : `BEDROCK_MODEL_ID` (id de profil d'inférence Claude) + droit `bedrock:InvokeModel`.
- T6 : l'URL publique où le front est servi et `/api` proxifié (même origine, pas de CORS en prod).
- T9 : l'URL de démo pour le jury, la section « Deploy » du README, le plan de repli, la preuve « aucun secret dans le repo ».
- Tout le monde : la CI sur chaque PR vers `main`.

**Fichiers possédés.** (section 1.5 : `infra/`, `.github/workflows/`, `mk/t8.mk`, `backend/tests/test_t8_*.py`)
- `infra/docker-compose.yml`, `infra/backend.Dockerfile`, `infra/backend.Dockerfile.dockerignore`, `infra/frontend.Dockerfile`, `infra/frontend.Dockerfile.dockerignore`, `infra/nginx.conf`
- `infra/deploy.sh`, `infra/render_env.sh`, `infra/user-data.sh`, `infra/scan_images.sh`, `infra/check_aws.py`
- `infra/fuji.env` (valeurs **non secrètes** forcées sur l'instance), `infra/iam-policy.json`, `infra/gitleaks.toml`, `infra/setup-aws.md` (runbook)
- `infra/testdata/frontend-stub/` (faux front pour tester le build tant que T6 n'a pas livré)
- `.github/workflows/ci.yml`, `mk/t8.mk`
- `backend/tests/test_t8_infra.py`, `backend/tests/test_t8_check_aws.py`, `backend/tests/test_t8_deploy.py`

**À lire avant de commencer.** TASKS.md sections 1.3, 1.5, 1.6 (règles 5, 6, 8), 2.1 (variables), 2.9 (routes, port 8000), 2.10 (store en mémoire : **un seul process**), 2.11 (make) ; `backend/settings.py` (lecture de `.env` à la racine, valeurs par défaut), `backend/main.py` (démarrage du moteur dans l'event `startup`), `fixtures/health.json`.

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| Dépendances Python | `requirements.txt` à la racine | T0 | celui du squelette |
| Code backend | `backend/`, `scenario/`, `evaluation/`, `fixtures/`, `abi/`, `deployments/` | T0..T5, T7 | squelette T0 (sert les fixtures) |
| Adresses Fuji | `deployments/fuji.json` (2.3), commité | T1 | aucun besoin en mode squelette (`USE_FIXTURES=true`) |
| Front buildable | `frontend/package.json` + `package-lock.json`, `npm run build` → `frontend/dist/` | T6 | `infra/testdata/frontend-stub/` (build = script node qui écrit `dist/index.html` contenant `<div id="root">`) |
| Contrats Foundry | `contracts/foundry.toml`, `contracts/lib/` (sous-modules) | T1 | job CI `contracts` sauté si `contracts/foundry.toml` absent |
| Health réel | `Health` (2.9) : `network`, `rpc_ok`, `engine_running`, `block_number` | T3 | `fixtures/health.json` |
| Clés Fuji et RPC | variables 2.1 (`*_PK`, `BOT_PKS`, `RPC_URL`) | l'équipe (générées pour l'événement, testnet uniquement) | `.env` local sur `NETWORK=local` (clés anvil publiques) |
| Compte AWS | console + clés temporaires de l'équipe | organisateurs | aucune (tests `check_aws` en mode stub botocore) |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| URL publique | `http://<elastic-ip>/` (front) et `http://<elastic-ip>/api/*` (API proxifiée) | T6, T9, jury |
| `SNS_TOPIC_ARN` | `arn:aws:sns:us-east-1:<account_id>:secure-horizons-alerts` | T4 |
| `EVIDENCE_BUCKET` | `secure-horizons-evidence-<account_id>` (versioning, Object Lock si possible) | T4 |
| `BEDROCK_MODEL_ID` | id de profil d'inférence copié depuis `aws bedrock list-inference-profiles`, forme `us.anthropic.claude-…` | T5 |
| Rôle d'instance | `secure-horizons-ec2-role` + profil `secure-horizons-ec2-profile`, politique `infra/iam-policy.json` | T4, T5 (boto3 sans clé) |
| Images | `sh-backend`, `sh-frontend` construites **sur l'instance** (pas de registre) | — |
| CI | `.github/workflows/ci.yml`, jobs `python`, `contracts`, `frontend`, `gitleaks`, `docker` | tout le monde |
| Cibles make | `deploy-aws`, `aws-check`, `aws-smoke`, `aws-logs`, `aws-rollback`, `aws-allow-my-ip`, `docker-build`, `docker-up`, `docker-down`, `docker-smoke`, `scan-images`, `gitleaks`, `test-t8` (dans `mk/t8.mk`) | tout le monde |
| Runbook | `infra/setup-aws.md` (commandes CLI pas à pas + tableau « Valeurs de l'équipe » non secrètes) | T9, équipe |

#### Spécification détaillée

**1. Image backend (`infra/backend.Dockerfile`, contexte = racine du repo).**
- Base `python:3.11-slim`. `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`. `WORKDIR /app`.
- `COPY requirements.txt .` puis `pip install --no-cache-dir -r requirements.txt` (couche mise en cache).
- `RUN apt-get update && apt-get install -y --no-install-recommends make git ca-certificates && rm -rf /var/lib/apt/lists/*` : `POST /api/demo/reset` (T2) appelle `make deploy` et `make seed` depuis le conteneur.
- `ARG WITH_FOUNDRY=true` ; si `true` : `COPY --from=ghcr.io/foundry-rs/foundry:stable /usr/local/bin/forge /usr/local/bin/cast /usr/local/bin/` (repli si les binaires ne tournent pas : `curl -L https://foundry.paradigm.xyz | bash && foundryup`), puis `RUN cd contracts && forge build` après la copie de `contracts/` (le cache de compilation est dans l'image, un `reset` sur Fuji ne recompile pas). Avec `WITH_FOUNDRY=false`, `make deploy` est indisponible dans l'image : réservé au cas où T2 n'en a pas besoin.
- Copies **explicites** uniquement (jamais `COPY . .`) : `Makefile`, `mk/`, `contracts/` (avec `contracts/lib/`, sous-modules OpenZeppelin), `backend/`, `scenario/`, `evaluation/`, `fixtures/`, `abi/`, `deployments/`, `infra/check_aws.py` → `/app/infra/check_aws.py`. Pas de `.env` dans l'image : le `-include .env` du `Makefile` ne trouve rien et les variables viennent de l'environnement du conteneur (`env_file`), que `make` hérite.
- `make deploy` écrit `deployments/<network>.json` **et** `abi/` : les deux doivent être inscriptibles par l'utilisateur du conteneur.
- Utilisateur non root `app` avec **uid 1000** (même uid que `ec2-user`, sinon le volume `data/` n'est pas inscriptible). `mkdir -p /app/data && chown -R 1000:1000 /app/data /app/deployments /app/abi /app/contracts` (le `reset` écrit les déploiements, les ABIs, `contracts/out` et `contracts/broadcast`, et T2 crée `data/runtime/<network>/maintenance.flag`).
- `EXPOSE 8000`. `CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]` : **pas** de `--reload`, **pas** de `--workers` (le store et le moteur sont en mémoire dans un seul process, 2.10).
- `infra/backend.Dockerfile.dockerignore` (fichier d'exclusion propre à ce Dockerfile, lu par BuildKit) : `.git`, `.env`, `.env.*`, `**/.env`, `**/.env.*`, `data/`, `frontend/`, `**/node_modules`, `**/__pycache__`, `contracts/out`, `contracts/cache`, `*.pem`, `*.key`.

**2. Image frontend (`infra/frontend.Dockerfile`, multi-stage).**
- `ARG FRONTEND_DIR=frontend`. Étape `build` : `node:20-alpine`, `WORKDIR /src/frontend`, `COPY ${FRONTEND_DIR}/package.json ${FRONTEND_DIR}/package-lock.json* ./`, `npm ci` (ou `npm install` si pas de lock, seulement pour le stub), `COPY ${FRONTEND_DIR}/ ./`, `COPY fixtures/ /src/fixtures/` (si T6 importe `../fixtures`), `ENV VITE_API_URL=` (vide : le front appelle `/api/...` en chemin relatif, même origine via nginx, 2.1) et `ENV VITE_USE_FIXTURES=false`, puis `npm run build` → `/src/frontend/dist`.
- Étape finale : `nginx:1.27-alpine`, `COPY infra/nginx.conf /etc/nginx/conf.d/default.conf`, `COPY --from=build /src/frontend/dist /usr/share/nginx/html`. Aucune variable d'environnement de secret, aucun `ARG` de secret.
- `infra/frontend.Dockerfile.dockerignore` : comme le backend + `frontend/.env*` (Vite injecte toutes les `VITE_*` des fichiers `.env*` du front **dans le bundle public**), `frontend/dist`, `frontend/node_modules`.

**3. `infra/nginx.conf`.**
```nginx
limit_req_zone $binary_remote_addr zone=demo:1m rate=6r/m;
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  gzip on; gzip_types application/json application/javascript text/css;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  location /api/demo/ { limit_req zone=demo burst=2 nodelay; proxy_pass http://backend:8000; proxy_read_timeout 300s; }
  location /api/      { proxy_pass http://backend:8000; proxy_read_timeout 120s; }
  location /assets/   { expires 7d; add_header Cache-Control "public, immutable"; }
  location /          { try_files $uri $uri/ /index.html; add_header Cache-Control "no-cache"; }
}
```
- `proxy_pass http://backend:8000;` **sans** barre finale : le préfixe `/api` est conservé (les routes FastAPI sont montées sous `/api`, 2.9). Les `proxy_set_header` au niveau `server` sont hérités par les deux `location`.
- `/api/demo/reset` sur Fuji redéploie les contrats : la réponse peut prendre plus d'une minute, d'où `proxy_read_timeout 300s`.
- La limite sur `/api/demo/` (6 req/min/IP) évite qu'un visiteur relance l'attaque en boucle et vide le gas Fuji. Rien d'autre en MVP.

**4. `infra/docker-compose.yml`.**
- Projet nommé `sh` (`-p sh`). Service `backend` : `build: {context: .., dockerfile: infra/backend.Dockerfile, args: {WITH_FOUNDRY: "${WITH_FOUNDRY:-true}"}}`, `image: sh-backend`, `env_file: [{path: "${ENV_FILE:-../.env}", required: false}]`, `volumes: ["${DATA_PATH:-../data}:/app/data", "../deployments:/app/deployments"]`, `ports: ["127.0.0.1:8000:8000"]` (jamais exposé publiquement), `healthcheck: python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"` toutes les 10 s, `restart: unless-stopped`, `logging: {driver: json-file, options: {max-size: 10m, max-file: "3"}}`.
- Service `frontend` : `build: {context: .., dockerfile: infra/frontend.Dockerfile, args: {FRONTEND_DIR: "${FRONTEND_DIR:-frontend}"}}`, `image: sh-frontend`, `ports: ["${FRONT_PORT:-80}:80"]`, `depends_on: {backend: {condition: service_healthy}}`, `restart: unless-stopped`.
- Aucune variable `*_PK` ni URL de RPC écrite dans le fichier : tout vient de `ENV_FILE`.

**5. Configuration de l'instance : `infra/fuji.env` + secrets.**
- `infra/fuji.env` (commité, **sans secret**) : `NETWORK=fuji`, `CHAIN_ID=43113`, `ENGINE_ENABLED=true`, `USE_FIXTURES=false`, `DRY_RUN_ACTIONS=false`, `POLL_INTERVAL_S=2`, `AWS_REGION=us-east-1`, `EXPLORER_URL=https://testnet.snowtrace.io`, `RPC_FALLBACK_URL=https://api.avax-test.network/ext/bc/C/rpc`.
- Secrets et identifiants de ressources (`RPC_URL` avec clé fournisseur, `DEPLOYER_PK`, `OWNER_PK`, `GUARDIAN_PK`, `PROTOCOL_GUARDIAN_PK`, `ATTACKER_PK`, `EVIDENCE_PK`, `BOT_PKS`, `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID`, `ALERT_WEBHOOK_URL`) : deux sources possibles, choisies par `ENV_SOURCE` :
  - `ssm` (recommandé) : un paramètre `SecureString` par variable sous `/secure-horizons/fuji/<VAR>` ; `infra/render_env.sh` lancé **sur l'instance** fait `aws ssm get-parameters-by-path --path /secure-horizons/fuji/ --with-decryption --recursive --query 'Parameters[].[Name,Value]' --output text` et écrit `NAME=value`.
  - `file` : un `.env.fuji` local (ignoré par git via la règle `.env.*` du `.gitignore` de T0) copié par `scp`.
- Fichier final sur l'instance : `~/sh/shared/.env`, `chmod 600`, = secrets **puis** `infra/fuji.env` ajouté à la fin (la dernière occurrence gagne : les 4 valeurs forcées ne peuvent pas être écrasées par erreur).
- Jamais de secret dans `user-data`, dans une `ARG`/`ENV` Docker, dans `fuji.env` ni dans une variable `VITE_*`.

**6. Création AWS (`infra/setup-aws.md`, une personne, CLI `--region us-east-1`).** Préfixe de nommage `secure-horizons-`. Le runbook contient les commandes exactes, dans cet ordre :
1. `aws sts get-caller-identity` → noter `ACCOUNT_ID`.
2. SNS : `aws sns create-topic --name secure-horizons-alerts` ; une `aws sns subscribe --protocol email --notification-endpoint <email>` par membre ; chacun **confirme** le mail (vérifier les spams).
3. S3 : `aws s3api create-bucket --bucket secure-horizons-evidence-$ACCOUNT_ID --object-lock-enabled-for-bucket` (pas de `--create-bucket-configuration` en us-east-1 ; l'Object Lock active le versioning) ; si l'option échoue : créer sans, puis `put-bucket-versioning Status=Enabled`. `put-public-access-block` avec les 4 booléens à `true`. **Pas** de rétention par défaut en mode `COMPLIANCE` (au plus `GOVERNANCE` 1 jour), sinon le compte ne peut plus être nettoyé.
4. Bedrock : une seule personne remplit le formulaire « first-time use » Anthropic dans la console Bedrock (Model catalog) et fait la **première** invocation depuis la console ; puis `aws bedrock list-inference-profiles --query "inferenceProfileSummaries[?contains(inferenceProfileId,'anthropic')].inferenceProfileId"` ; choisir un profil `us.anthropic.claude-…` Haiku (rapide, bon marché, conseillé pour T5) ou Sonnet ; copier l'id **exact** listé dans `BEDROCK_MODEL_ID`. Ne jamais construire l'id à la main.
5. IAM : rôle `secure-horizons-ec2-role` (trust `ec2.amazonaws.com`), politique en ligne `infra/iam-policy.json` (après remplacement de `<ACCOUNT_ID>`), profil `secure-horizons-ec2-profile`. Actions et ressources exactes :
   - `sns:Publish` sur l'ARN du topic ;
   - `s3:PutObject`, `s3:GetObject` sur `arn:aws:s3:::secure-horizons-evidence-<ACCOUNT_ID>/*` ; `s3:DeleteObject` **seulement** sur `…/healthcheck/*` (pour `check_aws.py`) ;
   - `bedrock:InvokeModel` sur `arn:aws:bedrock:us-east-1:<ACCOUNT_ID>:inference-profile/us.anthropic.*` **et** `arn:aws:bedrock:*::foundation-model/anthropic.*` (un profil `us.` route vers plusieurs régions) ;
   - `ssm:GetParametersByPath`, `ssm:GetParameter` sur `arn:aws:ssm:us-east-1:<ACCOUNT_ID>:parameter/secure-horizons/fuji*` (ajouter `kms:Decrypt` seulement si un `AccessDenied` KMS apparaît).
   - Aucune action `*`, aucune ressource `*` sauf les ARN de modèles ci-dessus.
6. Réseau : clé SSH `secure-horizons-key` (le `.pem` reste sur le poste, `chmod 400`, jamais dans le repo) ; groupe `secure-horizons-demo-sg` : entrée `80/tcp` depuis `0.0.0.0/0`, `22/tcp` depuis les IP `/32` de l'équipe uniquement ; **pas** de 8000.
7. EC2 : `aws ec2 run-instances --image-id resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --instance-type t3.medium --key-name secure-horizons-key --security-group-ids <sg> --iam-instance-profile Name=secure-horizons-ec2-profile --metadata-options HttpTokens=required,HttpPutResponseHopLimit=2 --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' --user-data file://infra/user-data.sh --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=secure-horizons-demo}]'` ; puis allouer et associer une Elastic IP (URL stable après un arrêt/redémarrage).
8. SSM : `aws ssm put-parameter --type SecureString --name /secure-horizons/fuji/GUARDIAN_PK --value "$GUARDIAN_PK"` pour chaque secret (depuis des variables shell, jamais tapées en clair dans un fichier commité ; `history -c` après).
9. Tableau « Valeurs de l'équipe » en fin de runbook : IP publique, ARN du topic, nom du bucket, `BEDROCK_MODEL_ID` (valeurs non secrètes).
- `infra/user-data.sh` : `dnf install -y docker git` ; `systemctl enable --now docker` ; `usermod -aG docker ec2-user` ; installe les plugins `docker-compose` et `docker-buildx` (binaires GitHub, x86_64) dans `/usr/local/lib/docker/cli-plugins/` ; `mkdir -p /home/ec2-user/sh/{releases,shared/data}` et `chown -R ec2-user`.

**7. `infra/deploy.sh` (lancé depuis un poste de l'équipe).**
- Usage : `infra/deploy.sh --host <ip> --key <pem> [--env-source file|ssm] [--env-file .env.fuji] [--dry-run] [--rollback]`. `set -euo pipefail`. Codes de sortie : `0` OK, `2` usage, `3` pré-vérification échouée, `4` transfert/SSH échoué, `5` santé KO après déploiement.
- Pré-vérifications (`3` si échec) : on est dans un repo git ; `deployments/fuji.json` et `abi/` sont **suivis** par git (sinon message « commit deployments/fuji.json first ») sauf `--allow-skeleton` ; en mode `file`, le fichier existe, est en `600`, et contient `GUARDIAN_PK`, `EVIDENCE_PK`, `RPC_URL` non vides (message `missing GUARDIAN_PK`) ; avertissement si l'arbre de travail n'est pas propre (seul le code commité part).
- Release : `REL=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)` ; envoi = `git ls-files -z --recurse-submodules | tar --null -T - -czf - | ssh ... "mkdir -p ~/sh/releases/$REL && tar -xzf - -C ~/sh/releases/$REL"` (n'envoie que des fichiers suivis, donc jamais `.env` ; inclut les sous-modules OpenZeppelin, contrairement à `git archive`).
- Secrets : `file` → `scp` vers `~/sh/shared/.env.secrets` puis `chmod 600` ; `ssm` → `bash ~/sh/releases/$REL/infra/render_env.sh > ~/sh/shared/.env.secrets`. Puis `cat .env.secrets infra/fuji.env > ~/sh/shared/.env && chmod 600`.
- Lancement : `ln -sfn ~/sh/releases/$REL ~/sh/current && cd ~/sh/current && ENV_FILE=/home/ec2-user/sh/shared/.env DATA_PATH=/home/ec2-user/sh/shared/data docker compose -p sh -f infra/docker-compose.yml up -d --build --remove-orphans`.
- Attente : jusqu'à 40 essais espacés de 3 s sur `http://<host>/api/health` ; succès si `network == "fuji"` et `rpc_ok == true` ; sinon affiche `docker compose logs --tail 80 backend` et sort en `5`.
- Ménage : garde les 3 dernières releases. `--rollback` : repointe `current` sur la release précédente et relance `up -d`.
- `--dry-run` : n'ouvre aucune connexion, affiche `DRY-RUN` puis chaque commande prévue et la liste des fichiers qui seraient envoyés.
- Logs : une ligne par étape, ex. `[deploy] release=20261011T081502Z-3fa91c2 files=412 env=ssm`, `[deploy] health ok block=45213377 rpc_ok=true`, `[deploy] DONE http://203.0.113.10/`. Jamais de contenu de `.env` affiché.

**8. `infra/check_aws.py` (stdlib + boto3, lancé dans le conteneur backend ou sur un poste).**
```python
@dataclass
class CheckResult:
    name: str          # "sts" | "sns" | "s3" | "bedrock" | "http"
    status: str        # "OK" | "FAIL" | "SKIP"
    detail: str
    duration_ms: int

def check_sts(sts) -> CheckResult                                   # get_caller_identity → account + arn du rôle
def check_sns(sns, topic_arn: str) -> CheckResult                   # publish Subject="secure-horizons check_aws", Message="check_aws test <iso>"
def check_s3(s3, bucket: str, prefix: str = "healthcheck/") -> CheckResult   # put → get (contenu identique) → delete
def check_bedrock(brt, model_id: str) -> CheckResult                # converse, 1 message "Reply with the single word OK.", maxTokens=64
def check_http(base_url: str, wait_s: float = 6.0) -> CheckResult   # /api/health x2, /api/state, /
def run_checks(only: set[str], session, base_url: str | None) -> list[CheckResult]
def format_line(r: CheckResult) -> str                              # f"{status:<5} {name:<8} {detail} ({ms} ms)"
def main(argv: list[str] | None = None) -> int
```
- Les variables viennent de `backend.settings` si importable (`AWS_REGION`, `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID`), sinon de `os.environ`. Variable vide → `SKIP` avec la raison (`SNS_TOPIC_ARN empty`), jamais `FAIL`.
- Chaque check attrape `botocore.exceptions.ClientError`, `BotoCoreError`, `urllib.error.URLError` et renvoie `FAIL` avec `code: message` ; aucune exception ne remonte ; aucune valeur de variable secrète n'est affichée.
- S3 : clé `healthcheck/check-<yyyymmddTHHMMSSZ>-<4 hex>.txt`, corps `b"secure-horizons check_aws <iso>"` ; `FAIL "content mismatch"` si le `get` diffère.
- Bedrock : pas de `temperature`/`topP` (refusés en 400 par les modèles Claude récents) ; une seule requête par exécution ; `OK` si le texte de réponse est non vide ; détail `model=<id> reply="OK" in=<n> out=<n> tokens`.
- HTTP (`--public-url http://<ip>`) : `OK` seulement si `network=="fuji"`, `chain_id==43113`, `rpc_ok`, `engine_running`, `block_number` du 2e appel (6 s plus tard) **strictement supérieur** au 1er, `GET /api/state` → `network=="fuji"` (un `503` `{"detail": "no snapshot yet"}` signifie que le moteur n'a encore lu aucun bloc : `FAIL "no snapshot yet"`, relancer quelques secondes plus tard), `GET /` → 200 et contient `<div id="root">`.
- CLI : `--only sts,sns,s3,bedrock,http` (défaut : `sts,sns,s3,bedrock`, plus `http` si `--public-url`), `--strict` (un `SKIP` compte comme échec). Dernière ligne : `SUMMARY <n> OK, <n> FAIL, <n> SKIP`. Code retour : `0` si aucun `FAIL` (et aucun `SKIP` en `--strict`), `1` si au moins un `FAIL`, `2` si seulement des `SKIP` en `--strict`.

**9. `infra/scan_images.sh`.** Pour `sh-backend` et `sh-frontend` : (a) `docker history --no-trunc --format '{{.CreatedBy}}'` ne contient ni `_PK`, ni `SECRET`, ni `RPC_URL=` ; (b) `docker image inspect -f '{{json .Config.Env}}'` ne contient aucun `_PK` ; (c) `docker run --rm --entrypoint sh <img> -c "find / -xdev \( -name '.env' -o -name '.env.*' \) 2>/dev/null"` est vide ; (d) export du système de fichiers (`docker create` + `docker export` → `/app` ou `/usr/share/nginx/html` extrait dans un dossier temporaire) puis `gitleaks detect --no-git --source <dir> --config infra/gitleaks.toml` → aucune fuite. Mode `--canary` : écrit un faux secret `T8_CANARY=sh-canary-7f3a9c41` dans `.env.canary` (racine) et `VITE_T8_CANARY=sh-canary-7f3a9c41` dans `frontend/.env.local` **uniquement s'ils n'existent pas**, reconstruit, vérifie par `grep -r sh-canary-7f3a9c41` qu'il n'apparaît dans aucune image, puis supprime les deux fichiers (`trap` pour nettoyer même en cas d'erreur). Sort `1` au premier problème, avec le nom du contrôle.

**10. CI (`.github/workflows/ci.yml`).** Déclencheurs : `push` sur `main`, `pull_request`. `concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}`. Jobs (tous `ubuntu-latest`) :
- `python` : `actions/checkout@v4` avec `submodules: recursive` ; `actions/setup-python@v5` 3.11 avec cache pip ; `foundry-rs/foundry-toolchain@v1` (pour `anvil` et `forge`) ; `pip install -r requirements.txt` ; si `contracts/foundry.toml` existe : `anvil --block-time 1 &`, attente du RPC (`cast block-number` en boucle, 30 s max), puis `make deploy NETWORK=local` et `make seed NETWORK=local` ; ensuite `python -m pytest backend/tests -q` avec `env: {NETWORK: local, USE_FIXTURES: "true", ENGINE_ENABLED: "false", DRY_RUN_ACTIONS: "true"}`. Aucun secret (sur `local`, `settings.private_key` retombe sur les comptes anvil), aucun accès AWS.
- `contracts` : checkout avec `submodules: recursive` ; étapes conditionnées par `if: hashFiles('contracts/foundry.toml') != ''` ; `forge build --sizes` puis `forge test -vvv` dans `contracts/`.
- `frontend` : `actions/setup-node@v4` node 20, cache npm (`cache-dependency-path: frontend/package-lock.json`) ; conditionné par `hashFiles('frontend/package.json') != ''` ; `npm ci` ; `npm run typecheck --if-present` puis, si absent, `npx tsc --noEmit` ; `npx vitest run` ; `npm run build`.
- `gitleaks` : checkout `fetch-depth: 0` ; télécharge le binaire gitleaks v8 (version épinglée) depuis les releases GitHub ; `gitleaks detect --source . --config infra/gitleaks.toml --redact -v --exit-code 1`. Pas de `gitleaks-action` (licence exigée pour les comptes organisation).
- `docker` : `docker compose -f infra/docker-compose.yml build` (avec `FRONTEND_DIR=infra/testdata/frontend-stub` si `frontend/package.json` absent) puis `bash infra/scan_images.sh`.
- `infra/gitleaks.toml` : `[extend] useDefault = true` ; allowlist limitée à `fixtures/.*\.json(l)?$` (empreintes sha256 et adresses de test) et à la mnémonique publique d'anvil dans `backend/settings.py`. Jamais d'allowlist sur `.env*`.

**11. `mk/t8.mk`.** Variables : `HOST`, `SSH_KEY ?= ~/.ssh/secure-horizons-key.pem`, `ENV_SOURCE ?= ssm`, `ENV_FILE ?= .env.fuji`. Ne **jamais** redéfinir `NETWORK` (il vient de `.env` ou de la ligne de commande, 2.11). Cibles :
- `test-t8` (appelée par `make test`) : `python -m pytest backend/tests/test_t8_*.py -q` + les contrôles d'infra qui n'ont besoin ni d'AWS ni du réseau : `bash -n infra/*.sh` + `shellcheck infra/*.sh` (si installé) + `docker compose -f infra/docker-compose.yml config -q` (si docker présent).
- `docker-build`, `docker-up` (`up -d --build`, `ENV_FILE` par défaut `../.env`), `docker-down`, `docker-smoke` (test T8-07), `scan-images`, `gitleaks`.
- `deploy-aws` : `bash infra/deploy.sh --host $(HOST) --key $(SSH_KEY) --env-source $(ENV_SOURCE) --env-file $(ENV_FILE)` (erreur claire si `HOST` vide).
- `aws-check` : `ssh ... "cd ~/sh/current && docker compose -p sh -f infra/docker-compose.yml exec -T backend python infra/check_aws.py"` puis `python3 infra/check_aws.py --only http --public-url http://$(HOST)` en local.
- `aws-smoke` : seulement le check `http`. `aws-logs` : `docker compose logs -f --tail 200`. `aws-rollback` : `deploy.sh --rollback`. `aws-allow-my-ip` : ajoute `$(curl -s https://checkip.amazonaws.com)/32` sur le port 22 du groupe de sécurité.

**12. Plan de repli (à répéter une fois, avant la démo).** (a) Même compose sur un portable pointé sur Fuji : `make docker-up ENV_FILE=../.env.fuji` → `http://localhost/` ; (b) `make demo` sur anvil local (backend lancé avec `ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false`) ; (c) vidéo enregistrée (T9). L'ordre de bascule est écrit en tête de `infra/setup-aws.md`.

#### Tests qui doivent passer

Commande globale : `make test-t8` (T8-01 à T8-06). Les autres sont des tests d'intégration lancés à la main, avec leur cible make.

- **T8-01 · unitaire** · `pytest backend/tests/test_t8_infra.py -q`. `test_compose_services` : `yaml.safe_load(infra/docker-compose.yml)["services"]` a exactement les clés `{"backend", "frontend"}` ; `backend.build.dockerfile == "infra/backend.Dockerfile"` et `context == ".."` ; chaque port publié du backend commence par `127.0.0.1:`. `test_backend_command_single_process` : la commande (CMD du Dockerfile ou `command` du compose) contient `uvicorn backend.main:app`, `--host 0.0.0.0`, `--port 8000`, et ne contient ni `--reload` ni `--workers`. `test_no_secret_in_compose` : aucune clé finissant par `_PK` dans `environment`, aucune chaîne `0x` + 64 hex dans le fichier.
- **T8-02 · unitaire** · même fichier. `test_dockerfiles_never_copy_env` : aucune ligne `COPY`/`ADD` des deux Dockerfiles ne contient `.env`, aucune ligne `COPY . .`, aucune `ARG`/`ENV` contenant `_PK`. `test_backend_image_can_reset` : `infra/backend.Dockerfile` contient une ligne `apt-get install` qui installe `make`, et des `COPY` de `Makefile`, `mk/` et `contracts/`. `test_frontend_api_url_empty` : `infra/frontend.Dockerfile` fixe `VITE_API_URL` à une valeur vide avant `npm run build`. `test_dockerignore_excludes_env` : les deux `*.dockerignore` contiennent `.env`, `**/.env*` (ou `**/.env.*`) et `data/` ; celui du front contient `frontend/.env*`.
- **T8-03 · unitaire** · `test_nginx_conf` : `infra/nginx.conf` contient `listen 80`, `location /api/`, `proxy_pass http://backend:8000;` (exactement, sans `/` final), `try_files $uri $uri/ /index.html;`, `limit_req` sur `/api/demo/`. `test_fuji_env_forced_values` : `infra/fuji.env` parsé contient `NETWORK=fuji`, `CHAIN_ID=43113`, `ENGINE_ENABLED=true`, `USE_FIXTURES=false`, `DRY_RUN_ACTIONS=false`, `AWS_REGION=us-east-1`, et aucune clé `*_PK`, `RPC_URL`, `SNS_TOPIC_ARN`. `test_iam_policy_minimal` : l'ensemble des actions de `infra/iam-policy.json` est exactement `{sns:Publish, s3:PutObject, s3:GetObject, s3:DeleteObject, bedrock:InvokeModel, ssm:GetParametersByPath, ssm:GetParameter}` ; aucune action `*` ; la ressource de `s3:DeleteObject` se termine par `/healthcheck/*`.
- **T8-04 · unitaire** · `test_ci_workflow_jobs` : `ci.yml` chargé (attention, PyYAML lit la clé `on` comme `True` : `wf.get("on", wf.get(True))`) ; jobs ⊇ `{"python", "contracts", "frontend", "gitleaks"}` ; déclencheurs `push` (branches contient `main`) et `pull_request` ; la chaîne `3.11` et la chaîne `20` apparaissent dans les jobs `python` et `frontend` ; le job `gitleaks` n'utilise pas `gitleaks/gitleaks-action` ; le job `python` fait un checkout avec `submodules: recursive` et contient `make deploy` puis `make seed` avant `pytest`.
- **T8-05 · unitaire (sans réseau)** · `pytest backend/tests/test_t8_check_aws.py -q`. Le module est chargé par `importlib.util.spec_from_file_location("check_aws", "infra/check_aws.py")`. Clients `boto3.client(<svc>, region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")` + `botocore.stub.Stubber` :
  - `test_check_sns_ok` : `publish` attendu avec `TopicArn="arn:aws:sns:us-east-1:123456789012:secure-horizons-alerts"`, `Subject="secure-horizons check_aws"`, `Message=ANY`, réponse `{"MessageId": "m-1"}` → `status == "OK"`, `"MessageId=m-1" in detail`.
  - `test_check_sns_denied` : `add_client_error("publish", service_error_code="AuthorizationError", http_status_code=403)` → `FAIL`, `"AuthorizationError" in detail`.
  - `test_check_s3_roundtrip_ok` : `put_object` → `{}` ; `get_object` → `Body=StreamingBody(io.BytesIO(body), len(body))` avec le corps envoyé (récupéré via un `monkeypatch` du générateur de corps, ou `expected_params` avec `ANY`) ; `delete_object` → `{}` → `OK`.
  - `test_check_s3_content_mismatch` : `get_object` renvoie `b"other"` → `FAIL`, `"content mismatch" in detail`.
  - `test_check_bedrock_ok` : `converse` → `{"output": {"message": {"role": "assistant", "content": [{"text": "OK"}]}}, "stopReason": "end_turn", "usage": {"inputTokens": 14, "outputTokens": 2, "totalTokens": 16}, "metrics": {"latencyMs": 420}}` → `OK`, `'reply="OK"' in detail`, `"in=14 out=2" in detail` ; et les paramètres envoyés ne contiennent pas `temperature`.
  - `test_missing_config_is_skip` : `check_sns(None, "")` → `SKIP`, `"SNS_TOPIC_ARN empty" in detail` ; idem `check_s3(None, "")`, `check_bedrock(None, "")`.
  - `test_main_exit_codes` : `monkeypatch` de `run_checks` → `[OK, OK]` donne `0` ; `[OK, FAIL]` donne `1` ; `[SKIP]` avec `--strict` donne `2` ; la sortie standard se termine par `SUMMARY 1 OK, 1 FAIL, 0 SKIP` dans le 2e cas.
  - `test_format_line` : `format_line(CheckResult("sns", "OK", "MessageId=m-1", 140)) == "OK    sns      MessageId=m-1 (140 ms)"`.
- **T8-06 · unitaire** · `pytest backend/tests/test_t8_deploy.py -q`. `test_scripts_syntax` : `bash -n` sur `deploy.sh`, `render_env.sh`, `user-data.sh`, `scan_images.sh` → code `0`. `test_deploy_missing_secret_refused` : fichier temporaire `600` contenant seulement `RPC_URL=https://example.invalid` ; `bash infra/deploy.sh --dry-run --host 203.0.113.10 --key /dev/null --env-source file --env-file <tmp>` → code `3`, sortie contient `missing GUARDIAN_PK`. `test_deploy_dry_run_ships_no_env` (sauté si pas de repo git) : avec un fichier env complet de **fausses** valeurs (`GUARDIAN_PK=0x` + `11`×32, etc.) et `--allow-skeleton` → code `0`, sortie contient `DRY-RUN` et `docker compose -p sh -f infra/docker-compose.yml up -d --build`, et aucune ligne de la liste des fichiers n'est `.env` ou ne se termine par `/.env`.
- **T8-07 · intégration locale (docker)** · `make docker-smoke`. Setup : `.env` local = `.env.example` (`NETWORK=local`, `USE_FIXTURES=true`) ; si T6 n'a pas livré, `FRONTEND_DIR=infra/testdata/frontend-stub`. Commandes et résultats attendus : `docker compose -f infra/docker-compose.yml build` → code 0 ; `up -d` puis attente `healthy` (≤ 60 s) ; `curl -fsS localhost:8000/api/health` → JSON avec les 7 champs de `Health` ; `curl -fsS localhost/api/health` → **même** JSON (le proxy marche) ; `curl -fsS localhost/` → 200, contient `<div id="root">` ; `curl -s -o /dev/null -w '%{http_code}' localhost/incidents/INC-20261011-001` → `200` (repli SPA) ; `curl -s localhost/api/does-not-exist` → `404` avec `{"detail":"Not Found"}` (vient de FastAPI, pas de nginx) ; `curl -s -o /dev/null -w '%{http_code}' localhost:8000` depuis une autre machine → refusé (port lié à 127.0.0.1). `docker compose down` en fin.
- **T8-08 · sécurité des images** · `make scan-images` puis `bash infra/scan_images.sh --canary`. Attendu : `OK history`, `OK env`, `OK no-dotenv`, `OK gitleaks` pour chaque image ; le canari `sh-canary-7f3a9c41` n'est trouvé ni dans `/app` ni dans `/usr/share/nginx/html` ; les fichiers canari sont supprimés après le test (`git status` propre).
- **T8-09 · secrets du repo** · `make gitleaks` (= `gitleaks detect --source . --config infra/gitleaks.toml --redact -v`) → `no leaks found`, code 0, sur tout l'historique. Contrôle négatif (fausses données uniquement) : sur une branche jetable, commiter un fichier contenant une fausse clé AWS au format du jeu de test officiel (`AKIA` + 16 caractères) → gitleaks code 1 ; supprimer la branche.
- **T8-10 · CI** · ouvrir une PR de test : les 5 jobs passent au vert ; après merge, le dernier run sur `main` est vert (`gh run list --branch main --limit 1` → `completed success`).
- **T8-11 · AWS, ressources** · `make aws-check HOST=<ip>`. Attendu dans le conteneur, 4 lignes puis le résumé, code 0 :
  `OK    sts      account=<id> arn=arn:aws:sts::<id>:assumed-role/secure-horizons-ec2-role/i-… (…)` · `OK    sns      MessageId=… (…)` · `OK    s3       put/get/delete s3://secure-horizons-evidence-<id>/healthcheck/check-….txt (…)` · `OK    bedrock  model=us.anthropic.claude-… reply="OK" in=… out=… tokens (…)` · `SUMMARY 4 OK, 0 FAIL, 0 SKIP`. Chaque membre abonné reçoit l'e-mail « secure-horizons check_aws ». Le `sts` prouve que le conteneur obtient les identifiants du rôle (limite de saut IMDS = 2).
- **T8-12 · AWS, URL publique** · `make aws-smoke HOST=<ip>` (après livraison de T1 et T3) → `OK    http     network=fuji chain_id=43113 rpc_ok=true engine_running=true block <n1> -> <n2> (n2 > n1)` ; depuis un téléphone en 4G, `http://<ip>/` affiche le dashboard. Avant T1/T3 (déploiement squelette) : seul `GET /` et `GET /api/health` en 200 sont exigés.
- **T8-13 · résilience et réseau** · `ssh … sudo reboot` → au plus 3 min plus tard, `make aws-smoke` repasse `OK` sans intervention (`restart: unless-stopped`, docker activé). `aws ec2 describe-security-groups --group-names secure-horizons-demo-sg --query 'SecurityGroups[0].IpPermissions'` : le port 22 n'a aucune plage `0.0.0.0/0`, le port 8000 n'apparaît pas. `make aws-rollback` revient à la release précédente et `aws-smoke` reste `OK`.
- **T8-14 · plan de repli** · sur un portable : `make docker-up ENV_FILE=../.env.fuji` → `http://localhost/api/health` renvoie `network: fuji` ; `make demo` démarre en local. Noter dans `infra/setup-aws.md` la durée de bascule constatée.

#### Definition of done

- [ ] `make test-t8` vert (T8-01 à T8-06), en local et dans le job CI `python`.
- [ ] `make docker-smoke` vert avec le vrai front (plus le stub) ; `make scan-images` et `--canary` verts.
- [ ] CI : 5 jobs verts sur `main` ; `gitleaks` vert sur tout l'historique.
- [ ] Topic SNS créé, e-mails confirmés par chaque membre ; bucket versionné (Object Lock si accepté), accès public bloqué ; profil Bedrock choisi et invoqué une fois.
- [ ] `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID` transmis à T4/T5 et inscrits dans le tableau « Valeurs de l'équipe » de `infra/setup-aws.md`.
- [ ] Secrets uniquement dans SSM (ou `.env.fuji` hors repo) ; aucun secret dans le repo, les images, `user-data` ou le bundle.
- [ ] `make deploy-aws` fonctionne de bout en bout depuis au moins deux postes différents.
- [ ] `make aws-check` → `SUMMARY 4 OK` ; `make aws-smoke` → `OK` avec `engine_running=true` et bloc qui avance.
- [ ] Reboot et rollback testés (T8-13) ; plan de repli répété (T8-14).
- [ ] `infra/setup-aws.md` permet à quelqu'un d'autre de tout recréer sans aide.

#### Pièges connus

- **Fixture trompeuse** : tant que T3 n'a pas branché `/api/health`, la fixture répond déjà `network: fuji`, `rpc_ok: true`. Seuls `engine_running == true` et un `block_number` qui augmente prouvent qu'on lit vraiment Fuji.
- **IMDSv2 et conteneurs** : avec une limite de saut à 1, boto3 dans un conteneur ne trouve aucun identifiant (`NoCredentialsError`). Mettre `HttpPutResponseHopLimit=2` (`aws ec2 modify-instance-metadata-options` si l'instance existe déjà).
- **Un seul worker uvicorn** : avec `--workers 2`, deux moteurs tournent, deux stores divergent, et la même alerte déclenche deux retraits.
- **`proxy_pass` avec `/` final** : `proxy_pass http://backend:8000/;` retire `/api` et toutes les routes renvoient 404.
- **Vite et les variables** : toute `VITE_*` lue au build finit en clair dans le JS public. Aucune clé ne doit jamais s'appeler `VITE_…`.
- **`git archive` ignore les sous-modules** (OpenZeppelin) et les fichiers non commités : on envoie `git ls-files --recurse-submodules`, et `deployments/fuji.json` doit être commité avant `deploy-aws`.
- **Pas de correctif fait à la main sur l'instance** : tout ce qui n'est pas poussé est perdu. Push fréquent après chaque test vert, le compte AWS est effacé à la fin de l'événement.
- **Object Lock en mode COMPLIANCE** : impossible de supprimer les objets avant l'échéance, même en root. GOVERNANCE ou pas de rétention par défaut.
- **Bedrock** : formulaire de première utilisation obligatoire (une seule personne) ; id de modèle à copier depuis la liste ; un profil `us.` exige les droits sur les ARN `foundation-model` de plusieurs régions ; pas de `temperature` sur les modèles récents ; moins d'1 requête/s par personne ; aucun test de jailbreak.
- **SNS** : un abonnement e-mail non confirmé ne reçoit rien alors que `publish` réussit ; `Subject` limité à 100 caractères ASCII, sans retour à la ligne.
- **IP de l'équipe qui change** (Wi-Fi du lieu) : SSH bloqué. `make aws-allow-my-ip`, jamais `0.0.0.0/0` sur le 22.
- **RPC public Fuji** : débit limité, la boucle de surveillance à 2 s le sature. Utiliser un RPC fournisseur dans `RPC_URL` (secret) et le public en `RPC_FALLBACK_URL`.
- **Permissions du volume `data/`** : l'uid du conteneur doit être 1000 (ec2-user), sinon `PermissionError` à l'écriture de `data/runtime/fuji/`.
- **Amazon Linux 2023** : `docker compose` (plugin) n'est pas installé par défaut, ni `buildx` ; `user-data.sh` les installe. Le disque de 8 Go par défaut se remplit avec les couches Docker : 30 Go.
- **Images construites sur l'instance** (x86_64) : ne pas pousser une image construite sur un Mac ARM.
- **GitHub Actions** : `hashFiles()` n'est pas utilisable dans un `if` au niveau du job avant le checkout ; le mettre au niveau des étapes. `gitleaks-action` v2 exige une licence pour un repo d'organisation : utiliser le binaire.
- **PyYAML et la clé `on`** du workflow lue comme booléen `True` (T8-04).
- **Règles des organisateurs** : on ne teste que ce qu'on a déployé, données synthétiques, pas de test de charge sur l'URL publique ni sur les services AWS, uniquement de fausses clés dans les tests de sécurité (canari, contrôle négatif gitleaks).

#### Plus tard (phase 2)

- HTTPS : nom de domaine + Caddy (certificat automatique) ou ALB + ACM.
- Images dans ECR, déploiement par GitHub Actions avec OIDC (plus de clé SSH), infra en CDK ou Terraform.
- CloudWatch : agent de logs, alarme sur `/api/health` (Route 53 health check), alarme de budget.
- Authentification sur les routes qui écrivent (`/api/demo/*`, `approve`, `submit`) : basic auth nginx ou Cognito.
- SSM Session Manager à la place du SSH, rotation automatique des secrets (Secrets Manager).
- Rétention Object Lock réglée par type de preuve (T4), réplication du bucket, chiffrement KMS dédié.
- Seconde instance de secours (warm standby) et bascule DNS.

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T8 (AWS, CI et mise en ligne) du fichier TASKS.md (racine du repo).
1. Lis les sections 1 et 2 de TASKS.md, puis la section T8 en entier. Lis aussi backend/settings.py,
   backend/main.py et fixtures/health.json.
2. Ne modifie QUE les fichiers possédés par T8 : infra/**, .github/workflows/ci.yml, mk/t8.mk,
   backend/tests/test_t8_*.py. Le .gitignore appartient à T0. Si tu as besoin d'un changement ailleurs (requirements.txt, .gitignore,
   frontend/, backend/ hors tests) ou dans le contrat (section 2), n'édite pas : écris la demande
   dans docs/contract-requests.md (quoi, pourquoi, qui est impacté) et préviens-moi.
3. Commence par les tests : backend/tests/test_t8_infra.py, test_t8_check_aws.py (botocore Stubber,
   aucun appel réseau), test_t8_deploy.py, exactement comme décrits dans « Tests qui doivent passer ».
   Ensuite écris les fichiers infra jusqu'à ce que make test-t8 soit vert.
4. Travaille contre les maquettes : .env local (NETWORK=local, USE_FIXTURES=true), faux front
   infra/testdata/frontend-stub tant que frontend/package.json n'existe pas, et uniquement de FAUSSES
   valeurs pour tout test de secret. Ne lance aucune commande AWS qui crée ou supprime des ressources
   sans me montrer la commande d'abord ; région us-east-1 uniquement.
5. Jamais de secret dans un fichier commité, une image, user-data, ou une variable VITE_*.
   Pas de --workers ni --reload pour uvicorn. Pas de test de charge, pas de jailbreak Bedrock.
6. Avant chaque commit : make test-t8 vert (puis make docker-smoke et make scan-images si docker
   est disponible). Push fréquent après chaque test vert, le compte AWS est effacé à la fin de l'événement.
```


---


### T9 · Livrables : README, playbook, conformité, defense sheet, deck, vidéo, pitch

**Objectif.** Produire tout ce que le jury lit, voit et entend : le `README.md` final, le playbook de réponse, la note de conformité, la defense sheet d'une page, le plan du deck (8 slides max), le script vidéo (2 à 3 min) et les scripts de pitch avec la préparation Q&A. Règle d'or : **aucun chiffre inventé**. Chaque chiffre vient de `data/eval/metrics.json`, de `deployments/fuji.json` ou d'une source listée dans `docs/numbers_allowlist.yaml`, et c'est vérifié par un test. Les parties qui dépendent du code (adresses, métriques, matrice de réponse) sont **générées** par script entre des marqueurs, pour rester à jour sans retouche manuelle.

**Dépend de.**
- T0 → `TASKS.md` sections 1 et 2, `Makefile`, `.env.example` → disponibles dès le départ.
- T1 → `deployments/fuji.json` (adresses Fuji) → maquette : `fixtures/deployments.example.json` (attention : ses clés `contracts` sont `Bridge`/`Oracle`, l'ancien format ; le format qui fait foi est celui de 2.3 avec `MockBridge`/`MockOracle`).
- T3 → `backend/config/rules.yaml` (pour `rules_version`) → maquette : le YAML initial de 2.7, copié dans `docs/tools/rules.mock.yaml`.
- T4 → `backend/config/playbook.yaml`, `make verify`, décisions ancrées → maquette : `docs/tools/playbook.mock.yaml` (copie **verbatim** du YAML de la section T4 3.1 : `version`, `min_exposure_usd`, `matrix`, `below_min_exposure`) et `fixtures/verify.json`.
- T5 → incident et rapport DORA, registre des dépendances → maquettes : `fixtures/dependencies.json` (structure valable) ; `fixtures/incident.json` (régénéré par T0 : alerte R1 et décision `DEC-fuji-45201812-1` au bloc 45 201 812, voir 2.13 ; si ta copie locale contient encore les anciens ids D1..D7, elle est antérieure à la régénération : rebase).
- T6 → captures du dashboard → maquette : `make backend` + `make frontend` avec `USE_FIXTURES=true` (le front tourne sur fixtures).
- T7 → `data/eval/metrics.json` (unités définies en 2.6 : `*_rate` en 0..1, `*_pct_*` en 0..100, `ttd_blocks_*` = -1 si rien n'est détecté) → maquette : `fixtures/metrics.json` (tout à 0, `notes` contient `FIXTURE`) ; rendu en mode PLACEHOLDER.
- T8 → URL publique de la démo AWS, schéma de déploiement → maquette : `TODO(T8): URL` dans le README.
- T2 → `make attack SEED=42` (pour filmer la démo) → maquette : la série `fixtures/snapshots_attack.jsonl` (faits du scénario).

**Débloque.** Le jury (dépôt final), la soutenance, et toute l'équipe (le README est la porte d'entrée du repo). T5 réutilise `docs/compliance.md` pour la cohérence de ses textes DORA ; T6 peut lier `docs/playbook.md` depuis l'UI.

**Fichiers possédés.**
- `README.md` (racine, version finale, propriété T9 d'après 1.5 ; chaque tâche fournit son paragraphe dans sa PR, T9 assemble ; personne d'autre n'édite le fichier)
- `docs/playbook.md`, `docs/compliance.md`, `docs/defense-sheet.md`, `docs/deck-outline.md`, `docs/video-script.md`, `docs/pitch.md`
- `docs/sources.md` (table des références vérifiées), `docs/numbers_allowlist.yaml`, `docs/assets/` (captures, schéma)
- `docs/tools/gen_docs.py`, `docs/tools/check_docs.py`, `docs/tools/docs_lib.py`, `docs/tools/fresh_clone_check.sh`, `docs/tools/playbook.mock.yaml`, `docs/tools/rules.mock.yaml`
- `mk/t9.mk`, `backend/tests/test_t9_docs.py`
- Pas à T9 : `docs/contract-requests.md` (partagé), `docs/tasks/` (T0).

**À lire avant de commencer.** `TASKS.md` sections 1 (surtout 1.2, 1.3, 1.6), 2.2 (paramètres du déploiement initial), 2.3, 2.7, 2.8, 2.9, 2.11 ; `backend/models.py` (`Decision`, `VerifyResult`, `Incident`, `DoraAssessment`, `DoraCriteria`, `Dependency`, `EvalMetrics`) ; `fixtures/metrics.json`, `fixtures/verify.json`, `fixtures/dependencies.json`, `fixtures/deployments.example.json`.

#### Entrées

| Entrée | Format | Fournie par | Maquette en attendant |
|---|---|---|---|
| Métriques d'évaluation | `EvalMetrics` JSON, `data/eval/metrics.json` | T7 | `fixtures/metrics.json` → rendu PLACEHOLDER |
| Adresses Fuji | `deployments/fuji.json` (2.3) | T1 | `fixtures/deployments.example.json` → bannière « adresses d'exemple » |
| Matrice de réponse | `backend/config/playbook.yaml` (schéma de la section T4 3.1) | T4 | `docs/tools/playbook.mock.yaml` (copie verbatim du YAML de T4 3.1) |
| Version des règles | `backend/config/rules.yaml` → `"sha256:<hex>"` | T3 | `docs/tools/rules.mock.yaml` (YAML de 2.7) |
| Résultat de vérification | sortie `make verify ID=DEC-…` (`VerifyResult`) | T4 | `fixtures/verify.json` |
| Registre des tiers (DORA Art. 28) | `GET /api/dependencies` → `Dependency[]` | T5 | `fixtures/dependencies.json` |
| Rapport DORA d'exemple | `GET /api/incidents/{id}/report.md` | T5 | structure de `DoraAssessment` dans `models.py` |
| Captures et vidéo | PNG dans `docs/assets/` | T6 (UI), T2 (scénario) | UI sur fixtures (`USE_FIXTURES=true`) |
| Paragraphes README par tâche | section « README snippet » dans la description de PR de chaque tâche | T1..T8 | T9 rédige d'après les `mk/tN.mk` et fait relire |
| URL démo AWS | texte | T8 | `TODO(T8): URL` |

#### Sorties

| Sortie | Format exact | Consommée par |
|---|---|---|
| `README.md` | Markdown anglais ; sections : Problem, Solution, Architecture, Quickstart (5 commandes), Run on Fuji, Fuji contracts (bloc généré), Results (bloc généré), Known limitations, Security notes, Repository layout | jury, équipe |
| `docs/playbook.md` | Markdown anglais ; bloc généré `gen:playbook` depuis `playbook.yaml` + `playbook_version` | jury, T6 (lien) |
| `docs/compliance.md` | Markdown anglais ; contenu de la slide conformité + annexe détaillée | jury, T5 |
| `docs/defense-sheet.md` | une page A4, ≤ 600 mots | jury |
| `docs/deck-outline.md` | `## Slide 1` … `## Slide 8` max, chaque slide : titre, 3 puces max, visuel, note orateur | équipe (deck réel fait à partir de ce plan) |
| `docs/video-script.md` | table de plans : `# | Durée (s) | Écran | Voix off` ; total 120 à 180 s | équipe |
| `docs/pitch.md` | Round 1 (5 min) + Q&A 2 min (10 questions) ; Finale (3 min) + Q&A 3 min | équipe |
| `docs/sources.md` | table `Référence | Intitulé officiel | URL | Vérifié (oui/non)` | `check_docs.py` |
| `make docs`, `make docs-check`, `make docs-final`, `make docs-smoke`, `make test-t9` | cibles dans `mk/t9.mk` | équipe |

#### Spécification détaillée

**1. Marqueurs et générateur (`docs/tools/docs_lib.py`, `gen_docs.py`).** Les parties vivantes sont entre `<!-- gen:NAME:start -->` et `<!-- gen:NAME:end -->`. Noms : `fuji-addresses` et `results` (README), `playbook` (playbook.md), `metrics` (defense-sheet.md, deck-outline.md slide Results), `versions` (compliance.md).

```python
def file_version(path: Path) -> str                       # "sha256:" + sha256(octets exacts du fichier) ; même calcul que rules_version (2.7)
def replace_block(text: str, name: str, content: str) -> str  # remplace entre marqueurs ; KeyError si un marqueur manque ; idempotent
def load_metrics(path: Path | None = None) -> tuple[dict, bool]
    # défaut data/eval/metrics.json, sinon fixtures/metrics.json ; placeholder=True si fichier de fixture,
    # si un élément de notes contient "FIXTURE", ou si synthetic.runs_attack == 0
def load_deployment(path: Path | None = None) -> tuple[dict, bool]   # défaut deployments/fuji.json, sinon l'exemple (placeholder=True)
def render_addresses_block(dep: dict, explorer: str = "https://testnet.snowtrace.io") -> str
def render_metrics_block(metrics: dict, placeholder: bool) -> str
def render_playbook(playbook_path: Path) -> str
```

CLI : `python docs/tools/gen_docs.py all|readme|playbook|metrics [--metrics P] [--deployments P] [--playbook P]`. Chaque repli sur une maquette écrit sur stderr `WARN t9: using mock <chemin>` et insère en tête du bloc `> PLACEHOLDER: generated from <chemin>, not final.`

**2. Bloc adresses.** Une ligne par adresse **unique**, en parcourant dans l'ordre `assets`, `contracts`, `lending` (dédoublonner : dans l'exemple, `contracts` répète les jetons). Colonnes `Name | Address | Explorer`, lien `https://testnet.snowtrace.io/address/<address>` (prendre `explorer` du JSON s'il existe). Sur `fuji.json` au format 2.3 comme sur l'exemple : 9 lignes. Ajouter une ligne « Deployed at block » avec `deployed_at_block`. Ne jamais afficher la section `roles` (adresses des clés de test : inutile pour le jury).

**3. Bloc métriques.** Unités fixées par 2.6 (`EvalMetrics.synthetic`) : `detection_rate`, `false_positive_rate` sont des fractions 0..1, affichées × 100 en % à 0 décimale ; `saved_pct_mean`, `baseline_saved_pct_mean` sont déjà en 0..100, affichées telles quelles (0 décimale) avec ` %` ; `ttd_blocks_p50/p90` en « N block(s) », et `-1` s'affiche « not detected » (jamais « -1 block »). Lignes : runs (attack/normal), detection rate, false positive rate, time to detect p50/p90, saved vs baseline, `rules_version` (12 premiers caractères hex + `…`). En mode placeholder, chaque valeur devient `[[PLACEHOLDER <clé>]]` (jamais « 0 % »). `mainnet_replay` : si `null`, écrire « Mainnet replay: phase 2 » et aucun chiffre. Copier aussi la liste `notes`.

**4. Playbook généré (`docs/playbook.md`).** Le fichier a une partie rédigée à la main (rôles, documentation) et un bloc `gen:playbook` :
- en-tête : `playbook_version: sha256:<hex>` = `file_version(backend/config/playbook.yaml)`, identique au champ `Decision.playbook_version` ;
- schéma lu (celui écrit par T4, section T4 3.1, aucun autre) : `version: int` ; `min_exposure_usd: number` ; `matrix: {critical|high|warning|info: [ {type, mode, per_position?: bool} … ]}` (liste ordonnée, `info: []`) ; `below_min_exposure: {notify_if_severity_at_least: <severity>}`. `render_playbook` ne lit que ces clés ; une clé inconnue ou manquante → `ValueError` explicite (on préfère casser le rendu que documenter une matrice fausse) ;
- une table `Severity | Exposure | Actions (in order)` : une ligne par clé de `matrix` dans l'ordre critical, high, warning, info ; colonne Exposure = `≥ <min_exposure_usd> $` pour critical et high, `any` pour warning, `—` pour info ; actions écrites `<type> (<mode>)` jointes par ` → `, avec le suffixe ` per concerned position` quand `per_position: true` (ex. `EMERGENCY_WITHDRAW (auto) per concerned position`) ; liste vide → `none` ;
- une ligne finale `Any | < <min_exposure_usd> $ | NOTIFY (auto) if severity ≥ <notify_if_severity_at_least>, otherwise none` tirée de `below_min_exposure` ;
- une note sous la table, issue de 2.8 et T4 3.2 (texte fixe dans le générateur) : `PAUSE_DEPOSITS` est toujours listé mais passe en `skipped` si les dépôts sont déjà en pause ; `EMERGENCY_WITHDRAW` n'est créé que pour les positions avec `withdrawable_now > 0`.
Partie rédigée :
- **Qui est alerté** : l'analyste d'astreinte (`NOTIFY` → topic SNS `SNS_TOPIC_ARN` et/ou `ALERT_WEBHOOK_URL`) ; les signataires de la trésorerie (rôle `owner`) pour toute action `pending_approval` ; le responsable conformité à l'ouverture d'un incident (`OPEN_INCIDENT`) pour la déclaration DORA.
- **Automatique** : `NOTIFY`, `PAUSE_DEPOSITS`, `OPEN_INCIDENT` ; `EMERGENCY_WITHDRAW` seulement en critical avec exposition ≥ seuil. La clé guardian ne peut que resserrer : retrait **vers le coffre lui-même**, jamais ailleurs (2.2, `emergencyWithdraw`). Comportements à décrire tels que 2.2 les fixe : `pauseDeposits` est idempotent ; `emergencyWithdraw` retire `min(position, liquidité)`, renvoie 0 (et émet l'event) s'il n'y a rien à retirer, et échoue (`MiniLend: paused`, action en `failed`) si la réserve est en pause.
- **Humain** : `EMERGENCY_WITHDRAW` en high (approbation `POST /api/decisions/{id}/approve` avec `{"action_index", "approver", "approve"}`), `UNPAUSE_DEPOSITS` (owner uniquement on-chain), `FULL_EXIT` (hors matrice MVP, toujours manuel), soumission DORA (`POST /api/incidents/{id}/submit`).
- **Comment c'est documenté** : `Decision` (alertes, `matrix_cell`, `rationale`, `inputs_hash`, `rules_version`, `playbook_version`), `record_hash` ancré dans `EvidenceRegistry` (`anchor_tx`, `anchor_block`), chronologie d'incident (`TimelineEvent.kind` ∈ alert, decision, action, chain, human, dora), vérification `make verify ID=DEC-…`.
- **Déroulé type** sur le scénario 1.2, phase par phase, en citant uniquement les faits de 2.2 et de `fixtures/snapshots_attack.jsonl`.

**5. `docs/compliance.md`.** Deux parties : (a) le texte exact de la slide (≤ 80 mots), (b) l'annexe. Chaque article cité a sa ligne dans `docs/sources.md` avec son lien ELI EUR-Lex (`https://eur-lex.europa.eu/eli/reg/2022/2554/oj` DORA ; `https://eur-lex.europa.eu/eli/reg_del/2024/1772/oj` RTS classification ; `https://eur-lex.europa.eu/eli/reg_del/2025/301/oj` RTS contenu et délais des rapports). Contenu de l'annexe :
- **DORA Art. 17** (processus de gestion des incidents liés aux TIC) → détection R1..R5, enregistrement de chaque alerte et décision. **Art. 18** (classification) + **RTS 2024/1772 Art. 8** (classification comme incident majeur) et **Art. 9** (seuils de matérialité) → `DoraCriteria` (dont les trois champs optionnels de l'art. 9(1) ajoutés en 2.6 : `counterparts_affected_pct`, `transactions_affected_count_pct`, `relevant_clients_affected`), `thresholds_met`, `is_major`, `legal_basis`. **Art. 19** (notification des incidents majeurs) + **Règlement délégué 2025/301** (délais) → `DoraDeadlines` : notification initiale 4 h après classification et au plus tard 24 h après la prise de connaissance, rapport intermédiaire 72 h après la notification initiale, rapport final 1 mois après le dernier rapport intermédiaire. Retrouver et citer l'article exact de 2025/301 qui fixe ces délais (attendu : Art. 5), après lecture du texte.
- **Qui déclare** : l'entité financière cliente, pas nous ; la plateforme pré-remplit, un humain valide et soumet (`submitted_by`).
- **DORA Art. 28** (registre d'informations sur les prestataires tiers de TIC) → page dépendances (`Dependency` : `kind`, `criticality`, `supports`, `fallback`). Une phrase : nous sommes nous-mêmes un prestataire tiers de TIC pour le client.
- **LBC/FT** : « Le traçage des fonds (d'où viennent les rsETH forgés, où part le WETH emprunté) est en phase 2 ; le MVP ne fait pas de screening. »
- **MiCA** (Règlement (UE) 2023/1114) : une seule phrase prudente, sans revendiquer de conformité : l'outil est de la gestion des risques interne au client, l'analyse MiCA dépend de son statut.
- **AI Act** (Règlement (UE) 2024/1689) : dans le MVP l'IA (Bedrock, `BEDROCK_MODEL_ID`) rédige seulement un paragraphe du rapport ; les sections concernées sont listées dans `ai_drafted_sections` et affichées comme telles ; toutes les décisions viennent de règles déterministes versionnées ; un humain soumet. Sans `BEDROCK_MODEL_ID`, un gabarit déterministe remplace l'IA. Ne citer aucun article de l'AI Act sans l'avoir lu.
- **Comment un auditeur vérifie** (bloc `gen:versions` + commandes) : `make verify ID=DEC-fuji-…` (id = bloc du snapshot des alertes, ex. `DEC-fuji-45201812-1` dans les fixtures) → première ligne `MATCH`, code de sortie 0, ligne `anchored: yes (block …, tx …)` (équivalent API : `VerifyResult.match == true` et `anchored == true`) ; `cast call <EvidenceRegistry> "anchoredAt(bytes32)(uint256)" <record_hash> --rpc-url $RPC_URL` → renvoie `anchor_block` ; lien snowtrace de `anchor_tx` ; `shasum -a 256 backend/config/rules.yaml` → égal au `rules_version` des alertes (sans le préfixe `sha256:`). Coller une vraie sortie de verify Fuji (maquette : `fixtures/verify.json`, marquée PLACEHOLDER).

**6. `docs/defense-sheet.md` (une page).** Quatre blocs : (1) NIST CSF 2.0, colonnes `Function | Subcategory | What we do`, fonctions Detect / Respond / Recover ; candidats à vérifier dans le texte officiel (NIST CSWP 29) avant usage : `DE.CM-09`, `DE.AE-02`, `DE.AE-04`, `DE.AE-08`, `RS.MA-01`, `RS.MI-01`, `RS.AN-06`, `RS.AN-07`, `RS.CO-02`, `RC.RP-01`, `RC.CO-03`, et `GV.SC-04` pour le registre des tiers ; on retire tout id dont l'intitulé ne colle pas. (2) Menaces : OWASP Smart Contract Top 10 (édition 2025, candidats `SC01:2025` contrôle d'accès pour `forgedRelease` appelable par tous, `SC03:2025` erreurs de logique), MITRE ATLAS `AML.T0051` (injection de prompt dans les données on-chain envoyées à Bedrock), MITRE ATT&CK : seulement si une technique colle vraiment (candidat à vérifier : `T1565`, Data Manipulation), sinon dire « ATT&CK Enterprise couvre mal la logique DeFi ». (3) Résultats : bloc `gen:metrics` uniquement. (4) Limites : contrats simulés, chaîne de test, une seule famille d'attaque, rejeu mainnet en phase 2, attaque dans le même bloc non bloquable.

**7. `docs/deck-outline.md` (8 slides max).** `## Slide 1 · Problem`, `2 · Solution`, `3 · Live demo`, `4 · Architecture`, `5 · Results` (bloc `gen:metrics`), `6 · Compliance` (texte de 5a), `7 · Business model`, `8 · Roadmap & team`. Chaque slide : ≤ 3 puces, visuel (`docs/assets/...`), note orateur ≤ 40 mots. Business model : SaaS B2B pour trésoreries crypto soumises à DORA (fintechs, gestionnaires d'actifs, trésoreries d'entreprise), abonnement par tranche d'actifs surveillés, module conformité en option, adaptateurs de protocoles. Tout prix est une **hypothèse** étiquetée comme telle et inscrite dans l'allowlist avec `source: hypothesis`. Slide équipe : `[membre 1..4]`, pas d'employeur.

**8. `docs/video-script.md`.** Table `# | Durée (s) | Écran | Voix off`, 8 à 12 plans, total 120 à 180 s. Ordre : accroche (le problème en une phrase), dashboard calme, `make attack SEED=42` / bouton démo, alerte R1 critique et son explication, décision (pause + retrait d'urgence, liens snowtrace), comparaison avec le déposant passif bloqué (position `lend-eth` WETH à 0 % retirable dans la série d'attaque), incident + brouillon DORA, `make verify`, conclusion. Tourner sur Fuji si possible, sinon en local en le disant.

**9. `docs/pitch.md`.** Round 1 : script 5 min (≤ 700 mots, environ 140 mots/min), découpé comme le deck ; Q&A 2 min : 10 questions difficiles, réponse ≤ 50 mots chacune. Les 10 : (1) différence avec les outils de monitoring on-chain existants ; (2) coût d'un faux positif ; (3) clé guardian compromise ; (4) attaquant plus rapide que nous / même bloc ; (5) aurait-ce marché sur le vrai incident (réponse honnête : rejeu mainnet en phase 2) ; (6) pourquoi ancrer sur une blockchain ; (7) qui déclare à l'autorité, sommes-nous soumis à DORA ; (8) rôle de l'IA et hallucinations ; (9) passage à des protocoles réels (adaptateurs) ; (10) qui paie et combien. Finale : script 3 min (≤ 420 mots) + Q&A 3 min (on reprend les 10 et on ajoute 3 questions de suivi).

**10. README.md.** Quickstart en exactement 5 commandes :
```
git clone <repo> && cd <repo>
cp .env.example .env
make setup
make demo            # anvil + deploy + seed + backend (engine on) + frontend
make attack SEED=42  # in a second terminal; then open the dashboard
```
`make demo` lance le backend avec `ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false` (2.11) : le README le dit, pour qu'on ne croie pas voir des fixtures. Puis « Verify a decision » : `make verify ID=<id from the dashboard>`. Section « Run on Fuji » : variables dans `.env` (le `Makefile` racine fait `-include .env` et exporte les variables, 2.11) : `NETWORK=fuji`, `RPC_URL`, clés par rôle (2.1), `USE_FIXTURES=false`, `ENGINE_ENABLED=true`, `DRY_RUN_ACTIONS=false` ; puis réutiliser `deployments/fuji.json` commité (cas normal) ou `make deploy FORCE=1` (obligatoire si un déploiement fuji existe déjà ; les adresses changent), `make seed`, `make backend`, `make frontend`, `make attack SEED=42` (variantes `default`, `slow`, `usdc` via l'API ; `seed = 0` donne les paramètres par défaut sans hasard). Security notes : aucune clé dans le repo, `gitleaks`, guardian à pouvoir restreint, `unpauseDeposits` owner seul, données synthétiques, contrats non audités. Known limitations : en plus de la liste de la defense sheet, `EvidenceRegistry` n'a pas de contrôle d'accès dans le MVP (n'importe qui peut ancrer ; on vérifie l'empreinte, pas l'auteur), et un ancrage ne peut pas être annulé.

**11. Vérificateur (`docs/tools/check_docs.py`).**
```python
def extract_numbers(md: str) -> list[tuple[int, str]]   # (ligne, nombre normalisé)
def allowed_numbers(metrics: dict, dep: dict, allowlist: list[dict]) -> set[str]
def find_secrets(md: str) -> list[str]
def find_reference_ids(md: str) -> set[str]               # NIST, ATT&CK, ATLAS, OWASP SC
def check(paths: list[Path], final: bool) -> list[str]    # liste de problèmes, vide = OK
```
`extract_numbers` ignore : blocs de code, code inline, URLs, commentaires HTML, ids de référence (`DE.AE-08`, `T1565`, `AML.T0051`, `SC01:2025`), numéros d'articles (`Art. 19`, `9(1)(a)`), numéros de règlements (`2022/2554`, `2024/1772`, `2025/301`, `2023/1114`, `2024/1689`), titres `Slide N` et `Q N`, timecodes `m:ss`, colonnes `#` et `Durée (s)` de la table vidéo, ids `R1`..`R5`, `T0`..`T9`. Normalisation : on retire `,`, espaces fines, `$`, `%`, `bps` ; `19.4` et `19,4` sont égaux. `allowed_numbers` contient : valeurs brutes de `metrics.json` et leurs formats affichés, `deployed_at_block`, et les `value` de `docs/numbers_allowlist.yaml`. Format de l'allowlist :
```yaml
- { value: "1325000", source: "TASKS.md 2.2 : 150 WETH et 100 WETH a 2500 $ + 400000 + 300000 USDC", where: [README.md, docs/pitch.md] }
- { value: "19.4", source: "fixtures/snapshots_attack.jsonl bloc 45201812 : backing_ratio_bps 1935", where: [docs/playbook.md] }
- { value: "72", source: "Reglement delegue (UE) 2025/301, delai du rapport intermediaire", where: [docs/compliance.md] }
```
`find_secrets` signale : `0x` + 64 hex hors d'une URL `…/tx/` ou d'une ligne `record_hash`/`anchor_tx`/`stored_hash`/`recomputed_hash`, `AKIA[0-9A-Z]{16}`, `BEGIN .*PRIVATE KEY`, `_PK=` suivi d'une valeur, `aws_secret_access_key`. Termes interdits (employeurs) : lus dans la variable d'environnement `T9_FORBIDDEN_TERMS` (séparés par des virgules, jamais commités). `final=True` ajoute : aucun `[[PLACEHOLDER`, aucun `TODO`, aucune bannière `PLACEHOLDER:`.

**12. `mk/t9.mk`.** Ne redéfinit jamais `NETWORK` (2.11). `T9_STRICT` sépare deux niveaux de tests : non strict (défaut, appelé par `make test`) et strict (cohérence des docs avec `backend/config/playbook.yaml`, `deployments/fuji.json` et `data/eval/metrics.json`, lancé seulement par `make docs-final`). Ainsi un commit de T1, T4 ou T7 qui change une adresse, la matrice ou les métriques ne casse pas `make test` sur `main` ; T9 régénère les docs ensuite.
```make
docs:        ; python docs/tools/gen_docs.py all
docs-check:  ; python docs/tools/check_docs.py
docs-final:  ; python docs/tools/gen_docs.py all && python docs/tools/check_docs.py --final && T9_STRICT=1 python -m pytest -q backend/tests/test_t9_docs.py
docs-smoke:  ; bash docs/tools/fresh_clone_check.sh
test-t9:     ; T9_STRICT=0 python -m pytest -q backend/tests/test_t9_docs.py
```
`test-t9` force `T9_STRICT=0` (le `Makefile` racine exporte `.env` : une valeur traînant dans `.env` ne doit pas rendre `make test` strict). Dans `test_t9_docs.py`, les tests stricts portent `strict = pytest.mark.skipif(os.environ.get("T9_STRICT") != "1", reason="strict docs checks: make docs-final")`.

`fresh_clone_check.sh` : clone dans un dossier temporaire, `cp .env.example .env`, `make setup`, `make demo` en arrière-plan, attend `GET http://127.0.0.1:8000/api/health` = 200 (120 s max), puis `GET /api/state` = 200 (503 `no snapshot yet` tant que le moteur n'a lu aucun bloc : réessayer), `POST /api/demo/attack {"seed":42,"variant":"default"}` (409 = run déjà en cours : échec de l'étape), attend une décision dans `GET /api/decisions` (120 s max), lance `make verify ID=<premier id>`, vérifie le code de sortie 0 et la première ligne `MATCH`, tue les process, affiche `SMOKE OK` ou l'étape qui a échoué.

#### Tests qui doivent passer

Commande : `pytest backend/tests/test_t9_docs.py` (jamais `-k`), via `make test-t9` (= `T9_STRICT=0 python -m pytest -q backend/tests/test_t9_docs.py`, tests non stricts seulement, appelé par `make test`). Les tests marqués **[strict]** (T9-03, T9-04, T9-06) ne tournent que sous `make docs-final` (ou `T9_STRICT=1`) : ils comparent les docs commitées aux fichiers produits par les autres tâches, qui changent sans que T9 le sache. Les tests chargent `docs/tools/docs_lib.py` et `check_docs.py` par `importlib` (le dossier `docs/` n'est pas un package).

- **T9-01** `test_deliverables_exist` (unitaire). Les 7 livrables existent, non vides, et contiennent leurs titres obligatoires (README : `## Quickstart`, `## Run on Fuji`, `## Known limitations`, `## Security notes` ; playbook : `## Who is alerted`, `## What is automatic`, `## What stays human`, `## How it is documented`). Attendu : 0 manquant.
- **T9-02** `test_playbook_render_from_mock` (unitaire). Setup : `render_playbook(docs/tools/playbook.mock.yaml)` (copie verbatim du YAML de T4 3.1). Attendu : la ligne critical contient exactement `NOTIFY (auto) → PAUSE_DEPOSITS (auto) → EMERGENCY_WITHDRAW (auto) per concerned position → OPEN_INCIDENT (auto) → UNPAUSE_DEPOSITS (human)` ; la ligne high contient `EMERGENCY_WITHDRAW (human) per concerned position` ; la ligne warning contient seulement `NOTIFY (auto)` ; la ligne info contient `none` ; une ligne `< 1000 $` contient `NOTIFY (auto) if severity ≥ high` ; l'en-tête contient `playbook_version: sha256:` suivi de 64 hex égal à `file_version` du fichier. Rendu deux fois : identique (idempotence). Cas négatif : un YAML sans `matrix` → `ValueError`.
- **T9-03** **[strict]** `test_playbook_doc_up_to_date` (intégration). Régénérer `docs/playbook.md` en mémoire depuis `backend/config/playbook.yaml` (échec explicite s'il n'existe pas : en strict on n'accepte pas la maquette) : identique au fichier commité, et `playbook_version` affiché = `file_version(backend/config/playbook.yaml)`.
- **T9-04a** `test_addresses_block_render` (unitaire, non strict). Setup : `fixtures/deployments.example.json`. Attendu : 9 lignes d'adresse, chacune avec le lien `https://testnet.snowtrace.io/address/<adresse>` ; aucune adresse de `roles` ; une ligne `45201700`.
- **T9-04** **[strict]** `test_readme_addresses_match_deployment` (intégration). `deployments/fuji.json` doit exister ; chaque adresse du bloc `gen:fuji-addresses` du README est présente dans ce fichier (hors `roles`) et inversement ; `deployed_at_block` identique ; aucune bannière `PLACEHOLDER:` dans le bloc.
- **T9-05** `test_metrics_placeholder_mode` (unitaire). Setup : `fixtures/metrics.json`. Attendu : `placeholder is True`, le bloc contient `[[PLACEHOLDER detection_rate]]` et ne contient ni `0 %` ni `0.0`. Second cas, fichier temporaire avec `runs_attack: 10, runs_normal: 10, detection_rate: 1.0, false_positive_rate: 0.0, ttd_blocks_p50: 1, ttd_blocks_p90: 2, saved_pct_mean: 100.0, baseline_saved_pct_mean: 0.0`, `notes: []` : `placeholder is False`, le bloc contient `100 %` (detection rate 1.0 × 100 et saved 100.0 tel quel), `1 block`, `2 blocks`, `Mainnet replay: phase 2`. Troisième cas : `ttd_blocks_p50: -1, ttd_blocks_p90: -1` → `not detected`, jamais `-1`.
- **T9-06a** `test_numbers_checker` (unitaire, non strict). Le texte `We save 87 % of funds.` avec allowlist vide renvoie un problème mentionnant `87` ; le même texte avec `{value: "87", …}` dans l'allowlist n'en renvoie aucun ; `Art. 19`, `2022/2554`, `R1`, `0:42` ne sont pas extraits.
- **T9-06** **[strict]** `test_numbers_traceable` (intégration). `check(...)` sur README et `docs/*.md` (hors `docs/tasks/`, `docs/contract-requests.md`) avec `data/eval/metrics.json` et `deployments/fuji.json` réels (échec explicite s'ils manquent) : 0 nombre inconnu.
- **T9-07** `test_no_secrets` (unitaire + intégration). Tous les livrables : 0 alerte. Cas négatif : `GUARDIAN_PK=0x` + 64 caractères `a` est détecté ; un lien `https://testnet.snowtrace.io/tx/0x` + 64 hex ne l'est pas.
- **T9-08** `test_forbidden_terms` (intégration). Skip si `T9_FORBIDDEN_TERMS` n'est pas défini ; sinon 0 occurrence (insensible à la casse) dans tous les livrables.
- **T9-09** `test_deck_max_8_slides`. Nombre de `^## Slide \d+` entre 7 et 8 ; titres contenant `Live demo`, `Results`, `Compliance`, `Business model`.
- **T9-10** `test_video_duration`. Somme de la colonne `Durée (s)` entre 120 et 180 ; 8 à 12 plans.
- **T9-11** `test_defense_sheet_one_page`. ≤ 600 mots (hors marqueurs), ≤ 70 lignes non vides ; contient `Detect`, `Respond`, `Recover`, `Limitations`.
- **T9-12** `test_reference_ids_verified`. Chaque id renvoyé par `find_reference_ids` sur tous les livrables existe dans `docs/sources.md` avec `Vérifié` = `oui` et une URL officielle (`nist.gov`, `attack.mitre.org`, `atlas.mitre.org`, `owasp.org`). `docs/sources.md` contient aussi les 3 liens ELI EUR-Lex de 5.
- **T9-13** `test_pitch_structure`. Section `## Round 1 (5 min)` ≤ 700 mots ; exactement 10 titres `### Q` dans `## Round 1 Q&A` ; section `## Final (3 min)` ≤ 420 mots.
- **T9-14** smoke (manuel, avant le dépôt). `make docs-smoke` sur un clone neuf : dernière ligne `SMOKE OK`.
- **T9-15** final (manuel, avant le dépôt). `make docs-final` : code de sortie 0 (régénération, `check_docs.py --final`, puis tests stricts T9-03, T9-04, T9-06 avec `T9_STRICT=1` ; donc vraies métriques T7, vraies adresses T1, playbook T4 réel). Chaque lien snowtrace du README ouvert à la main : la page de l'adresse existe.
- **T9-16** relecture des citations (manuel). Pour chaque article réglementaire cité, ouvrir le lien ELI et cocher la colonne `Vérifié` de `docs/sources.md` ; un article non retrouvé est retiré du texte.

#### Definition of done

- [ ] `make test-t9` vert (tests non stricts : T9-01, T9-02, T9-04a, T9-05, T9-06a, T9-07 à T9-13 ; T9-03, T9-04, T9-06 skippés) ; T9-08 lancé au moins une fois avec `T9_FORBIDDEN_TERMS` renseigné.
- [ ] `make docs-final` vert : plus aucun PLACEHOLDER ni TODO, métriques réelles de `data/eval/metrics.json`, tests stricts T9-03, T9-04, T9-06 verts.
- [ ] `make docs-smoke` affiche `SMOKE OK` sur un clone neuf.
- [ ] README : 5 commandes, section Fuji, adresses Fuji avec liens snowtrace, limites, notes de sécurité, URL AWS (T8).
- [ ] Playbook généré depuis le `backend/config/playbook.yaml` réel ; `playbook_version` identique à celui des décisions.
- [ ] Compliance : sortie réelle de `make verify` sur Fuji collée ; chaque article vérifié dans `docs/sources.md`.
- [ ] Deck ≤ 8 slides, vidéo 120 à 180 s, defense sheet sur une page A4 à l'impression, pitch chronométré à voix haute (5 min et 3 min).
- [ ] Chaque tâche a relu le paragraphe README qui la concerne.

#### Pièges connus

- **Chiffres « parlants » inventés.** Pas de « 99 % de détection » tant que T7 n'a pas produit `metrics.json`. Le mode PLACEHOLDER est là pour ça ; `make docs-final` bloque le dépôt sinon.
- **`fixtures/metrics.json` vaut 0 partout.** Afficher « 0 % de faux positifs » serait faux et flatteur : le test T9-05 l'interdit.
- **Unités des métriques.** Fixées par 2.6 : `*_rate` en 0..1 (multiplier par 100 à l'affichage), `*_pct_*` déjà en 0..100 (ne pas re-multiplier), `ttd_blocks_*` = -1 quand rien n'est détecté (afficher « not detected »). Un « 10000 % » ou « 1 % » de fonds sauvés trahit une double conversion.
- **Fixtures d'API.** Les fixtures régénérées (2.13) mettent l'alerte R1 et `DEC-fuji-45201812-1` au bloc 45 201 812 ; si ta copie de `alerts.json`, `decisions.json` ou `incident.json` contient encore D1..D7, elle est périmée (rebase). Même à jour, une fixture n'est pas une source de chiffre pour le jury : tout chiffre passe par l'allowlist avec sa source. Les règles s'appellent `R1_BRIDGE_INVARIANT` à `R5_CONTAINMENT`.
- **Tests stricts dans `make test`.** Ne jamais retirer le `skipif` de T9-03, T9-04, T9-06 : ils dépendent de fichiers d'autres tâches et casseraient `main` à chaque redéploiement T1, changement de matrice T4 ou nouvelle évaluation T7. Ils tournent dans `make docs-final`.
- **Ids de décision.** Ils portent le bloc du snapshot des alertes (`DEC-<network>-<block>-<n>`), pas le bloc d'exécution des transactions : dans les docs, citer `DEC-fuji-45201812-1` pour les fixtures, et l'id réel copié du dashboard pour Fuji.
- **`deployments.example.json` ≠ format 2.3** (`Bridge`/`Oracle` au lieu de `MockBridge`/`MockOracle`) : le générateur parcourt les clés présentes, sans liste en dur.
- **Hash de 64 hex = tx ou clé ?** Un hash de transaction a la même forme qu'une clé privée : n'en écrire que dans des liens `…/tx/` ou des champs nommés (voir 11).
- **Lister les employeurs dans un fichier commité les révèle.** D'où la variable d'environnement.
- **Citations.** Ne citer un paragraphe (ex. `Art. 19(4)`) que si on l'a lu ; sinon citer l'article seul. Ne pas attribuer à DORA lui-même les délais 4 h / 72 h / 1 mois : ils viennent du Règlement délégué 2025/301.
- **Le vrai incident Kelp/Aave.** Ne rien affirmer sur ses montants ou sa chronologie sans source publique vérifiée et listée dans `docs/sources.md` ; dire « rejeu synthétique inspiré de ».
- **Temps de démo.** Sur Fuji, environ 2 s par bloc : la vidéo doit couper les attentes, la démo live doit tenir sans attendre le gel du protocole.
- **README en anglais, docs internes en français** (1.6 règle 7) : tous les livrables jury sont en anglais.

#### Plus tard (phase 2)

- Résultats du rejeu mainnet (`mainnet_replay` dans `metrics.json`) dans le README, le deck et la defense sheet.
- Section LBC/FT réelle (traçage des fonds, screening).
- Export PDF automatique (deck, defense sheet) et vérification de mise en page sur une page.
- Mapping complet NIST CSF 2.0 (Identify, Protect, Govern) et ATT&CK/ATLAS étendu quand les règles avancées existeront.
- Playbook multi-protocoles et niveaux d'astreinte (escalade temporisée).
- Vérification automatique des liens snowtrace et EUR-Lex en CI (T8).

#### Prompt de démarrage pour Claude Code

```
Tu travailles sur la tâche T9 (livrables : README, playbook, conformité, defense sheet,
deck, vidéo, pitch) du fichier TASKS.md à la racine du repo.
1. Lis TASKS.md sections 1 et 2 en entier, puis la section T9 en entier. Lis backend/models.py
   (Decision, VerifyResult, Incident, DoraAssessment, Dependency, EvalMetrics) et les fixtures
   metrics.json, verify.json, dependencies.json, deployments.example.json.
2. Ne modifie QUE les fichiers listés dans « Fichiers possédés » de T9 (README.md, docs/ sauf
   docs/tasks/ et docs/contract-requests.md, mk/t9.mk, backend/tests/test_t9_docs.py).
   Si tu as besoin d'un changement ailleurs ou dans le contrat (section 2), n'édite pas :
   écris la demande dans docs/contract-requests.md et préviens-moi.
3. Commence par écrire backend/tests/test_t9_docs.py (tests T9-01 à T9-13 ; T9-03, T9-04,
   T9-06 marqués strict : skippés sauf T9_STRICT=1), puis
   docs/tools/docs_lib.py, gen_docs.py, check_docs.py, mk/t9.mk, puis les documents.
4. Travaille contre les maquettes : fixtures/metrics.json (mode PLACEHOLDER),
   fixtures/deployments.example.json, docs/tools/playbook.mock.yaml (copie verbatim du YAML de T4 3.1),
   fixtures/verify.json. N'invente AUCUN chiffre : tout chiffre vient de metrics.json,
   deployments/fuji.json ou docs/numbers_allowlist.yaml (avec sa source).
5. N'écris aucun identifiant NIST/ATT&CK/ATLAS/OWASP ni article de loi sans me demander de le
   vérifier sur la source officielle ; ajoute-le à docs/sources.md avec Vérifié = non.
6. Livrables jury en anglais. Aucun secret, aucun nom d'employeur, aucun nom de personne.
7. Avant chaque commit : make test-t9 et make docs-check doivent être verts ; push fréquent
   après chaque test vert. make docs-final (strict) seulement quand T1, T4 et T7 ont livré.
```


---

## 4. Intégration : ordre d'assemblage et tests de bout en bout

### 4.1 Ordre d'assemblage

1. **T0** est mergé en premier. Toutes les branches partent de ce commit.
2. **En parallèle, chacun sur ses maquettes :**
   - T1 (déploiement local) ;
   - T3 (règles sur les séries enregistrées) ;
   - T4 (dry-run) ;
   - T5 (décisions construites à la main) ;
   - T6 (fixtures) ;
   - T8 (infra) ;
   - T9 (brouillons).
3. **T2** démarre dès que `make deploy NETWORK=local` de T1 fonctionne.
4. **E2E-1 (local)** dès que T1, T2, T3 et T4 sont mergés. T5 et T6 se branchent dessus.
5. **T1 sur Fuji**, puis **E2E-2 (Fuji)**.
6. **T8** met la version Fuji sur AWS, puis **E2E-3 (AWS)**.
7. **T7** fait tourner l'évaluation sur la chaîne locale (seuils gelés) et produit `data/eval/metrics.json`.
8. **T9** remplace tous les chiffres provisoires par ceux de `metrics.json` et `deployments/fuji.json`.

Règle de merge : une PR n'est mergée que si `make test` est vert sur la branche rebasée sur `main`. En cas de conflit sur un fichier, la tâche propriétaire du fichier tranche.

### 4.2 E2E-1 : bout en bout sur chaîne locale

```
make chain                                   # terminal 1
NETWORK=local make deploy seed               # terminal 2
NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false make backend   # terminal 3
make frontend                                # terminal 4
make attack SEED=42                          # terminal 2
```

Résultats attendus :

| # | Vérification | Attendu |
|---|---|---|
| 1 | `GET /api/alerts` | une alerte `R1_BRIDGE_INVARIANT` critique au plus 2 blocs après le bloc de `forgedRelease` (bloc lu dans `data/runs/<run_id>.json`) |
| 2 | `GET /api/decisions` | une décision avec `NOTIFY`, `PAUSE_DEPOSITS`, 4 × `EMERGENCY_WITHDRAW`, `OPEN_INCIDENT` au statut `executed` (avec `tx_hash`), et `UNPAUSE_DEPOSITS` en `pending_approval` |
| 3 | `GET /api/state` | `vault.deposits_paused = true`, `positions = []`, `idle_balances` = 250 WETH et 700 000 USDC, `totals.at_risk_usd = 0` |
| 4 | après protection | plus aucune alerte R2 à R5 : le coffre n'a plus d'exposition |
| 5 | `make verify ID=<id de la décision>` | `MATCH`, `anchored = true` |
| 6 | `make tamper …` puis `make verify` | `MISMATCH` avec au moins une différence lisible |
| 7 | `GET /api/incidents` | un incident `contained`, DORA `is_major = true`, seuils 9(1) et 9(4), délais calculés |
| 8 | dashboard | badge critique, positions vides, incident, bouton Verify → MATCH, journal du run d'attaque |

### 4.3 E2E-2 : bout en bout sur Fuji

Mêmes commandes avec `NETWORK=fuji` et un `RPC_URL` de fournisseur. On utilise l'attaque par défaut (une tranche toutes les 8 s).

Attendus :
- les points 1 à 8 de E2E-1 ;
- chaque `tx_hash` s'ouvre sur `https://testnet.snowtrace.io` ;
- la transaction d'ancrage est visible ;
- les adresses de `deployments/fuji.json` sont commitées.

### 4.4 E2E-3 : démo hébergée sur AWS

- **Pages publiques** : l'URL publique sert le dashboard, et `GET /api/health` renvoie `network = fuji` et `rpc_ok = true`.
- **Attaque** : un clic sur « Launch attack » déclenche le scénario.
- **Notification** : un email SNS arrive dans la minute.
- **Preuve** : la preuve est déposée dans le bucket S3.
- **Rapport** : le rapport DORA s'affiche, avec la description rédigée par Bedrock ou le modèle de repli.
- **Plan B** : `make demo` en local et la vidéo enregistrée.

### 4.5 Déroulé de la démo

1. Le coffre est sain : positions sur `lend-eth` et `lend-avax`, risque `info`.
2. Un juré clique « Launch attack ». La graine aléatoire s'affiche, ce qui montre que l'attaque n'est pas scriptée pour nous.
3. Alerte R1 critique, avec sa phrase chiffrée. Dans les blocs qui suivent : pause des dépôts et rapatriement de toutes les positions exposées. Les liens snowtrace sont visibles.
4. Le graphique de `lend-eth` montre ensuite la liquidité qui tombe à zéro : un déposant passif serait bloqué, nous ne le sommes pas.
5. Incident ouvert, classification DORA proposée, délais affichés, rapport pré-rempli. Un humain clique « Submit ».
6. « Verify » renvoie MATCH. On falsifie la preuve en direct, et le résultat passe à MISMATCH.

---

## 5. Plus tard (phase 2, ne pas coder dans le MVP)

- **Agent IA** qui propose les allocations ; réglage « règles garanties » vs « consignes » ; membrane entre agents (réponse à ASI07).
- **Instructions et allowlist** scellée par une racine de Merkle, vrai Safe et module guardian, mandats EIP-712.
- **Règles de détection avancées** :
  - afflux de garantie ;
  - rendement-appât (rendement en hausse et liquidité en baisse) ;
  - règle de contagion dédiée ;
  - écart d'oracle ;
  - vitesse d'emprunt ;
  - diff des changements de gouvernance.
- **Rejeu du vrai incident Aave** du 18 avril 2026, sur les données Ethereum, et mesure des faux positifs sur des journées normales.
- **Traçage des fonds de l'attaquant**, pour le volet AML/CFT.
- **Robustesse** :
  - deux RPC indépendants qui doivent s'accorder sur le hash de bloc ;
  - conditions revérifiées dans la transaction (anti-TOCTOU) ;
  - S3 Object Lock.
- **Coûts de sortie** réels (slippage), et sortie partielle optimisée.
