# IdealDSL — linguaggio per ideali polinomiali e basi di Gröbner

IdealDSL è un linguaggio specifico di dominio implementato in Python 3.12+ per descrivere e manipolare polinomi multivariati, ideali e basi di Gröbner. Il progetto riadatta il nucleo algebrico originario trasformandolo in un interprete completo, con parser, AST, ambiente, store, funzioni con closure, `let`, strutture di controllo e visualizzazione Graphviz.

## Avvio rapido

```bash
python -m pip install -r requirements.txt
python main.py examples/01_grobner_and_membership.idl
python -m unittest discover -s tests -v
```

Per la modalità interattiva:

```bash
python main.py --repl
```

Nella REPL una riga vuota o `:run` esegue il buffer corrente; `:quit` termina.

## Esempio completo

```text
ring Q[x,y] order lex;

function canonical(I) = reduced(I);

var I = ideal{x^2-y; x*y-1};
var G = canonical(I);

show G;
print contains(I, poly{x^3-x*y});
print let H = reduced(I) in generator_count(H);

var i = 0;
while i < 2 do
    if i == 0 then
        visualize G to "output/grobner.dot";
    else
        print normalform(poly{x^4}, I);
    endif;
    i <- i + 1;
done;
```

Output principale:

```text
Ideale in Q[x,y]/lex
Rappresentazione: base di Gröbner ridotta
Numero di generatori: 2
  g1 = x-y^2    LT=x
  g2 = y^3-1    LT=y^3
true
2
visualization: .../output/grobner.dot
y^2
```

## Funzionalità del linguaggio

Il DSL comprende:

- espressioni intere, booleane, stringhe, polinomiali e ideali;
- `let` binding lessicale;
- variabili mutabili con `var` e assegnamento `<-`;
- funzioni pure con closure e scoping statico;
- `if`/`else` e `while`;
- variabili locali ai blocchi;
- operatori aritmetici, relazionali e booleani;
- primitive per basi di Gröbner, appartenenza, forme normali, somma e prodotto di ideali;
- visualizzazione in formato Graphviz DOT;
- REPL, CLI, esempi e test automatici.

## Sintassi essenziale

### Dichiarazione dell’anello

```text
ring Q[x,y,z] order degrevlex;
```

Ordini supportati:

- `lex`
- `deglex` (graded lexicographic)
- `degrevlex` (graded reverse lexicographic)

L’ordine delle variabili è quello scritto nella dichiarazione: in `Q[x,y,z]`, `x > y > z`.

### Letterali di dominio

```text
poly{x^2 + 1/2*x*y - y}
ideal{x^2-y; x*y-1}
ideal{}
```

I generatori di un ideale sono separati da `;`. La moltiplicazione nei polinomi è esplicita (`2*x`, non `2x`). I coefficienti sono razionali esatti.

### Comandi

```text
var x = 10;
x <- x + 1;
print x;
show I;
visualize I to "output/I.dot";
assert x > 0;
```

### Controllo di flusso

```text
if condition then
    command;
else
    command;
endif;

while condition do
    command;
done;
```

Le variabili dichiarate dentro un ramo o nel corpo del ciclo sono locali al blocco. Gli assegnamenti a variabili esterne restano visibili.

### Let binding

```text
print let G = reduced(I) in generator_count(G);
```

Il nome introdotto da `let` è immutabile e visibile soltanto nel corpo dell’espressione.

### Funzioni e closure

```text
var threshold = 1;
function larger(n) = n > threshold;
var threshold = 100;
print larger(2);   // true
```

La funzione cattura l’ambiente della dichiarazione. La seconda dichiarazione di `threshold` crea un nuovo binding e non modifica quello catturato dalla closure.

Le closure sono denotabili ma non memorizzabili: possono essere associate al nome di una funzione, ma non assegnate a una variabile dello store. Questa scelta impedisce la fuga di closure da blocchi i cui dati sono allocati con disciplina a pila.

## Operatori

| Categoria | Operatori |
|---|---|
| Aritmetici | `+`, `-`, `*`, `/`, `%`, `^` |
| Relazionali | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| Booleani | `and`, `or`, `not` |

Gli operatori sono valori denotabili inseriti nell’ambiente iniziale. L’evaluator non codifica direttamente ogni operazione: cerca l’operatore nell’ambiente, controlla l’arità e applica la relativa semantica.

Overload di dominio:

- `p + q`, `p - q`, `p * q`, `p ^ n` per polinomi;
- `n * p` e `p * n` per moltiplicazione scalare;
- `I + J` per somma di ideali;
- `I * J` per prodotto di ideali.

La divisione `/` fra interi usa divisione intera. La divisione per zero e gli esponenti negativi generano un errore del DSL.

## Primitive specifiche del dominio

| Primitiva | Significato |
|---|---|
| `groebner(I)` | calcola una base di Gröbner |
| `reduced(I)` | calcola la base di Gröbner ridotta e monica |
| `contains(I, p)` | verifica se `p ∈ I` |
| `normalform(p, I)` | resto di `p` rispetto alla base ridotta di `I` |
| `ideal_sum(I, J)` | somma di ideali |
| `ideal_product(I, J)` | prodotto di ideali |
| `subset(I, J)` | verifica `I ⊆ J` |
| `equal(I, J)` | uguaglianza matematica degli ideali |
| `generator_count(I)` | numero di generatori della rappresentazione corrente |
| `basis_size(I)` | numero di elementi della base ridotta |
| `leadterm(p)` | termine principale di `p`, restituito come polinomio |
| `spoly(p, q)` | S-polinomio |
| `degree(p)` | grado totale |
| `is_zero(v)` | test di zero per interi, polinomi e ideali |
| `change_order(I, "degrevlex")` | ricalcola la base con un altro ordine |
| `ring_name()` | descrizione dell’anello attivo |

