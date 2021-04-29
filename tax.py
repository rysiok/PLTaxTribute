import click
from tabulate import tabulate

from exante import Account


def ls(text: str):
    text = text.strip() + " "
    print()
    print("* " + text + "*" * (10 - len(text)))


@click.group(chain=True)
@click.pass_context
def cli(ctx):
    """This script calculates trade income, cost, dividends and paid tax from Exante transaction log, using FIFO approach and D-1 NBP PLN exchange rate."""
    pass


@cli.command(help='Calculates profit for the Exante account.')
@click.option('-i', '--input-file', required=True, help='Transaction log file name.')
@click.option('-t', '--calculation', required=True, multiple=True, type=click.Choice(['TRADE', 'TRADE_PLN', 'DIVIDEND', 'DIVIDEND_PLN'], case_sensitive=False),
              help="Calculation type")
@click.pass_context
def exante(ctx, input_file, calculation):
    account = Account()
    account.load_transaction_log(input_file)
    account.init_cash_flow()

    for c in calculation:
        ls(f"{c}")
        if c == "TRADE":
            table = account.get_foreign()
        elif c == "TRADE_PLN":
            table = account.get_pln()
        elif c == "DIVIDEND":
            table = account.get_dividends()
        elif c == "DIVIDEND_PLN":
            table = account.get_dividends_pln()
            """
                Kwotę należnego podatku wpisuje do pola o enigmatycznej nazwie „Zryczałtowany podatek obliczony od przychodów (dochodów), o których mowa w art. 30a ust. 1 pkt 1–5 ustawy, uzyskanych poza granicami Rzeczypospolitej Polskiej”.
                Kwotę podatku pobranego za granicą wpisujemy do pola „Podatek zapłacony za granicą, o którym mowa w art. 30a ust. 9 ustawy”.
    
                2019
                W PIT-36 – pola 355, 356, 357 i 358 w sekcji N.
                W PIT-36L – pola 115 i 116 w sekcji K.
                W PIT-38 – pola 45 i 46 w sekcji G.
            """
        if table:
            print(tabulate(table, headers="firstrow", floatfmt=".2f", tablefmt="presto"))


if __name__ == '__main__':
    cli(obj={})
