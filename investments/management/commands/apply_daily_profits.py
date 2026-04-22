from django.core.management.base import BaseCommand

from investments.services import sync_investment_profits


class Command(BaseCommand):
    help = "Apply due investment profits (daily/weekly/monthly) and catch up missed payouts."

    def handle(self, *args, **options):
        summary = sync_investment_profits()
        self.stdout.write(
            self.style.SUCCESS(
                "Profit sync complete: "
                f"checked={summary['investments_checked']}, "
                f"payouts={summary['payouts_created']}, "
                f"completed={summary['investments_completed']}."
            )
        )