## Domini semantici

L’interprete distingue esplicitamente tre domini:

```text
EVal = int | bool | string | Polynomial | Ideal
MVal = EVal
DVal = EVal | Loc | Builtin | Closure
```

- **EVal**: valori prodotti dalle espressioni;
- **MVal**: valori memorizzabili nello store;
- **DVal**: valori associabili a identificatori nell’ambiente.

Una closure e un operatore sono denotabili, ma non sono esprimibili né memorizzabili.

## Ambiente e stato

L’ambiente è una funzione persistente, estesa tramite closure:

```text
Environment : Identifier -> DVal
```

Lo stato contiene una funzione da locazioni a valori e il prossimo indirizzo libero:

```text
StoreState = (store : Location -> MVal, next_loc : int)
```

Una dichiarazione `var`:

1. valuta l’espressione;
2. alloca una nuova locazione;
3. estende l’ambiente associando il nome alla locazione.

Un assegnamento aggiorna lo store senza modificare il binding nell’ambiente.

Alla fine di un blocco, le estensioni locali dell’ambiente vengono scartate e `next_loc` viene ripristinato. Le locazioni locali diventano irraggiungibili e possono essere riutilizzate; gli aggiornamenti a locazioni esterne vengono conservati.

## Architettura

```text
ideal_dsl_project/
├── dsl_ast.py          AST del linguaggio
├── dsl_parser.py       grammatica Lark e trasformazione parse tree -> AST
├── interpreter.py      domini semantici, ambiente, store e semantica
├── domain.py           PolynomialRing e Ideal
├── monomial.py         monomi razionali
├── polynomial.py       polinomi sparsi
├── Ordinamento.py      ordini, riduzione e Buchberger
├── Parser.py           compatibilità con il parser originario
├── ideals.py           API procedurale senza side effect all’import
├── state.py            configurazione dell’ordine monomiale
├── main.py             CLI e REPL
├── examples/           quattro programmi completi
├── tests/              test unitari
└── RELAZIONE.md        relazione progettuale estesa
```

## Algoritmi algebrici

Il nucleo usa:

- coefficienti `Fraction`, quindi aritmetica razionale esatta;
- rappresentazione sparsa dei polinomi;
- divisione multivariata standard;
- S-polinomi;
- algoritmo di Buchberger;
- criterio del prodotto per saltare coppie con monomi principali coprimi;
- selezione delle coppie tramite sugar degree;
- normalizzazione monica e riduzione finale della base.

L’implementazione è didattica: privilegia chiarezza e corrispondenza con la semantica matematica rispetto alle ottimizzazioni dei sistemi di computer algebra industriali.

## Visualizzazione

Il comando:

```text
visualize G to "output/G.dot";
```

produce un grafo DOT con:

- nodo dell’ideale e dell’anello;
- generatori;
- termini principali;
- variabili e relativi esponenti.

Per convertire il file in PNG, se Graphviz è installato:

```bash
dot -Tpng output/G.dot -o output/G.png
```

La generazione del DOT non richiede Graphviz né altre dipendenze grafiche.

## Esempi inclusi

1. `01_grobner_and_membership.idl`: base ridotta, appartenenza, forma normale e DOT.
2. `02_functions_closures_let.idl`: funzioni, closure, scoping statico e `let`.
3. `03_control_flow_and_scope.idl`: `if`, `while`, assegnamento e scope locale.
4. `04_ideal_operations_and_order.idl`: somma, prodotto e cambio d’ordine.

Esecuzione di tutti gli esempi:

```bash
for f in examples/*.idl; do python main.py "$f"; done
```

## Test

```bash
python -m unittest discover -s tests -v
```

I test verificano:

- parsing e normalizzazione dei coefficienti razionali;
- ordini monomiali;
- base di Gröbner ridotta;
- appartenenza e forma normale;
- operazioni tra ideali;
- precedenza degli operatori;
- `let`, funzioni e scoping lessicale;
- variabili locali e riuso delle locazioni;
- generazione dei file DOT;
- gestione degli errori.

## Limiti dichiarati

- Le funzioni hanno un corpo espressivo, non una sequenza di comandi: sono quindi pure.
- Le closure non sono valori di prima classe e non possono essere salvate nello store.
- Non sono supportati esponenti negativi nei polinomi.
- La sintassi polinomiale richiede la moltiplicazione esplicita.
- L’implementazione non è pensata per ideali di grandi dimensioni o benchmark industriali.
- La configurazione dell’anello è globale nel nucleo algebrico; ogni valore `Ideal` riattiva comunque il proprio anello prima di un calcolo, evitando confronti accidentali.

## Controllo sintattico e stampa dell’AST

```bash
python main.py --check examples/01_grobner_and_membership.idl
python main.py --ast examples/01_grobner_and_membership.idl
```
