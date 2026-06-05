import razorpay
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import ServiceRequest

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class CreateRazorpayOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        request_id = request.data.get('request_id')
        amount = request.data.get('amount') # in INR

        if not request_id or not amount:
            return Response({"error": "request_id and amount are required"}, status=status.HTTP_400_BAD_REQUEST)

        service_req = get_object_or_404(ServiceRequest, id=request_id)
        
        # Razorpay expects amount in paise (multiply by 100)
        order_amount = int(float(amount) * 100)
        order_currency = 'INR'

        data = {
            "amount": order_amount,
            "currency": order_currency,
            "receipt": f"receipt_{service_req.id}",
            "notes": {
                "service_request_id": service_req.id,
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
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VerifyRazorpayPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')
        request_id = request.data.get('request_id')

        try:
            # Verify signature
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            
            # Update Service Request
            service_req = get_object_or_404(ServiceRequest, id=request_id)
            service_req.is_paid = True
            service_req.save()

            return Response({"message": "Payment verified successfully"}, status=status.HTTP_200_OK)

        except razorpay.errors.SignatureVerificationError:
            return Response({"error": "Signature verification failed"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
