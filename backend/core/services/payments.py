from decimal import Decimal
import uuid
from .models import Payment, Booking

class PaymentService:
    """
    Mock service to handle external payment gateway integrations 
    (mimicking Stripe, Razorpay, or PayPal logic).
    """

    @staticmethod
    def create_payment_intent(booking: Booking) -> str:
        """
        Simulates creating a payment intent or session with an external provider.
        Returns a mock transaction ID.
        """
        # In a real app: stripe.PaymentIntent.create(amount=booking.total_amount, ...)
        transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
        print(f"DEBUG: Created Payment Intent for {booking.client.organization_name} | Amount: {booking.total_amount}")
        return transaction_id

    @staticmethod
    def process_webhook_success(booking: Booking, transaction_id: str):
        """
        Callback handler to finalize payment state after receiving gateway webhook.
        """
        # Create a payment record in our DB
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_amount,
            status='PAID',
            transaction_id=transaction_id
        )
        
        # Mark booking as fully paid
        booking.payment_status = 'PAID'
        booking.save()
        
        # Trigger success notification logic
        print(f"DEBUG: Payment Confirmed for Booking {booking.id} | Txn: {transaction_id}")
        return payment
