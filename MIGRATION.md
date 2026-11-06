# Note di migrazione dal progetto originario

## Moduli mantenuti e riadattati

- `monomial.py`: coefficienti razionali, firme canoniche e confronto tramite ordine attivo.
- `polynomial.py`: rappresentazione sparsa, uguaglianza indipendente dall’ordine dei termini e parser razionale.
- `Ordinamento.py`: divisione multivariata, Buchberger con sugar strategy, criterio del prodotto e base ridotta.
- `state.py`: configurazione validata per `lex`, `deglex` e `degrevlex`.
- `Parser.py`: interfaccia compatibile per `Ambiente` e `Ideale`.
- `ideals.py`: API procedurale senza letture da input o stampe eseguite all’importazione.

## Nuovi moduli

- `domain.py`: `PolynomialRing` e `Ideal`.
- `dsl_ast.py`: AST del linguaggio.
- `dsl_parser.py`: grammatica Lark completa.
- `interpreter.py`: ambiente e store funzionali, closure, `let`, comandi e primitive.
- `main.py`: CLI e REPL.

## Incompatibilità intenzionali

L’esecuzione interattiva non parte più importando `ideals.py`. Per usare il progetto:

```bash
python main.py programma.idl
```

oppure:

```bash
python main.py --repl
```

Le funzioni `Isum`, `Imul`, `isEqual`, `isIinJ` e `is_pol_in_ideal` restano disponibili in `ideals.py`, ma operano sui valori `Ideal` invece che su liste non tipizzate di polinomi. Sono presenti anche `list_sum` e `list_product` per la compatibilità procedurale di base.
