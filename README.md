![example workflow](https://github.com/rysiok/exante_pl_tax/actions/workflows/python-package.yml/badge.svg)

This script Calculates income and cost from Exante transaction log, using FIFO approach and D-1 NBP PLN exchange rate.

Usage: 
    
    exante.py [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...

Options:
    
    -i, --input-file TEXT  Transaction log file name.  [required]
    --help                 Show this message and exit.

Commands:
  
    foreign  Calculation without conversion to PLN per asset.
    pln      Calculation in PLN per asset (includes total).
    total    Total calculation in PLN.

## TODO:
- multifile transaction log
- dividends
- mulitiyear support
- mulitiyear cache and opt
- autoconversion support
- stock split support
