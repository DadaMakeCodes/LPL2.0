# Relazione progettuale — IdealDSL

## 1. Obiettivo e dominio applicativo

Il progetto realizza un linguaggio specifico di dominio dedicato al calcolo con polinomi multivariati e ideali. L’obiettivo non è soltanto fornire una raccolta di funzioni Python, ma definire un vero linguaggio con sintassi, albero sintattico astratto, domini semantici e interprete.

Il dominio è adatto a un DSL perché le operazioni hanno una notazione e una semantica riconoscibili: costruzione di polinomi e ideali, calcolo di basi di Gröbner, appartenenza, forma normale, somma, prodotto e confronto fra ideali. Il linguaggio consente inoltre di combinare tali primitive con astrazioni generali come variabili, `let`, funzioni, condizioni e cicli.

## 2. Evoluzione rispetto al progetto iniziale

Il progetto iniziale conteneva già:

- classi per monomi e polinomi;
- parsing delle espressioni polinomiali;
- ordinamenti monomiali;
- riduzione e algoritmo di Buchberger;
- funzioni procedurali per somma, prodotto e appartenenza agli ideali.

Queste componenti erano però fortemente accoppiate a variabili globali e input interattivo. In particolare, il modulo degli ideali eseguiva letture da terminale al momento dell’importazione e non esistevano AST, ambiente, store o semantica per un linguaggio completo.

La ristrutturazione ha separato quattro livelli:

1. **nucleo algebrico**, indipendente dall’interfaccia;
2. **valori di dominio**, ossia anelli e ideali;
3. **front-end linguistico**, costituito da grammatica e AST;
4. **interprete**, che implementa ambiente, store, funzioni e controllo di flusso.

## 3. Sintassi concreta

Un programma può iniziare con una dichiarazione di anello:

```text
ring Q[x,y] order lex;
```

Sono disponibili letterali specifici:

```text
poly{x^2-y}
ideal{x^2-y; x*y-1}
```

La scelta delle parentesi graffe separa chiaramente il linguaggio esterno dalla sintassi polinomiale interna. Il punto e virgola separa i generatori dentro `ideal{...}` e termina i comandi fuori dal letterale.

I costrutti generali sono:

```text
var x = expression;
x <- expression;
print expression;
show expression;
function f(a,b) = expression;
if condition then ... else ... endif;
while condition do ... done;
let x = expression in expression
```

Il parser è realizzato con Lark in modalità LALR e lexer contestuale. La precedenza è:

1. potenza;
2. operatori unari;
3. moltiplicazione, divisione e modulo;
4. somma e sottrazione;
5. confronti;
6. uguaglianza;
7. `and`;
8. `or`.

La potenza è associativa a destra. Di conseguenza `-2^2` viene interpretato come `-(2^2)`.

## 4. Albero sintattico astratto

L’AST è definito con dataclass immutabili. Le espressioni includono:

- `IntLiteral`, `BoolLiteral`, `StringLiteral`;
- `PolynomialLiteral`, `IdealLiteral`;
- `Variable`;
- `Let`;
- `Unary`, `Binary`;
- `Call`.

I comandi includono:

- `VarDeclaration`;
- `Assignment`;
- `Print`, `Show`, `Visualize`, `Assert`;
- `FunctionDeclaration`;
- `IfElse`;
- `While`.

Il parser non esegue calcoli algebrici. Converte esclusivamente il testo in AST; la costruzione effettiva di polinomi e ideali avviene durante la valutazione. Questa separazione rende possibile analizzare o stampare l’AST senza eseguire il programma.

## 5. Domini semantici

I domini sono distinti esplicitamente:

```text
EVal = int | bool | string | Polynomial | Ideal
MVal = EVal
DVal = EVal | Loc | Builtin | Closure
```

Un valore esprimibile può essere prodotto da una valutazione. Un valore memorizzabile può essere inserito nello store. Un valore denotabile può essere associato a un identificatore nell’ambiente.

La distinzione è significativa per operatori e closure: entrambi sono denotabili, ma non sono memorizzabili. Una variabile del programma non può quindi contenere una closure. Questa scelta preserva la disciplina a pila delle locazioni locali e impedisce che una closure sopravviva al blocco contenente le variabili catturate.

## 6. Ambiente e store

L’ambiente è una funzione da identificatori a valori denotabili. Ogni estensione costruisce una nuova closure: per il nome appena associato restituisce il nuovo valore, per tutti gli altri delega alla funzione precedente.

Lo store è rappresentato da:

```text
StoreState(store, next_loc)
```

`store` è una funzione che associa indirizzi interi a valori memorizzabili; `next_loc` indica la prossima locazione libera. Le operazioni `allocate`, `access` e `update` producono nuove funzioni di store invece di modificare strutture condivise.

Una dichiarazione:

```text
var x = e;
```

valuta `e`, alloca una cella e associa `x` alla relativa `Loc`. Un assegnamento cerca la locazione nell’ambiente e aggiorna soltanto lo store.

Questa indirezione permette di distinguere correttamente shadowing e aggiornamento. Per esempio:

```text
var x = 10;
function f(y) = x + y;
var x = 100;
print f(1);
```

stampa `11`: la seconda dichiarazione crea una nuova locazione e un nuovo binding, mentre la closure mantiene l’ambiente contenente la prima locazione.

## 7. Scope di blocco

I rami di `if` e il corpo di `while` sono blocchi lessicali. Prima dell’esecuzione si salva `next_loc`. Al termine:

- l’ambiente esteso nel blocco viene scartato;
- `next_loc` viene ripristinato;
- le locazioni locali diventano irraggiungibili e sono riutilizzabili;
- gli aggiornamenti a locazioni esterne vengono mantenuti.

