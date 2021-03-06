import click
from tabulate import tabulate

from engine.exante import ExanteAccount
from engine.mintos import MintosAccount
from engine.utils import bcolors


class Mutex(click.Option):
    def __init__(self, *args, **kwargs):
        self.not_required_if:list = kwargs.pop("not_required_if")

        assert self.not_required_if, "'not_required_if' parameter required"
        kwargs["help"] = (kwargs.get("help", "") + "Option is mutually exclusive with " + ", ".join(self.not_required_if) + ".").strip()
        super(Mutex, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        current_opt:bool = self.name in opts
        for mutex_opt in self.not_required_if:
            if mutex_opt in opts:
                if current_opt:
                    raise click.UsageError("Illegal usage: '" + str(self.name) + "' is mutually exclusive with " + str(mutex_opt) + ".")
                else:
                    self.prompt = None
        return super(Mutex, self).handle_parse_result(ctx, opts, args)


def ls(text: str):
    text = text.strip() + " "
    print()
    print("* " + text + "*" * (10 - len(text)))


def warning_handler(e):
    print(f"{bcolors.WARNING}{e}{bcolors.ENDC}")


@click.group(chain=True)
def cli():
    pass


@cli.command()
@click.option('-i', '--input-file', help='Transaction log file name.', cls=Mutex, not_required_if=["input_directory"])
@click.option('-d', '--input-directory', help='Directory containing transaction log file names (csv|txt extension).', cls=Mutex, not_required_if=["input_file"])
@click.option('-c', '--calculation', required=True, multiple=True, type=click.Choice(['TRADE', 'TRADE_PLN', 'DIVIDEND', 'DIVIDEND_PLN'], case_sensitive=False),
              help="Calculation type")
def exante(input_file, input_directory, calculation):
    """Calculates trade income, cost, dividends and paid tax from Exante transaction log, using FIFO approach and D-1 NBP PLN exchange rate."""
    account = ExanteAccount(warning_handler)
    if input_file:
        account.load_transaction_log(input_file)
    else:
        account.load_transaction_logs(input_directory)
    account.init_cash_flow()
    table = None
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
                Kwot?? nale??nego podatku wpisuje do pola o enigmatycznej nazwie ???Zrycza??towany podatek obliczony od przychod??w (dochod??w), o kt??rych mowa w art. 30a ust. 1 pkt 1???5 ustawy, uzyskanych poza granicami Rzeczypospolitej Polskiej???.
                Kwot?? podatku pobranego za granic?? wpisujemy do pola ???Podatek zap??acony za granic??, o kt??rym mowa w art. 30a ust. 9 ustawy???.
    
                2019
                W PIT-36 ??? pola 355, 356, 357 i 358 w sekcji N.
                W PIT-36L ??? pola 115 i 116 w sekcji K.
                W PIT-38 ??? pola 45 i 46 w sekcji G.
            """
        if table:
            print(tabulate(table, headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@cli.command()
@click.option('-i', '--input-file', help='Transaction log file name.', cls=Mutex, not_required_if=["input_directory"])
@click.option('-d', '--input-directory', help='Directory containing transaction log file names.', cls=Mutex, not_required_if=["input_file"])
@click.option('-c', '--calculation', required=True, multiple=True, type=click.Choice(['INCOME', 'INCOME_PLN'], case_sensitive=False),
              help="Calculation type")
def mintos(input_file, input_directory, calculation):
    """Calculates income and tax from Mintos transaction log, using D-1 NBP PLN exchange rate."""
    account = MintosAccount()
    if input_file:
        account.load_transaction_log(input_file)
    else:
        account.load_transaction_logs(input_directory)
    account.init_cash_flow()
    table = None
    for c in calculation:
        ls(f"{c}")
        if c == "INCOME":
            table = account.get_foreign()
        elif c == "INCOME_PLN":
            table = account.get_pln()
            """
                Kwot?? nale??nego podatku wpisuje do pola o enigmatycznej nazwie ???Zrycza??towany podatek obliczony od przychod??w (dochod??w), o kt??rych mowa w art. 30a ust. 1 pkt 1???5 ustawy, uzyskanych poza granicami Rzeczypospolitej Polskiej???.
                Kwot?? podatku pobranego za granic?? wpisujemy do pola ???Podatek zap??acony za granic??, o kt??rym mowa w art. 30a ust. 9 ustawy???.

                2019
                W PIT-36 ??? pola 355, 356, 357 i 358 w sekcji N.
                W PIT-36L ??? pola 115 i 116 w sekcji K.
                W PIT-38 ??? pola 45 i 46 w sekcji G.
            """
        if table:
            print(tabulate(table, headers="firstrow", floatfmt=".2f", tablefmt="presto"))


if __name__ == '__main__':
    cli()
