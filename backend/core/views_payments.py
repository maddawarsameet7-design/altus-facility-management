import razorpay
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import ServiceRequest
from .permissions import IsClientUser

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


class CreateRazorpayOrderView(APIView):
    """
    POST /api/payments/create-order/
    Initiates a Razorpay payment order for a service request.

    Restricted to: MEMBER, CHAIRMAN (the reporter of the request).
    Workers, Supervisors, and Directors cannot initiate payments.
    """
    permission_classes = [IsAuthenticated, IsClientUser]

    def post(self, request, *args, **kwargs):
        request_id = request.data.get('request_id')
        amount = request.data.get('amount')  # in INR

        if not request_id or not amount:
            return Response(
                {"error": "request_id and amount are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        service_req = get_object_or_404(ServiceRequest, id=request_id)

        # Enforce ownership — only the reporter can pay
        if service_req.reporter != request.user:
            return Response(
                {"error": "You can only create a payment order for your own requests."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Guard: don't allow duplicate payment orders
        if service_req.is_paid:
            return Response(
                {"error": "This request has already been paid."},
                status=status.HTTP_409_CONFLICT
            )

        # Razorpay expects amount in paise (multiply by 100)
        order_amount = int(float(amount) * 100)

        data = {
            "amount": order_amount,
            "currency": "INR",
            "receipt": f"receipt_{str(service_req.id)[:8]}",
            "notes": {
                "service_request_id": str(service_req.id),
                "user": request.user.username
            }
        }

        try:
            razorpay_order = client.order.create(data=data)
            return Response({
                "order_id": razorpay_order['id'],
                "amount": razorpay_order['amount'],
                "currency": razorpay_order['currency'],
                "key": settings.RAZORPAY_KEY_ID
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Payment gateway error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyRazorpayPaymentView(APIView):
    """
    POST /api/payments/verify/
    Verifies a Razorpay payment signature and marks the request as paid.

    Restricted to: MEMBER, CHAIRMAN (the reporter of the request).
    This endpoint is called by the frontend after the Razorpay checkout completes.
    """
    permission_classes = [IsAuthenticated, IsClientUser]

    def post(self, request, *args, **kwargs):
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')
        request_id = request.data.get('request_id')

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, request_id]):
            return Response(
                {"error": "razorpay_order_id, razorpay_payment_id, razorpay_signature, and request_id are all required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        service_req = get_object_or_404(ServiceRequest, id=request_id)

        # Ownership check
        if service_req.reporter != request.user:
            return Response(
                {"error": "You can only verify payment for your own requests."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })

            service_req.is_paid = True
            service_req.save(update_fields=['is_paid'])

            return Response({"message": "Payment verified successfully."}, status=status.HTTP_200_OK)

        except razorpay.errors.SignatureVerificationError:
            return Response(
                {"error": "Payment signature verification failed. Do not retry — contact support."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
