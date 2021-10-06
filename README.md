Simple python script for Polish tax calculation from foreign income from platforms that don't provide PIT8C form - from Exante, Mintos.

![ci](https://github.com/rysiok/PLTaxTribute/actions/workflows/python-package.yml/badge.svg) [![Coverage Status](https://coveralls.io/repos/github/rysiok/PLTaxTribute/badge.svg)](https://coveralls.io/github/rysiok/PLTaxTribute) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Total alerts](https://img.shields.io/lgtm/alerts/g/rysiok/PLTaxTribute.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/rysiok/PLTaxTribute/alerts/) [![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/rysiok/PLTaxTribute.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/rysiok/PLTaxTribute/context:python)

### Exante
Usage: tax.py exante [OPTIONS]

    Calculates trade income, cost, dividends and paid tax from Exante
    transaction log, using FIFO approach and D-1 NBP PLN exchange rate.

Options:

    -i, --input-file TEXT                                       Transaction log file name. [option is mutually exclusive with input_directory]
    -d, --input-directory TEXT                                  Directory containing transaction log file names (csv|txt extension). [option is mutually exclusive with input_file]
    -c, --calculation [TRADE|TRADE_PLN|DIVIDEND|DIVIDEND_PLN]   Calculation type  [required]

### Mintos

Usage: tax.py mintos [OPTIONS]

    Calculates income and tax from Mintos transaction log, using D-1 NBP PLN exchange rate.

Options:
    
    -i, --input-file TEXT                   Transaction log file name.  [option is mutually exclusive with input_directory]
    -d, --input-directory TEXT              Directory containing transaction log file names (csv|txt extension). [option is mutually exclusive with input_file]
    -c, --calculation [INCOME|INCOME_PLN]   Calculation type  [required]


## TODO:

- multifile transaction log
- multiyear support
- multiyear cache and opt
- PIT/ZG support
- autoconversion support
- stock split support

# Disclaimer

**This code is provided "as is" and without warranty of any kind. I'm not an accountant or tax advisor. Use at your own risk.**
