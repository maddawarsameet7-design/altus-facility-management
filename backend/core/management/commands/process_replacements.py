from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import ReplacementRequest, ReplacementOffer, Alert, Notification, User


class Command(BaseCommand):
    help = "Expire outdated replacement offers and escalate urgent unfilled replacement requests."

    def handle(self, *args, **options):
        now = timezone.now()

        # 1. Expire outdated offers
        expired_offers = ReplacementOffer.objects.filter(
            status='OFFERED',
            expires_at__lte=now
        )
        expired_count = expired_offers.update(status='EXPIRED')

        # Check requests in OFFERING status that now have 0 active offers
        offering_requests = ReplacementRequest.objects.filter(status='OFFERING')
        reopened_count = 0
        for req in offering_requests:
            if not req.offers.filter(status='OFFERED').exists():
                req.status = 'OPEN'
                req.save(update_fields=['status', 'updated_at'])
                reopened_count += 1

        # 2. Escalate requests based on time to shift start or time since opened
        active_requests = ReplacementRequest.objects.filter(
            status__in=['OPEN', 'OFFERING']
        ).select_related('society', 'roster_entry')

        escalated_count = 0
        for req in active_requests:
            settings_obj = getattr(req.society, 'settings', None)
            escalation_window = getattr(settings_obj, 'replacement_escalation_minutes', 60) if settings_obj else 60

            shift_start = req.roster_entry.shift_start_at
            time_to_start_escalation = shift_start - timedelta(minutes=escalation_window)
            opened_duration_escalation = req.opened_at + timedelta(minutes=escalation_window * 2)

            should_escalate = False
            reason = ""
            if now >= time_to_start_escalation:
                should_escalate = True
                reason = f"Shift starts within {escalation_window} minutes."
            elif now >= opened_duration_escalation:
                should_escalate = True
                reason = f"Request open for longer than {escalation_window * 2} minutes."

            if should_escalate:
                req.status = 'ESCALATED'
                req.escalated_at = now
                req.save(update_fields=['status', 'escalated_at', 'updated_at'])
                escalated_count += 1

                # Create Alert
                Alert.objects.get_or_create(
                    society=req.society,
                    roster_entry=req.roster_entry,
                    alert_type='UNFILLED',
                    defaults={'notes': f"Replacement escalated to Director: {reason}"}
                )

                # Send Notification to Directors
                directors = User.objects.filter(role='DIRECTOR')
                for d in directors:
                    Notification.objects.create(
                        society=req.society,
                        recipient=d,
                        notification_type='REPLACEMENT_ESCALATED',
                        title=f"URGENT: Escalated Replacement Request",
                        body=f"Replacement request {req.id} for {req.roster_entry.post.name} on {req.roster_entry.date} escalated: {reason}",
                        related_model='ReplacementRequest',
                        related_id=req.id
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Processed replacements: {expired_count} offers expired, "
            f"{reopened_count} requests reopened to OPEN, "
            f"{escalated_count} requests escalated."
        ))
