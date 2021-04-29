import click
from tabulate import tabulate

def ls(text: str):
    text = text.strip() + " "
    click.echo()
    click.echo("* " + text + "*" * (10 - len(text)))

@click.group(chain=True)
@click.option('-i', '--input-file', required=True, help='Transaction log file name.')
@click.pass_context
# @click.option('--output', type=click.Choice(['TABLE', 'JSON'], case_sensitive=False), default='TABLE', help='Transaction log file name.')
def exante(ctx, input_file):
    """This script calculates trade income, cost, dividends and paid tax from Exante transaction log, using FIFO approach and D-1 NBP PLN exchange rate."""
    account = Account()
    account.load_transaction_log(input_file)
    account.init_cash_flow()
    ctx.obj["account"] = account


@exante.command(help='Trade income/cost without conversion to PLN per asset.')
@click.pass_context
def foreign(ctx):
    account = ctx.obj['account']
    ls("FOREIGN")
    click.echo(tabulate(account.get_foreign(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@exante.command(help='Trade income/cost in PLN per asset (includes total).')
@click.pass_context
def pln(ctx):
    account = ctx.obj['account']
    ls("PLN")
    click.echo(tabulate(account.get_pln(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@exante.command(help='Total trade income/cost in PLN.')
@click.pass_context
def total(ctx):
    account = ctx.obj['account']
    ls("TOTAL PLN")
    click.echo(tabulate(account.get_pln_total(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@exante.command(help='Dividend and paid tax witohut conversion to PLN per asset.')
@click.pass_context
def dividend(ctx):
    account = ctx.obj['account']
    ls("FOREIGN DIVIDEND")
    click.echo(tabulate(account.get_dividends(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))

@exante.command(help='Dividend and paid tax in PLN.')
@click.pass_context
def dividend_pln(ctx):
    """
        Kwotę należnego podatku wpisuje do pola o enigmatycznej nazwie „Zryczałtowany podatek obliczony od przychodów (dochodów), o których mowa w art. 30a ust. 1 pkt 1–5 ustawy, uzyskanych poza granicami Rzeczypospolitej Polskiej”.
        Kwotę podatku pobranego za granicą wpisujemy do pola „Podatek zapłacony za granicą, o którym mowa w art. 30a ust. 9 ustawy”.

        2019
        W PIT-36 – pola 355, 356, 357 i 358 w sekcji N.
        W PIT-36L – pola 115 i 116 w sekcji K.
        W PIT-38 – pola 45 i 46 w sekcji G.
    """
    account = ctx.obj['account']
    ls("PLN DIVIDEND")
    click.echo(tabulate(account.get_dividends_pln(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


if __name__ == '__main__':
    exante(obj={})