Il meccanismo modella un’allocazione a pila. In un ciclo, la stessa fascia di locazioni può essere riutilizzata a ogni iterazione, evitando crescita non limitata dello store.

## 8. Funzioni e closure

Una dichiarazione di funzione produce una closure composta da:

- dichiarazione sintattica;
- ambiente presente nel punto di definizione.

Gli argomenti sono valutati nell’ambiente chiamante. I parametri vengono poi allocati in locazioni temporanee e associati a un ambiente che estende quello catturato dalla closure. Il corpo è valutato in tale ambiente.

Le funzioni sono call-by-value e lessicalmente scoped. Il corpo è un’espressione e non può contenere assegnamenti, quindi le funzioni sono pure. Il nome della funzione viene reinserito nell’ambiente di chiamata della closure, rendendo possibile l’auto-riferimento; non è invece implementata la ricorsione mutua fra dichiarazioni separate.

## 9. Operatori nell’ambiente

Gli operatori non sono implementati tramite un grande `match` sul simbolo. L’ambiente iniziale contiene oggetti `Builtin`, ognuno con:

- nome;
- arità minima e massima;
- funzione semantica.

L’evaluator valuta gli argomenti, cerca l’operatore nell’ambiente e ne invoca la semantica. Questo modello tratta uniformemente operatori generali e primitive specifiche del dominio.

`and` e `or` mantengono short-circuit evaluation. L’evaluator valuta il secondo operando soltanto quando necessario, quindi invoca l’operatore denotato nell’ambiente.

## 10. Valori di dominio

`PolynomialRing` contiene:

- dominio dei coefficienti;
- sequenza ordinata delle variabili;
- ordine monomiale.

`Ideal` contiene:

- anello;
- generatori;
- indicazione del tipo di rappresentazione: generatori, base di Gröbner o base ridotta.

Ogni operazione riattiva la configurazione dell’anello associato all’ideale. In questo modo valori creati con ordini diversi conservano il proprio significato anche se il nucleo algebrico usa una configurazione globale per compatibilità.

## 11. Nucleo algebrico

I monomi hanno coefficienti `Fraction` e una mappa variabile-esponente. Le firme dei monomi sono canoniche e indipendenti dall’ordine attivo; l’ordine viene usato soltanto per confronti e rendering.

I polinomi sono rappresentati in forma sparsa. Il costruttore combina termini simili ed elimina coefficienti nulli. L’uguaglianza confronta la mappa canonica dei coefficienti, non l’ordine di inserimento.

La base di Gröbner è calcolata tramite:

1. normalizzazione monica dei generatori;
2. creazione delle coppie critiche;
3. ordinamento secondo sugar degree;
4. criterio del prodotto per monomi principali coprimi;
5. costruzione dell’S-polinomio;
6. divisione multivariata rispetto alla base corrente;
7. aggiunta dei resti non nulli;
8. eliminazione dei generatori ridondanti;
9. riduzione reciproca e normalizzazione finale.

Sono supportati `lex`, `deglex` e `degrevlex`.

## 12. Primitive di dominio

Le primitive principali sono `groebner`, `reduced`, `contains`, `normalform`, `ideal_sum`, `ideal_product`, `subset`, `equal`, `leadterm`, `spoly`, `degree` e `change_order`.

L’uguaglianza fra ideali è matematica, non strutturale: viene verificata la doppia inclusione. L’operatore `==` applicato a due ideali usa la stessa semantica.

## 13. Visualizzazione

`visualize` produce un file DOT. Il grafo contiene:

- un nodo radice con anello e tipo di base;
- un nodo per ogni generatore;
- un nodo per il termine principale;
- archi verso le variabili, etichettati con gli esponenti.

La scelta del formato DOT evita una dipendenza obbligatoria da librerie grafiche. Graphviz può convertire successivamente il file in SVG, PNG o PDF.

## 14. Programmi di esempio

### Esempio 1 — Gröbner e appartenenza

Costruisce un ideale, calcola la base ridotta, verifica l’appartenenza di un polinomio, calcola una forma normale e produce una visualizzazione.

### Esempio 2 — Funzioni, closure e let

Definisce funzioni per canonicalizzare e confrontare ideali, usa `let` per un binding locale e dimostra lo scoping lessicale tramite shadowing.

### Esempio 3 — Controllo di flusso

Usa un ciclo e una condizione. Una base locale viene dichiarata nel ramo `then` e deallocata al termine del blocco, mentre contatori esterni vengono aggiornati.

### Esempio 4 — Operazioni e ordini

Calcola somma e prodotto di ideali e ricalcola una base con ordine `degrevlex`, producendo un secondo grafo DOT.

## 15. Verifica

La suite usa `unittest` e copre tredici casi, tra cui:

- coefficienti razionali;
- confronto degli ordini;
- basi ridotte note;
- appartenenza e forme normali;
- somma, prodotto e inclusione;
- precedenza sintattica;
- closure e shadowing;
- blocchi e riuso delle locazioni;
- primitive del DSL;
- generazione DOT;
- errori di variabili non dichiarate e anello mancante.

## 16. Scelte e limiti

L’implementazione è intenzionalmente didattica. L’ambiente e lo store sono funzioni persistenti e semanticamente trasparenti, ma non ottimizzati per grandi programmi. Buchberger è adeguato a esempi piccoli e medi, non a carichi da sistema di algebra computazionale industriale.

Le funzioni sono pure e le closure non sono di prima classe. Per renderle memorizzabili sarebbe necessario spostare gli ambienti catturati su heap e introdurre garbage collection o reference counting. Tale estensione è lasciata fuori dal progetto per mantenere coerente il modello a pila richiesto per le variabili locali.
