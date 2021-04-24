This script calculates trade income, cost, dividends and paid tax from
Exante transaction log, using FIFO approach and D-1 NBP PLN exchange rate.

![ci](https://github.com/rysiok/exante_pl_tax/actions/workflows/python-package.yml/badge.svg)

Usage: 
    
    exante.py [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...

Options:
    
    -i, --input-file TEXT  Transaction log file name.  [required]
    --help                 Show this message and exit.

Commands:
  
    dividend      Dividend and paid tax witohut conversion to PLN per asset.
    dividend-pln  Dividend and paid tax in PLN.
    foreign       Trade income/cost without conversion to PLN per asset.
    pln           Trade income/cost in PLN per asset (includes total).    
    total         Total trade income/cost in PLN.

## TODO:
- multifile transaction log
- multiyear support
- multiyear cache and opt
- PIT/ZG support
- autoconversion support
- stock split support

# Disclaimer

**This code is provided "as is" and without warranty of any kind. I'm not an accountant or tax advisor. Use at your own risk.**
