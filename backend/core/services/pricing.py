from decimal import Decimal
from django.utils import timezone
from ..models import Booking, ServiceCategory

class PricingEngine:
    """
    Handles calculation of service costs based on 
    category base rates, duration, and worker count.
    """

    @staticmethod
    def calculate_estimated_total(booking: Booking) -> Decimal:
        """
        Calculates the estimated amount based on scheduled duration.
        """
        if not booking.scheduled_start or not booking.scheduled_end:
            return Decimal("0.00")

        duration = booking.scheduled_end - booking.scheduled_start
        hours = Decimal(duration.total_seconds() / 3600)
        
        # Ensure minimum 1 hour billing
        billing_hours = max(hours, Decimal("1.00"))
        
        base_rate = booking.service.base_hourly_rate
        
        # We might have a 'worker_count' field in the model (adding below)
        # For now, let's assume 1 worker if the relation isn't there yet.
        worker_count = Decimal("1.00") 
        
        total = billing_hours * base_rate * worker_count
        return total.quantize(Decimal("0.01"))

    @staticmethod
    def finalize_booking_and_invoice(booking: Booking):
        """
        Updates the booking status and generates a final invoice record.
        """
        total = PricingEngine.calculate_estimated_total(booking)
        booking.total_amount = total
        booking.status = 'COMPLETED'
        booking.save()
        
        # Mock logic for invoice generation
        print(f"DEBUG: Generating Invoice for Booking {booking.id} | Amount: {total}")
        return total
